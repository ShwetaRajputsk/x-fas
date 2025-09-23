from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.user import User
from models.admin import (
    CarrierRate, CarrierRateCreate, CarrierRateUpdate,
    AdminDashboardData, UserManagement, BookingManagement,
    SystemAlert
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
    # For now, allow all authenticated users to access admin endpoints
    # In production, implement proper role-based access control
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive"
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update a carrier rate."""
    
    try:
        admin_service = AdminService()
        rate = await admin_service.update_carrier_rate(rate_id, update_data, current_user.id, db)
        
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
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
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
    alert_type: str,
    title: str,
    message: str,
    component: str,
    severity: int = 1,
    current_user: User = Depends(get_current_user),
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
    current_user: User = Depends(get_current_user),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Resolve a system alert."""
    
    try:
        admin_service = AdminService()
        resolved = await admin_service.resolve_system_alert(alert_id, current_user.id, db)
        
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
    current_user: User = Depends(get_current_user),
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
    is_active: bool,
    current_user: User = Depends(get_current_user),
    admin_user: User = Depends(check_admin_role),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update user active status."""
    
    try:
        admin_service = AdminService()
        updated = await admin_service.update_user_status(user_id, is_active, current_user.id, db)
        
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
    current_user: User = Depends(get_current_user),
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