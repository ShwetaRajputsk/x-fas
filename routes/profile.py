from fastapi import APIRouter, Depends, HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from typing import List
from pydantic import BaseModel

from models.user import (
    User, UserResponse, UserUpdate, 
    Address, AddressCreate, AddressUpdate,
    PaymentMethod, PaymentMethodCreate, PaymentMethodUpdate
)
from utils.auth import get_current_user

# Database dependency
async def get_database() -> AsyncIOMotorDatabase:
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    return client[os.environ.get('DB_NAME', 'xfas_logistics')]

router = APIRouter(prefix="/profile", tags=["Profile Management"])

# Pydantic models for request bodies
class OTPVerificationRequest(BaseModel):
    otp_code: str

# User Profile Management

@router.get("/", response_model=UserResponse)
async def get_user_profile(
    current_user: User = Depends(get_current_user)
):
    """Get current user's complete profile."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        phone=current_user.phone,
        user_type=current_user.user_type,
        is_verified=current_user.is_verified,
        is_email_verified=current_user.is_email_verified,
        is_phone_verified=current_user.is_phone_verified,
        created_at=current_user.created_at,
        business_info=current_user.business_info
    )

@router.put("/", response_model=UserResponse)
async def update_user_profile(
    profile_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update user profile information."""
    
    # Prepare update data
    update_data = {}
    for field, value in profile_update.dict(exclude_unset=True).items():
        if value is not None:
            update_data[field] = value
    
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        
        # Update user in database
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": update_data}
        )
        
        # Get updated user
        updated_user_doc = await db.users.find_one({"id": current_user.id})
        updated_user = User(**updated_user_doc)
        
        return UserResponse(
            id=updated_user.id,
            email=updated_user.email,
            first_name=updated_user.first_name,
            last_name=updated_user.last_name,
            phone=updated_user.phone,
            user_type=updated_user.user_type,
            is_verified=updated_user.is_verified,
            is_email_verified=updated_user.is_email_verified,
            is_phone_verified=updated_user.is_phone_verified,
            created_at=updated_user.created_at,
            business_info=updated_user.business_info
        )
    
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        phone=current_user.phone,
        user_type=current_user.user_type,
        is_verified=current_user.is_verified,
        is_email_verified=current_user.is_email_verified,
        is_phone_verified=current_user.is_phone_verified,
        created_at=current_user.created_at,
        business_info=current_user.business_info
    )

# Address Management

@router.get("/addresses", response_model=List[Address])
async def get_user_addresses(
    current_user: User = Depends(get_current_user)
):
    """Get all saved addresses for the current user."""
    return current_user.saved_addresses

@router.post("/addresses", response_model=Address)
async def add_user_address(
    address_data: AddressCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Add a new address for the current user."""
    
    # Create new address
    new_address = Address(**address_data.dict())
    
    # If this is set as default, unset other default addresses of the same type
    if address_data.is_default:
        user_doc = await db.users.find_one({"id": current_user.id})
        if user_doc and "saved_addresses" in user_doc:
            updated_addresses = []
            for addr in user_doc["saved_addresses"]:
                if addr.get("address_type") == address_data.address_type and addr.get("is_default"):
                    addr["is_default"] = False
                updated_addresses.append(addr)
            
            await db.users.update_one(
                {"id": current_user.id},
                {"$set": {"saved_addresses": updated_addresses}}
            )
    
    # Add the new address
    await db.users.update_one(
        {"id": current_user.id},
        {"$push": {"saved_addresses": new_address.dict()}}
    )
    
    return new_address

@router.put("/addresses/{address_id}", response_model=Address)
async def update_user_address(
    address_id: str,
    address_update: AddressUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update a specific address."""
    
    user_doc = await db.users.find_one({"id": current_user.id})
    if not user_doc or "saved_addresses" not in user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    # Find and update the address
    address_found = False
    updated_addresses = []
    
    for addr in user_doc["saved_addresses"]:
        if addr["id"] == address_id:
            address_found = True
            
            # Update fields
            for field, value in address_update.dict(exclude_unset=True).items():
                if value is not None:
                    addr[field] = value
            
            addr["updated_at"] = datetime.utcnow().isoformat()
            
            # If setting as default, unset other defaults of same type
            if address_update.is_default:
                for other_addr in user_doc["saved_addresses"]:
                    if (other_addr["id"] != address_id and 
                        other_addr.get("address_type") == addr.get("address_type")):
                        other_addr["is_default"] = False
        
        updated_addresses.append(addr)
    
    if not address_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    # Update in database
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"saved_addresses": updated_addresses}}
    )
    
    # Return updated address
    updated_address = next(addr for addr in updated_addresses if addr["id"] == address_id)
    return Address(**updated_address)

