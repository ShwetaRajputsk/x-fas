from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.dashboard import (
    SavedAddress, SavedAddressCreate, SavedAddressUpdate,
    UserPreferences, UserPreferencesUpdate,
    DashboardStats, MonthlyTrend, CarrierPerformance, RecentActivity, DashboardData,
    AddressBookEntry, AddressBookCreate, AddressBookUpdate
)
from models.shipment import ShipmentStatus
from models.user import User, Address, PaymentMethod

class DashboardService:
    def __init__(self):
        pass
    
    def _parse_datetime(self, dt_value):
        """Helper method to parse datetime that handles both string and datetime objects."""
        if dt_value is None:
            return datetime(1970, 1, 1)  # Default fallback date
        
        if isinstance(dt_value, datetime):
            return dt_value
        
        if isinstance(dt_value, str):
            try:
                return datetime.fromisoformat(dt_value)
            except ValueError:
                return datetime(1970, 1, 1)
        
        return datetime(1970, 1, 1)
    
    # ===== SAVED ADDRESSES =====
    
    async def create_saved_address(self, address_data: SavedAddressCreate, user_id: str, db: AsyncIOMotorDatabase) -> SavedAddress:
        """Create a new saved address."""
        
        # If this is set as default, update other addresses
        if address_data.is_default:
            await db.saved_addresses.update_many(
                {"user_id": user_id, "address_type": address_data.address_type},
                {"$set": {"is_default": False}}
            )
        
        saved_address = SavedAddress(
            user_id=user_id,
            **address_data.dict()
        )
        
        await db.saved_addresses.insert_one(saved_address.dict())
        return saved_address
    
    async def get_saved_addresses(self, user_id: str, address_type: Optional[str], db: AsyncIOMotorDatabase) -> List[SavedAddress]:
        """Get user's saved addresses."""
        
        query = {"user_id": user_id}
        if address_type:
            query["address_type"] = {"$in": [address_type, "both"]}
        
        cursor = db.saved_addresses.find(query).sort("created_at", -1)
        addresses_data = await cursor.to_list(length=100)
        
        return [SavedAddress(**addr) for addr in addresses_data]
    
    async def update_saved_address(self, address_id: str, user_id: str, update_data: SavedAddressUpdate, db: AsyncIOMotorDatabase) -> Optional[SavedAddress]:
        """Update a saved address."""
        
        # Check ownership
        existing = await db.saved_addresses.find_one({"id": address_id, "user_id": user_id})
        if not existing:
            return None
        
        # If setting as default, update other addresses
        if update_data.is_default:
            await db.saved_addresses.update_many(
                {"user_id": user_id, "address_type": existing["address_type"], "id": {"$ne": address_id}},
                {"$set": {"is_default": False}}
            )
        
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        update_dict["updated_at"] = datetime.utcnow()
        
        result = await db.saved_addresses.update_one(
            {"id": address_id, "user_id": user_id},
            {"$set": update_dict}
        )
        
        if result.modified_count:
            updated_data = await db.saved_addresses.find_one({"id": address_id})
            return SavedAddress(**updated_data)
        
        return None
    
    async def delete_saved_address(self, address_id: str, user_id: str, db: AsyncIOMotorDatabase) -> bool:
        """Delete a saved address."""
        
        result = await db.saved_addresses.delete_one({"id": address_id, "user_id": user_id})
        return result.deleted_count > 0
    
    # ===== USER PREFERENCES =====
    
    async def get_user_preferences(self, user_id: str, db: AsyncIOMotorDatabase) -> UserPreferences:
        """Get user preferences, create default if not exists."""
        
        prefs_data = await db.user_preferences.find_one({"user_id": user_id})
        
        if prefs_data:
            return UserPreferences(**prefs_data)
        else:
            # Create default preferences
            default_prefs = UserPreferences(user_id=user_id)
            await db.user_preferences.insert_one(default_prefs.dict())
            return default_prefs
    
    async def update_user_preferences(self, user_id: str, update_data: UserPreferencesUpdate, db: AsyncIOMotorDatabase) -> UserPreferences:
        """Update user preferences."""
        
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        update_dict["updated_at"] = datetime.utcnow()
        
        await db.user_preferences.update_one(
            {"user_id": user_id},
            {"$set": update_dict},
            upsert=True
        )
        
        return await self.get_user_preferences(user_id, db)
    
    # ===== DASHBOARD STATISTICS =====
    
    async def get_dashboard_stats(self, user_id: str, db: AsyncIOMotorDatabase) -> DashboardStats:
        """Calculate comprehensive dashboard statistics for user."""
        
        # Get all user shipments
        shipments_cursor = db.shipments.find({"user_id": user_id})
        shipments_data = await shipments_cursor.to_list(length=10000)
        
        if not shipments_data:
            return DashboardStats()
        
        stats = DashboardStats()
        
        # Basic counts
        stats.total_shipments = len(shipments_data)
        
        # Status-based counts
        status_counts = {}
        total_cost = 0
        delivered_shipments = []
        carrier_usage = {}
        
        for shipment in shipments_data:
            status = shipment.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Financial calculations
            payment_info = shipment.get("payment_info", {})
            if payment_info.get("amount"):
                total_cost += payment_info["amount"]
            
            # Carrier usage
            carrier = shipment.get("carrier_info", {}).get("carrier_name", "Unknown")
            carrier_usage[carrier] = carrier_usage.get(carrier, 0) + 1
            
            # Delivered shipments for performance metrics
            if status == ShipmentStatus.DELIVERED:
                delivered_shipments.append(shipment)
        
        # Set status counts
        stats.delivered_shipments = status_counts.get(ShipmentStatus.DELIVERED, 0)
        stats.active_shipments = sum(status_counts.get(status, 0) for status in [
            ShipmentStatus.BOOKED, ShipmentStatus.PICKUP_SCHEDULED, 
            ShipmentStatus.PICKED_UP, ShipmentStatus.IN_TRANSIT, 
            ShipmentStatus.OUT_FOR_DELIVERY
        ])
        stats.pending_shipments = status_counts.get(ShipmentStatus.BOOKED, 0)
        stats.cancelled_shipments = status_counts.get(ShipmentStatus.CANCELLED, 0)
        
        # Financial metrics
        stats.total_spent = total_cost
        stats.average_shipment_cost = total_cost / len(shipments_data) if shipments_data else 0
        
        # Calculate this month's spending
        current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        this_month_cost = sum(
            shipment.get("payment_info", {}).get("amount", 0)
            for shipment in shipments_data
            if self._parse_datetime(shipment.get("created_at")) >= current_month
        )
        stats.this_month_spent = this_month_cost
        
        # Performance metrics
        if delivered_shipments:
            # Calculate delivery performance
            on_time_count = 0
            total_delivery_days = 0
            
            for shipment in delivered_shipments:
                created_at = self._parse_datetime(shipment.get("created_at"))
                delivered_at = shipment.get("delivery_date")
                estimated_delivery = shipment.get("carrier_info", {}).get("estimated_delivery")
                
                if delivered_at and estimated_delivery:
                    delivered_dt = self._parse_datetime(delivered_at)
                    estimated_dt = self._parse_datetime(estimated_delivery)
                    
                    if delivered_dt <= estimated_dt:
                        on_time_count += 1
                    
                    delivery_days = (delivered_dt - created_at).days
                    total_delivery_days += delivery_days
            
            stats.on_time_delivery_rate = (on_time_count / len(delivered_shipments)) * 100
            stats.average_delivery_time = total_delivery_days / len(delivered_shipments)
        
        stats.success_rate = (stats.delivered_shipments / stats.total_shipments) * 100 if stats.total_shipments else 0
        
        # Carrier statistics
        stats.carrier_distribution = carrier_usage
        if carrier_usage:
            stats.favorite_carrier = max(carrier_usage, key=carrier_usage.get)
        
        # Recent activity
        if shipments_data:
            latest_shipment = max(shipments_data, key=lambda x: self._parse_datetime(x.get("created_at")))
            stats.last_shipment_date = self._parse_datetime(latest_shipment.get("created_at"))
        
        # Time-based counts
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        stats.shipments_this_week = sum(
            1 for shipment in shipments_data
            if self._parse_datetime(shipment.get("created_at")) >= week_ago
        )
        
        stats.shipments_this_month = sum(
            1 for shipment in shipments_data
            if self._parse_datetime(shipment.get("created_at")) >= month_ago
        )
        
        return stats
    
    async def get_monthly_trends(self, user_id: str, months: int, db: AsyncIOMotorDatabase) -> List[MonthlyTrend]:
        """Get monthly shipment trends."""
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=months * 30)
        
        # Aggregate monthly data
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "created_at": {
                        "$gte": start_date,
                        "$lte": end_date
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$created_at"},
                        "month": {"$month": "$created_at"}
                    },
                    "shipment_count": {"$sum": 1},
                    "total_cost": {"$sum": "$payment_info.amount"},
                    "delivered_count": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", ShipmentStatus.DELIVERED]}, 1, 0]
                        }
                    }
                }
            },
            {"$sort": {"_id.year": 1, "_id.month": 1}}
        ]
        
        cursor = db.shipments.aggregate(pipeline)
        monthly_data = await cursor.to_list(length=months)
        
        trends = []
        for data in monthly_data:
            month_names = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            
            trends.append(MonthlyTrend(
                month=month_names[data["_id"]["month"]],
                year=data["_id"]["year"],
                shipment_count=data["shipment_count"],
                total_cost=data["total_cost"] or 0,
                delivered_count=data["delivered_count"],
                average_delivery_time=3.5  # Mock data for now
            ))
        
        return trends
    
    async def get_carrier_performance(self, user_id: str, db: AsyncIOMotorDatabase) -> List[CarrierPerformance]:
        """Get carrier performance metrics."""
        
        # Aggregate carrier performance data
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": "$carrier_info.carrier_name",
                    "total_shipments": {"$sum": 1},
                    "delivered_shipments": {
                        "$sum": {
                            "$cond": [{"$eq": ["$status", ShipmentStatus.DELIVERED]}, 1, 0]
                        }
                    },
                    "total_cost": {"$sum": "$payment_info.amount"}
                }
            }
        ]
        
        cursor = db.shipments.aggregate(pipeline)
        carrier_data = await cursor.to_list(length=50)
        
        performance_list = []
        for data in carrier_data:
            if not data["_id"]:  # Skip null carrier names
                continue
                
            performance = CarrierPerformance(
                carrier_name=data["_id"],
                total_shipments=data["total_shipments"],
                delivered_shipments=data["delivered_shipments"],
                average_cost=data["total_cost"] / data["total_shipments"] if data["total_shipments"] else 0,
                average_delivery_time=3.2,  # Mock data
                on_time_rate=92.5,  # Mock data
                success_rate=(data["delivered_shipments"] / data["total_shipments"]) * 100 if data["total_shipments"] else 0
            )
            performance_list.append(performance)
        
        return sorted(performance_list, key=lambda x: x.total_shipments, reverse=True)
    
    async def get_recent_activities(self, user_id: str, limit: int, db: AsyncIOMotorDatabase) -> List[RecentActivity]:
        """Get recent user activities."""
        
        activities = []
        
        # Get recent shipments
        recent_shipments = await db.shipments.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(limit).to_list(length=limit)
        
        for shipment in recent_shipments:
            # Shipment created activity
            activities.append(RecentActivity(
                activity_type="shipment_created",
                description=f"Created shipment to {shipment.get('recipient', {}).get('city', 'Unknown')}",
                shipment_id=shipment.get("id"),
                awb=shipment.get("carrier_info", {}).get("tracking_number"),
                timestamp=self._parse_datetime(shipment.get("created_at")),
                metadata={
                    "carrier": shipment.get("carrier_info", {}).get("carrier_name"),
                    "cost": shipment.get("payment_info", {}).get("amount")
                }
            ))
            
            # Status update activities
            tracking_events = shipment.get("tracking_events", [])
            for event in tracking_events[-2:]:  # Last 2 events per shipment
                activities.append(RecentActivity(
                    activity_type="status_update",
                    description=f"Shipment {event.get('status', 'updated')} at {event.get('location', 'Unknown')}",
                    shipment_id=shipment.get("id"),
                    awb=shipment.get("carrier_info", {}).get("tracking_number"),
                    timestamp=self._parse_datetime(event.get("timestamp")),
                    metadata={"location": event.get("location"), "description": event.get("description")}
                ))
        
        # Sort by timestamp and limit
        activities.sort(key=lambda x: x.timestamp, reverse=True)
        return activities[:limit]
    
    async def get_dashboard_data(self, user_id: str, db: AsyncIOMotorDatabase) -> DashboardData:
        """Get comprehensive dashboard data."""
        
        stats = await self.get_dashboard_stats(user_id, db)
        monthly_trends = await self.get_monthly_trends(user_id, 6, db)
        carrier_performance = await self.get_carrier_performance(user_id, db)
        recent_activities = await self.get_recent_activities(user_id, 10, db)
        
        # Quick actions
        quick_actions = [
            {"title": "Ship Now", "description": "Create a new shipment", "action": "create_shipment", "icon": "package"},
            {"title": "Get Quote", "description": "Compare shipping rates", "action": "get_quote", "icon": "calculator"},
            {"title": "Track Package", "description": "Track your shipments", "action": "track_shipment", "icon": "search"},
            {"title": "Address Book", "description": "Manage saved addresses", "action": "manage_addresses", "icon": "address-book"}
        ]
        
        # Notifications (mock for now)
        notifications = [
            {"type": "info", "message": "Your shipment XF1234567890 is out for delivery", "timestamp": datetime.utcnow()},
            {"type": "success", "message": "Shipment DH9876543210 delivered successfully", "timestamp": datetime.utcnow() - timedelta(hours=2)}
        ]
        
        return DashboardData(
            stats=stats,
            monthly_trends=monthly_trends,
            carrier_performance=carrier_performance,
            recent_activities=recent_activities,
            quick_actions=quick_actions,
            notifications=notifications
        )
    
    # ===== ADDRESS BOOK =====
    
    async def create_address_book_entry(self, entry_data: AddressBookCreate, user_id: str, db: AsyncIOMotorDatabase) -> AddressBookEntry:
        """Create a new address book entry."""
        
        entry = AddressBookEntry(
            user_id=user_id,
            **entry_data.dict()
        )
        
        await db.address_book.insert_one(entry.dict())
        return entry
    
    async def get_address_book(self, user_id: str, db: AsyncIOMotorDatabase) -> List[AddressBookEntry]:
        """Get user's address book."""
        
        cursor = db.address_book.find({"user_id": user_id}).sort("last_used", -1)
        entries_data = await cursor.to_list(length=1000)
        
        return [AddressBookEntry(**entry) for entry in entries_data]
    
    async def update_address_book_entry(self, entry_id: str, user_id: str, update_data: AddressBookUpdate, db: AsyncIOMotorDatabase) -> Optional[AddressBookEntry]:
        """Update an address book entry."""
        
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        update_dict["updated_at"] = datetime.utcnow()
        
        result = await db.address_book.update_one(
            {"id": entry_id, "user_id": user_id},
            {"$set": update_dict}
        )
        
        if result.modified_count:
            updated_data = await db.address_book.find_one({"id": entry_id})
            return AddressBookEntry(**updated_data)
        
        return None
    
    async def delete_address_book_entry(self, entry_id: str, user_id: str, db: AsyncIOMotorDatabase) -> bool:
        """Delete an address book entry."""
        
        result = await db.address_book.delete_one({"id": entry_id, "user_id": user_id})
        return result.deleted_count > 0
    
    async def increment_address_usage(self, entry_id: str, user_id: str, db: AsyncIOMotorDatabase) -> bool:
        """Increment usage count for an address book entry."""
        
        result = await db.address_book.update_one(
            {"id": entry_id, "user_id": user_id},
            {
                "$inc": {"usage_count": 1},
                "$set": {"last_used": datetime.utcnow()}
            }
        )
        
        return result.modified_count > 0
    
    # ===== PROFILE MANAGEMENT INTEGRATION =====
    
    async def get_user_profile_summary(self, user_id: str, db: AsyncIOMotorDatabase) -> Dict[str, Any]:
        """Get user profile summary for dashboard."""
        
        # Get user data
        user_doc = await db.users.find_one({"id": user_id})
        if not user_doc:
            return {}
        
        user = User(**user_doc)
        
        # Calculate profile completion
        profile_completion = self._calculate_profile_completion(user)
        
        # Get verification status
        verification_status = {
            "email_verified": user.is_email_verified,
            "phone_verified": user.is_phone_verified,
            "profile_verified": user.is_verified
        }
        
        # Count addresses and payment methods
        address_count = len(user.saved_addresses)
        payment_method_count = len([pm for pm in user.payment_methods if pm.is_active])
        
        return {
            "profile_completion": profile_completion,
            "verification_status": verification_status,
            "saved_addresses_count": address_count,
            "payment_methods_count": payment_method_count,
            "user_type": user.user_type,
            "member_since": user.created_at,
            "last_login": user.last_login,
            "business_profile": user.business_info is not None
        }
    
    def _calculate_profile_completion(self, user: User) -> Dict[str, Any]:
        """Calculate profile completion percentage and missing items."""
        
        total_fields = 0
        completed_fields = 0
        missing_items = []
        
        # Basic profile fields
        basic_fields = [
            ('first_name', 'First Name'),
            ('last_name', 'Last Name'),
            ('phone', 'Phone Number'),
            ('email', 'Email Address')
        ]
        
        for field, display_name in basic_fields:
            total_fields += 1
            if getattr(user, field, None):
                completed_fields += 1
            else:
                missing_items.append(display_name)
        
        # Verification fields
        verification_fields = [
            ('is_email_verified', 'Email Verification'),
            ('is_phone_verified', 'Phone Verification')
        ]
        
        for field, display_name in verification_fields:
            total_fields += 1
            if getattr(user, field, False):
                completed_fields += 1
            else:
                missing_items.append(display_name)
        
        # Address and payment method
        if user.saved_addresses:
            completed_fields += 1
        else:
            missing_items.append('At least one saved address')
        total_fields += 1
        
        active_payment_methods = [pm for pm in user.payment_methods if pm.is_active]
        if active_payment_methods:
            completed_fields += 1
        else:
            missing_items.append('Payment method')
        total_fields += 1
        
        # Business profile (if applicable)
        if user.user_type == 'business':
            business_fields = [
                ('company_name', 'Company Name'),
                ('gst_number', 'GST Number'),
                ('business_type', 'Business Type')
            ]
            
            business_info = user.business_info
            for field, display_name in business_fields:
                total_fields += 1
                if business_info and getattr(business_info, field, None):
                    completed_fields += 1
                else:
                    missing_items.append(f'Business {display_name}')
        
        percentage = (completed_fields / total_fields) * 100 if total_fields > 0 else 0
        
        return {
            "percentage": round(percentage, 1),
            "completed_fields": completed_fields,
            "total_fields": total_fields,
            "missing_items": missing_items
        }
    
    async def get_address_suggestions(self, user_id: str, address_type: str, db: AsyncIOMotorDatabase) -> List[Dict[str, Any]]:
        """Get address suggestions based on user's shipping history."""
        
        # Get frequently used addresses from shipment history
        pipeline = [
            {"$match": {"user_id": user_id}},
            {
                "$group": {
                    "_id": {
                        "city": f"${address_type}.city",
                        "state": f"${address_type}.state",
                        "postal_code": f"${address_type}.postal_code"
                    },
                    "count": {"$sum": 1},
                    "latest_usage": {"$max": "$created_at"}
                }
            },
            {"$match": {"_id.city": {"$ne": None}}},
            {"$sort": {"count": -1, "latest_usage": -1}},
            {"$limit": 5}
        ]
        
        cursor = db.shipments.aggregate(pipeline)
        suggestions_data = await cursor.to_list(length=5)
        
        suggestions = []
        for data in suggestions_data:
            suggestion = {
                "city": data["_id"]["city"],
                "state": data["_id"]["state"],
                "postal_code": data["_id"]["postal_code"],
                "usage_count": data["count"],
                "last_used": data["latest_usage"]
            }
            suggestions.append(suggestion)
        
        return suggestions
    
    async def get_enhanced_dashboard_data(self, user_id: str, db: AsyncIOMotorDatabase) -> Dict[str, Any]:
        """Get enhanced dashboard data including profile management features."""
        
        # Get basic dashboard data
        dashboard_data = await self.get_dashboard_data(user_id, db)
        
        # Get profile summary
        profile_summary = await self.get_user_profile_summary(user_id, db)
        
        # Get user preferences
        preferences = await self.get_user_preferences(user_id, db)
        
        # Get address suggestions
        pickup_suggestions = await self.get_address_suggestions(user_id, "pickup", db)
        delivery_suggestions = await self.get_address_suggestions(user_id, "recipient", db)
        
        # Enhanced quick actions based on profile completion
        enhanced_quick_actions = dashboard_data.quick_actions.copy()
        
        if profile_summary.get("profile_completion", {}).get("percentage", 0) < 80:
            enhanced_quick_actions.insert(0, {
                "title": "Complete Profile",
                "description": "Improve your profile for better service",
                "action": "complete_profile",
                "icon": "user-check",
                "priority": "high"
            })
        
        if not profile_summary.get("verification_status", {}).get("email_verified", False):
            enhanced_quick_actions.append({
                "title": "Verify Email",
                "description": "Verify your email address",
                "action": "verify_email",
                "icon": "mail-check",
                "priority": "medium"
            })
        
        if not profile_summary.get("verification_status", {}).get("phone_verified", False):
            enhanced_quick_actions.append({
                "title": "Verify Phone",
                "description": "Verify your phone number",
                "action": "verify_phone",
                "icon": "phone-check",
                "priority": "medium"
            })
        
        return {
            "stats": dashboard_data.stats,
            "monthly_trends": dashboard_data.monthly_trends,
            "carrier_performance": dashboard_data.carrier_performance,
            "recent_activities": dashboard_data.recent_activities,
            "quick_actions": enhanced_quick_actions,
            "notifications": dashboard_data.notifications,
            "profile_summary": profile_summary,
            "user_preferences": preferences.dict() if preferences else {},
            "address_suggestions": {
                "pickup": pickup_suggestions,
                "delivery": delivery_suggestions
            }
        }
