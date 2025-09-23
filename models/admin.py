from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    SUPPORT = "support"

class CarrierRate(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    carrier_name: str
    service_type: str  # 'standard', 'express', 'economy'
    
    # Rate structure
    base_rate_per_kg: float
    fuel_surcharge_percentage: float = 0.0
    insurance_rate_percentage: float = 0.5
    signature_fee: float = 0.0
    
    # Zone-based pricing
    domestic_multiplier: float = 1.0
    international_multiplier: float = 2.5
    
    # Weight brackets
    min_weight: float = 0.5
    max_weight: float = 50.0
    
    # Geographic coverage
    covered_countries: List[str] = ["IN"]  # ISO country codes
    excluded_pincodes: List[str] = []
    
    # Operational details
    pickup_cutoff_time: str = "18:00"
    estimated_delivery_days: int = 3
    max_dimensions: Dict[str, float] = {"length": 100, "width": 60, "height": 40}
    
    # Status and metadata
    is_active: bool = True
    effective_from: datetime = Field(default_factory=datetime.utcnow)
    effective_until: Optional[datetime] = None
    created_by: str
    updated_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class CarrierRateCreate(BaseModel):
    carrier_name: str
    service_type: str
    base_rate_per_kg: float
    fuel_surcharge_percentage: float = 0.0
    insurance_rate_percentage: float = 0.5
    signature_fee: float = 0.0
    domestic_multiplier: float = 1.0
    international_multiplier: float = 2.5
    min_weight: float = 0.5
    max_weight: float = 50.0
    covered_countries: List[str] = ["IN"]
    excluded_pincodes: List[str] = []
    pickup_cutoff_time: str = "18:00"
    estimated_delivery_days: int = 3
    max_dimensions: Dict[str, float] = {"length": 100, "width": 60, "height": 40}
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None

class CarrierRateUpdate(BaseModel):
    carrier_name: Optional[str] = None
    service_type: Optional[str] = None
    base_rate_per_kg: Optional[float] = None
    fuel_surcharge_percentage: Optional[float] = None
    insurance_rate_percentage: Optional[float] = None
    signature_fee: Optional[float] = None
    domestic_multiplier: Optional[float] = None
    international_multiplier: Optional[float] = None
    min_weight: Optional[float] = None
    max_weight: Optional[float] = None
    covered_countries: Optional[List[str]] = None
    excluded_pincodes: Optional[List[str]] = None
    pickup_cutoff_time: Optional[str] = None
    estimated_delivery_days: Optional[int] = None
    max_dimensions: Optional[Dict[str, float]] = None
    is_active: Optional[bool] = None
    effective_until: Optional[datetime] = None

class AdminStats(BaseModel):
    # User statistics
    total_users: int = 0
    active_users: int = 0
    new_users_this_month: int = 0
    user_growth_rate: float = 0.0
    
    # Shipment statistics
    total_shipments: int = 0
    active_shipments: int = 0
    completed_shipments: int = 0
    shipments_today: int = 0
    shipments_this_month: int = 0
    
    # Financial statistics
    total_revenue: float = 0.0
    revenue_this_month: float = 0.0
    revenue_today: float = 0.0
    average_order_value: float = 0.0
    
    # Performance statistics
    overall_success_rate: float = 0.0
    average_delivery_time: float = 0.0
    customer_satisfaction: float = 0.0
    
    # Carrier statistics
    total_carriers: int = 0
    active_carriers: int = 0
    best_performing_carrier: Optional[str] = None
    
    # System statistics
    api_requests_today: int = 0
    error_rate: float = 0.0
    uptime_percentage: float = 99.9

class RevenueBreakdown(BaseModel):
    carrier_name: str
    total_revenue: float
    shipment_count: int
    average_rate: float
    market_share: float

class UserGrowthData(BaseModel):
    period: str  # 'YYYY-MM' or 'YYYY-MM-DD'
    new_users: int
    total_users: int
    churn_rate: float = 0.0

class CarrierAnalytics(BaseModel):
    carrier_name: str
    total_shipments: int
    success_rate: float
    average_delivery_time: float
    customer_rating: float
    revenue_contribution: float
    cost_efficiency: float
    on_time_percentage: float

class SystemAlert(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    alert_type: str  # 'error', 'warning', 'info', 'critical'
    title: str
    message: str
    component: str  # 'api', 'database', 'carrier', 'payment'
    severity: int = 1  # 1-5, 5 being critical
    is_resolved: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}

class AdminDashboardData(BaseModel):
    stats: AdminStats
    revenue_breakdown: List[RevenueBreakdown]
    user_growth: List[UserGrowthData]
    carrier_analytics: List[CarrierAnalytics]
    recent_shipments: List[Dict[str, Any]]
    system_alerts: List[SystemAlert]
    top_routes: List[Dict[str, Any]]
    performance_metrics: Dict[str, float]

class UserManagement(BaseModel):
    id: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    user_type: str
    is_active: bool
    total_shipments: int
    total_spent: float
    last_login: Optional[datetime] = None
    created_at: datetime
    verification_status: str = "pending"  # 'pending', 'verified', 'rejected'

class BookingManagement(BaseModel):
    id: str
    shipment_number: str
    awb: str
    status: str
    carrier: str
    sender_name: str
    sender_city: str
    recipient_name: str
    recipient_city: str
    created_at: datetime
    estimated_delivery: Optional[datetime] = None
    actual_delivery: Optional[datetime] = None
    amount: float
    user_email: str

class RouteAnalytics(BaseModel):
    route: str  # "City A → City B"
    shipment_count: int
    total_revenue: float
    average_delivery_time: float
    success_rate: float
    popular_carriers: List[str]

class PerformanceMetrics(BaseModel):
    metric_name: str
    current_value: float
    target_value: float
    unit: str
    trend: str  # 'up', 'down', 'stable'
    percentage_change: float

class KYCDocumentType(str, Enum):
    AADHAR = "aadhar"
    PAN = "pan"
    PASSPORT = "passport"
    DRIVING_LICENSE = "driving_license"
    VOTER_ID = "voter_id"
    GST_CERTIFICATE = "gst_certificate"
    BANK_STATEMENT = "bank_statement"
    ADDRESS_PROOF = "address_proof"
    BUSINESS_REGISTRATION = "business_registration"

class KYCStatus(str, Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

class KYCDocument(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    user_id: str
    document_type: KYCDocumentType
    document_number: str
    document_url: str  # File storage URL
    front_image_url: Optional[str] = None
    back_image_url: Optional[str] = None
    status: KYCStatus = KYCStatus.PENDING
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None  # Admin user ID
    rejection_reason: Optional[str] = None
    expiry_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = {}

class GSTInfo(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    user_id: str
    gst_number: str
    business_name: str
    business_type: str  # 'proprietorship', 'partnership', 'private_limited', etc.
    business_address: Dict[str, str]
    status: KYCStatus = KYCStatus.PENDING
    verified_at: Optional[datetime] = None
    verified_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    certificate_url: Optional[str] = None
    annual_turnover: Optional[float] = None

class CustomerKYC(BaseModel):
    user_id: str
    kyc_status: KYCStatus = KYCStatus.PENDING
    documents: List[KYCDocument] = []
    gst_info: Optional[GSTInfo] = None
    verification_score: int = 0  # 0-100
    risk_level: str = "medium"  # 'low', 'medium', 'high'
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = None
    assigned_reviewer: Optional[str] = None

class TrackingEvent(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    shipment_id: str
    tracking_number: str
    event_time: datetime
    event_code: str
    event_description: str
    location: Optional[str] = None
    carrier_name: str
    raw_data: Optional[Dict[str, Any]] = {}  # Original carrier API response
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AutoTrackingConfig(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    carrier_name: str
    api_endpoint: str
    api_key: Optional[str] = None
    auth_header: Optional[str] = None
    polling_interval_minutes: int = 30
    is_active: bool = True
    last_sync: Optional[datetime] = None
    error_count: int = 0
    max_errors: int = 5
    request_mapping: Dict[str, str] = {}  # How to map our fields to carrier API
    response_mapping: Dict[str, str] = {}  # How to map carrier response to our fields

class BulkOperation(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    operation_type: str  # 'update_status', 'assign_carrier', 'bulk_tracking_update'
    total_items: int
    processed_items: int = 0
    successful_items: int = 0
    failed_items: int = 0
    status: str = "pending"  # 'pending', 'processing', 'completed', 'failed'
    initiated_by: str  # Admin user ID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error_log: List[str] = []
    metadata: Dict[str, Any] = {}