@router.delete("/addresses/{address_id}")
async def delete_user_address(
    address_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete a specific address."""
    
    user_doc = await db.users.find_one({"id": current_user.id})
    if not user_doc or "saved_addresses" not in user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    # Filter out the address to delete
    original_count = len(user_doc["saved_addresses"])
    updated_addresses = [
        addr for addr in user_doc["saved_addresses"] 
        if addr["id"] != address_id
    ]
    
    if len(updated_addresses) == original_count:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )
    
    # Update in database
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"saved_addresses": updated_addresses}}
    )
    
    return {"message": "Address deleted successfully"}

# Payment Methods Management

@router.get("/payment-methods", response_model=List[PaymentMethod])
async def get_user_payment_methods(
    current_user: User = Depends(get_current_user)
):
    """Get all payment methods for the current user."""
    return [pm for pm in current_user.payment_methods if pm.is_active]

@router.post("/payment-methods", response_model=PaymentMethod)
async def add_payment_method(
    payment_data: PaymentMethodCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Add a new payment method (for reference only, not storing actual payment data)."""
    
    # Create new payment method
    new_payment_method = PaymentMethod(**payment_data.dict())
    
    # If this is set as default, unset other default payment methods
    if payment_data.is_default:
        user_doc = await db.users.find_one({"id": current_user.id})
        if user_doc and "payment_methods" in user_doc:
            updated_payment_methods = []
            for pm in user_doc["payment_methods"]:
                if pm.get("is_default"):
                    pm["is_default"] = False
                updated_payment_methods.append(pm)
            
            await db.users.update_one(
                {"id": current_user.id},
                {"$set": {"payment_methods": updated_payment_methods}}
            )
    
    # Add the new payment method
    await db.users.update_one(
        {"id": current_user.id},
        {"$push": {"payment_methods": new_payment_method.dict()}}
    )
    
    return new_payment_method

@router.put("/payment-methods/{payment_method_id}", response_model=PaymentMethod)
async def update_payment_method(
    payment_method_id: str,
    payment_update: PaymentMethodUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update a specific payment method."""
    
    user_doc = await db.users.find_one({"id": current_user.id})
    if not user_doc or "payment_methods" not in user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found"
        )
    
    # Find and update the payment method
    payment_method_found = False
    updated_payment_methods = []
    
    for pm in user_doc["payment_methods"]:
        if pm["id"] == payment_method_id:
            payment_method_found = True
            
            # Update fields
            for field, value in payment_update.dict(exclude_unset=True).items():
                if value is not None:
                    pm[field] = value
            
            pm["updated_at"] = datetime.utcnow().isoformat()
            
            # If setting as default, unset other defaults
            if payment_update.is_default:
                for other_pm in user_doc["payment_methods"]:
                    if other_pm["id"] != payment_method_id:
                        other_pm["is_default"] = False
        
        updated_payment_methods.append(pm)
    
    if not payment_method_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found"
        )
    
    # Update in database
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"payment_methods": updated_payment_methods}}
    )
    
    # Return updated payment method
    updated_payment_method = next(pm for pm in updated_payment_methods if pm["id"] == payment_method_id)
    return PaymentMethod(**updated_payment_method)

@router.delete("/payment-methods/{payment_method_id}")
async def delete_payment_method(
    payment_method_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete/deactivate a specific payment method."""
    
    user_doc = await db.users.find_one({"id": current_user.id})
    if not user_doc or "payment_methods" not in user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found"
        )
    
    # Find and deactivate the payment method
    payment_method_found = False
    updated_payment_methods = []
    
    for pm in user_doc["payment_methods"]:
        if pm["id"] == payment_method_id:
            payment_method_found = True
            pm["is_active"] = False
            pm["updated_at"] = datetime.utcnow().isoformat()
        updated_payment_methods.append(pm)
    
    if not payment_method_found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment method not found"
        )
    
    # Update in database
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"payment_methods": updated_payment_methods}}
    )
    
    return {"message": "Payment method deleted successfully"}

# Verification Management

