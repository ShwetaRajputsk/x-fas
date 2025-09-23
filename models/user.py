from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime
import uuid
from enum import Enum

class UserType(str, Enum):
    INDIVIDUAL = "individual"
    BUSINESS = "business"
    # Add uppercase variants for backward compatibility
    BUSINESS_UPPER = "BUSINESS"
    INDIVIDUAL_UPPER = "INDIVIDUAL"

class UserRole(str, Enum):
    USER = "user"
    SUPPORT = "support"
    MANAGER = "manager"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"
    # Add uppercase variants for backward compatibility
    SUPER_ADMIN_UPPER = "SUPER_ADMIN"
    ADMIN_UPPER = "ADMIN"
    MANAGER_UPPER = "MANAGER"

class AddressType(str, Enum):
    PICKUP = "pickup"
    DELIVERY = "delivery"
    BOTH = "both"

class PaymentMethodType(str, Enum):
    CARD = "card"
    UPI = "upi"
    NETBANKING = "netbanking"
    WALLET = "wallet"

class Address(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str  # e.g., "Home", "Office", "Warehouse"
    contact_name: str
    contact_phone: str
    street: str
    landmark: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str = "India"
    address_type: AddressType
    is_default: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class PaymentMethod(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: PaymentMethodType
    label: str  # e.g., "Personal Card", "Business Account"
    # For security, we only store tokenized/masked details
    masked_details: str  # e.g., "****1234" for cards, "****@paytm" for UPI
    provider: Optional[str] = None  # e.g., "Visa", "MasterCard", "PayTM"
    is_default: bool = False
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class BusinessInfo(BaseModel):
    company_name: str
    gst_number: Optional[str] = None
    pan_number: Optional[str] = None
    business_type: str
    annual_volume: Optional[int] = None
    industry: Optional[str] = None
    registration_date: Optional[datetime] = None
    cin_number: Optional[str] = None  # Corporate Identification Number

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: EmailStr
    password_hash: str
    first_name: str
    last_name: str
    phone: str
    user_type: UserType = UserType.INDIVIDUAL
    role: UserRole = UserRole.USER
    
    # Profile verification status
    is_verified: bool = False
    is_email_verified: bool = False
    is_phone_verified: bool = False
    
    # Account status
    is_active: bool = True
    
    # Saved addresses and payment methods
    saved_addresses: List[Address] = Field(default_factory=list)
    payment_methods: List[PaymentMethod] = Field(default_factory=list)
    
    # Business information for B2B users
    business_info: Optional[BusinessInfo] = None
    
    # User preferences
    preferred_language: str = "en"
    timezone: str = "Asia/Kolkata"
    notification_preferences: dict = Field(default_factory=lambda: {
        "email_notifications": True,
        "sms_notifications": True,
        "push_notifications": True,
        "marketing_emails": False
    })
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None
    email_verified_at: Optional[datetime] = None
    phone_verified_at: Optional[datetime] = None
    
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: str
    user_type: UserType = UserType.INDIVIDUAL
    business_info: Optional[BusinessInfo] = None

class UserResponse(BaseModel):
    id: str
    email: str
    first_name: str
    last_name: str
    phone: str
    user_type: UserType
    role: UserRole = UserRole.USER
    is_verified: bool
    is_email_verified: bool
    is_phone_verified: bool
    created_at: datetime
    business_info: Optional[BusinessInfo] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    business_info: Optional[BusinessInfo] = None
    preferred_language: Optional[str] = None
    timezone: Optional[str] = None
    notification_preferences: Optional[dict] = None

# Address Management Models
class AddressCreate(BaseModel):
    label: str
    contact_name: str
    contact_phone: str
    street: str
    landmark: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str = "India"
    address_type: AddressType
    is_default: bool = False

class AddressUpdate(BaseModel):
    label: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    street: Optional[str] = None
    landmark: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    address_type: Optional[AddressType] = None
    is_default: Optional[bool] = None

# Payment Method Models (for reference only, not storing actual payment data)
class PaymentMethodCreate(BaseModel):
    type: PaymentMethodType
    label: str
    masked_details: str
    provider: Optional[str] = None
    is_default: bool = False

class PaymentMethodUpdate(BaseModel):
    label: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None

# OTP Models
class OTPRequest(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    purpose: str  # "registration", "login", "verify_email", "verify_phone"

class OTPVerification(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    otp_code: str
    purpose: str

# Enhanced Registration Models
class UserCreateWithOTP(BaseModel):
    email: EmailStr
    phone: str
    first_name: str
    last_name: str
    user_type: UserType = UserType.INDIVIDUAL
    business_info: Optional[BusinessInfo] = None
    otp_code: str
    
class PhoneLoginRequest(BaseModel):
    phone: str
    otp_code: str
