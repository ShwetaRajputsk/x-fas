from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime

from models.shipment import (
    Shipment, ShipmentCreate, ShipmentResponse, ShipmentStatus, 
    PaymentInfo, PaymentStatus, CarrierInfo, TrackingEvent
)
from models.user import User
from services.carrier_service import CarrierService
from services.payment_service import PaymentService
from utils.auth import get_current_user, get_optional_current_user

# Database dependency
async def get_database() -> AsyncIOMotorDatabase:
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    return client[os.environ.get('DB_NAME', 'xfas_logistics')]

router = APIRouter(prefix="/shipments", tags=["Shipments"])

@router.post("/", response_model=ShipmentResponse)
async def create_shipment(
    shipment_data: ShipmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new shipment."""
    
    try:
        # Create carrier service
        carrier_service = CarrierService()
        
        # Calculate shipping cost (get from quote or calculate)
        shipping_cost = await _calculate_shipping_cost(shipment_data, db)
        
        # Create payment info
        payment_info = PaymentInfo(
            amount=shipping_cost,
            status=PaymentStatus.PENDING
        )
        
        # Create carrier info
        carrier_info = CarrierInfo(
            carrier_name=shipment_data.carrier_name,
            service_type=shipment_data.service_type
        )
        
        # Create initial tracking event
        initial_event = TrackingEvent(
            timestamp=datetime.utcnow(),
            status="Created",
            location="XFas Logistics Hub",
            description="Shipment created and awaiting payment"
        )
        
        # Create shipment
        shipment = Shipment(
            user_id=current_user.id,
            quote_id=shipment_data.quote_id,
            sender=shipment_data.sender,
            recipient=shipment_data.recipient,
            package_info=shipment_data.package_info,
            carrier_info=carrier_info,
            payment_info=payment_info,
            insurance_required=shipment_data.insurance_required,
            signature_required=shipment_data.signature_required,
            notes=shipment_data.notes,
            custom_reference=shipment_data.custom_reference,
            tracking_events=[initial_event]
        )
        
        # Save to database
        await db.shipments.insert_one(shipment.dict())
        
        # Convert to response
        response = ShipmentResponse(
            id=shipment.id,
            shipment_number=shipment.shipment_number,
            status=shipment.status,
            sender=shipment.sender,
            recipient=shipment.recipient,
            package_info=shipment.package_info,
            carrier_info=shipment.carrier_info,
            payment_info=shipment.payment_info,
            tracking_events=shipment.tracking_events,
            created_at=shipment.created_at,
            estimated_delivery=carrier_info.estimated_delivery
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating shipment: {str(e)}"
        )

@router.get("/", response_model=List[ShipmentResponse])
async def get_user_shipments(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    status: Optional[ShipmentStatus] = None,
    limit: int = 20,
    skip: int = 0
):
    """Get user's shipments."""
    
    # Build query
    query = {"user_id": current_user.id}
    if status:
        query["status"] = status
    
    # Find shipments
    shipments_cursor = db.shipments.find(query).sort("created_at", -1).limit(limit).skip(skip)
    shipments_data = await shipments_cursor.to_list(length=limit)
    
    # Convert to response objects
    responses = []
    for shipment_data in shipments_data:
        shipment = Shipment(**shipment_data)
        response = ShipmentResponse(
            id=shipment.id,
            shipment_number=shipment.shipment_number,
            status=shipment.status,
            sender=shipment.sender,
            recipient=shipment.recipient,
            package_info=shipment.package_info,
            carrier_info=shipment.carrier_info,
            payment_info=shipment.payment_info,
            tracking_events=shipment.tracking_events,
            created_at=shipment.created_at,
            estimated_delivery=shipment.carrier_info.estimated_delivery
        )
        responses.append(response)
    
    return responses

@router.get("/{shipment_id}", response_model=ShipmentResponse)
async def get_shipment(
    shipment_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get shipment details."""
    
    # Find shipment
    shipment_data = await db.shipments.find_one({"id": shipment_id})
    if not shipment_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found"
        )
    
    shipment = Shipment(**shipment_data)
    
    # Check access (shipment owner or public tracking)
    if current_user and shipment.user_id != current_user.id:
        # For public tracking, only show limited info
        pass
    
    response = ShipmentResponse(
        id=shipment.id,
        shipment_number=shipment.shipment_number,
        status=shipment.status,
        sender=shipment.sender,
        recipient=shipment.recipient,
        package_info=shipment.package_info,
        carrier_info=shipment.carrier_info,
        payment_info=shipment.payment_info,
        tracking_events=shipment.tracking_events,
        created_at=shipment.created_at,
        estimated_delivery=shipment.carrier_info.estimated_delivery
    )
    
    return response

@router.get("/track/{tracking_number}")
async def track_shipment(
    tracking_number: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Track shipment by tracking number (public endpoint)."""
    
    # Find by shipment number or carrier tracking number
    shipment_data = await db.shipments.find_one({
        "$or": [
            {"shipment_number": tracking_number},
            {"carrier_info.tracking_number": tracking_number}
        ]
    })
    
    if not shipment_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracking number not found"
        )
    
    shipment = Shipment(**shipment_data)
    
    # Return public tracking info
    return {
        "shipment_number": shipment.shipment_number,
        "status": shipment.status,
        "tracking_events": shipment.tracking_events,
        "estimated_delivery": shipment.carrier_info.estimated_delivery,
        "carrier": shipment.carrier_info.carrier_name
    }

@router.post("/{shipment_id}/pay")
async def initiate_payment(
    shipment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Initiate payment for a shipment."""
    
    # Find shipment
    shipment_data = await db.shipments.find_one({"id": shipment_id})
    if not shipment_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shipment not found"
        )
    
    shipment = Shipment(**shipment_data)
    
    # Check ownership
    if shipment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Check if already paid
    if shipment.payment_info.status == PaymentStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shipment already paid"
        )
    
    # Create payment order
    payment_service = PaymentService()
    payment_order = await payment_service.create_payment_order(
        amount=shipment.payment_info.amount,
        order_id=shipment.id
    )
    
    return payment_order

async def _calculate_shipping_cost(shipment_data: ShipmentCreate, db: AsyncIOMotorDatabase) -> float:
    """Calculate shipping cost based on shipment data."""
    
    if shipment_data.quote_id:
        # Get cost from existing quote
        quote_data = await db.quotes.find_one({"id": shipment_data.quote_id})
        if quote_data:
            # Find matching carrier quote
            for carrier_quote in quote_data.get("carrier_quotes", []):
                if carrier_quote["carrier_name"] == shipment_data.carrier_name:
                    return carrier_quote["total_cost"]
    
    # Default calculation if no quote found
    base_cost = 200.0
    
    # Add insurance cost
    if shipment_data.insurance_required:
        insurance_cost = shipment_data.package_info.declared_value * 0.01
        base_cost += insurance_cost
    
    # Add signature cost
    if shipment_data.signature_required:
        base_cost += 50.0
    
    return base_cost