from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime

from models.user import User
from models.dashboard import (
    SavedAddress, SavedAddressCreate, SavedAddressUpdate,
    UserPreferences, UserPreferencesUpdate,
    DashboardData, DashboardStats, AddressBookEntry, AddressBookCreate, AddressBookUpdate
)
from services.dashboard_service import DashboardService
from utils.auth import get_current_user

# Database dependency
async def get_database() -> AsyncIOMotorDatabase:
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    return client[os.environ.get('DB_NAME', 'xfas_logistics')]

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# ===== DASHBOARD OVERVIEW =====

@router.get("/", response_model=DashboardData)
async def get_dashboard_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get comprehensive dashboard data for user."""
    
    try:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Getting dashboard data for user: {current_user.id}")
        
        dashboard_service = DashboardService()
        
        # Get individual components with error handling
        try:
            stats = await dashboard_service.get_dashboard_stats(current_user.id, db)
            logger.info("Stats retrieved successfully")
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            stats = DashboardStats()
        
        try:
            monthly_trends = await dashboard_service.get_monthly_trends(current_user.id, 6, db)
            logger.info("Monthly trends retrieved successfully")
        except Exception as e:
            logger.error(f"Error getting monthly trends: {e}")
            monthly_trends = []
        
        try:
            carrier_performance = await dashboard_service.get_carrier_performance(current_user.id, db)
            logger.info("Carrier performance retrieved successfully")
        except Exception as e:
            logger.error(f"Error getting carrier performance: {e}")
            carrier_performance = []
        
        try:
            recent_activities = await dashboard_service.get_recent_activities(current_user.id, 10, db)
            logger.info("Recent activities retrieved successfully")
        except Exception as e:
            logger.error(f"Error getting recent activities: {e}")
            recent_activities = []
        
        # Create simple data that won't cause serialization issues
        quick_actions = [
            {"title": "Ship Now", "description": "Create a new shipment", "action": "create_shipment", "icon": "package"},
            {"title": "Get Quote", "description": "Compare shipping rates", "action": "get_quote", "icon": "calculator"},
            {"title": "Track Package", "description": "Track your shipments", "action": "track_shipment", "icon": "search"},
            {"title": "Address Book", "description": "Manage saved addresses", "action": "manage_addresses", "icon": "address-book"}
        ]
        
        notifications = [
            {"type": "info", "message": "Welcome to XFas Logistics dashboard!", "timestamp": datetime.utcnow().isoformat()},
            {"type": "success", "message": "Dashboard loaded successfully", "timestamp": datetime.utcnow().isoformat()}
        ]
        
        dashboard_data = DashboardData(
            stats=stats,
            monthly_trends=monthly_trends,
            carrier_performance=carrier_performance,
            recent_activities=recent_activities,
            quick_actions=quick_actions,
            notifications=notifications
        )
        
        logger.info(f"Dashboard data retrieved successfully for user: {current_user.id}")
        return dashboard_data
        
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting dashboard data for user {current_user.id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting dashboard data: {str(e)}"
        )

@router.get("/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get dashboard statistics only."""
    
    try:
        dashboard_service = DashboardService()
        stats = await dashboard_service.get_dashboard_stats(current_user.id, db)
        
        return {"success": True, "data": stats}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting dashboard stats: {str(e)}"
        )

@router.get("/trends")
async def get_monthly_trends(
    months: int = Query(6, ge=1, le=24),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get monthly shipment trends."""
    
    try:
        dashboard_service = DashboardService()
        trends = await dashboard_service.get_monthly_trends(current_user.id, months, db)
        
        return {"success": True, "data": trends}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting trends: {str(e)}"
        )

@router.get("/carrier-performance")
async def get_carrier_performance(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get carrier performance metrics."""
    
    try:
        dashboard_service = DashboardService()
        performance = await dashboard_service.get_carrier_performance(current_user.id, db)
        
        return {"success": True, "data": performance}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting carrier performance: {str(e)}"
        )