@router.post("/verify-email")
async def request_email_verification(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Request email verification OTP."""
    
    if current_user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified"
        )
    
    # Try Twilio Verify for email first (if configured)
    from services.twilio_verify_service import twilio_verify_service
    
    if twilio_verify_service.is_configured():
        result = await twilio_verify_service.send_verification(
            to=current_user.email,
            channel='email'
        )
        
        if result['success']:
            return {
                "message": "Verification email sent successfully",
                "expires_in_minutes": 10,  # Twilio default
                "provider": "twilio_verify"
            }
        # If Twilio fails, fallback to custom email service
    
    # Use custom OTP service for email
    from services.otp_service import get_otp_service
    
    otp_service = get_otp_service(db)
    
    otp_data = await otp_service.create_otp(
        identifier=current_user.email,
        purpose="verify_email",
        identifier_type="email"
    )
    
    # In development, we might not have SMTP configured, so handle gracefully
    import os
    if os.getenv('ENVIRONMENT', 'development') == 'development' and (
        not os.getenv('SMTP_USER') or os.getenv('SMTP_USER') == 'your-email@gmail.com'
    ):
        # Development mode: log OTP instead of sending email
        print(f"[DEV] Email OTP for {current_user.email}: {otp_data['otp_code']}")
        email_sent = True
    else:
        # Production mode: actually send email
        email_sent = await otp_service.send_email_otp(
            email=current_user.email,
            otp_code=otp_data["otp_code"],
            purpose="verify_email"
        )
    
    if not email_sent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email"
        )
    
    return {
        "message": "Verification email sent successfully",
        "expires_in_minutes": otp_service.otp_expiry_minutes,
        "provider": "custom_email"
    }

@router.post("/verify-phone")
async def request_phone_verification(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Request phone verification using Twilio Verify."""
    
    if current_user.is_phone_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone is already verified"
        )
    
    if not current_user.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No phone number found in profile"
        )
    
    # Use Twilio Verify service
    from services.twilio_verify_service import twilio_verify_service
    
    if not twilio_verify_service.is_configured():
        # Fallback to custom OTP service if Twilio is not configured
        from services.otp_service import get_otp_service
        
        otp_service = get_otp_service(db)
        
        otp_data = await otp_service.create_otp(
            identifier=current_user.phone,
            purpose="verify_phone",
            identifier_type="phone"
        )
        
        sms_sent = await otp_service.send_sms_otp(
            phone=current_user.phone,
            otp_code=otp_data["otp_code"],
            purpose="verify_phone"
        )
        
        if not sms_sent:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification SMS"
            )
        
        return {
            "message": "Verification SMS sent successfully",
            "expires_in_minutes": otp_service.otp_expiry_minutes,
            "provider": "custom_otp"
        }
    
    # Use Twilio Verify
    result = await twilio_verify_service.send_verification(
        to=current_user.phone,
        channel='sms'
    )
    
    if not result['success']:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result['error']
        )
    
    return {
        "message": "Verification SMS sent successfully",
        "expires_in_minutes": 10,  # Twilio default
        "provider": "twilio_verify"
    }

@router.post("/confirm-email-verification")
async def confirm_email_verification(
    request: OTPVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Confirm email verification with OTP."""
    
    from services.otp_service import get_otp_service
    
    otp_service = get_otp_service(db)
    
    verification_result = await otp_service.verify_otp(
        identifier=current_user.email,
        otp_code=request.otp_code,
        purpose="verify_email"
    )
    
    if not verification_result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=verification_result["error"]
        )
    
    # Update user verification status
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {
            "is_email_verified": True,
            "email_verified_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }}
    )
    
    return {"message": "Email verified successfully"}

@router.post("/confirm-phone-verification")
async def confirm_phone_verification(
    request: OTPVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Confirm phone verification with OTP using Twilio Verify."""
    
    if not current_user.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No phone number found in profile"
        )
    
    # Try Twilio Verify first
    from services.twilio_verify_service import twilio_verify_service
    
    if twilio_verify_service.is_configured():
        # Use Twilio Verify
        result = await twilio_verify_service.check_verification(
            to=current_user.phone,
            code=request.otp_code
        )
        
        if not result['success']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result['error']
            )
    else:
        # Fallback to custom OTP service
        from services.otp_service import get_otp_service
        
        otp_service = get_otp_service(db)
        
        verification_result = await otp_service.verify_otp(
            identifier=current_user.phone,
            otp_code=request.otp_code,
            purpose="verify_phone"
        )
        
        if not verification_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=verification_result["error"]
            )
    
    # Update user verification status
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {
            "is_phone_verified": True,
            "phone_verified_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }}
    )
    
    return {"message": "Phone verified successfully"}
