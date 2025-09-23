from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from enum import Enum
import uuid

class QuoteStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    USED = "used"

class ServiceLevel(str, Enum):
    ECONOMY = "economy"
    STANDARD = "standard"  
    EXPRESS = "express"
    OVERNIGHT = "overnight"
    SAME_DAY = "same_day"

class QuoteRequest(BaseModel):
    from_country: str
    from_postal_code: Optional[str] = None
    to_country: str 
    to_postal_code: Optional[str] = None
    
    # Package details
    shipment_type: str  # "parcel" or "document"
    weight: float  # kg
    length: Optional[float] = None  # cm
    width: Optional[float] = None   # cm  
    height: Optional[float] = None  # cm
    declared_value: float = 0
    
    # Service preferences
    service_level: Optional[ServiceLevel] = None
    insurance_required: bool = False
    signature_required: bool = False

class CarrierQuote(BaseModel):
    carrier_name: str
    service_name: str
    service_level: ServiceLevel
    
    # Pricing
    base_rate: float
    fuel_surcharge: float = 0
    insurance_cost: float = 0
    additional_fees: float = 0
    total_cost: float
    currency: str = "INR"
    
    # Service details  
    estimated_delivery_days: int
    estimated_delivery_date: datetime
    
    # Features
    features: List[str] = []
    restrictions: List[str] = []
    
    # Carrier specific
    carrier_reference: Optional[str] = None
    rate_id: Optional[str] = None

class Quote(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: Optional[str] = None
    
    # Quote request details
    request: QuoteRequest
    
    # Quote results
    carrier_quotes: List[CarrierQuote] = []
    
    # Quote metadata
    status: QuoteStatus = QuoteStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(hours=24))
    
    # Usage tracking
    selected_carrier: Optional[str] = None
    used_at: Optional[datetime] = None

class QuoteResponse(BaseModel):
    id: str
    request: QuoteRequest  
    carrier_quotes: List[CarrierQuote]
    status: QuoteStatus
    created_at: datetime
    expires_at: datetime
    total_quotes: int
    cheapest_quote: Optional[CarrierQuote] = None
    fastest_quote: Optional[CarrierQuote] = None
    recommended_quote: Optional[CarrierQuote] = None

class CarrierRate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    carrier_name: str
    service_name: str
    from_country: str
    to_country: str
    
    # Weight brackets
    min_weight: float = 0
    max_weight: Optional[float] = None
    
    # Pricing per kg
    base_rate_per_kg: float
    minimum_charge: float
    
    # Surcharges
    fuel_surcharge_percent: float = 0
    remote_area_surcharge: float = 0
    
    # Service details
    delivery_days_min: int
    delivery_days_max: int
    
    # Coverage
    postal_codes: List[str] = []
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = True