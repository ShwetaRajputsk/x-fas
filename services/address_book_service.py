from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from bson import ObjectId
from pymongo.errors import DuplicateKeyError
# Database connection will be passed from routes
from models.address_book import (
    SavedAddress, SavedAddressCreate, SavedAddressUpdate, 
    SavedAddressResponse, AddressBookSummary, AddressType,
    AddressCategory
)
import logging

logger = logging.getLogger(__name__)

class AddressBookService:
    def __init__(self, db):
        self.db = db
        self.collection = self.db.saved_addresses
        # Create indexes for better performance
        self._create_indexes()
    
    def _create_indexes(self):
        """Create necessary database indexes"""
        try:
            # Skip index creation in __init__ to avoid blocking
            pass
            # Indexes will be created lazily when first needed
            pass
            
        except Exception as e:
            logger.warning(f"Index creation failed: {e}")
    
    async def ensure_indexes(self):
        """Ensure database indexes are created (async version)"""
        try:
            # Compound index for user queries
            await self.collection.create_index([
                ("user_id", 1),
                ("is_active", 1),
                ("address_type", 1)
            ])
            
            # Index for default addresses
            await self.collection.create_index([
                ("user_id", 1),
                ("is_default_pickup", 1),
                ("is_active", 1)
            ])
            await self.collection.create_index([
                ("user_id", 1),
                ("is_default_delivery", 1),
                ("is_active", 1)
            ])
            
            # Index for usage statistics
            await self.collection.create_index([
                ("user_id", 1),
                ("usage_count", -1),
                ("last_used_at", -1)
            ])
            
            # Text search index
            await self.collection.create_index([
                ("label", "text"),
                ("name", "text"),
                ("company", "text"),
                ("street", "text"),
                ("city", "text"),
                ("state", "text")
            ])
            
            logger.info("Address book indexes created successfully")
            
        except Exception as e:
            logger.warning(f"Async index creation failed: {e}")
    
    async def create_address(self, user_id: str, address_data: SavedAddressCreate) -> SavedAddressResponse:
        """Create a new saved address"""
        try:
            # Create address object
            address = SavedAddress(
                user_id=user_id,
                **address_data.dict()
            )
            
            # Handle default address logic
            if address.is_default_pickup:
                await self._unset_default_addresses(user_id, "pickup")
            
            if address.is_default_delivery:
                await self._unset_default_addresses(user_id, "delivery")
            
            # Insert into database
            result = await self.collection.insert_one(address.dict())
            
            # Return created address
            created_address = await self.collection.find_one({"_id": result.inserted_id})
            return self._format_address_response(created_address)
            
        except Exception as e:
            logger.error(f"Failed to create address: {e}")
            raise Exception(f"Failed to create address: {str(e)}")
    
    async def get_user_addresses(
        self, 
        user_id: str, 
        address_type: Optional[AddressType] = None,
        category: Optional[AddressCategory] = None,
        is_active: Optional[bool] = True,
        limit: int = 50,
        offset: int = 0
    ) -> List[SavedAddressResponse]:
        """Get all addresses for a user with optional filtering"""
        
        query = {"user_id": user_id}
        
        if is_active is not None:
            query["is_active"] = is_active
        
        if address_type:
            query["address_type"] = {"$in": [address_type.value, "both"]}
        
        if category:
            query["category"] = category.value
        
        try:
            cursor = self.collection.find(query).skip(offset).limit(limit).sort("created_at", -1)
            addresses = await cursor.to_list(length=limit)
            
            return [self._format_address_response(addr) for addr in addresses]
            
        except Exception as e:
            logger.error(f"Failed to get user addresses: {e}")
            raise Exception(f"Failed to retrieve addresses: {str(e)}")
    
    async def get_address_by_id(self, user_id: str, address_id: str) -> Optional[SavedAddressResponse]:
        """Get a specific address by ID"""
        try:
            address = await self.collection.find_one({
                "id": address_id,
                "user_id": user_id,
                "is_active": True
            })
            
            if address:
                return self._format_address_response(address)
            return None
            
        except Exception as e:
            logger.error(f"Failed to get address by ID: {e}")
            raise Exception(f"Failed to retrieve address: {str(e)}")
    
    async def update_address(
        self, 
        user_id: str, 
        address_id: str, 
        update_data: SavedAddressUpdate
    ) -> Optional[SavedAddressResponse]:
        """Update an existing address"""
        try:
            # Get current address
            current_address = await self.collection.find_one({
                "id": address_id,
                "user_id": user_id,
                "is_active": True
            })
            
            if not current_address:
                return None
            
            # Prepare update data
            update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
            update_dict["updated_at"] = datetime.utcnow()
            
            # Handle default address logic
            if update_data.is_default_pickup:
                await self._unset_default_addresses(user_id, "pickup")
            
            if update_data.is_default_delivery:
                await self._unset_default_addresses(user_id, "delivery")
            
            # Update address
            result = await self.collection.update_one(
                {"id": address_id, "user_id": user_id},
                {"$set": update_dict}
            )
            
            if result.modified_count > 0:
                updated_address = await self.collection.find_one({"id": address_id})
                return self._format_address_response(updated_address)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to update address: {e}")
            raise Exception(f"Failed to update address: {str(e)}")
    
    async def delete_address(self, user_id: str, address_id: str) -> bool:
        """Soft delete an address"""
        try:
            result = await self.collection.update_one(
                {"id": address_id, "user_id": user_id},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to delete address: {e}")
            raise Exception(f"Failed to delete address: {str(e)}")
    
    async def bulk_delete_addresses(self, user_id: str, address_ids: List[str]) -> int:
        """Bulk soft delete multiple addresses"""
        try:
            result = await self.collection.update_many(
                {"id": {"$in": address_ids}, "user_id": user_id},
                {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
            )
            
            return result.modified_count
            
        except Exception as e:
            logger.error(f"Failed to bulk delete addresses: {e}")
            raise Exception(f"Failed to bulk delete addresses: {str(e)}")
    
    async def set_default_address(
        self, 
        user_id: str, 
        address_id: str, 
        address_type: AddressType
    ) -> bool:
        """Set an address as default for pickup or delivery"""
        try:
            # First, unset current default
            await self._unset_default_addresses(user_id, address_type.value)
            
            # Set new default
            update_field = f"is_default_{address_type.value}"
            result = await self.collection.update_one(
                {"id": address_id, "user_id": user_id, "is_active": True},
                {"$set": {update_field: True, "updated_at": datetime.utcnow()}}
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to set default address: {e}")
            raise Exception(f"Failed to set default address: {str(e)}")
    
    async def search_addresses(
        self, 
        user_id: str, 
        query: str,
        address_type: Optional[AddressType] = None,
        category: Optional[AddressCategory] = None,
        limit: int = 20
    ) -> List[SavedAddressResponse]:
        """Search addresses by text query"""
        try:
            search_filter = {
                "user_id": user_id,
                "is_active": True,
                "$text": {"$search": query}
            }
            
            if address_type:
                search_filter["address_type"] = {"$in": [address_type.value, "both"]}
            
            if category:
                search_filter["category"] = category.value
            
            cursor = self.collection.find(
                search_filter,
                {"score": {"$meta": "textScore"}}
            ).sort([("score", {"$meta": "textScore"})]).limit(limit)
            
            addresses = await cursor.to_list(length=limit)
            return [self._format_address_response(addr) for addr in addresses]
            
        except Exception as e:
            logger.error(f"Failed to search addresses: {e}")
            return []
    
    async def get_address_book_summary(self, user_id: str) -> AddressBookSummary:
        """Get summary statistics for user's address book"""
        try:
            # Get all active addresses
            addresses = await self.collection.find({
                "user_id": user_id,
                "is_active": True
            }).to_list(length=None)
            
            # Calculate statistics
            total_addresses = len(addresses)
            pickup_addresses = len([a for a in addresses if a["address_type"] in ["pickup", "both"]])
            delivery_addresses = len([a for a in addresses if a["address_type"] in ["delivery", "both"]])
            both_addresses = len([a for a in addresses if a["address_type"] == "both"])
            
            # Get default addresses
            default_pickup = next((a for a in addresses if a.get("is_default_pickup")), None)
            default_delivery = next((a for a in addresses if a.get("is_default_delivery")), None)
            
            # Get recently used (last 30 days, top 5)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recently_used = sorted(
                [a for a in addresses if a.get("last_used_at") and a["last_used_at"] > thirty_days_ago],
                key=lambda x: x.get("last_used_at", datetime.min),
                reverse=True
            )[:5]
            
            # Get most used (top 5 by usage_count)
            most_used = sorted(
                [a for a in addresses if a.get("usage_count", 0) > 0],
                key=lambda x: x.get("usage_count", 0),
                reverse=True
            )[:5]
            
            return AddressBookSummary(
                total_addresses=total_addresses,
                pickup_addresses=pickup_addresses,
                delivery_addresses=delivery_addresses,
                both_addresses=both_addresses,
                default_pickup=self._format_address_response(default_pickup) if default_pickup else None,
                default_delivery=self._format_address_response(default_delivery) if default_delivery else None,
                recently_used=[self._format_address_response(a) for a in recently_used],
                most_used=[self._format_address_response(a) for a in most_used]
            )
            
        except Exception as e:
            logger.error(f"Failed to get address book summary: {e}")
            raise Exception(f"Failed to get summary: {str(e)}")
    
    async def increment_usage(self, user_id: str, address_id: str) -> bool:
        """Increment usage count and update last used timestamp"""
        try:
            result = await self.collection.update_one(
                {"id": address_id, "user_id": user_id, "is_active": True},
                {
                    "$inc": {"usage_count": 1},
                    "$set": {"last_used_at": datetime.utcnow()}
                }
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            logger.error(f"Failed to increment usage: {e}")
            return False
    
    async def get_default_addresses(self, user_id: str) -> Dict[str, Optional[SavedAddressResponse]]:
        """Get default pickup and delivery addresses"""
        try:
            addresses = await self.collection.find({
                "user_id": user_id,
                "is_active": True,
                "$or": [{"is_default_pickup": True}, {"is_default_delivery": True}]
            }).to_list(length=2)
            
            default_pickup = None
            default_delivery = None
            
            for addr in addresses:
                if addr.get("is_default_pickup"):
                    default_pickup = self._format_address_response(addr)
                if addr.get("is_default_delivery"):
                    default_delivery = self._format_address_response(addr)
            
            return {
                "pickup": default_pickup,
                "delivery": default_delivery
            }
            
        except Exception as e:
            logger.error(f"Failed to get default addresses: {e}")
            return {"pickup": None, "delivery": None}
    
    async def import_addresses(
        self, 
        user_id: str, 
        addresses: List[SavedAddressCreate],
        skip_duplicates: bool = True
    ) -> Dict[str, Any]:
        """Import multiple addresses with duplicate handling"""
        try:
            created_count = 0
            skipped_count = 0
            errors = []
            
            for addr_data in addresses:
                try:
                    # Check for duplicates if required
                    if skip_duplicates:
                        existing = await self.collection.find_one({
                            "user_id": user_id,
                            "phone": addr_data.phone,
                            "street": addr_data.street,
                            "postal_code": addr_data.postal_code,
                            "is_active": True
                        })
                        
                        if existing:
                            skipped_count += 1
                            continue
                    
                    # Create address
                    await self.create_address(user_id, addr_data)
                    created_count += 1
                    
                except Exception as e:
                    errors.append(f"Failed to import address '{addr_data.label}': {str(e)}")
            
            return {
                "created_count": created_count,
                "skipped_count": skipped_count,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Failed to import addresses: {e}")
            raise Exception(f"Failed to import addresses: {str(e)}")
    
    async def export_addresses(self, user_id: str) -> List[SavedAddressResponse]:
        """Export all active addresses for a user"""
        try:
            addresses = await self.collection.find({
                "user_id": user_id,
                "is_active": True
            }).sort("created_at", 1).to_list(length=None)
            
            return [self._format_address_response(addr) for addr in addresses]
            
        except Exception as e:
            logger.error(f"Failed to export addresses: {e}")
            raise Exception(f"Failed to export addresses: {str(e)}")
    
    async def _unset_default_addresses(self, user_id: str, address_type: str):
        """Unset current default addresses of specified type"""
        field_name = f"is_default_{address_type}"
        await self.collection.update_many(
            {"user_id": user_id, field_name: True},
            {"$set": {field_name: False}}
        )
    
    def _format_address_response(self, address_doc: dict) -> SavedAddressResponse:
        """Convert database document to response model"""
        if not address_doc:
            return None
        
        # Remove MongoDB _id field and ensure all required fields exist
        address_doc.pop("_id", None)
        
        return SavedAddressResponse(**address_doc)

# Service will be instantiated per request with database dependency
