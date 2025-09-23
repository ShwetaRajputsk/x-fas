from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.user import User
from models.admin import (
    CarrierRate, CarrierRateCreate, CarrierRateUpdate,
    AdminDashboardData, UserManagement, BookingManagement,
    SystemAlert, KYCDocument, GSTInfo, CustomerKYC, KYCStatus,
    TrackingEvent, AutoTrackingConfig, BulkOperation
)
from services.admin_service import AdminService
from utils.auth import get_current_user

# Database dependency
async def get_database() -> AsyncIOMotorDatabase:
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    return client[os.environ.get('DB_NAME', 'xfas_logistics')]

router = APIRouter(prefix="/admin", tags=["Admin"])

def check_admin_role(current_user: User = Depends(get_current_user)):
    """Check if user has admin privileges."""
    from models.user import UserRole
    
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive"
        )
    
    # Check if user has admin role
    if not hasattr(current_user, 'role'):
        current_user.role = UserRole.USER  # Default for existing users
    
    # Support both lowercase and uppercase role values
    admin_roles = [
        UserRole.ADMIN, UserRole.SUPER_ADMIN, UserRole.MANAGER,
        UserRole.ADMIN_UPPER, UserRole.SUPER_ADMIN_UPPER, UserRole.MANAGER_UPPER,
        "ADMIN", "SUPER_ADMIN", "MANAGER"  # Direct string comparison as fallback
    ]
    
    if current_user.role not in admin_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user

def check_super_admin_role(current_user: User = Depends(get_current_user)):
    """Check if user has super admin privileges."""
    from models.user import UserRole
    
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive"
        )
    
    if not hasattr(current_user, 'role'):
        current_user.role = UserRole.USER
    
    # Support both lowercase and uppercase super admin role values
    super_admin_roles = [
        UserRole.SUPER_ADMIN, 
        UserRole.SUPER_ADMIN_UPPER,
        "SUPER_ADMIN"  # Direct string comparison as fallback
    ]
    
    if current_user.role not in super_admin_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required"
        )
    
    return current_user

# ===== ADMIN DASHBOARD =====

@router.get("/dashboard", response_model=AdminDashboardData)
async def get_admin_dashboard(
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get comprehensive admin dashboard data."""
    
    try:
        admin_service = AdminService()
        dashboard_data = await admin_service.get_admin_dashboard_data(db)
        
        return dashboard_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting admin dashboard data: {str(e)}"
        )

@router.get("/stats")
async def get_admin_stats(
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get admin statistics only."""
    
    try:
        admin_service = AdminService()
        stats = await admin_service.get_admin_stats(db)
        
        return {"success": True, "data": stats}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting admin stats: {str(e)}"
        )

@router.get("/revenue-breakdown")
async def get_revenue_breakdown(
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get revenue breakdown by carrier."""
    
    try:
        admin_service = AdminService()
        breakdown = await admin_service.get_revenue_breakdown(db)
        
        return {"success": True, "data": breakdown}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting revenue breakdown: {str(e)}"
        )

@router.get("/user-growth")
async def get_user_growth_data(
    months: int = Query(6, ge=1, le=24),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user growth data."""
    
    try:
        admin_service = AdminService()
        growth_data = await admin_service.get_user_growth_data(months, db)
        
        return {"success": True, "data": growth_data}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting user growth data: {str(e)}"
        )

@router.get("/carrier-analytics")
async def get_carrier_analytics(
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get carrier analytics."""
    
    try:
        admin_service = AdminService()
        analytics = await admin_service.get_carrier_analytics(db)
        
        return {"success": True, "data": analytics}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting carrier analytics: {str(e)}"
        )

# ===== CARRIER RATE MANAGEMENT =====

@router.post("/carrier-rates", response_model=CarrierRate)
async def create_carrier_rate(
    rate_data: CarrierRateCreate,
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new carrier rate."""
    
    try:
        admin_service = AdminService()
        rate = await admin_service.create_carrier_rate(rate_data, admin_user.id, db)
        
        return rate
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating carrier rate: {str(e)}"
        )

