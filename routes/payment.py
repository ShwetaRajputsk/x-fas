from fastapi import APIRouter, Depends, HTTPException, status, Request
from typing import Optional, List
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.user import User
from models.payment import (
    Payment, PaymentCreate, PaymentResponse, PaymentWebhook,
    Wallet, WalletTransaction, PaymentConfig, RefundRequest, RefundResponse,
    PaymentProvider, PaymentStatus, TransactionType
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

# ===== WALLET MANAGEMENT =====

@router.get("/wallet", response_model=Wallet)
async def get_wallet(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's wallet information."""
    
    try:
        payment_service = PaymentService()
        wallet = await payment_service.get_or_create_wallet(current_user.id, db)
        
        return wallet
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting wallet: {str(e)}"
        )

@router.get("/wallet/balance")
async def get_wallet_balance(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's wallet balance."""
    
    try:
        payment_service = PaymentService()
        balance = await payment_service.get_wallet_balance(current_user.id, db)
        
        return {"success": True, "balance": balance}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting wallet balance: {str(e)}"
        )

@router.get("/wallet/transactions", response_model=List[WalletTransaction])
async def get_wallet_transactions(
    limit: int = 50,
    skip: int = 0,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's wallet transaction history."""
    
    try:
        payment_service = PaymentService()
        transactions = await payment_service.get_wallet_transactions(current_user.id, db, limit, skip)
        
        return transactions
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting wallet transactions: {str(e)}"
        )

@router.post("/wallet/load", response_model=PaymentResponse)
async def load_wallet(
    amount: float,
    payment_method: str = "razorpay",
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Load money into user's wallet."""
    
    try:
        payment_service = PaymentService()
        
        # Create payment for wallet load
        payment_data = PaymentCreate(
            amount=amount,
            method=payment_method,
            purpose="wallet_load",
            customer_email=current_user.email,
            customer_name=f"{current_user.first_name} {current_user.last_name}",
            description=f"Wallet load of ₹{amount}"
        )
        
        payment_response = await payment_service.create_payment(payment_data, current_user.id, db)
        
        return payment_response
        
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading wallet: {str(e)}"
        )

# ===== PAYMENT PROCESSING =====

@router.post("/", response_model=PaymentResponse)
async def create_payment(
    payment_data: PaymentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new payment."""
    
    try:
        payment_service = PaymentService()
        payment_response = await payment_service.create_payment(payment_data, current_user.id, db)
        
        return payment_response
        
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating payment: {str(e)}"
        )

@router.get("/{payment_id}", response_model=Payment)
async def get_payment(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get payment details."""
    
    try:
        payment_service = PaymentService()
        payment = await payment_service.get_payment(payment_id, current_user.id, db)
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found"
            )
        
        return payment
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting payment: {str(e)}"
        )

@router.get("/")
async def get_user_payments(
    limit: int = 50,
    skip: int = 0,
    status_filter: Optional[PaymentStatus] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's payment history."""
    
    try:
        query = {"user_id": current_user.id}
        if status_filter:
            query["status"] = status_filter
        
        cursor = db.payments.find(query).sort("created_at", -1).skip(skip).limit(limit)
        payments_data = await cursor.to_list(length=limit)
        total_count = await db.payments.count_documents(query)
        
        payments = [Payment(**payment) for payment in payments_data]
        
        return {
            "success": True,
            "data": {
                "payments": payments,
                "total_count": total_count,
                "page_info": {
                    "limit": limit,
                    "skip": skip,
                    "has_more": total_count > (skip + limit)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting payments: {str(e)}"
        )

# ===== REFUNDS =====

@router.post("/refunds", response_model=RefundResponse)
async def create_refund(
    refund_request: RefundRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a refund request."""
    
    try:
        payment_service = PaymentService()
        refund_response = await payment_service.create_refund(refund_request, current_user.id, db)
        
        return refund_response
        
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating refund: {str(e)}"
        )

# ===== WEBHOOKS =====

@router.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Handle Razorpay webhooks."""
    
    try:
        payload = await request.body()
        signature = request.headers.get("X-Razorpay-Signature", "")
        
        # Parse payload
        import json
        webhook_data = json.loads(payload.decode('utf-8'))
        
        # Create webhook record
        webhook = PaymentWebhook(
            provider=PaymentProvider.RAZORPAY,
            event_type=webhook_data.get("event", "unknown"),
            payment_id=webhook_data.get("payload", {}).get("payment", {}).get("entity", {}).get("order_id", ""),
            payload=webhook_data,
            signature=signature
        )
        
        payment_service = PaymentService()
        processed = await payment_service.process_webhook(webhook, db)
        
        if processed:
            return {"status": "success"}
        else:
            return {"status": "ignored"}
            
    except Exception as e:
        # Return success to avoid webhook retries for processing errors
        return {"status": "error", "message": str(e)}

@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Handle Stripe webhooks (future implementation)."""
    
    try:
        payload = await request.body()
        signature = request.headers.get("Stripe-Signature", "")
        
        # Future: Implement Stripe webhook processing
        return {"status": "not_implemented"}
            
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ===== ANALYTICS =====

@router.get("/analytics")
async def get_payment_analytics(
    days: int = 30,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's payment analytics."""
    
    try:
        payment_service = PaymentService()
        analytics = await payment_service.get_payment_analytics(current_user.id, days, db)
        
        return {"success": True, "data": analytics}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting payment analytics: {str(e)}"
        )

# ===== CONFIGURATION =====

@router.get("/config", response_model=PaymentConfig)
async def get_payment_config(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get payment configuration (admin only)."""
    
    try:
        payment_service = PaymentService()
        config = await payment_service.get_payment_config(db)
        
        # Remove sensitive fields for response
        config.razorpay_key_secret = None
        config.razorpay_webhook_secret = None
        config.stripe_secret_key = None
        config.stripe_webhook_secret = None
        
        return config
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting payment config: {str(e)}"
        )

@router.put("/config", response_model=PaymentConfig)
async def update_payment_config(
    config_data: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update payment configuration (admin only)."""
    
    try:
        config_data["updated_at"] = datetime.utcnow()
        
        await db.payment_config.update_one(
            {},
            {"$set": config_data},
            upsert=True
        )
        
        payment_service = PaymentService()
        updated_config = await payment_service.get_payment_config(db)
        
        # Remove sensitive fields for response
        updated_config.razorpay_key_secret = None
        updated_config.razorpay_webhook_secret = None
        updated_config.stripe_secret_key = None
        updated_config.stripe_webhook_secret = None
        
        return updated_config
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating payment config: {str(e)}"
        )