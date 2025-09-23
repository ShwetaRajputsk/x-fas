from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.admin import (
    CarrierRate, CarrierRateCreate, CarrierRateUpdate,
    AdminStats, RevenueBreakdown, UserGrowthData, CarrierAnalytics,
    SystemAlert, AdminDashboardData,
    UserManagement, BookingManagement, RouteAnalytics, PerformanceMetrics
)
from models.shipment import ShipmentStatus
from models.user import User

class AdminService:
    def __init__(self):
        pass
    
    # ===== CARRIER RATE MANAGEMENT =====
    
    async def create_carrier_rate(self, rate_data: CarrierRateCreate, admin_user_id: str, db: AsyncIOMotorDatabase) -> CarrierRate:
        """Create a new carrier rate."""
        
        rate_dict = rate_data.dict()
        if not rate_dict.get("effective_from"):
            rate_dict["effective_from"] = datetime.utcnow()
        rate_dict["created_by"] = admin_user_id
        
        rate = CarrierRate(**rate_dict)
        
        await db.carrier_rates.insert_one(rate.dict())
        return rate
    
    async def get_carrier_rates(self, carrier_name: Optional[str], is_active: Optional[bool], db: AsyncIOMotorDatabase) -> List[CarrierRate]:
        """Get carrier rates with optional filtering."""
        
        query = {}
        if carrier_name:
            query["carrier_name"] = carrier_name
        if is_active is not None:
            query["is_active"] = is_active
        
        cursor = db.carrier_rates.find(query).sort("created_at", -1)
        rates_data = await cursor.to_list(length=1000)
        
        return [CarrierRate(**rate) for rate in rates_data]
    
    async def update_carrier_rate(self, rate_id: str, update_data: CarrierRateUpdate, admin_user_id: str, db: AsyncIOMotorDatabase) -> Optional[CarrierRate]:
        """Update a carrier rate."""
        
        update_dict = {k: v for k, v in update_data.dict().items() if v is not None}
        update_dict["updated_by"] = admin_user_id
        update_dict["updated_at"] = datetime.utcnow()
        
        result = await db.carrier_rates.update_one(
            {"id": rate_id},
            {"$set": update_dict}
        )
        
        if result.modified_count:
            updated_data = await db.carrier_rates.find_one({"id": rate_id})
            return CarrierRate(**updated_data)
        
        return None
    
    async def delete_carrier_rate(self, rate_id: str, db: AsyncIOMotorDatabase) -> bool:
        """Delete (deactivate) a carrier rate."""
        
        result = await db.carrier_rates.update_one(
            {"id": rate_id},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )
        
        return result.modified_count > 0
    
    # ===== ADMIN DASHBOARD STATISTICS =====
    
    async def get_admin_stats(self, db: AsyncIOMotorDatabase) -> AdminStats:
        """Calculate comprehensive admin dashboard statistics."""
        
        stats = AdminStats()
        
        # Get current time boundaries
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month_start = (month_start - timedelta(days=1)).replace(day=1)
        
        # User statistics
        total_users = await db.users.count_documents({})
        active_users = await db.users.count_documents({"is_active": True})
        new_users_this_month = await db.users.count_documents({
            "created_at": {"$gte": month_start.isoformat()}
        })
        new_users_last_month = await db.users.count_documents({
            "created_at": {
                "$gte": last_month_start.isoformat(),
                "$lt": month_start.isoformat()
            }
        })
        
        stats.total_users = total_users
        stats.active_users = active_users
        stats.new_users_this_month = new_users_this_month
        
        # Calculate user growth rate
        if new_users_last_month > 0:
            stats.user_growth_rate = ((new_users_this_month - new_users_last_month) / new_users_last_month) * 100
        
        # Shipment statistics
        total_shipments = await db.shipments.count_documents({})
        active_shipments = await db.shipments.count_documents({
            "status": {"$in": [
                ShipmentStatus.BOOKED, ShipmentStatus.PICKUP_SCHEDULED,
                ShipmentStatus.PICKED_UP, ShipmentStatus.IN_TRANSIT,
                ShipmentStatus.OUT_FOR_DELIVERY
            ]}
        })
        completed_shipments = await db.shipments.count_documents({
            "status": {"$in": [ShipmentStatus.DELIVERED, ShipmentStatus.RETURNED]}
        })
        shipments_today = await db.shipments.count_documents({
            "created_at": {"$gte": today_start.isoformat()}
        })
        shipments_this_month = await db.shipments.count_documents({
            "created_at": {"$gte": month_start.isoformat()}
        })
        
        stats.total_shipments = total_shipments
        stats.active_shipments = active_shipments
        stats.completed_shipments = completed_shipments
        stats.shipments_today = shipments_today
        stats.shipments_this_month = shipments_this_month
        
        # Financial statistics
        revenue_pipeline = [
            {"$match": {"payment_info.amount": {"$gt": 0}}},
            {"$group": {
                "_id": None,
                "total_revenue": {"$sum": "$payment_info.amount"},
                "total_count": {"$sum": 1}
            }}
        ]
        
        revenue_cursor = db.shipments.aggregate(revenue_pipeline)
        revenue_data = await revenue_cursor.to_list(length=1)
        
        if revenue_data:
            stats.total_revenue = revenue_data[0]["total_revenue"]
            stats.average_order_value = revenue_data[0]["total_revenue"] / revenue_data[0]["total_count"]
        
        # This month revenue
        month_revenue_pipeline = [
            {"$match": {
                "created_at": {"$gte": month_start.isoformat()},
                "payment_info.amount": {"$gt": 0}
            }},
            {"$group": {
                "_id": None,
                "revenue": {"$sum": "$payment_info.amount"}
            }}
        ]
        
        month_revenue_cursor = db.shipments.aggregate(month_revenue_pipeline)
        month_revenue_data = await month_revenue_cursor.to_list(length=1)
        
        if month_revenue_data:
            stats.revenue_this_month = month_revenue_data[0]["revenue"]
        
        # Today revenue
        today_revenue_pipeline = [
            {"$match": {
                "created_at": {"$gte": today_start.isoformat()},
                "payment_info.amount": {"$gt": 0}
            }},
            {"$group": {
                "_id": None,
                "revenue": {"$sum": "$payment_info.amount"}
            }}
        ]
        
        today_revenue_cursor = db.shipments.aggregate(today_revenue_pipeline)
        today_revenue_data = await today_revenue_cursor.to_list(length=1)
        
        if today_revenue_data:
            stats.revenue_today = today_revenue_data[0]["revenue"]
        
        # Performance statistics
        if total_shipments > 0:
            stats.overall_success_rate = (completed_shipments / total_shipments) * 100
        
        # Mock some statistics that would require complex calculations
        stats.average_delivery_time = 3.2
        stats.customer_satisfaction = 4.5
        stats.total_carriers = 5
        stats.active_carriers = 5
        stats.best_performing_carrier = "XFas Self Network"
        stats.api_requests_today = 1250
        stats.error_rate = 0.8
        stats.uptime_percentage = 99.9
        
        return stats
    
    async def get_revenue_breakdown(self, db: AsyncIOMotorDatabase) -> List[RevenueBreakdown]:
        """Get revenue breakdown by carrier."""
        
        pipeline = [
            {"$match": {"payment_info.amount": {"$gt": 0}}},
            {"$group": {
                "_id": "$carrier_info.carrier_name",
                "total_revenue": {"$sum": "$payment_info.amount"},
                "shipment_count": {"$sum": 1}
            }},
            {"$sort": {"total_revenue": -1}}
        ]
        
        cursor = db.shipments.aggregate(pipeline)
        revenue_data = await cursor.to_list(length=50)
        
        total_revenue = sum(item["total_revenue"] for item in revenue_data)
        
        breakdown = []
        for item in revenue_data:
            if not item["_id"]:
                continue
                
            breakdown.append(RevenueBreakdown(
                carrier_name=item["_id"],
                total_revenue=item["total_revenue"],
                shipment_count=item["shipment_count"],
                average_rate=item["total_revenue"] / item["shipment_count"],
                market_share=(item["total_revenue"] / total_revenue) * 100 if total_revenue > 0 else 0
            ))
        
        return breakdown
    
    async def get_user_growth_data(self, months: int, db: AsyncIOMotorDatabase) -> List[UserGrowthData]:
        """Get user growth data for the specified number of months."""
        
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=months * 30)
        
        pipeline = [
            {"$match": {
                "created_at": {
                    "$gte": start_date.isoformat(),
                    "$lte": end_date.isoformat()
                }
            }},
            {"$addFields": {
                "created_date": {"$dateFromString": {"dateString": "$created_at"}}
            }},
            {"$group": {
                "_id": {
                    "year": {"$year": "$created_date"},
                    "month": {"$month": "$created_date"}
                },
                "new_users": {"$sum": 1}
            }},
            {"$sort": {"_id.year": 1, "_id.month": 1}}
        ]
        
        cursor = db.users.aggregate(pipeline)
        growth_data = await cursor.to_list(length=months)
        
        result = []
        running_total = 0
        
        for data in growth_data:
            running_total += data["new_users"]
            period = f"{data['_id']['year']}-{data['_id']['month']:02d}"
            
            result.append(UserGrowthData(
                period=period,
                new_users=data["new_users"],
                total_users=running_total,
                churn_rate=2.5  # Mock data
            ))
        
        return result
    
    async def get_carrier_analytics(self, db: AsyncIOMotorDatabase) -> List[CarrierAnalytics]:
        """Get comprehensive carrier analytics."""
        
        pipeline = [
            {"$group": {
                "_id": "$carrier_info.carrier_name",
                "total_shipments": {"$sum": 1},
                "delivered_shipments": {
                    "$sum": {"$cond": [{"$eq": ["$status", ShipmentStatus.DELIVERED]}, 1, 0]}
                },
                "total_revenue": {"$sum": "$payment_info.amount"}
            }}
        ]
        
        cursor = db.shipments.aggregate(pipeline)
        analytics_data = await cursor.to_list(length=50)
        
        total_revenue = sum(item["total_revenue"] for item in analytics_data if item["total_revenue"])
        
        analytics = []
        for item in analytics_data:
            if not item["_id"]:
                continue
            
            analytics.append(CarrierAnalytics(
                carrier_name=item["_id"],
                total_shipments=item["total_shipments"],
                success_rate=(item["delivered_shipments"] / item["total_shipments"]) * 100 if item["total_shipments"] > 0 else 0,
                average_delivery_time=3.2,  # Mock data
                customer_rating=4.3,  # Mock data
                revenue_contribution=(item["total_revenue"] / total_revenue) * 100 if total_revenue > 0 else 0,
                cost_efficiency=85.5,  # Mock data
                on_time_percentage=92.3  # Mock data
            ))
        
        return sorted(analytics, key=lambda x: x.total_shipments, reverse=True)
    
    async def get_system_alerts(self, limit: int, resolved: Optional[bool], db: AsyncIOMotorDatabase) -> List[SystemAlert]:
        """Get system alerts."""
        
        query = {}
        if resolved is not None:
            query["is_resolved"] = resolved
        
        cursor = db.system_alerts.find(query).sort("created_at", -1).limit(limit)
        alerts_data = await cursor.to_list(length=limit)
        
        return [SystemAlert(**alert) for alert in alerts_data]
    
    async def create_system_alert(self, alert_type: str, title: str, message: str, component: str, severity: int, db: AsyncIOMotorDatabase) -> SystemAlert:
        """Create a new system alert."""
        
        alert = SystemAlert(
            alert_type=alert_type,
            title=title,
            message=message,
            component=component,
            severity=severity
        )
        
        await db.system_alerts.insert_one(alert.dict())
        return alert
    
    async def resolve_system_alert(self, alert_id: str, admin_user_id: str, db: AsyncIOMotorDatabase) -> bool:
        """Resolve a system alert."""
        
        result = await db.system_alerts.update_one(
            {"id": alert_id},
            {
                "$set": {
                    "is_resolved": True,
                    "resolved_at": datetime.utcnow(),
                    "resolved_by": admin_user_id
                }
            }
        )
        
        return result.modified_count > 0
    
    async def get_admin_dashboard_data(self, db: AsyncIOMotorDatabase) -> AdminDashboardData:
        """Get comprehensive admin dashboard data."""
        
        stats = await self.get_admin_stats(db)
        revenue_breakdown = await self.get_revenue_breakdown(db)
        user_growth = await self.get_user_growth_data(6, db)
        carrier_analytics = await self.get_carrier_analytics(db)
        system_alerts = await self.get_system_alerts(10, False, db)
        
        # Get recent shipments
        recent_shipments_cursor = db.shipments.find({}).sort("created_at", -1).limit(10)
        recent_shipments_data = await recent_shipments_cursor.to_list(length=10)
        
        # Convert ObjectId to string for JSON serialization
        for shipment in recent_shipments_data:
            if '_id' in shipment:
                shipment['_id'] = str(shipment['_id'])
        
        # Get top routes
        routes_pipeline = [
            {"$group": {
                "_id": {
                    "from_city": "$sender.city",
                    "to_city": "$recipient.city"
                },
                "count": {"$sum": 1},
                "revenue": {"$sum": "$payment_info.amount"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        
        routes_cursor = db.shipments.aggregate(routes_pipeline)
        routes_data = await routes_cursor.to_list(length=10)
        
        top_routes = [
            {
                "route": f"{item['_id']['from_city']} → {item['_id']['to_city']}",
                "shipments": item["count"],
                "revenue": item["revenue"]
            }
            for item in routes_data if item["_id"]["from_city"] and item["_id"]["to_city"]
        ]
        
        # Performance metrics
        performance_metrics = {
            "api_response_time": 245.5,
            "database_performance": 98.2,
            "carrier_integration_uptime": 99.5,
            "customer_satisfaction": 4.5,
            "order_fulfillment_rate": 96.8
        }
        
        return AdminDashboardData(
            stats=stats,
            revenue_breakdown=revenue_breakdown,
            user_growth=user_growth,
            carrier_analytics=carrier_analytics,
            recent_shipments=recent_shipments_data,
            system_alerts=system_alerts,
            top_routes=top_routes,
            performance_metrics=performance_metrics
        )
    
    # ===== USER MANAGEMENT =====
    
    async def get_users_management(self, limit: int, skip: int, search: Optional[str], db: AsyncIOMotorDatabase) -> Tuple[List[UserManagement], int]:
        """Get users for management with search and pagination."""
        
        query = {}
        if search:
            query["$or"] = [
                {"first_name": {"$regex": search, "$options": "i"}},
                {"last_name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}}
            ]
        
        # Get users with shipment statistics
        pipeline = [
            {"$match": query},
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
                    "total_spent": {"$sum": "$shipments.payment_info.amount"}
                }
            },
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit}
        ]
        
        cursor = db.users.aggregate(pipeline)
        users_data = await cursor.to_list(length=limit)
        
        # Get total count
        total_count = await db.users.count_documents(query)
        
        users = []
        for user_data in users_data:
            users.append(UserManagement(
                id=user_data["id"],
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                email=user_data["email"],
                phone=user_data.get("phone"),
                user_type=user_data["user_type"],
                is_active=user_data["is_active"],
                total_shipments=user_data["total_shipments"],
                total_spent=user_data["total_spent"],
                last_login=user_data.get("last_login"),
                created_at=datetime.fromisoformat(user_data["created_at"]) if isinstance(user_data["created_at"], str) else user_data["created_at"],
                verification_status=user_data.get("verification_status", "pending")
            ))
        
        return users, total_count
    
    async def update_user_status(self, user_id: str, is_active: bool, admin_user_id: str, db: AsyncIOMotorDatabase) -> bool:
        """Update user active status."""
        
        result = await db.users.update_one(
            {"id": user_id},
            {
                "$set": {
                    "is_active": is_active,
                    "updated_at": datetime.utcnow().isoformat(),
                    "updated_by": admin_user_id
                }
            }
        )
        
        return result.modified_count > 0
    
    # ===== BOOKING MANAGEMENT =====
    
    async def get_bookings_management(self, limit: int, skip: int, status_filter: Optional[str], search: Optional[str], db: AsyncIOMotorDatabase) -> Tuple[List[BookingManagement], int]:
        """Get bookings for management with filters and pagination."""
        
        query = {}
        if status_filter:
            query["status"] = status_filter
        
        if search:
            query["$or"] = [
                {"shipment_number": {"$regex": search, "$options": "i"}},
                {"carrier_info.tracking_number": {"$regex": search, "$options": "i"}},
                {"sender.name": {"$regex": search, "$options": "i"}},
                {"recipient.name": {"$regex": search, "$options": "i"}}
            ]
        
        # Get bookings with user info
        pipeline = [
            {"$match": query},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "user_id",
                    "foreignField": "id",
                    "as": "user"
                }
            },
            {"$unwind": "$user"},
            {"$sort": {"created_at": -1}},
            {"$skip": skip},
            {"$limit": limit}
        ]
        
        cursor = db.shipments.aggregate(pipeline)
        bookings_data = await cursor.to_list(length=limit)
        
        # Get total count
        total_count = await db.shipments.count_documents(query)
        
        bookings = []
        for booking_data in bookings_data:
            bookings.append(BookingManagement(
                id=booking_data["id"],
                shipment_number=booking_data["shipment_number"],
                awb=booking_data["carrier_info"]["tracking_number"],
                status=booking_data["status"],
                carrier=booking_data["carrier_info"]["carrier_name"],
                sender_name=booking_data["sender"]["name"],
                sender_city=booking_data["sender"]["city"],
                recipient_name=booking_data["recipient"]["name"],
                recipient_city=booking_data["recipient"]["city"],
                created_at=datetime.fromisoformat(booking_data["created_at"]) if isinstance(booking_data["created_at"], str) else booking_data["created_at"],
                estimated_delivery=booking_data["carrier_info"].get("estimated_delivery"),
                actual_delivery=booking_data.get("delivery_date"),
                amount=booking_data["payment_info"]["amount"],
                user_email=booking_data["user"]["email"]
            ))
        
        return bookings, total_count