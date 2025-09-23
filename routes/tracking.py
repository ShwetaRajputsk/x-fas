from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from models.user import User
from services.tracking_service import TrackingService
from utils.auth import get_optional_current_user, get_current_user

# Request/Response models
class BulkTrackingRequest(BaseModel):
    awb_numbers: List[str]

class TrackingResponse(BaseModel):
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class NotificationSetupRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    notification_types: List[str] = ['email', 'sms']

class CarrierSyncRequest(BaseModel):
    carrier_name: Optional[str] = None

# Database dependency
async def get_database() -> AsyncIOMotorDatabase:
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    return client[os.environ.get('DB_NAME', 'xfas_logistics')]

router = APIRouter(prefix="/tracking", tags=["Tracking"])


@router.get("/awb/{awb}")
async def track_single_awb(
    awb: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Track a single shipment by AWB number (public endpoint)."""
    
    try:
        tracking_service = TrackingService()
        
        # Validate AWB format
        if not tracking_service.validate_awb_format(awb):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid AWB format"
            )
        
        # Find shipment by AWB
        shipment_data = await db.shipments.find_one({"carrier_info.tracking_number": awb.upper()})
        
        if not shipment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tracking number not found"
            )
        
        from models.shipment import Shipment
        shipment = Shipment(**shipment_data)
        
        # Get enhanced tracking info
        tracking_info = tracking_service.get_enhanced_tracking_info(shipment)
        
        return TrackingResponse(
            success=True,
            data=tracking_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error tracking shipment: {str(e)}"
        )

@router.post("/bulk")
async def track_multiple_awbs(
    request: BulkTrackingRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Track multiple shipments by AWB numbers (public endpoint)."""
    
    try:
        if not request.awb_numbers:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one AWB number is required"
            )
        
        if len(request.awb_numbers) > 50:  # Limit bulk tracking to 50 AWBs
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 50 AWB numbers allowed per request"
            )
        
        tracking_service = TrackingService()
        
        # Track multiple AWBs
        results = await tracking_service.track_multiple_awbs(request.awb_numbers, db)
        
        return TrackingResponse(
            success=True,
            data=results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error tracking shipments: {str(e)}"
        )

