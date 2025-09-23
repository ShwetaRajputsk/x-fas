from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum
import uuid

class AddressType(str, Enum):
    PICKUP = "pickup"
    DELIVERY = "delivery"
    BOTH = "both"

class AddressCategory(str, Enum):
    HOME = "home"
    OFFICE = "office"
    WAREHOUSE = "warehouse"
    SHOP = "shop"
    OTHER = "other"

class SavedAddress(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    
    # Address identification
    label: str = Field(..., min_length=1, max_length=100, description="User-friendly name for the address")
    address_type: AddressType = AddressType.BOTH
    category: AddressCategory = AddressCategory.OTHER
    
    # Address details (following the existing Address model structure)
    name: str = Field(..., min_length=1, max_length=100)
    company: Optional[str] = Field(None, max_length=100)
    phone: str = Field(..., min_length=10, max_length=15)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    street: str = Field(..., min_length=5, max_length=200)
    city: str = Field(..., min_length=2, max_length=50)
    state: str = Field(..., min_length=2, max_length=50)
    postal_code: str = Field(..., min_length=5, max_length=10)
    country: str = Field(default="India", max_length=50)
    landmark: Optional[str] = Field(None, max_length=100)
    
    # Additional metadata
    is_default_pickup: bool = Field(default=False)
    is_default_delivery: bool = Field(default=False)
    is_active: bool = Field(default=True)
    
    # Usage statistics
    usage_count: int = Field(default=0)
    last_used_at: Optional[datetime] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('phone')
    def validate_phone(cls, v):
        # Remove all non-digits
        digits = ''.join(filter(str.isdigit, v))
        
        # Indian phone number validation
        if len(digits) == 10 and digits[0] in '6789':
            return f"+91{digits}"
        elif len(digits) == 12 and digits.startswith('91'):
            return f"+{digits}"
        elif len(digits) == 13 and digits.startswith('91'):
            return f"+{digits[1:]}"
        else:
            raise ValueError('Invalid Indian phone number')
    
    @validator('postal_code')
    def validate_postal_code(cls, v, values):
        if values.get('country') == 'India':
            # Indian postal code validation (6 digits)
            if not v.isdigit() or len(v) != 6:
                raise ValueError('Indian postal code must be 6 digits')
        return v
    
    def to_address_dict(self):
        """Convert to Address model format for shipment creation"""
        return {
            "name": self.name,
            "company": self.company,
            "phone": self.phone,
            "email": self.email,
            "street": self.street,
            "city": self.city,
            "state": self.state,
            "postal_code": self.postal_code,
            "country": self.country,
            "landmark": self.landmark
        }

class SavedAddressCreate(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    address_type: AddressType = AddressType.BOTH
    category: AddressCategory = AddressCategory.OTHER
    
    name: str = Field(..., min_length=1, max_length=100)
    company: Optional[str] = Field(None, max_length=100)
    phone: str = Field(..., min_length=10, max_length=15)
    email: str = Field(..., pattern=r'^[^@]+@[^@]+\.[^@]+$')
    street: str = Field(..., min_length=5, max_length=200)
    city: str = Field(..., min_length=2, max_length=50)
    state: str = Field(..., min_length=2, max_length=50)
    postal_code: str = Field(..., min_length=5, max_length=10)
    country: str = Field(default="India", max_length=50)
    landmark: Optional[str] = Field(None, max_length=100)
    
    is_default_pickup: bool = Field(default=False)
    is_default_delivery: bool = Field(default=False)
    
    @validator('phone')
    def validate_phone(cls, v):
        # Same validation as SavedAddress
        digits = ''.join(filter(str.isdigit, v))
        
        if len(digits) == 10 and digits[0] in '6789':
            return f"+91{digits}"
        elif len(digits) == 12 and digits.startswith('91'):
            return f"+{digits}"
        elif len(digits) == 13 and digits.startswith('91'):
            return f"+{digits[1:]}"
        else:
            raise ValueError('Invalid Indian phone number')
    
    @validator('postal_code')
    def validate_postal_code(cls, v, values):
        if values.get('country') == 'India':
            if not v.isdigit() or len(v) != 6:
                raise ValueError('Indian postal code must be 6 digits')
        return v

class SavedAddressUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=100)
    address_type: Optional[AddressType] = None
    category: Optional[AddressCategory] = None
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    company: Optional[str] = Field(None, max_length=100)
    phone: Optional[str] = Field(None, min_length=10, max_length=15)
    email: Optional[str] = Field(None, pattern=r'^[^@]+@[^@]+\.[^@]+$')
    street: Optional[str] = Field(None, min_length=5, max_length=200)
    city: Optional[str] = Field(None, min_length=2, max_length=50)
    state: Optional[str] = Field(None, min_length=2, max_length=50)
    postal_code: Optional[str] = Field(None, min_length=5, max_length=10)
    country: Optional[str] = Field(None, max_length=50)
    landmark: Optional[str] = Field(None, max_length=100)
    
    is_default_pickup: Optional[bool] = None
    is_default_delivery: Optional[bool] = None
    is_active: Optional[bool] = None
    
    @validator('phone')
    def validate_phone(cls, v):
        if v is None:
            return v
        # Same validation as SavedAddress
        digits = ''.join(filter(str.isdigit, v))
        
        if len(digits) == 10 and digits[0] in '6789':
            return f"+91{digits}"
        elif len(digits) == 12 and digits.startswith('91'):
            return f"+{digits}"
        elif len(digits) == 13 and digits.startswith('91'):
            return f"+{digits[1:]}"
        else:
            raise ValueError('Invalid Indian phone number')
    
    @validator('postal_code')
    def validate_postal_code(cls, v, values):
        if v is None:
            return v
        if values.get('country', 'India') == 'India':
            if not v.isdigit() or len(v) != 6:
                raise ValueError('Indian postal code must be 6 digits')
        return v

class SavedAddressResponse(BaseModel):
    id: str
    label: str
    address_type: AddressType
    category: AddressCategory
    
    name: str
    company: Optional[str]
    phone: str
    email: str
    street: str
    city: str
    state: str
    postal_code: str
    country: str
    landmark: Optional[str]
    
    is_default_pickup: bool
    is_default_delivery: bool
    is_active: bool
    
    usage_count: int
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

class AddressBookSummary(BaseModel):
    total_addresses: int
    pickup_addresses: int
    delivery_addresses: int
    both_addresses: int
    default_pickup: Optional[SavedAddressResponse]
    default_delivery: Optional[SavedAddressResponse]
    recently_used: List[SavedAddressResponse]
    most_used: List[SavedAddressResponse]

# Request models for API endpoints
class BulkDeleteRequest(BaseModel):
    address_ids: List[str] = Field(..., min_items=1, max_items=50)

class SetDefaultRequest(BaseModel):
    address_type: AddressType  # pickup or delivery

class AddressSearchRequest(BaseModel):
    query: Optional[str] = None
    address_type: Optional[AddressType] = None
    category: Optional[AddressCategory] = None
    city: Optional[str] = None
    state: Optional[str] = None
    is_active: Optional[bool] = True
    
class AddressImportRequest(BaseModel):
    addresses: List[SavedAddressCreate] = Field(..., min_items=1, max_items=100)
    skip_duplicates: bool = Field(default=True)
    
class AddressExportResponse(BaseModel):
    addresses: List[SavedAddressResponse]
    total_count: int
    export_date: datetime = Field(default_factory=datetime.utcnow)