@router.get("/carrier-rates", response_model=List[CarrierRate])
async def get_carrier_rates(
    carrier_name: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get carrier rates with optional filtering."""
    
    try:
        admin_service = AdminService()
        rates = await admin_service.get_carrier_rates(carrier_name, is_active, db)
        
        return rates
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting carrier rates: {str(e)}"
        )

@router.put("/carrier-rates/{rate_id}", response_model=CarrierRate)
async def update_carrier_rate(
    rate_id: str,
    update_data: CarrierRateUpdate,
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update a carrier rate."""
    
    try:
        admin_service = AdminService()
        rate = await admin_service.update_carrier_rate(rate_id, update_data, admin_user.id, db)
        
        if not rate:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carrier rate not found"
            )
        
        return rate
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating carrier rate: {str(e)}"
        )

@router.delete("/carrier-rates/{rate_id}")
async def delete_carrier_rate(
    rate_id: str,
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete (deactivate) a carrier rate."""
    
    try:
        admin_service = AdminService()
        deleted = await admin_service.delete_carrier_rate(rate_id, db)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Carrier rate not found"
            )
        
        return {"success": True, "message": "Carrier rate deactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting carrier rate: {str(e)}"
        )

# ===== SYSTEM ALERTS =====

@router.get("/alerts", response_model=List[SystemAlert])
async def get_system_alerts(
    limit: int = Query(50, ge=1, le=200),
    resolved: Optional[bool] = Query(None),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get system alerts."""
    
    try:
        admin_service = AdminService()
        alerts = await admin_service.get_system_alerts(limit, resolved, db)
        
        return alerts
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting system alerts: {str(e)}"
        )

@router.post("/alerts")
async def create_system_alert(
    alert_type: str = Query(...),
    title: str = Query(...),
    message: str = Query(...),
    component: str = Query(...),
    severity: int = Query(1),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new system alert."""
    
    try:
        admin_service = AdminService()
        alert = await admin_service.create_system_alert(alert_type, title, message, component, severity, db)
        
        return {"success": True, "data": alert}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating system alert: {str(e)}"
        )

@router.put("/alerts/{alert_id}/resolve")
async def resolve_system_alert(
    alert_id: str,
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Resolve a system alert."""
    
    try:
        admin_service = AdminService()
        resolved = await admin_service.resolve_system_alert(alert_id, admin_user.id, db)
        
        if not resolved:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="System alert not found"
            )
        
        return {"success": True, "message": "Alert resolved successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error resolving system alert: {str(e)}"
        )

# ===== USER MANAGEMENT =====

