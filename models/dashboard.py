from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

from models.user import Address

class SavedAddress(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    user_id: str
    address_type: str  # 'pickup', 'delivery', 'both'
    label: str  # 'Home', 'Office', 'Warehouse', etc.
    address: Address
    is_default: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class SavedAddressCreate(BaseModel):
    address_type: str
    label: str
    address: Address
    is_default: bool = False

class SavedAddressUpdate(BaseModel):
    address_type: Optional[str] = None
    label: Optional[str] = None
    address: Optional[Address] = None
    is_default: Optional[bool] = None

class UserPreferences(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    user_id: str
    
    # Notification preferences
    email_notifications: bool = True
    sms_notifications: bool = True
    push_notifications: bool = False
    marketing_emails: bool = True
    
    # Default shipping preferences
    default_service_type: Optional[str] = "standard"
    default_insurance: bool = False
    default_signature: bool = False
    
    # Dashboard preferences
    dashboard_layout: str = "grid"  # 'grid', 'list'
    items_per_page: int = 10
    default_date_range: str = "30_days"  # '7_days', '30_days', '90_days', 'all'
    
    # Currency and locale
    currency: str = "INR"
    timezone: str = "Asia/Kolkata"
    language: str = "en"
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class UserPreferencesUpdate(BaseModel):
    email_notifications: Optional[bool] = None
    sms_notifications: Optional[bool] = None
    push_notifications: Optional[bool] = None
    marketing_emails: Optional[bool] = None
    default_service_type: Optional[str] = None
    default_insurance: Optional[bool] = None
    default_signature: Optional[bool] = None
    dashboard_layout: Optional[str] = None
    items_per_page: Optional[int] = None
    default_date_range: Optional[str] = None
    currency: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None

class DashboardStats(BaseModel):
    # Shipment statistics
    total_shipments: int = 0
    active_shipments: int = 0
    delivered_shipments: int = 0
    pending_shipments: int = 0
    cancelled_shipments: int = 0
    
    # Financial statistics
    total_spent: float = 0.0
    this_month_spent: float = 0.0
    average_shipment_cost: float = 0.0
    total_savings: float = 0.0
    
    # Performance statistics
    on_time_delivery_rate: float = 0.0
    average_delivery_time: float = 0.0
    success_rate: float = 0.0
    
    # Carrier usage
    favorite_carrier: Optional[str] = None
    carrier_distribution: Dict[str, int] = {}
    
    # Recent activity
    last_shipment_date: Optional[datetime] = None
    shipments_this_week: int = 0
    shipments_this_month: int = 0

class MonthlyTrend(BaseModel):
    month: str
    year: int
    shipment_count: int
    total_cost: float
    delivered_count: int
    average_delivery_time: float

class CarrierPerformance(BaseModel):
    carrier_name: str
    total_shipments: int
    delivered_shipments: int
    average_cost: float
    average_delivery_time: float
    on_time_rate: float
    success_rate: float

class RecentActivity(BaseModel):
    activity_type: str  # 'shipment_created', 'status_update', 'delivered', etc.
    description: str
    shipment_id: Optional[str] = None
    awb: Optional[str] = None
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = {}

class DashboardData(BaseModel):
    stats: DashboardStats
    monthly_trends: List[MonthlyTrend]
    carrier_performance: List[CarrierPerformance]
    recent_activities: List[RecentActivity]
    quick_actions: List[Dict[str, Any]]
    notifications: List[Dict[str, Any]]

class AddressBookEntry(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    user_id: str
    contact_type: str  # 'personal', 'business'
    name: str
    company: Optional[str] = None
    phone: str
    email: str
    address: Address
    tags: List[str] = []  # 'frequent', 'vip', 'family', etc.
    notes: Optional[str] = None
    usage_count: int = 0
    last_used: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class AddressBookCreate(BaseModel):
    contact_type: str
    name: str
    company: Optional[str] = None
    phone: str
    email: str
    address: Address
    tags: List[str] = []
    notes: Optional[str] = None

class AddressBookUpdate(BaseModel):
    contact_type: Optional[str] = None
    name: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[Address] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None