from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid

class ShipmentType(str, Enum):
    PARCEL = "parcel"
    DOCUMENT = "document"
    CARGO = "cargo"

class ShipmentStatus(str, Enum):
    DRAFT = "draft"
    BOOKED = "booked"
    PICKUP_SCHEDULED = "pickup_scheduled"
    PICKED_UP = "picked_up"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    RETURNED = "returned"
    CANCELLED = "cancelled"
    LOST = "lost"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"

class ServiceType(str, Enum):
    STANDARD = "standard"
    EXPRESS = "express"
    OVERNIGHT = "overnight"
    ECONOMY = "economy"
    SAME_DAY = "same_day"

class Address(BaseModel):
    name: str
    company: Optional[str] = None
    phone: str
    email: str
    street: str
    city: str
    state: str
    postal_code: str
    country: str
    landmark: Optional[str] = None

class PackageDimensions(BaseModel):
    length: float  # cm
    width: float   # cm
    height: float  # cm
    weight: float  # kg

class PackageInfo(BaseModel):
    type: ShipmentType
    dimensions: PackageDimensions
    declared_value: float
    contents_description: str
    quantity: int = 1
    fragile: bool = False
    dangerous_goods: bool = False

class CarrierInfo(BaseModel):
    carrier_name: str
    service_type: ServiceType
    tracking_number: Optional[str] = None
    estimated_delivery: Optional[datetime] = None
    carrier_reference: Optional[str] = None

class TrackingEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime
    status: str
    location: str
    description: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PaymentInfo(BaseModel):
    amount: float
    currency: str = "INR"
    status: PaymentStatus
    payment_method: Optional[str] = None
    payment_id: Optional[str] = None
    transaction_id: Optional[str] = None

class Shipment(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    quote_id: Optional[str] = None
    shipment_number: str = Field(default_factory=lambda: f"XF{str(uuid.uuid4())[:8].upper()}")
    
    # Shipment details
    sender: Address
    recipient: Address
    package_info: PackageInfo
    
    # Carrier and service
    carrier_info: CarrierInfo
    
    # Status and tracking
    status: ShipmentStatus = ShipmentStatus.DRAFT
    tracking_events: List[TrackingEvent] = []
    
    # Payment
    payment_info: PaymentInfo
    
    # Additional services
    insurance_required: bool = False
    insurance_amount: Optional[float] = None
    signature_required: bool = False
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    pickup_date: Optional[datetime] = None
    delivery_date: Optional[datetime] = None
    
    # Internal notes
    notes: Optional[str] = None
    custom_reference: Optional[str] = None

class ShipmentCreate(BaseModel):
    quote_id: Optional[str] = None
    sender: Address
    recipient: Address
    package_info: PackageInfo
    carrier_name: str
    service_type: ServiceType
    insurance_required: bool = False
    signature_required: bool = False
    custom_reference: Optional[str] = None
    notes: Optional[str] = None

class ShipmentResponse(BaseModel):
    id: str
    shipment_number: str
    status: ShipmentStatus
    sender: Address
    recipient: Address
    package_info: PackageInfo
    carrier_info: CarrierInfo
    payment_info: PaymentInfo
    tracking_events: List[TrackingEvent]
    created_at: datetime
    estimated_delivery: Optional[datetime] = None

class ShipmentUpdate(BaseModel):
    status: Optional[ShipmentStatus] = None
    tracking_number: Optional[str] = None
    notes: Optional[str] = None