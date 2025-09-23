from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class PaymentProvider(str, Enum):
    RAZORPAY = "razorpay"
    STRIPE = "stripe"
    PAYPAL = "paypal"
    UPI = "upi"
    WALLET = "wallet"
    COD = "cod"

class PaymentMethod(str, Enum):
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    NET_BANKING = "net_banking"
    UPI = "upi"
    WALLET = "wallet"
    EMI = "emi"
    COD = "cod"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"

class TransactionType(str, Enum):
    PAYMENT = "payment"
    REFUND = "refund"
    WALLET_LOAD = "wallet_load"
    WALLET_DEDUCT = "wallet_deduct"
    ADJUSTMENT = "adjustment"

class Wallet(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    user_id: str
    balance: float = 0.0
    currency: str = "INR"
    
    # Limits and settings
    max_balance: float = 100000.0  # ₹1,00,000 max wallet balance
    min_transaction: float = 10.0  # ₹10 minimum transaction
    max_transaction: float = 50000.0  # ₹50,000 maximum single transaction
    
    # Status
    is_active: bool = True
    is_frozen: bool = False
    
    # Security
    last_transaction_at: Optional[datetime] = None
    daily_limit: float = 25000.0  # ₹25,000 daily limit
    daily_used: float = 0.0
    daily_reset_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class WalletTransaction(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    wallet_id: str
    user_id: str
    
    # Transaction details
    transaction_type: TransactionType
    amount: float
    balance_before: float
    balance_after: float
    currency: str = "INR"
    
    # Payment reference
    payment_id: Optional[str] = None
    shipment_id: Optional[str] = None
    reference_id: Optional[str] = None
    
    # Description and metadata
    description: str
    metadata: Optional[Dict[str, Any]] = {}
    
    # Status
    status: PaymentStatus = PaymentStatus.COMPLETED
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Payment(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    user_id: str
    
    # Amount and currency
    amount: float
    currency: str = "INR"
    
    # Payment details
    provider: PaymentProvider
    method: PaymentMethod
    status: PaymentStatus = PaymentStatus.PENDING
    
    # Provider-specific data
    provider_payment_id: Optional[str] = None
    provider_order_id: Optional[str] = None
    provider_signature: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = {}
    
    # Purpose and references
    purpose: str  # 'shipment', 'wallet_load', 'subscription'
    shipment_id: Optional[str] = None
    reference_id: Optional[str] = None
    
    # Customer details
    customer_email: str
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = None
    
    # Billing address
    billing_address: Optional[Dict[str, Any]] = None
    
    # Transaction details
    description: str
    notes: Optional[Dict[str, Any]] = {}
    
    # Fees and taxes
    gateway_fee: float = 0.0
    tax_amount: float = 0.0
    total_amount: float = 0.0  # amount + gateway_fee + tax_amount
    
    # Processing
    attempts: int = 0
    max_attempts: int = 3
    
    # Refund information
    refunded_amount: float = 0.0
    refund_reason: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

class PaymentCreate(BaseModel):
    amount: float
    currency: str = "INR"
    method: PaymentMethod
    purpose: str
    shipment_id: Optional[str] = None
    reference_id: Optional[str] = None
    customer_email: str
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = None
    billing_address: Optional[Dict[str, Any]] = None
    description: str
    notes: Optional[Dict[str, Any]] = {}

class PaymentResponse(BaseModel):
    id: str
    amount: float
    currency: str
    provider: PaymentProvider
    method: PaymentMethod
    status: PaymentStatus
    provider_payment_id: Optional[str]
    provider_order_id: Optional[str]
    purpose: str
    description: str
    customer_email: str
    gateway_fee: float
    total_amount: float
    created_at: datetime
    payment_url: Optional[str] = None  # For redirect-based payments
    qr_code: Optional[str] = None  # For UPI QR payments

class PaymentWebhook(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    provider: PaymentProvider
    event_type: str
    payment_id: str
    payload: Dict[str, Any]
    signature: Optional[str] = None
    processed: bool = False
    processed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

# COD Models
class CODCharge(BaseModel):
    base_charge: float = 50.0  # Base COD handling charge
    percentage_charge: float = 2.0  # Percentage of shipment value
    minimum_charge: float = 25.0  # Minimum COD charge
    maximum_charge: float = 500.0  # Maximum COD charge
    free_cod_threshold: Optional[float] = 2000.0  # Free COD above this amount
    
    def calculate_charge(self, shipment_value: float) -> float:
        """Calculate COD charge based on shipment value"""
        if self.free_cod_threshold and shipment_value >= self.free_cod_threshold:
            return 0.0
        
        percentage_amount = (shipment_value * self.percentage_charge) / 100
        total_charge = self.base_charge + percentage_amount
        
        # Apply min/max limits
        total_charge = max(self.minimum_charge, min(total_charge, self.maximum_charge))
        
        return round(total_charge, 2)

class PaymentConfig(BaseModel):
    id: str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    
    # Razorpay configuration
    razorpay_key_id: Optional[str] = None
    razorpay_key_secret: Optional[str] = None
    razorpay_webhook_secret: Optional[str] = None
    razorpay_enabled: bool = False
    
    # Stripe configuration (for future)
    stripe_publishable_key: Optional[str] = None
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    stripe_enabled: bool = False
    
    # General settings
    default_currency: str = "INR"
    gateway_fee_percentage: float = 2.5  # 2.5% gateway fee
    min_payment_amount: float = 10.0
    max_payment_amount: float = 100000.0
    
    # Wallet settings
    wallet_enabled: bool = True
    auto_wallet_deduction: bool = True
    wallet_bonus_percentage: float = 1.0  # 1% bonus on wallet loads
    
    # COD settings
    cod_enabled: bool = True
    cod_charges: CODCharge = Field(default_factory=CODCharge)
    cod_availability_zones: List[str] = []  # Postal codes where COD is available
    
    # Features
    enable_emi: bool = True
    enable_upi: bool = True
    enable_net_banking: bool = True
    enable_cards: bool = True
    
    # Security
    require_cvv: bool = True
    enable_3d_secure: bool = True
    max_payment_attempts: int = 3
    payment_timeout_minutes: int = 15
    
    # Notifications
    send_payment_confirmations: bool = True
    send_failure_notifications: bool = True
    
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class RefundRequest(BaseModel):
    payment_id: str
    amount: float
    reason: str
    notes: Optional[str] = None

class RefundResponse(BaseModel):
    id: str
    payment_id: str
    amount: float
    status: PaymentStatus
    reason: str
    provider_refund_id: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]

# Payment Breakdown Models
class PaymentBreakdown(BaseModel):
    subtotal: float
    shipping_charges: float
    cod_charges: Optional[float] = 0.0
    tax_amount: float
    discount_amount: Optional[float] = 0.0
    wallet_discount: Optional[float] = 0.0  # Bonus for using wallet
    total_amount: float
    currency: str = "INR"

class ShipmentPaymentSummary(BaseModel):
    shipment_id: str
    user_id: str
    breakdown: PaymentBreakdown
    available_methods: List[PaymentMethod]
    selected_method: Optional[PaymentMethod] = None
    wallet_balance: float
    can_use_wallet: bool
    requires_gateway: bool  # True if amount > wallet balance
    gateway_amount: float  # Amount to be paid via gateway
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PaymentAnalytics(BaseModel):
    total_transactions: int
    total_amount: float
    successful_transactions: int
    failed_transactions: int
    success_rate: float
    average_transaction_amount: float
    
    # By method
    method_breakdown: Dict[str, Dict[str, Any]]
    
    # By status
    status_breakdown: Dict[str, int]
    
    # Time-based
    daily_volume: float
    monthly_volume: float
    
    # Wallet stats
    total_wallet_balance: float
    wallet_transactions: int
    
    # Recent trends
    growth_rate: float
    popular_methods: List[str]