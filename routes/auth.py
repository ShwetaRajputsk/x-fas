from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta, datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.user import (
    User, UserCreate, UserResponse, UserLogin, UserCreateWithOTP, 
    PhoneLoginRequest, OTPRequest, OTPVerification, UserType
)
from utils.auth import (
    verify_password, 
    get_password_hash, 
    create_access_token, 
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from services.otp_service import get_otp_service

# Database dependency
async def get_database() -> AsyncIOMotorDatabase:
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    return client[os.environ.get('DB_NAME', 'xfas_logistics')]

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=dict)
async def register_user(
    user_data: UserCreate,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Register a new user."""
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password and create user
    hashed_password = get_password_hash(user_data.password)
    
    user = User(
        email=user_data.email,
        password_hash=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone=user_data.phone,
        user_type=user_data.user_type,
        business_info=user_data.business_info
    )
    
    # Save to database
    await db.users.insert_one(user.dict())
    
    # Create access token with user role
    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        user_role=user.role
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            user_type=user.user_type,
            role=user.role,
            is_verified=user.is_verified,
            is_email_verified=user.is_email_verified,
            is_phone_verified=user.is_phone_verified,
            created_at=user.created_at,
            business_info=user.business_info
        )
    }

@router.post("/login", response_model=dict)
async def login_user(
    user_data: UserLogin,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Login user and return access token."""
    
    # Find user by email
    user_doc = await db.users.find_one({"email": user_data.email})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    user = User(**user_doc)
    
    # Verify password
    if not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is disabled"
        )
    
    # Update last login
    await db.users.update_one(
        {"id": user.id},
        {"$set": {"last_login": user.created_at}}
    )
    
    # Create access token with user role
    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        user_role=user.role
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            user_type=user.user_type,
            role=user.role,
            is_verified=user.is_verified,
            is_email_verified=user.is_email_verified,
            is_phone_verified=user.is_phone_verified,
            created_at=user.created_at,
            business_info=user.business_info
        )
    }

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """Get current user information."""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        phone=current_user.phone,
        user_type=current_user.user_type,
        role=current_user.role,
        is_verified=current_user.is_verified,
        is_email_verified=current_user.is_email_verified,
        is_phone_verified=current_user.is_phone_verified,
        created_at=current_user.created_at,
        business_info=current_user.business_info
    )

@router.post("/refresh", response_model=dict)
async def refresh_token(
    current_user: User = Depends(get_current_user)
):
    """Refresh access token."""
    
    access_token = create_access_token(
        data={"sub": current_user.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

# OTP-based Authentication Endpoints

@router.post("/request-otp", response_model=dict)
async def request_otp(
    otp_request: OTPRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Request OTP for email or phone verification."""
    
    if not otp_request.email and not otp_request.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either email or phone must be provided"
        )
    
    otp_service = get_otp_service(db)
    
    try:
        if otp_request.email:
            # Create OTP for email
            otp_data = await otp_service.create_otp(
                identifier=otp_request.email,
                purpose=otp_request.purpose,
                identifier_type="email"
            )
            
            # Send OTP via email
            email_sent = await otp_service.send_email_otp(
                email=otp_request.email,
                otp_code=otp_data["otp_code"],
                purpose=otp_request.purpose
            )
            
            if not email_sent:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to send OTP email"
                )
            
            return {
                "message": "OTP sent to email successfully",
                "email": otp_request.email,
                "expires_in_minutes": otp_service.otp_expiry_minutes
            }
            
        elif otp_request.phone:
            # Create OTP for phone
            otp_data = await otp_service.create_otp(
                identifier=otp_request.phone,
                purpose=otp_request.purpose,
                identifier_type="phone"
            )
            
            # Send OTP via SMS
            sms_sent = await otp_service.send_sms_otp(
                phone=otp_request.phone,
                otp_code=otp_data["otp_code"],
                purpose=otp_request.purpose
            )
            
            if not sms_sent:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to send OTP SMS"
                )
            
            return {
                "message": "OTP sent to phone successfully",
                "phone": otp_request.phone,
                "expires_in_minutes": otp_service.otp_expiry_minutes
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send OTP: {str(e)}"
        )

@router.post("/verify-otp", response_model=dict)
async def verify_otp(
    otp_verification: OTPVerification,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Verify OTP code."""
    
    if not otp_verification.email and not otp_verification.phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either email or phone must be provided"
        )
    
    otp_service = get_otp_service(db)
    identifier = otp_verification.email or otp_verification.phone
    
    result = await otp_service.verify_otp(
        identifier=identifier,
        otp_code=otp_verification.otp_code,
        purpose=otp_verification.purpose
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["error"]
        )
    
    return {
        "message": "OTP verified successfully",
        "verified": True
    }

@router.post("/register-with-otp", response_model=dict)
async def register_user_with_otp(
    user_data: UserCreateWithOTP,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Register a new user with OTP verification."""
    
    # First verify the OTP
    otp_service = get_otp_service(db)
    
    # Verify email OTP
    email_verification = await otp_service.verify_otp(
        identifier=user_data.email,
        otp_code=user_data.otp_code,
        purpose="registration"
    )
    
    if not email_verification["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email OTP verification failed: {email_verification['error']}"
        )
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Check if phone already exists
    existing_phone = await db.users.find_one({"phone": user_data.phone})
    if existing_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered"
        )
    
    # Create user (no password needed for OTP registration)
    user = User(
        email=user_data.email,
        password_hash="",  # No password for OTP-only registration
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone=user_data.phone,
        user_type=user_data.user_type,
        business_info=user_data.business_info,
        is_email_verified=True,
        email_verified_at=datetime.utcnow()
    )
    
    # Save to database
    await db.users.insert_one(user.dict())
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            user_type=user.user_type,
            role=user.role,
            is_verified=user.is_verified,
            is_email_verified=user.is_email_verified,
            is_phone_verified=user.is_phone_verified,
            created_at=user.created_at,
            business_info=user.business_info
        )
    }

@router.post("/login-with-phone", response_model=dict)
async def login_with_phone(
    phone_login: PhoneLoginRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Login user using phone number and OTP."""
    
    # Verify OTP
    otp_service = get_otp_service(db)
    otp_verification = await otp_service.verify_otp(
        identifier=phone_login.phone,
        otp_code=phone_login.otp_code,
        purpose="login"
    )
    
    if not otp_verification["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OTP verification failed: {otp_verification['error']}"
        )
    
    # Find user by phone
    user_doc = await db.users.find_one({"phone": phone_login.phone})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phone number not registered"
        )
    
    user = User(**user_doc)
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account is disabled"
        )
    
    # Update last login and phone verification status
    update_data = {
        "last_login": datetime.utcnow(),
        "is_phone_verified": True
    }
    if not user.phone_verified_at:
        update_data["phone_verified_at"] = datetime.utcnow()
    
    await db.users.update_one(
        {"id": user.id},
        {"$set": update_data}
    )
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user.id},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            user_type=user.user_type,
            role=user.role,
            is_verified=user.is_verified,
            is_email_verified=user.is_email_verified,
            is_phone_verified=user.is_phone_verified,
            created_at=user.created_at,
            business_info=user.business_info
        )
    }