@router.get("/activities")
async def get_recent_activities(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get recent user activities."""
    
    try:
        dashboard_service = DashboardService()
        activities = await dashboard_service.get_recent_activities(current_user.id, limit, db)
        
        return {"success": True, "data": activities}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting activities: {str(e)}"
        )

# ===== SAVED ADDRESSES =====

@router.post("/addresses", response_model=SavedAddress)
async def create_saved_address(
    address_data: SavedAddressCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new saved address."""
    
    try:
        dashboard_service = DashboardService()
        address = await dashboard_service.create_saved_address(address_data, current_user.id, db)
        
        return address
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating saved address: {str(e)}"
        )

@router.get("/addresses", response_model=List[SavedAddress])
async def get_saved_addresses(
    address_type: Optional[str] = Query(None, description="Filter by address type"),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's saved addresses."""
    
    try:
        dashboard_service = DashboardService()
        addresses = await dashboard_service.get_saved_addresses(current_user.id, address_type, db)
        
        return addresses
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting saved addresses: {str(e)}"
        )

@router.put("/addresses/{address_id}", response_model=SavedAddress)
async def update_saved_address(
    address_id: str,
    update_data: SavedAddressUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update a saved address."""
    
    try:
        dashboard_service = DashboardService()
        address = await dashboard_service.update_saved_address(address_id, current_user.id, update_data, db)
        
        if not address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved address not found"
            )
        
        return address
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating saved address: {str(e)}"
        )

@router.delete("/addresses/{address_id}")
async def delete_saved_address(
    address_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete a saved address."""
    
    try:
        dashboard_service = DashboardService()
        deleted = await dashboard_service.delete_saved_address(address_id, current_user.id, db)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved address not found"
            )
        
        return {"success": True, "message": "Address deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting saved address: {str(e)}"
        )

# ===== USER PREFERENCES =====

@router.get("/preferences", response_model=UserPreferences)
async def get_user_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user preferences."""
    
    try:
        dashboard_service = DashboardService()
        preferences = await dashboard_service.get_user_preferences(current_user.id, db)
        
        return preferences
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting user preferences: {str(e)}"
        )

@router.put("/preferences", response_model=UserPreferences)
async def update_user_preferences(
    update_data: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update user preferences."""
    
    try:
        dashboard_service = DashboardService()
        preferences = await dashboard_service.update_user_preferences(current_user.id, update_data, db)
        
        return preferences
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user preferences: {str(e)}"
        )

# ===== ADDRESS BOOK =====

@router.post("/address-book", response_model=AddressBookEntry)
async def create_address_book_entry(
    entry_data: AddressBookCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new address book entry."""
    
    try:
        dashboard_service = DashboardService()
        entry = await dashboard_service.create_address_book_entry(entry_data, current_user.id, db)
        
        return entry
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating address book entry: {str(e)}"
        )

@router.get("/address-book", response_model=List[AddressBookEntry])
async def get_address_book(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's address book."""
    
    try:
        dashboard_service = DashboardService()
        entries = await dashboard_service.get_address_book(current_user.id, db)
        
        return entries
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting address book: {str(e)}"
        )

@router.put("/address-book/{entry_id}", response_model=AddressBookEntry)
async def update_address_book_entry(
    entry_id: str,
    update_data: AddressBookUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update an address book entry."""
    
    try:
        dashboard_service = DashboardService()
        entry = await dashboard_service.update_address_book_entry(entry_id, current_user.id, update_data, db)
        
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address book entry not found"
            )
        
        return entry
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating address book entry: {str(e)}"
        )

@router.delete("/address-book/{entry_id}")
async def delete_address_book_entry(
    entry_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete an address book entry."""
    
    try:
        dashboard_service = DashboardService()
        deleted = await dashboard_service.delete_address_book_entry(entry_id, current_user.id, db)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address book entry not found"
            )
        
        return {"success": True, "message": "Address book entry deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting address book entry: {str(e)}"
        )