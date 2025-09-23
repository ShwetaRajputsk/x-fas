from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import hashlib
import hmac
import json
import uuid
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.payment import (
    Payment, PaymentCreate, PaymentResponse, PaymentWebhook,
    Wallet, WalletTransaction, PaymentConfig, RefundRequest, RefundResponse,
    PaymentProvider, PaymentMethod, PaymentStatus, TransactionType,
    PaymentAnalytics, CODCharge, PaymentBreakdown, ShipmentPaymentSummary
)
from services.notification_service import NotificationService

class PaymentService:
    def __init__(self):
        self.notification_service = NotificationService()
    
    # ===== WALLET MANAGEMENT =====
    
    async def get_or_create_wallet(self, user_id: str, db: AsyncIOMotorDatabase) -> Wallet:
        """Get user's wallet or create if doesn't exist."""
        
        wallet_data = await db.wallets.find_one({"user_id": user_id})
        
        if wallet_data:
            return Wallet(**wallet_data)
        else:
            # Create new wallet
            wallet = Wallet(user_id=user_id)
            await db.wallets.insert_one(wallet.dict())
            return wallet
    
    async def get_wallet_balance(self, user_id: str, db: AsyncIOMotorDatabase) -> float:
        """Get user's current wallet balance."""
        
        wallet = await self.get_or_create_wallet(user_id, db)
        return wallet.balance
    
    async def update_wallet_balance(self, user_id: str, amount: float, transaction_type: TransactionType, 
                                  description: str, db: AsyncIOMotorDatabase, reference_id: Optional[str] = None) -> Tuple[Wallet, WalletTransaction]:
        """Update wallet balance and create transaction record."""
        
        wallet = await self.get_or_create_wallet(user_id, db)
        
        # Check if wallet is active and not frozen
        if not wallet.is_active or wallet.is_frozen:
            raise ValueError("Wallet is inactive or frozen")
        
        # Check daily limits for deductions
        if transaction_type == TransactionType.WALLET_DEDUCT:
            if wallet.daily_used + abs(amount) > wallet.daily_limit:
                raise ValueError("Daily transaction limit exceeded")
        
        # Calculate new balance
        balance_before = wallet.balance
        
        if transaction_type in [TransactionType.WALLET_LOAD, TransactionType.ADJUSTMENT]:
            new_balance = balance_before + amount
        else:  # WALLET_DEDUCT
            if balance_before < amount:
                raise ValueError("Insufficient wallet balance")
            new_balance = balance_before - amount
        
        # Check maximum balance limit
        if new_balance > wallet.max_balance:
            raise ValueError("Maximum wallet balance limit exceeded")
        
        # Update wallet
        update_data = {
            "balance": new_balance,
            "last_transaction_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        # Update daily usage for deductions
        if transaction_type == TransactionType.WALLET_DEDUCT:
            update_data["daily_used"] = wallet.daily_used + amount
        
        await db.wallets.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )
        
        # Create transaction record
        transaction = WalletTransaction(
            wallet_id=wallet.id,
            user_id=user_id,
            transaction_type=transaction_type,
            amount=amount,
            balance_before=balance_before,
            balance_after=new_balance,
            reference_id=reference_id,
            description=description
        )
        
        await db.wallet_transactions.insert_one(transaction.dict())
        
        # Get updated wallet
        updated_wallet_data = await db.wallets.find_one({"user_id": user_id})
        updated_wallet = Wallet(**updated_wallet_data)
        
        return updated_wallet, transaction
    
    async def get_wallet_transactions(self, user_id: str, db: AsyncIOMotorDatabase, limit: int = 50, skip: int = 0) -> List[WalletTransaction]:
        """Get user's wallet transaction history."""
        
        cursor = db.wallet_transactions.find({"user_id": user_id}).sort("created_at", -1).skip(skip).limit(limit)
        transactions_data = await cursor.to_list(length=limit)
        
        return [WalletTransaction(**txn) for txn in transactions_data]
    
    # ===== PAYMENT PROCESSING =====
    
    async def get_payment_config(self, db: AsyncIOMotorDatabase) -> PaymentConfig:
        """Get payment configuration."""
        
        config_data = await db.payment_config.find_one({})
        if config_data:
            return PaymentConfig(**config_data)
        else:
            # Create default config
            default_config = PaymentConfig()
            await db.payment_config.insert_one(default_config.dict())
            return default_config
    
    async def create_payment(self, payment_data: PaymentCreate, user_id: str, db: AsyncIOMotorDatabase) -> PaymentResponse:
        """Create a new payment request."""
        
        config = await self.get_payment_config(db)
        
        # Validate payment amount
        if payment_data.amount < config.min_payment_amount:
            raise ValueError(f"Minimum payment amount is ₹{config.min_payment_amount}")
        
        if payment_data.amount > config.max_payment_amount:
            raise ValueError(f"Maximum payment amount is ₹{config.max_payment_amount}")
        
        # Calculate fees and total
        gateway_fee = 0.0
        if payment_data.method != PaymentMethod.WALLET:
            gateway_fee = (payment_data.amount * config.gateway_fee_percentage) / 100
        
        total_amount = payment_data.amount + gateway_fee
        
        # Determine payment provider
        provider = PaymentProvider.RAZORPAY  # Default
        if payment_data.method == PaymentMethod.WALLET:
            provider = PaymentProvider.WALLET
        
        # Create payment record
        payment = Payment(
            user_id=user_id,
            amount=payment_data.amount,
            currency=payment_data.currency,
            provider=provider,
            method=payment_data.method,
            purpose=payment_data.purpose,
            shipment_id=payment_data.shipment_id,
            reference_id=payment_data.reference_id,
            customer_email=payment_data.customer_email,
            customer_phone=payment_data.customer_phone,
            customer_name=payment_data.customer_name,
            billing_address=payment_data.billing_address,
            description=payment_data.description,
            notes=payment_data.notes,
            gateway_fee=gateway_fee,
            total_amount=total_amount,
            expires_at=datetime.utcnow() + timedelta(minutes=config.payment_timeout_minutes)
        )
        
        # Process based on payment method
        if payment_data.method == PaymentMethod.WALLET:
            # Process wallet payment immediately
            try:
                wallet_balance = await self.get_wallet_balance(user_id, db)
                if wallet_balance < payment_data.amount:
                    payment.status = PaymentStatus.FAILED
                    payment.notes["error"] = "Insufficient wallet balance"
                else:
                    # Deduct from wallet
                    await self.update_wallet_balance(
                        user_id, 
                        payment_data.amount, 
                        TransactionType.WALLET_DEDUCT,
                        f"Payment for {payment_data.purpose}",
                        db,
                        payment.id
                    )
                    payment.status = PaymentStatus.COMPLETED
                    payment.completed_at = datetime.utcnow()
                    
            except Exception as e:
                payment.status = PaymentStatus.FAILED
                payment.notes["error"] = str(e)
        
        else:
            # For gateway payments, create order with provider
            if config.razorpay_enabled and provider == PaymentProvider.RAZORPAY:
                try:
                    # Mock Razorpay order creation (replace with actual integration)
                    payment.provider_order_id = f"order_{uuid.uuid4().hex[:12]}"
                    payment.provider_payment_id = f"pay_{uuid.uuid4().hex[:12]}"
                    payment.status = PaymentStatus.PROCESSING
                except Exception as e:
                    payment.status = PaymentStatus.FAILED
                    payment.notes["error"] = f"Gateway error: {str(e)}"
        
        # Save payment
        await db.payments.insert_one(payment.dict())
        
        # Prepare response
        response = PaymentResponse(
            id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            provider=payment.provider,
            method=payment.method,
            status=payment.status,
            provider_payment_id=payment.provider_payment_id,
            provider_order_id=payment.provider_order_id,
            purpose=payment.purpose,
            description=payment.description,
            customer_email=payment.customer_email,
            gateway_fee=payment.gateway_fee,
            total_amount=payment.total_amount,
            created_at=payment.created_at
        )
        
        # Add payment URL for gateway payments
        if payment.method != PaymentMethod.WALLET and payment.status == PaymentStatus.PROCESSING:
            response.payment_url = f"https://checkout.razorpay.com/v1/checkout.js"  # Mock URL
        
        return response
    
    async def get_payment(self, payment_id: str, user_id: Optional[str], db: AsyncIOMotorDatabase) -> Optional[Payment]:
        """Get payment by ID."""
        
        query = {"id": payment_id}
        if user_id:
            query["user_id"] = user_id
        
        payment_data = await db.payments.find_one(query)
        if payment_data:
            return Payment(**payment_data)
        return None
    
    async def update_payment_status(self, payment_id: str, status: PaymentStatus, provider_data: Optional[Dict[str, Any]], db: AsyncIOMotorDatabase) -> Optional[Payment]:
        """Update payment status (typically called by webhooks)."""
        
        payment = await self.get_payment(payment_id, None, db)
        if not payment:
            return None
        
        update_data = {
            "status": status,
            "updated_at": datetime.utcnow()
        }
        
        if provider_data:
            update_data["provider_response"] = provider_data
            if "payment_id" in provider_data:
                update_data["provider_payment_id"] = provider_data["payment_id"]
            if "signature" in provider_data:
                update_data["provider_signature"] = provider_data["signature"]
        
        if status == PaymentStatus.COMPLETED:
            update_data["completed_at"] = datetime.utcnow()
        
        await db.payments.update_one(
            {"id": payment_id},
            {"$set": update_data}
        )
        
        # Get updated payment
        updated_payment_data = await db.payments.find_one({"id": payment_id})
        updated_payment = Payment(**updated_payment_data)
        
        # Send notifications
        if status == PaymentStatus.COMPLETED:
            await self._send_payment_success_notification(updated_payment, db)
        elif status == PaymentStatus.FAILED:
            await self._send_payment_failure_notification(updated_payment, db)
        
        return updated_payment
    
    async def process_webhook(self, webhook_data: PaymentWebhook, db: AsyncIOMotorDatabase) -> bool:
        """Process payment webhook."""
        
        try:
            # Save webhook
            await db.payment_webhooks.insert_one(webhook_data.dict())
            
            # Process based on provider and event type
            if webhook_data.provider == PaymentProvider.RAZORPAY:
                return await self._process_razorpay_webhook(webhook_data, db)
            
            return False
            
        except Exception as e:
            # Log error and mark webhook as processed to avoid reprocessing
            await db.payment_webhooks.update_one(
                {"id": webhook_data.id},
                {"$set": {"processed": True, "processed_at": datetime.utcnow(), "error": str(e)}}
            )
            return False
    
    async def _process_razorpay_webhook(self, webhook_data: PaymentWebhook, db: AsyncIOMotorDatabase) -> bool:
        """Process Razorpay webhook events."""
        
        payload = webhook_data.payload
        event_type = webhook_data.event_type
        
        if event_type == "payment.captured":
            # Payment successful
            payment_id = payload.get("payment", {}).get("order_id", "").replace("order_", "")
            if payment_id:
                await self.update_payment_status(
                    payment_id, 
                    PaymentStatus.COMPLETED,
                    payload.get("payment", {}),
                    db
                )
                return True
        
        elif event_type == "payment.failed":
            # Payment failed
            payment_id = payload.get("payment", {}).get("order_id", "").replace("order_", "")
            if payment_id:
                await self.update_payment_status(
                    payment_id,
                    PaymentStatus.FAILED,
                    payload.get("payment", {}),
                    db
                )
                return True
        
        return False
    
    # ===== REFUND PROCESSING =====
    
    async def create_refund(self, refund_request: RefundRequest, user_id: str, db: AsyncIOMotorDatabase) -> RefundResponse:
        """Create a refund request."""
        
        payment = await self.get_payment(refund_request.payment_id, user_id, db)
        if not payment:
            raise ValueError("Payment not found")
        
        if payment.status != PaymentStatus.COMPLETED:
            raise ValueError("Can only refund completed payments")
        
        if refund_request.amount > payment.amount:
            raise ValueError("Refund amount cannot exceed payment amount")
        
        # For wallet payments, add back to wallet
        if payment.method == PaymentMethod.WALLET:
            await self.update_wallet_balance(
                user_id,
                refund_request.amount,
                TransactionType.WALLET_LOAD,
                f"Refund for {payment.purpose}: {refund_request.reason}",
                db,
                payment.id
            )
            
            refund_response = RefundResponse(
                id=uuid.uuid4().hex,
                payment_id=payment.id,
                amount=refund_request.amount,
                status=PaymentStatus.COMPLETED,
                reason=refund_request.reason,
                created_at=datetime.utcnow(),
                processed_at=datetime.utcnow()
            )
        
        else:
            # For gateway payments, create refund request
            # This would integrate with actual payment provider
            refund_response = RefundResponse(
                id=uuid.uuid4().hex,
                payment_id=payment.id,
                amount=refund_request.amount,
                status=PaymentStatus.PROCESSING,
                reason=refund_request.reason,
                provider_refund_id=f"rfnd_{uuid.uuid4().hex[:12]}",
                created_at=datetime.utcnow()
            )
        
        # Update payment with refund info
        await db.payments.update_one(
            {"id": payment.id},
            {
                "$set": {
                    "refunded_amount": payment.refunded_amount + refund_request.amount,
                    "refund_reason": refund_request.reason,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return refund_response
    
    # ===== ANALYTICS =====
    
    async def get_payment_analytics(self, user_id: Optional[str], days: int, db: AsyncIOMotorDatabase) -> PaymentAnalytics:
        """Get payment analytics."""
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = {"created_at": {"$gte": start_date.isoformat()}}
        if user_id:
            query["user_id"] = user_id
        
        # Get payments
        cursor = db.payments.find(query)
        payments = await cursor.to_list(length=10000)
        
        analytics = PaymentAnalytics(
            total_transactions=len(payments),
            total_amount=sum(p.get("amount", 0) for p in payments),
            successful_transactions=sum(1 for p in payments if p.get("status") == PaymentStatus.COMPLETED),
            failed_transactions=sum(1 for p in payments if p.get("status") == PaymentStatus.FAILED),
            success_rate=0.0,
            average_transaction_amount=0.0,
            method_breakdown={},
            status_breakdown={},
            daily_volume=0.0,
            monthly_volume=0.0,
            total_wallet_balance=0.0,
            wallet_transactions=0,
            growth_rate=0.0,
            popular_methods=[]
        )
        
        if payments:
            analytics.success_rate = (analytics.successful_transactions / analytics.total_transactions) * 100
            analytics.average_transaction_amount = analytics.total_amount / analytics.total_transactions
        
        # Method breakdown
        method_counts = {}
        for payment in payments:
            method = payment.get("method", "unknown")
            if method not in method_counts:
                method_counts[method] = {"count": 0, "amount": 0}
            method_counts[method]["count"] += 1
            method_counts[method]["amount"] += payment.get("amount", 0)
        
        analytics.method_breakdown = method_counts
        
        # Status breakdown
        status_counts = {}
        for payment in payments:
            status = payment.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
        
        analytics.status_breakdown = status_counts
        
        # Popular methods
        analytics.popular_methods = sorted(method_counts.keys(), 
                                         key=lambda x: method_counts[x]["count"], 
                                         reverse=True)[:3]
        
        return analytics
    
    # ===== NOTIFICATIONS =====
    
    async def _send_payment_success_notification(self, payment: Payment, db: AsyncIOMotorDatabase):
        """Send payment success notification."""
        try:
            # Implementation would use notification service
            pass
        except Exception:
            pass  # Don't fail payment processing due to notification errors
    
    async def _send_payment_failure_notification(self, payment: Payment, db: AsyncIOMotorDatabase):
        """Send payment failure notification."""
        try:
            # Implementation would use notification service
            pass
        except Exception:
            pass  # Don't fail payment processing due to notification errors
    
    # ===== COD AND PAYMENT BREAKDOWN =====
    
    def calculate_cod_charges(self, shipment_value: float, cod_config: Optional[CODCharge] = None) -> float:
        """Calculate COD charges for a shipment."""
        
        if not cod_config:
            cod_config = CODCharge()  # Use default config
        
        return cod_config.calculate_charge(shipment_value)
    
    def is_cod_available(self, postal_code: str) -> bool:
        """Check if COD is available for given postal code."""
        # This would typically check against a database of serviceable pincodes
        # For now, we'll assume COD is available everywhere in India
        return True
    
    async def calculate_payment_breakdown(self, shipment_value: float, shipping_charges: float,
                                        payment_method: PaymentMethod, user_id: str, 
                                        db: AsyncIOMotorDatabase) -> PaymentBreakdown:
        """Calculate detailed payment breakdown with all charges."""
        
        config = await self.get_payment_config(db)
        
        # Base amounts
        subtotal = shipment_value
        
        # COD charges
        cod_charges = 0.0
        if payment_method == PaymentMethod.COD:
            cod_charges = self.calculate_cod_charges(shipment_value, config.cod_charges)
        
        # Tax calculation (18% GST)
        taxable_amount = subtotal + shipping_charges + cod_charges
        tax_amount = taxable_amount * 0.18
        
        # Wallet discount (bonus for using wallet)
        wallet_discount = 0.0
        if payment_method == PaymentMethod.WALLET:
            wallet_discount = subtotal * (config.wallet_bonus_percentage / 100)  # Apply wallet bonus
        
        # Calculate total amount
        total_amount = subtotal + shipping_charges + cod_charges + tax_amount - wallet_discount
        
        return PaymentBreakdown(
            subtotal=subtotal,
            shipping_charges=shipping_charges,
            cod_charges=cod_charges,
            tax_amount=tax_amount,
            wallet_discount=wallet_discount,
            total_amount=round(total_amount, 2)
        )
    
    async def get_shipment_payment_summary(self, shipment_id: str, user_id: str,
                                         shipment_value: float, shipping_charges: float,
                                         db: AsyncIOMotorDatabase) -> ShipmentPaymentSummary:
        """Get comprehensive payment summary for a shipment."""
        
        config = await self.get_payment_config(db)
        
        # Get user's wallet balance
        wallet_balance = await self.get_wallet_balance(user_id, db)
        
        # Determine available payment methods
        available_methods = []
        
        if config.wallet_enabled:
            available_methods.append(PaymentMethod.WALLET)
        
        if config.enable_cards:
            available_methods.extend([PaymentMethod.CREDIT_CARD, PaymentMethod.DEBIT_CARD])
        
        if config.enable_net_banking:
            available_methods.append(PaymentMethod.NET_BANKING)
        
        if config.enable_upi:
            available_methods.append(PaymentMethod.UPI)
        
        if config.cod_enabled:
            available_methods.append(PaymentMethod.COD)
        
        # Calculate breakdown for wallet payment (default)
        breakdown = await self.calculate_payment_breakdown(
            shipment_value, shipping_charges, PaymentMethod.WALLET, user_id, db
        )
        
        # Check wallet coverage
        can_use_wallet = wallet_balance >= breakdown.total_amount
        requires_gateway = not can_use_wallet and PaymentMethod.WALLET in available_methods
        gateway_amount = max(0, breakdown.total_amount - wallet_balance) if not can_use_wallet else 0
        
        return ShipmentPaymentSummary(
            shipment_id=shipment_id,
            user_id=user_id,
            breakdown=breakdown,
            available_methods=available_methods,
            wallet_balance=wallet_balance,
            can_use_wallet=can_use_wallet,
            requires_gateway=requires_gateway,
            gateway_amount=gateway_amount
        )
    
    async def process_cod_payment(self, shipment_id: str, user_id: str, amount: float,
                                db: AsyncIOMotorDatabase) -> PaymentResponse:
        """Process COD payment (creates pending payment record)."""
        
        # Create COD payment record
        payment_data = PaymentCreate(
            amount=amount,
            method=PaymentMethod.COD,
            purpose="shipment_cod",
            shipment_id=shipment_id,
            customer_email="",  # Will be filled from user data
            description=f"COD payment for shipment {shipment_id}"
        )
        
        # Create payment with COD status
        payment = Payment(
            user_id=user_id,
            amount=amount,
            provider=PaymentProvider.COD,
            method=PaymentMethod.COD,
            status=PaymentStatus.PENDING,
            purpose="shipment_cod",
            shipment_id=shipment_id,
            customer_email="",
            description=f"COD payment for shipment {shipment_id}",
            total_amount=amount
        )
        
        await db.payments.insert_one(payment.dict())
        
        return PaymentResponse(
            id=payment.id,
            amount=amount,
            currency="INR",
            provider=PaymentProvider.COD,
            method=PaymentMethod.COD,
            status=PaymentStatus.PENDING,
            provider_payment_id=None,
            provider_order_id=None,
            purpose="shipment_cod",
            description=f"COD payment for shipment {shipment_id}",
            customer_email="",
            gateway_fee=0.0,
            total_amount=amount,
            created_at=payment.created_at
        )
    
    async def confirm_cod_collection(self, payment_id: str, db: AsyncIOMotorDatabase) -> bool:
        """Confirm COD collection (called when delivery agent collects payment)."""
        
        result = await db.payments.update_one(
            {"id": payment_id, "method": PaymentMethod.COD},
            {
                "$set": {
                    "status": PaymentStatus.COMPLETED,
                    "completed_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return result.modified_count > 0
    
    # ===== UTILITY METHODS =====
    
    def verify_razorpay_signature(self, payload: str, signature: str, secret: str) -> bool:
        """Verify Razorpay webhook signature."""
        
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
    
    async def cleanup_expired_payments(self, db: AsyncIOMotorDatabase) -> int:
        """Clean up expired pending payments."""
        
        expired_time = datetime.utcnow()
        
        result = await db.payments.update_many(
            {
                "status": PaymentStatus.PENDING,
                "expires_at": {"$lt": expired_time}
            },
            {
                "$set": {
                    "status": PaymentStatus.CANCELLED,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return result.modified_count