from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from models.user import User
from models.payment import (
    PaymentCreate, PaymentResponse, PaymentMethod, PaymentProvider,
    Wallet, WalletTransaction, PaymentBreakdown, ShipmentPaymentSummary,
    CODCharge, PaymentAnalytics, RefundRequest, RefundResponse
)
from services.payment_service import PaymentService
from utils.auth import get_current_user

# Database dependency
async def get_database() -> AsyncIOMotorDatabase:
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    return client[os.environ.get('DB_NAME', 'xfas_logistics')]

router = APIRouter(prefix="/payments", tags=["Payments"])

# Request/Response Models
class WalletTopupRequest(BaseModel):
    amount: float
    payment_method: PaymentMethod = PaymentMethod.UPI
    
class ProcessPaymentRequest(BaseModel):
    shipment_id: str
    payment_method: PaymentMethod
    use_wallet_balance: bool = False

class CODChargeRequest(BaseModel):
    shipment_value: float

class PaymentSummaryRequest(BaseModel):
    shipment_id: str
    shipment_value: float
    shipping_charges: float

# ===== WALLET ENDPOINTS =====

@router.get("/wallet/balance")
async def get_wallet_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's wallet balance and limits."""
    
    try:
        payment_service = PaymentService()
        wallet = await payment_service.get_or_create_wallet(current_user.id, db)
        
        # Get spending analytics
        today = __import__('datetime').datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        daily_transactions = await payment_service.get_wallet_transactions(current_user.id, db)
        
        daily_spent = sum(tx.amount for tx in daily_transactions 
                         if tx.transaction_type.value == "WALLET_DEDUCT" 
                         and tx.created_at >= today)
        
        return {
            "success": True,
            "data": {
                "balance": wallet.balance,
                "currency": wallet.currency,
                "daily_limit": wallet.daily_limit,
                "daily_spent": daily_spent,
                "daily_remaining": max(0, wallet.daily_limit - daily_spent),
                "max_balance": wallet.max_balance,
                "is_active": wallet.is_active,
                "is_frozen": wallet.is_frozen,
                "last_transaction_at": wallet.last_transaction_at
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching wallet balance: {str(e)}"
        )

@router.post("/wallet/topup")
async def topup_wallet(
    request: WalletTopupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Top up wallet balance."""
    
    try:
        if request.amount <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Amount must be positive"
            )
        
        if request.amount < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Minimum top-up amount is ₹10"
            )
        
        payment_service = PaymentService()
        
        # Create payment for wallet top-up
        payment_data = PaymentCreate(
            amount=request.amount,
            method=request.payment_method,
            purpose="wallet_topup",
            customer_email=current_user.email,
            customer_name=current_user.name,
            customer_phone=getattr(current_user, 'phone', None),
            description=f"Wallet top-up of ₹{request.amount}"
        )
        
        payment_response = await payment_service.create_payment(payment_data, current_user.id, db)
        
        return {
            "success": True,
            "data": {
                "payment": payment_response,
                "message": "Payment initiated successfully"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing wallet top-up: {str(e)}"
        )

@router.get("/wallet/transactions")
async def get_wallet_transactions(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get wallet transaction history."""
    
    try:
        payment_service = PaymentService()
        transactions = await payment_service.get_wallet_transactions(current_user.id, db, limit, offset)
        
        # Get total count
        total_count = await db.wallet_transactions.count_documents({"user_id": current_user.id})
        
        return {
            "success": True,
            "data": {
                "transactions": [tx.dict() for tx in transactions],
                "pagination": {
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": total_count > (offset + limit)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching wallet transactions: {str(e)}"
        )

# ===== COD ENDPOINTS =====

@router.post("/cod/calculate-charges")
async def calculate_cod_charges(
    request: CODChargeRequest,
    current_user: User = Depends(get_current_user)
):
    """Calculate COD charges for a shipment value."""
    
    try:
        if request.shipment_value <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shipment value must be positive"
            )
        
        payment_service = PaymentService()
        cod_charges = payment_service.calculate_cod_charges(request.shipment_value)
        
        return {
            "success": True,
            "data": {
                "shipment_value": request.shipment_value,
                "cod_charges": cod_charges,
                "total_amount": request.shipment_value + cod_charges,
                "free_cod_eligible": cod_charges == 0
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating COD charges: {str(e)}"
        )

@router.get("/cod/availability/{postal_code}")
async def check_cod_availability(
    postal_code: str,
    current_user: User = Depends(get_current_user)
):
    """Check if COD is available for a postal code."""
    
    try:
        payment_service = PaymentService()
        is_available = payment_service.is_cod_available(postal_code)
        
        return {
            "success": True,
            "data": {
                "postal_code": postal_code,
                "cod_available": is_available,
                "message": "COD is available" if is_available else "COD not available in this area"
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error checking COD availability: {str(e)}"
        )

# ===== PAYMENT PROCESSING ENDPOINTS =====

@router.post("/payment-summary")
async def get_payment_summary(
    request: PaymentSummaryRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get payment summary with breakdown and available methods."""
    
    try:
        if request.shipment_value <= 0 or request.shipping_charges < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid amount values"
            )
        
        payment_service = PaymentService()
        summary = await payment_service.get_shipment_payment_summary(
            request.shipment_id,
            current_user.id,
            request.shipment_value,
            request.shipping_charges,
            db
        )
        
        return {
            "success": True,
            "data": summary.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating payment summary: {str(e)}"
        )

@router.post("/process-payment")
async def process_payment(
    request: ProcessPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Process payment for a shipment."""
    
    try:
        payment_service = PaymentService()
        
        # Get shipment details to calculate amount
        shipment_data = await db.shipments.find_one({
            "id": request.shipment_id,
            "user_id": current_user.id
        })
        
        if not shipment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found"
            )
        
        # Calculate payment amount based on shipment
        shipment_value = shipment_data.get("package_info", {}).get("declared_value", 0)
        shipping_charges = shipment_data.get("payment_info", {}).get("amount", 0) - shipment_value
        
        # Calculate breakdown
        breakdown = await payment_service.calculate_payment_breakdown(
            shipment_value, shipping_charges, request.payment_method, current_user.id, db
        )
        
        # Process based on payment method
        if request.payment_method == PaymentMethod.COD:
            # Process COD payment
            payment_response = await payment_service.process_cod_payment(
                request.shipment_id, current_user.id, breakdown.total_amount, db
            )
        elif request.payment_method == PaymentMethod.WALLET:
            # Process wallet payment
            payment_data = PaymentCreate(
                amount=breakdown.total_amount,
                method=PaymentMethod.WALLET,
                purpose="shipment",
                shipment_id=request.shipment_id,
                customer_email=current_user.email,
                customer_name=current_user.name,
                description=f"Payment for shipment {request.shipment_id}"
            )
            payment_response = await payment_service.create_payment(payment_data, current_user.id, db)
        else:
            # Process gateway payment
            payment_data = PaymentCreate(
                amount=breakdown.total_amount,
                method=request.payment_method,
                purpose="shipment",
                shipment_id=request.shipment_id,
                customer_email=current_user.email,
                customer_name=current_user.name,
                description=f"Payment for shipment {request.shipment_id}"
            )
            payment_response = await payment_service.create_payment(payment_data, current_user.id, db)
        
        return {
            "success": True,
            "data": {
                "payment": payment_response.dict(),
                "breakdown": breakdown.dict(),
                "message": "Payment processed successfully"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing payment: {str(e)}"
        )

# ===== PAYMENT MANAGEMENT =====

@router.get("/history")
async def get_payment_history(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's payment history."""
    
    try:
        # Build query
        query = {"user_id": current_user.id}
        if status_filter:
            query["status"] = status_filter
        
        # Get payments
        payments_cursor = db.payments.find(query).sort("created_at", -1).limit(limit).skip(offset)
        payments_data = await payments_cursor.to_list(length=limit)
        
        # Get total count
        total_count = await db.payments.count_documents(query)
        
        return {
            "success": True,
            "data": {
                "payments": payments_data,
                "pagination": {
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": total_count > (offset + limit)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching payment history: {str(e)}"
        )

@router.get("/{payment_id}")
async def get_payment_details(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get payment details by ID."""
    
    try:
        payment_service = PaymentService()
        payment = await payment_service.get_payment(payment_id, current_user.id, db)
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        return {
            "success": True,
            "data": payment.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching payment details: {str(e)}"
        )

# ===== REFUNDS =====

@router.post("/refund")
async def create_refund(
    refund_request: RefundRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Request refund for a payment."""
    
    try:
        payment_service = PaymentService()
        refund_response = await payment_service.create_refund(refund_request, current_user.id, db)
        
        return {
            "success": True,
            "data": refund_response.dict(),
            "message": "Refund request created successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating refund: {str(e)}"
        )

# ===== ANALYTICS =====

@router.get("/analytics/summary")
async def get_payment_analytics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get payment analytics summary."""
    
    try:
        payment_service = PaymentService()
        analytics = await payment_service.get_payment_analytics(current_user.id, days, db)
        
        return {
            "success": True,
            "data": analytics.dict()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching payment analytics: {str(e)}"
        )

# ===== WEBHOOK ENDPOINTS (Admin/System use) =====

@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    payload: Dict[str, Any] = Body(...),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Handle Razorpay webhook events."""
    
    try:
        # This would include signature verification in production
        from models.payment import PaymentWebhook, PaymentProvider
        
        webhook_data = PaymentWebhook(
            provider=PaymentProvider.RAZORPAY,
            event_type=payload.get("event", ""),
            payment_id=payload.get("payload", {}).get("payment", {}).get("entity", {}).get("order_id", ""),
            payload=payload
        )
        
        payment_service = PaymentService()
        success = await payment_service.process_webhook(webhook_data, db)
        
        return {
            "success": success,
            "message": "Webhook processed successfully" if success else "Webhook processing failed"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}"
        )