@router.get("/search")
async def search_shipments(
    q: str = Query(..., description="Search query (AWB, shipment number, or reference)"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Search shipments by various criteria."""
    
    try:
        # Build search query
        search_conditions = []
        
        # Search by AWB
        search_conditions.append({"carrier_info.tracking_number": {"$regex": q, "$options": "i"}})
        
        # Search by shipment number
        search_conditions.append({"shipment_number": {"$regex": q, "$options": "i"}})
        
        # Search by custom reference
        search_conditions.append({"custom_reference": {"$regex": q, "$options": "i"}})
        
        # Search by sender/recipient names
        search_conditions.append({"sender.name": {"$regex": q, "$options": "i"}})
        search_conditions.append({"recipient.name": {"$regex": q, "$options": "i"}})
        
        query = {"$or": search_conditions}
        
        # If user is authenticated, show only their shipments, otherwise show public shipments
        if current_user:
            query["user_id"] = current_user.id
        
        # Execute search
        shipments_cursor = db.shipments.find(query).sort("created_at", -1).limit(limit).skip(offset)
        shipments_data = await shipments_cursor.to_list(length=limit)
        
        # Get total count
        total_count = await db.shipments.count_documents(query)
        
        # Process results
        tracking_service = TrackingService()
        results = []
        
        for shipment_data in shipments_data:
            from models.shipment import Shipment
            shipment = Shipment(**shipment_data)
            tracking_info = tracking_service.get_enhanced_tracking_info(shipment)
            results.append(tracking_info)
        
        return {
            "success": True,
            "data": {
                "results": results,
                "total_count": total_count,
                "page_info": {
                    "limit": limit,
                    "offset": offset,
                    "has_more": total_count > (offset + limit)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error searching shipments: {str(e)}"
        )

@router.get("/analytics")
async def get_tracking_analytics(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get tracking analytics for authenticated user."""
    
    try:
        tracking_service = TrackingService()
        analytics = await tracking_service.get_tracking_analytics(current_user.id, db)
        
        return TrackingResponse(
            success=True,
            data=analytics
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting analytics: {str(e)}"
        )

@router.get("/validate-awb/{awb}")
async def validate_awb_format(awb: str):
    """Validate AWB format (public endpoint)."""
    
    try:
        tracking_service = TrackingService()
        is_valid = tracking_service.validate_awb_format(awb)
        
        return {
            "success": True,
            "data": {
                "awb": awb,
                "is_valid": is_valid,
                "format_info": {
                    "length": len(awb),
                    "pattern": "Valid AWB format" if is_valid else "Invalid AWB format",
                    "expected_formats": [
                        "XF + 10 digits (XFas)",
                        "FX + 10 digits (FedEx)",
                        "DH + 10 digits (DHL)",
                        "AR + 10 digits (Aramex)",
                        "UP + 10 digits (UPS)",
                        "10-15 digits (Generic)"
                    ]
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error validating AWB: {str(e)}"
        )

@router.get("/status-distribution")
async def get_status_distribution(
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get shipment status distribution (public endpoint, filtered by user if authenticated)."""
    
    try:
        query = {}
        if current_user:
            query["user_id"] = current_user.id
        
        # Aggregate status distribution
        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        
        cursor = db.shipments.aggregate(pipeline)
        status_data = await cursor.to_list(length=50)
        
        # Format response
        distribution = {}
        total_count = 0
        
        for item in status_data:
            status = item["_id"]
            count = item["count"]
            distribution[status] = count
            total_count += count
        
        # Calculate percentages
        distribution_with_percentages = {}
        for status, count in distribution.items():
            distribution_with_percentages[status] = {
                "count": count,
                "percentage": round((count / total_count) * 100, 2) if total_count > 0 else 0
            }
        
        return {
            "success": True,
            "data": {
                "total_shipments": total_count,
                "distribution": distribution_with_percentages
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting status distribution: {str(e)}"
        )

@router.post("/notify/{awb}")
async def setup_tracking_notifications(
    awb: str,
    notification_request: NotificationSetupRequest,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Setup tracking notifications for a shipment (public endpoint)."""
    
    try:
        # Find shipment
        shipment_data = await db.shipments.find_one({"carrier_info.tracking_number": awb.upper()})
        
        if not shipment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tracking number not found"
            )
        
        from services.notification_service import NotificationService
        notification_service = NotificationService()
        
        # Setup notifications
        result = await notification_service.setup_tracking_notifications(
            shipment_id=shipment_data["id"],
            email=notification_request.email,
            phone=notification_request.phone,
            notification_types=notification_request.notification_types,
            db=db
        )
        
        return {
            "success": True,
            "data": {
                "message": "Notifications setup successfully",
                "notification_id": result["notification_id"],
                "awb": awb,
                "email": notification_request.email,
                "phone": notification_request.phone,
                "types": notification_request.notification_types
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error setting up notifications: {str(e)}"
        )

@router.get("/real-time/{awb}")
async def get_real_time_updates(
    awb: str,
    last_update: Optional[str] = Query(None, description="ISO timestamp of last known update"),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get real-time updates for a shipment (public endpoint)."""
    
    try:
        # Find shipment
        shipment_data = await db.shipments.find_one({"carrier_info.tracking_number": awb.upper()})
        
        if not shipment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tracking number not found"
            )
        
        from models.shipment import Shipment
        shipment = Shipment(**shipment_data)
        
        # Check if there are new updates
        has_updates = False
        if last_update:
            from datetime import datetime
            last_update_dt = datetime.fromisoformat(last_update.replace('Z', '+00:00'))
            has_updates = shipment.updated_at > last_update_dt
        else:
            has_updates = True
        
        tracking_service = TrackingService()
        
        response_data = {
            "awb": awb,
            "has_updates": has_updates,
            "last_checked": datetime.utcnow().isoformat(),
            "shipment_data": None
        }
        
        if has_updates:
            response_data["shipment_data"] = tracking_service.get_enhanced_tracking_info(shipment)
        
        return {
            "success": True,
            "data": response_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting real-time updates: {str(e)}"
        )

@router.post("/carrier-sync")
async def sync_carrier_data(
    sync_request: CarrierSyncRequest = None,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Sync tracking data from carrier APIs (admin endpoint - public for demo)."""
    
    try:
        tracking_service = TrackingService()
        
        carrier_name = None
        if sync_request and sync_request.carrier_name:
            carrier_name = sync_request.carrier_name
        
        # Sync carrier data
        result = await tracking_service.sync_all_carriers(db, carrier_name)
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error syncing carrier data: {str(e)}"
        )

class NotificationSetupRequest(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    notification_types: List[str] = ['email', 'sms']

class CarrierSyncRequest(BaseModel):
    carrier_name: Optional[str] = None
