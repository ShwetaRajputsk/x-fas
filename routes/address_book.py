from fastapi import APIRouter, HTTPException, Depends, Query, status
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.address_book import (
    SavedAddressCreate, SavedAddressUpdate, SavedAddressResponse,
    AddressBookSummary, BulkDeleteRequest, SetDefaultRequest,
    AddressSearchRequest, AddressImportRequest, AddressExportResponse,
    AddressType, AddressCategory
)
from services.address_book_service import AddressBookService
from utils.auth import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/address-book", tags=["Address Book"])

# Database dependency
async def get_database() -> AsyncIOMotorDatabase:
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    return client[os.environ.get('DB_NAME', 'xfas_logistics')]

# Helper to get address book service
def get_address_book_service(db: AsyncIOMotorDatabase) -> AddressBookService:
    return AddressBookService(db)

@router.post("/addresses", response_model=SavedAddressResponse)
async def create_saved_address(
    address_data: SavedAddressCreate,
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a new saved address"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        address = await service.create_address(user_id, address_data)
        return address
    except Exception as e:
        logger.error(f"Failed to create address for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/addresses", response_model=List[SavedAddressResponse])
async def get_user_addresses(
    address_type: Optional[AddressType] = None,
    category: Optional[AddressCategory] = None,
    is_active: Optional[bool] = True,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get all addresses for the current user"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        addresses = await service.get_user_addresses(
            user_id=user_id,
            address_type=address_type,
            category=category,
            is_active=is_active,
            limit=limit,
            offset=offset
        )
        return addresses
    except Exception as e:
        logger.error(f"Failed to get addresses for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve addresses"
        )

@router.get("/addresses/{address_id}", response_model=SavedAddressResponse)
async def get_address_by_id(
    address_id: str,
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a specific address by ID"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        address = await service.get_address_by_id(user_id, address_id)
        
        if not address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found"
            )
        
        return address
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get address {address_id} for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve address"
        )

@router.put("/addresses/{address_id}", response_model=SavedAddressResponse)
async def update_address(
    address_id: str,
    update_data: SavedAddressUpdate,
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Update an existing address"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        address = await service.update_address(user_id, address_id, update_data)
        
        if not address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found"
            )
        
        return address
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update address {address_id} for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/addresses/{address_id}")
async def delete_address(
    address_id: str,
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete (soft delete) an address"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        success = await service.delete_address(user_id, address_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found"
            )
        
        return {"message": "Address deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete address {address_id} for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete address"
        )

@router.post("/addresses/bulk-delete")
async def bulk_delete_addresses(
    request: BulkDeleteRequest,
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Bulk delete multiple addresses"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        deleted_count = await service.bulk_delete_addresses(user_id, request.address_ids)
        
        return {
            "message": f"Successfully deleted {deleted_count} address(es)",
            "deleted_count": deleted_count
        }
    except Exception as e:
        logger.error(f"Failed to bulk delete addresses for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete addresses"
        )

@router.post("/addresses/{address_id}/set-default")
async def set_default_address(
    address_id: str,
    request: SetDefaultRequest,
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Set an address as default for pickup or delivery"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        success = await service.set_default_address(
            user_id, address_id, request.address_type
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found"
            )
        
        return {"message": f"Address set as default {request.address_type.value}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set default address {address_id} for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set default address"
        )

@router.get("/addresses/search", response_model=List[SavedAddressResponse])
async def search_addresses(
    query: str = Query(..., min_length=1),
    address_type: Optional[AddressType] = None,
    category: Optional[AddressCategory] = None,
    limit: int = Query(20, ge=1, le=50),
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Search addresses by text query"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        addresses = await service.search_addresses(
            user_id=user_id,
            query=query,
            address_type=address_type,
            category=category,
            limit=limit
        )
        return addresses
    except Exception as e:
        logger.error(f"Failed to search addresses for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed"
        )

@router.get("/summary", response_model=AddressBookSummary)
async def get_address_book_summary(
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get address book summary with statistics"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        summary = await service.get_address_book_summary(user_id)
        return summary
    except Exception as e:
        logger.error(f"Failed to get address book summary for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get summary"
        )

@router.get("/defaults")
async def get_default_addresses(
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get default pickup and delivery addresses"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        defaults = await service.get_default_addresses(user_id)
        return defaults
    except Exception as e:
        logger.error(f"Failed to get default addresses for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get default addresses"
        )

@router.post("/addresses/{address_id}/use")
async def mark_address_used(
    address_id: str,
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Mark an address as used (increment usage statistics)"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        success = await service.increment_usage(user_id, address_id)
        
        if success:
            return {"message": "Usage recorded"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Address not found"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to mark address {address_id} as used for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update usage"
        )

@router.post("/import")
async def import_addresses(
    import_request: AddressImportRequest,
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Import multiple addresses from a list"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        result = await service.import_addresses(
            user_id=user_id,
            addresses=import_request.addresses,
            skip_duplicates=import_request.skip_duplicates
        )
        
        return {
            "message": "Import completed",
            **result
        }
    except Exception as e:
        logger.error(f"Failed to import addresses for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/export", response_model=AddressExportResponse)
async def export_addresses(
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Export all user addresses"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        addresses = await service.export_addresses(user_id)
        
        return AddressExportResponse(
            addresses=addresses,
            total_count=len(addresses)
        )
    except Exception as e:
        logger.error(f"Failed to export addresses for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Export failed"
        )

# Additional utility endpoints

@router.get("/addresses/pickup/default", response_model=Optional[SavedAddressResponse])
async def get_default_pickup_address(
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get the default pickup address"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        defaults = await service.get_default_addresses(user_id)
        return defaults["pickup"]
    except Exception as e:
        logger.error(f"Failed to get default pickup address for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get default pickup address"
        )

@router.get("/addresses/delivery/default", response_model=Optional[SavedAddressResponse])
async def get_default_delivery_address(
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get the default delivery address"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        defaults = await service.get_default_addresses(user_id)
        return defaults["delivery"]
    except Exception as e:
        logger.error(f"Failed to get default delivery address for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get default delivery address"
        )

@router.get("/addresses/recent", response_model=List[SavedAddressResponse])
async def get_recent_addresses(
    limit: int = Query(10, ge=1, le=20),
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get recently used addresses"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        summary = await service.get_address_book_summary(user_id)
        return summary.recently_used[:limit]
    except Exception as e:
        logger.error(f"Failed to get recent addresses for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get recent addresses"
        )

@router.get("/addresses/frequent", response_model=List[SavedAddressResponse])
async def get_frequent_addresses(
    limit: int = Query(10, ge=1, le=20),
    current_user = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get frequently used addresses"""
    try:
        user_id = current_user.id
        service = get_address_book_service(db)
        summary = await service.get_address_book_summary(user_id)
        return summary.most_used[:limit]
    except Exception as e:
        logger.error(f"Failed to get frequent addresses for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get frequent addresses"
        )