@router.get("/users")
async def get_users_management(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get users for management with search and pagination."""
    
    try:
        admin_service = AdminService()
        users, total_count = await admin_service.get_users_management(limit, skip, search, db)
        
        return {
            "success": True,
            "data": {
                "users": users,
                "total_count": total_count,
                "page_info": {
                    "limit": limit,
                    "skip": skip,
                    "has_more": total_count > (skip + limit)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting users: {str(e)}"
        )

@router.put("/users/{user_id}/status")
async def update_user_status(
    user_id: str,
    is_active: bool = Query(...),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update user active status."""
    
    try:
        admin_service = AdminService()
        updated = await admin_service.update_user_status(user_id, is_active, admin_user.id, db)
        
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        status_text = "activated" if is_active else "deactivated"
        return {"success": True, "message": f"User {status_text} successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user status: {str(e)}"
        )

# ===== BOOKING MANAGEMENT =====

@router.get("/bookings")
async def get_bookings_management(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get bookings for management with filters and pagination."""
    
    try:
        admin_service = AdminService()
        bookings, total_count = await admin_service.get_bookings_management(limit, skip, status_filter, search, db)
        
        return {
            "success": True,
            "data": {
                "bookings": bookings,
                "total_count": total_count,
                "page_info": {
                    "limit": limit,
                    "skip": skip,
                    "has_more": total_count > (skip + limit)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting bookings: {str(e)}"
        )

@router.put("/bookings/{booking_id}/status")
async def update_booking_status(
    booking_id: str,
    new_status: str = Query(...),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update booking/shipment status."""
    
    try:
        from models.shipment import ShipmentStatus
        
        # Validate status
        valid_statuses = [status.value for status in ShipmentStatus]
        if new_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status. Valid options: {valid_statuses}"
            )
        
        result = await db.shipments.update_one(
            {"id": booking_id},
            {
                "$set": {
                    "status": new_status,
                    "updated_at": datetime.utcnow().isoformat(),
                    "updated_by": admin_user.id
                }
            }
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found"
            )
        
        return {"success": True, "message": f"Booking status updated to {new_status}"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating booking status: {str(e)}"
        )

# ===== KYC MANAGEMENT =====

@router.get("/kyc")
async def get_kyc_documents(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get KYC documents for review."""
    
    try:
        query = {}
        if status_filter:
            query["status"] = status_filter
        if user_id:
            query["user_id"] = user_id
        
        cursor = db.kyc_documents.find(query).sort("uploaded_at", -1).skip(skip).limit(limit)
        kyc_docs = await cursor.to_list(length=limit)
        total_count = await db.kyc_documents.count_documents(query)
        
        # Convert to response format
        for doc in kyc_docs:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
        
        return {
            "success": True,
            "data": {
                "documents": kyc_docs,
                "total_count": total_count,
                "page_info": {
                    "limit": limit,
                    "skip": skip,
                    "has_more": total_count > (skip + limit)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting KYC documents: {str(e)}"
        )

@router.put("/kyc/{document_id}/verify")
async def verify_kyc_document(
    document_id: str,
    status: KYCStatus = Query(...),
    rejection_reason: Optional[str] = Query(None),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Verify or reject a KYC document."""
    
    try:
        update_data = {
            "status": status.value,
            "verified_at": datetime.utcnow(),
            "verified_by": admin_user.id
        }
        
        if status == KYCStatus.REJECTED and rejection_reason:
            update_data["rejection_reason"] = rejection_reason
        
        result = await db.kyc_documents.update_one(
            {"id": document_id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="KYC document not found"
            )
        
        return {"success": True, "message": f"KYC document {status.value}"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying KYC document: {str(e)}"
        )

@router.get("/gst")
async def get_gst_info(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get GST information for verification."""
    
    try:
        query = {}
        if status_filter:
            query["status"] = status_filter
        
        cursor = db.gst_info.find(query).sort("created_at", -1).skip(skip).limit(limit)
        gst_docs = await cursor.to_list(length=limit)
        total_count = await db.gst_info.count_documents(query)
        
        # Convert to response format
        for doc in gst_docs:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
        
        return {
            "success": True,
            "data": {
                "gst_info": gst_docs,
                "total_count": total_count,
                "page_info": {
                    "limit": limit,
                    "skip": skip,
                    "has_more": total_count > (skip + limit)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting GST information: {str(e)}"
        )

@router.put("/gst/{gst_id}/verify")
async def verify_gst_info(
    gst_id: str,
    status: KYCStatus = Query(...),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Verify GST information."""
    
    try:
        result = await db.gst_info.update_one(
            {"id": gst_id},
            {
                "$set": {
                    "status": status.value,
                    "verified_at": datetime.utcnow(),
                    "verified_by": admin_user.id
                }
            }
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="GST information not found"
            )
        
        return {"success": True, "message": f"GST information {status.value}"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying GST information: {str(e)}"
        )

# ===== TRACKING MANAGEMENT =====

@router.get("/tracking/events/{shipment_id}")
async def get_tracking_events(
    shipment_id: str,
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get tracking events for a shipment."""
    
    try:
        cursor = db.tracking_events.find({"shipment_id": shipment_id}).sort("event_time", -1)
        events = await cursor.to_list(length=100)
        
        # Convert to response format
        for event in events:
            if '_id' in event:
                event['_id'] = str(event['_id'])
        
        return {"success": True, "data": {"events": events}}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting tracking events: {str(e)}"
        )

@router.post("/tracking/sync")
async def sync_tracking_updates(
    carrier_name: Optional[str] = Query(None),
    admin_user: User = Depends(check_super_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Manually trigger tracking sync for carriers."""
    
    try:
        # This would integrate with actual carrier APIs
        # For now, return a placeholder response
        from services.tracking_service import TrackingService
        
        tracking_service = TrackingService()
        result = await tracking_service.sync_all_carriers(db, carrier_name)
        
        return {
            "success": True,
            "message": "Tracking sync initiated",
            "data": result
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error syncing tracking updates: {str(e)}"
        )

@router.get("/tracking/config")
async def get_tracking_configs(
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get auto-tracking configurations."""
    
    try:
        cursor = db.auto_tracking_configs.find({}).sort("carrier_name", 1)
        configs = await cursor.to_list(length=100)
        
        # Convert to response format
        for config in configs:
            if '_id' in config:
                config['_id'] = str(config['_id'])
        
        return {"success": True, "data": {"configs": configs}}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting tracking configs: {str(e)}"
        )

# ===== ANALYTICS AND REPORTING =====

@router.get("/analytics/daily-bookings")
async def get_daily_bookings_report(
    days: int = Query(30, ge=1, le=365),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get daily bookings report for the specified number of days."""
    
    try:
        from datetime import datetime, timedelta
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        pipeline = [
            {
                "$match": {
                    "created_at": {
                        "$gte": start_date.isoformat(),
                        "$lte": end_date.isoformat()
                    }
                }
            },
            {
                "$addFields": {
                    "created_date": {"$dateFromString": {"dateString": "$created_at"}}
                }
            },
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$created_date"},
                        "month": {"$month": "$created_date"},
                        "day": {"$dayOfMonth": "$created_date"}
                    },
                    "bookings_count": {"$sum": 1},
                    "total_revenue": {"$sum": "$payment_info.amount"},
                    "avg_value": {"$avg": "$payment_info.amount"}
                }
            },
            {
                "$sort": {"_id.year": 1, "_id.month": 1, "_id.day": 1}
            }
        ]
        
        cursor = db.shipments.aggregate(pipeline)
        daily_data = await cursor.to_list(length=days)
        
        # Format response
        report = []
        for data in daily_data:
            date_obj = datetime(data["_id"]["year"], data["_id"]["month"], data["_id"]["day"])
            report.append({
                "date": date_obj.strftime("%Y-%m-%d"),
                "bookings_count": data["bookings_count"],
                "total_revenue": round(data["total_revenue"], 2),
                "average_value": round(data["avg_value"], 2)
            })
        
        return {"success": True, "data": {"daily_report": report}}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating daily bookings report: {str(e)}"
        )

@router.get("/analytics/courier-usage")
async def get_courier_usage_report(
    days: int = Query(30, ge=1, le=365),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get courier usage breakdown report."""
    
    try:
        from datetime import datetime, timedelta
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        pipeline = [
            {
                "$match": {
                    "created_at": {
                        "$gte": start_date.isoformat(),
                        "$lte": end_date.isoformat()
                    }
                }
            },
            {
                "$group": {
                    "_id": "$carrier_info.carrier_name",
                    "total_shipments": {"$sum": 1},
                    "total_revenue": {"$sum": "$payment_info.amount"},
                    "avg_delivery_time": {"$avg": 3.5},  # Placeholder
                    "success_rate": {"$avg": 0.95},  # Placeholder
                    "delivered_count": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", "delivered"]}, 1, 0]
                        }
                    }
                }
            },
            {"$sort": {"total_shipments": -1}}
        ]
        
        cursor = db.shipments.aggregate(pipeline)
        usage_data = await cursor.to_list(length=50)
        
        # Calculate percentages
        total_shipments = sum(item["total_shipments"] for item in usage_data)
        total_revenue = sum(item["total_revenue"] for item in usage_data)
        
        report = []
        for data in usage_data:
            if not data["_id"]:
                continue
                
            report.append({
                "carrier_name": data["_id"],
                "total_shipments": data["total_shipments"],
                "shipment_percentage": round((data["total_shipments"] / total_shipments) * 100, 2) if total_shipments > 0 else 0,
                "total_revenue": round(data["total_revenue"], 2),
                "revenue_percentage": round((data["total_revenue"] / total_revenue) * 100, 2) if total_revenue > 0 else 0,
                "avg_delivery_time": round(data["avg_delivery_time"], 1),
                "success_rate": round(data["success_rate"] * 100, 2),
                "delivered_count": data["delivered_count"]
            })
        
        return {"success": True, "data": {"courier_usage": report}}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating courier usage report: {str(e)}"
        )

@router.get("/analytics/revenue-report")
async def get_revenue_report(
    period: str = Query("monthly", regex="^(daily|weekly|monthly|yearly)$"),
    months: int = Query(12, ge=1, le=60),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get comprehensive revenue report."""
    
    try:
        from datetime import datetime, timedelta
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=months * 30)
        
        # Group by period
        group_by = {}
        if period == "daily":
            group_by = {
                "year": {"$year": "$created_date"},
                "month": {"$month": "$created_date"},
                "day": {"$dayOfMonth": "$created_date"}
            }
        elif period == "weekly":
            group_by = {
                "year": {"$year": "$created_date"},
                "week": {"$week": "$created_date"}
            }
        elif period == "monthly":
            group_by = {
                "year": {"$year": "$created_date"},
                "month": {"$month": "$created_date"}
            }
        else:  # yearly
            group_by = {"year": {"$year": "$created_date"}}
        
        pipeline = [
            {
                "$match": {
                    "created_at": {
                        "$gte": start_date.isoformat(),
                        "$lte": end_date.isoformat()
                    },
                    "payment_info.amount": {"$gt": 0}
                }
            },
            {
                "$addFields": {
                    "created_date": {"$dateFromString": {"dateString": "$created_at"}}
                }
            },
            {
                "$group": {
                    "_id": group_by,
                    "total_revenue": {"$sum": "$payment_info.amount"},
                    "shipment_count": {"$sum": 1},
                    "avg_order_value": {"$avg": "$payment_info.amount"},
                    "carriers": {
                        "$addToSet": "$carrier_info.carrier_name"
                    }
                }
            },
            {
                "$sort": {"_id.year": 1, "_id.month": 1, "_id.week": 1, "_id.day": 1}
            }
        ]
        
        cursor = db.shipments.aggregate(pipeline)
        revenue_data = await cursor.to_list(length=months * 31)
        
        # Format response
        report = []
        for data in revenue_data:
            period_label = ""
            if period == "daily":
                period_label = f"{data['_id']['year']}-{data['_id']['month']:02d}-{data['_id']['day']:02d}"
            elif period == "weekly":
                period_label = f"{data['_id']['year']}-W{data['_id']['week']:02d}"
            elif period == "monthly":
                period_label = f"{data['_id']['year']}-{data['_id']['month']:02d}"
            else:
                period_label = str(data['_id']['year'])
            
            report.append({
                "period": period_label,
                "total_revenue": round(data["total_revenue"], 2),
                "shipment_count": data["shipment_count"],
                "avg_order_value": round(data["avg_order_value"], 2),
                "active_carriers": len(data["carriers"])
            })
        
        # Calculate summary statistics
        total_revenue = sum(item["total_revenue"] for item in report)
        total_shipments = sum(item["shipment_count"] for item in report)
        
        summary = {
            "total_revenue": round(total_revenue, 2),
            "total_shipments": total_shipments,
            "average_order_value": round(total_revenue / total_shipments, 2) if total_shipments > 0 else 0,
            "periods_count": len(report)
        }
        
        return {
            "success": True,
            "data": {
                "revenue_report": report,
                "summary": summary,
                "period_type": period
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating revenue report: {str(e)}"
        )

@router.get("/analytics/user-insights")
async def get_user_insights(
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user behavior insights and segmentation."""
    
    try:
        # User segmentation pipeline
        pipeline = [
            {
                "$lookup": {
                    "from": "shipments",
                    "localField": "id",
                    "foreignField": "user_id",
                    "as": "shipments"
                }
            },
            {
                "$addFields": {
                    "total_shipments": {"$size": "$shipments"},
                    "total_spent": {"$sum": "$shipments.payment_info.amount"},
                    "avg_order_value": {"$avg": "$shipments.payment_info.amount"}
                }
            },
            {
                "$group": {
                    "_id": {
                        "$switch": {
                            "branches": [
                                {"case": {"$eq": ["$total_shipments", 0]}, "then": "inactive"},
                                {"case": {"$lte": ["$total_shipments", 1]}, "then": "new"},
                                {"case": {"$lte": ["$total_shipments", 5]}, "then": "occasional"},
                                {"case": {"$lte": ["$total_shipments", 20]}, "then": "regular"},
                                {"case": {"$gt": ["$total_shipments", 20]}, "then": "power_user"}
                            ],
                            "default": "unknown"
                        }
                    },
                    "user_count": {"$sum": 1},
                    "avg_shipments": {"$avg": "$total_shipments"},
                    "avg_spent": {"$avg": "$total_spent"}
                }
            }
        ]
        
        cursor = db.users.aggregate(pipeline)
        segmentation_data = await cursor.to_list(length=10)
        
        # Get user type distribution
        user_types_cursor = db.users.aggregate([
            {"$group": {
                "_id": "$user_type",
                "count": {"$sum": 1}
            }}
        ])
        user_types_data = await user_types_cursor.to_list(length=10)
        
        # Get verification status distribution
        verification_cursor = db.users.aggregate([
            {"$group": {
                "_id": {
                    "email_verified": "$is_email_verified",
                    "phone_verified": "$is_phone_verified"
                },
                "count": {"$sum": 1}
            }}
        ])
        verification_data = await verification_cursor.to_list(length=10)
        
        return {
            "success": True,
            "data": {
                "user_segmentation": segmentation_data,
                "user_types": user_types_data,
                "verification_status": verification_data
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating user insights: {str(e)}"
        )
