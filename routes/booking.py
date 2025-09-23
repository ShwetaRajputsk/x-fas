from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.shipment import ShipmentCreate, ShipmentResponse, ShipmentUpdate, ShipmentStatus
from models.user import User
from models.quote import CarrierQuote
from services.booking_service import BookingService
from utils.auth import get_current_user

# Database dependency
async def get_database() -> AsyncIOMotorDatabase:
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    return client[os.environ.get('DB_NAME', 'xfas_logistics')]

router = APIRouter(prefix="/bookings", tags=["Bookings"])

@router.post("/", response_model=ShipmentResponse)
async def create_booking(
    booking_request: ShipmentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new shipment booking."""
    
    try:
        booking_service = BookingService()
        
        # If quote_id provided, get the quote and selected carrier info
        carrier_quote = None
        if booking_request.quote_id:
            quote_data = await db.quotes.find_one({"id": booking_request.quote_id})
            if quote_data:
                # Find the selected carrier quote
                for cq in quote_data.get("carrier_quotes", []):
                    if cq["carrier_name"] == booking_request.carrier_name:
                        carrier_quote = CarrierQuote(**cq)
                        break
        
        # Create the booking
        shipment = await booking_service.create_booking(
            booking_request, 
            current_user.id, 
            carrier_quote
        )
        
        # Save to database
        await db.shipments.insert_one(shipment.dict())
        
        # Mark quote as used if provided
        if booking_request.quote_id:
            await db.quotes.update_one(
                {"id": booking_request.quote_id},
                {
                    "$set": {
                        "status": "used",
                        "selected_carrier": booking_request.carrier_name,
                        "used_at": shipment.created_at
                    }
                }
            )
        
        # Process response
        response = booking_service.process_shipment_response(shipment)
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating booking: {str(e)}"
        )

@router.get("/", response_model=List[ShipmentResponse])
async def get_user_bookings(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    limit: int = 20,
    skip: int = 0,
    status_filter: Optional[ShipmentStatus] = None
):
    """Get user's booking history."""
    
    # Build query
    query = {"user_id": current_user.id}
    if status_filter:
        query["status"] = status_filter
    
    # Find user's shipments
    shipments_cursor = db.shipments.find(query).sort("created_at", -1).limit(limit).skip(skip)
    shipments_data = await shipments_cursor.to_list(length=limit)
    
    # Convert to response format
    booking_service = BookingService()
    responses = []
    
    for shipment_data in shipments_data:
        from models.shipment import Shipment
        shipment = Shipment(**shipment_data)
        response = booking_service.process_shipment_response(shipment)
        responses.append(response)
    
    return responses

@router.get("/{booking_id}", response_model=ShipmentResponse)
async def get_booking(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a specific booking by ID."""
    
    # Find shipment
    shipment_data = await db.shipments.find_one({"id": booking_id})
    if not shipment_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    from models.shipment import Shipment
    shipment = Shipment(**shipment_data)
    
    # Check ownership
    if shipment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Process and return response
    booking_service = BookingService()
    response = booking_service.process_shipment_response(shipment)
    
    return response

@router.get("/track/{awb}", response_model=ShipmentResponse)
async def track_shipment(
    awb: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Track shipment by AWB/tracking number (public endpoint)."""
    
    # Find shipment by tracking number
    shipment_data = await db.shipments.find_one({"carrier_info.tracking_number": awb})
    if not shipment_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracking number not found"
        )
    
    from models.shipment import Shipment
    shipment = Shipment(**shipment_data)
    
    # Process and return response
    booking_service = BookingService()
    response = booking_service.process_shipment_response(shipment)
    
    return response

@router.put("/{booking_id}", response_model=ShipmentResponse)
async def update_booking(
    booking_id: str,
    update_request: ShipmentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update a booking (limited fields)."""
    
    # Find shipment
    shipment_data = await db.shipments.find_one({"id": booking_id})
    if not shipment_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    from models.shipment import Shipment
    shipment = Shipment(**shipment_data)
    
    # Check ownership
    if shipment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Apply updates
    update_data = {}
    if update_request.notes is not None:
        update_data["notes"] = update_request.notes
    if update_request.tracking_number is not None:
        update_data["carrier_info.tracking_number"] = update_request.tracking_number
    
    # Update in database
    if update_data:
        update_data["updated_at"] = shipment.updated_at
        await db.shipments.update_one(
            {"id": booking_id},
            {"$set": update_data}
        )
        
        # Refresh from database
        shipment_data = await db.shipments.find_one({"id": booking_id})
        shipment = Shipment(**shipment_data)
    
    # Process and return response
    booking_service = BookingService()
    response = booking_service.process_shipment_response(shipment)
    
    return response

@router.delete("/{booking_id}")
async def cancel_booking(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Cancel a booking."""
    
    # Find shipment
    shipment_data = await db.shipments.find_one({"id": booking_id})
    if not shipment_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    from models.shipment import Shipment
    shipment = Shipment(**shipment_data)
    
    # Check ownership
    if shipment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Check if cancellation is allowed
    if shipment.status in [ShipmentStatus.DELIVERED, ShipmentStatus.CANCELLED, ShipmentStatus.RETURNED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel shipment with status: {shipment.status}"
        )
    
    # Update status to cancelled
    booking_service = BookingService()
    updated_shipment = await booking_service.update_shipment_status(
        shipment,
        ShipmentStatus.CANCELLED,
        location="XFas Logistics Hub",
        description="Shipment cancelled by customer"
    )
    
    # Save to database
    await db.shipments.update_one(
        {"id": booking_id},
        {"$set": updated_shipment.dict()}
    )
    
    return {"message": "Booking cancelled successfully"}

@router.post("/{booking_id}/simulate-progress")
async def simulate_booking_progress(
    booking_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Simulate booking progress for demo purposes."""
    
    # Find shipment
    shipment_data = await db.shipments.find_one({"id": booking_id})
    if not shipment_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Booking not found"
        )
    
    from models.shipment import Shipment
    shipment = Shipment(**shipment_data)
    
    # Check ownership
    if shipment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Simulate progress
    booking_service = BookingService()
    updated_shipment = await booking_service.simulate_shipment_progress(shipment)
    
    # Save to database
    await db.shipments.update_one(
        {"id": booking_id},
        {"$set": updated_shipment.dict()}
    )
    
    # Return updated response
    response = booking_service.process_shipment_response(updated_shipment)
    return response