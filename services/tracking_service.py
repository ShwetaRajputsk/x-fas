from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import random
import re
import httpx
import logging

from models.shipment import Shipment, ShipmentStatus, TrackingEvent
from models.admin import AutoTrackingConfig
from services.booking_service import BookingService

logger = logging.getLogger(__name__)

class TrackingService(BookingService):
    def __init__(self):
        super().__init__()
    
    async def track_multiple_awbs(self, awb_list: List[str], db) -> Dict[str, Any]:
        """Track multiple AWBs and return comprehensive tracking data."""
        
        results = {
            "tracked_count": 0,
            "not_found_count": 0,
            "shipments": [],
            "not_found": [],
            "summary": {}
        }
        
        for awb in awb_list:
            awb = awb.strip().upper()
            if not awb:
                continue
                
            try:
                # Find shipment by AWB
                shipment_data = await db.shipments.find_one({"carrier_info.tracking_number": awb})
                
                if shipment_data:
                    shipment = Shipment(**shipment_data)
                    tracking_info = self.get_enhanced_tracking_info(shipment)
                    results["shipments"].append(tracking_info)
                    results["tracked_count"] += 1
                else:
                    results["not_found"].append(awb)
                    results["not_found_count"] += 1
                    
            except Exception as e:
                results["not_found"].append(awb)
                results["not_found_count"] += 1
        
        # Generate summary statistics
        results["summary"] = self._generate_tracking_summary(results["shipments"])
        
        return results
    
    def get_enhanced_tracking_info(self, shipment: Shipment) -> Dict[str, Any]:
        """Get enhanced tracking information with milestones and progress."""
        
        # Calculate progress percentage
        progress_percentage = self._calculate_progress_percentage(shipment.status)
        
        # Get milestone status
        milestones = self._get_milestone_status(shipment)
        
        # Estimate next update
        next_update = self._estimate_next_update(shipment)
        
        # Get delivery insights
        delivery_insights = self._get_delivery_insights(shipment)
        
        return {
            "id": shipment.id,  # Include internal ID for API calls
            "awb": shipment.carrier_info.tracking_number,
            "shipment_number": shipment.shipment_number,
            "status": shipment.status,
            "progress_percentage": progress_percentage,
            "carrier": shipment.carrier_info.carrier_name,
            "service_type": shipment.carrier_info.service_type,
            "sender": {
                "name": shipment.sender.name,
                "city": shipment.sender.city,
                "state": shipment.sender.state
            },
            "recipient": {
                "name": shipment.recipient.name,
                "city": shipment.recipient.city,
                "state": shipment.recipient.state
            },
            "package_info": {
                "weight": shipment.package_info.dimensions.weight,
                "contents": shipment.package_info.contents_description,
                "declared_value": shipment.package_info.declared_value
            },
            "milestones": milestones,
            "tracking_events": [
                {
                    "timestamp": event.timestamp,
                    "status": event.status,
                    "location": event.location,
                    "description": event.description
                }
                for event in shipment.tracking_events
            ],
            "estimated_delivery": shipment.carrier_info.estimated_delivery,
            "next_update": next_update,
            "delivery_insights": delivery_insights,
            "created_at": shipment.created_at,
            "last_updated": shipment.updated_at
        }
    
    def _calculate_progress_percentage(self, status: ShipmentStatus) -> int:
        """Calculate progress percentage based on shipment status."""
        
        status_progress = {
            ShipmentStatus.DRAFT: 0,
            ShipmentStatus.BOOKED: 15,
            ShipmentStatus.PICKUP_SCHEDULED: 25,
            ShipmentStatus.PICKED_UP: 40,
            ShipmentStatus.IN_TRANSIT: 60,
            ShipmentStatus.OUT_FOR_DELIVERY: 85,
            ShipmentStatus.DELIVERED: 100,
            ShipmentStatus.RETURNED: 100,
            ShipmentStatus.CANCELLED: 0,
            ShipmentStatus.LOST: 0
        }
        
        return status_progress.get(status, 0)
    
    def _get_milestone_status(self, shipment: Shipment) -> List[Dict[str, Any]]:
        """Get milestone status with icons and colors."""
        
        current_status = shipment.status
        
        milestones = [
            {
                "id": "booked",
                "title": "Booking Confirmed",
                "description": "Your shipment has been booked",
                "icon": "check-circle",
                "status": "completed" if current_status in [
                    ShipmentStatus.BOOKED, ShipmentStatus.PICKUP_SCHEDULED, 
                    ShipmentStatus.PICKED_UP, ShipmentStatus.IN_TRANSIT,
                    ShipmentStatus.OUT_FOR_DELIVERY, ShipmentStatus.DELIVERED
                ] else "pending",
                "timestamp": shipment.created_at
            },
            {
                "id": "pickup_scheduled",
                "title": "Pickup Scheduled",
                "description": "Pickup has been scheduled",
                "icon": "calendar",
                "status": "completed" if current_status in [
                    ShipmentStatus.PICKUP_SCHEDULED, ShipmentStatus.PICKED_UP,
                    ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY,
                    ShipmentStatus.DELIVERED
                ] else "current" if current_status == ShipmentStatus.BOOKED else "pending",
                "timestamp": self._get_milestone_timestamp(shipment, "pickup_scheduled")
            },
            {
                "id": "picked_up",
                "title": "Package Picked Up",
                "description": "Package collected from sender",
                "icon": "truck",
                "status": "completed" if current_status in [
                    ShipmentStatus.PICKED_UP, ShipmentStatus.IN_TRANSIT,
                    ShipmentStatus.OUT_FOR_DELIVERY, ShipmentStatus.DELIVERED
                ] else "current" if current_status == ShipmentStatus.PICKUP_SCHEDULED else "pending",
                "timestamp": self._get_milestone_timestamp(shipment, "picked_up")
            },
            {
                "id": "in_transit",
                "title": "In Transit",
                "description": "Package is on the way",
                "icon": "navigation",
                "status": "completed" if current_status in [
                    ShipmentStatus.IN_TRANSIT, ShipmentStatus.OUT_FOR_DELIVERY,
                    ShipmentStatus.DELIVERED
                ] else "current" if current_status == ShipmentStatus.PICKED_UP else "pending",
                "timestamp": self._get_milestone_timestamp(shipment, "in_transit")
            },
            {
                "id": "out_for_delivery",
                "title": "Out for Delivery",
                "description": "Package is out for delivery",
                "icon": "map-pin",
                "status": "completed" if current_status in [
                    ShipmentStatus.OUT_FOR_DELIVERY, ShipmentStatus.DELIVERED
                ] else "current" if current_status == ShipmentStatus.IN_TRANSIT else "pending",
                "timestamp": self._get_milestone_timestamp(shipment, "out_for_delivery")
            },
            {
                "id": "delivered",
                "title": "Delivered",
                "description": "Package successfully delivered",
                "icon": "check-circle-2",
                "status": "completed" if current_status == ShipmentStatus.DELIVERED else "current" if current_status == ShipmentStatus.OUT_FOR_DELIVERY else "pending",
                "timestamp": shipment.delivery_date if current_status == ShipmentStatus.DELIVERED else None
            }
        ]
        
        return milestones
    
    def _get_milestone_timestamp(self, shipment: Shipment, milestone_id: str) -> Optional[datetime]:
        """Get timestamp for a specific milestone from tracking events."""
        
        milestone_keywords = {
            "pickup_scheduled": ["scheduled", "pickup scheduled"],
            "picked_up": ["picked up", "collected", "pickup"],
            "in_transit": ["in transit", "departed", "forwarded"],
            "out_for_delivery": ["out for delivery", "delivery", "final mile"]
        }
        
        keywords = milestone_keywords.get(milestone_id, [])
        
        for event in reversed(shipment.tracking_events):
            for keyword in keywords:
                if keyword.lower() in event.status.lower() or keyword.lower() in event.description.lower():
                    return event.timestamp
        
        return None
    
    def _estimate_next_update(self, shipment: Shipment) -> Optional[Dict[str, Any]]:
        """Estimate when the next tracking update will occur."""
        
        if shipment.status == ShipmentStatus.DELIVERED:
            return None
        
        status_next_updates = {
            ShipmentStatus.BOOKED: {
                "expected_status": "Pickup Scheduled",
                "hours_estimate": 2,
                "description": "Pickup will be scheduled soon"
            },
            ShipmentStatus.PICKUP_SCHEDULED: {
                "expected_status": "Picked Up",
                "hours_estimate": 24,
                "description": "Package will be picked up within 24 hours"
            },
            ShipmentStatus.PICKED_UP: {
                "expected_status": "In Transit",
                "hours_estimate": 4,
                "description": "Package will start moving to destination"
            },
            ShipmentStatus.IN_TRANSIT: {
                "expected_status": "Out for Delivery",
                "hours_estimate": 12,
                "description": "Package will reach destination hub"
            },
            ShipmentStatus.OUT_FOR_DELIVERY: {
                "expected_status": "Delivered",
                "hours_estimate": 8,
                "description": "Package will be delivered today"
            }
        }
        
        next_update_info = status_next_updates.get(shipment.status)
        
        if next_update_info:
            estimated_time = datetime.utcnow() + timedelta(hours=next_update_info["hours_estimate"])
            return {
                "expected_status": next_update_info["expected_status"],
                "estimated_time": estimated_time,
                "description": next_update_info["description"]
            }
        
        return None
    
    def _get_delivery_insights(self, shipment: Shipment) -> Dict[str, Any]:
        """Get delivery insights and recommendations."""
        
        insights = {
            "is_delayed": False,
            "delivery_confidence": "high",
            "special_instructions": [],
            "recommendations": []
        }
        
        # Check if delivery is delayed
        if shipment.carrier_info.estimated_delivery:
            if datetime.utcnow() > shipment.carrier_info.estimated_delivery and shipment.status != ShipmentStatus.DELIVERED:
                insights["is_delayed"] = True
                insights["delivery_confidence"] = "medium"
                insights["recommendations"].append("Contact customer service for updated delivery timeline")
        
        # Add special instructions based on package info
        if shipment.package_info.fragile:
            insights["special_instructions"].append("Handle with care - Fragile item")
        
        if shipment.signature_required:
            insights["special_instructions"].append("Signature required on delivery")
        
        if shipment.insurance_required:
            insights["special_instructions"].append("Insured package - Extra security measures")
        
        # Add status-specific recommendations
        if shipment.status == ShipmentStatus.OUT_FOR_DELIVERY:
            insights["recommendations"].append("Ensure someone is available to receive the package")
        
        return insights
    
    def _generate_tracking_summary(self, shipments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics for bulk tracking."""
        
        if not shipments:
            return {}
        
        status_counts = {}
        carrier_counts = {}
        total_value = 0
        delayed_count = 0
        
        for shipment in shipments:
            # Status distribution
            status = shipment["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Carrier distribution
            carrier = shipment["carrier"]
            carrier_counts[carrier] = carrier_counts.get(carrier, 0) + 1
            
            # Total declared value
            total_value += shipment["package_info"]["declared_value"]
            
            # Delayed count
            if shipment["delivery_insights"]["is_delayed"]:
                delayed_count += 1
        
        return {
            "total_shipments": len(shipments),
            "status_distribution": status_counts,
            "carrier_distribution": carrier_counts,
            "total_declared_value": total_value,
            "delayed_shipments": delayed_count,
            "on_time_percentage": ((len(shipments) - delayed_count) / len(shipments)) * 100
        }
    
    def validate_awb_format(self, awb: str) -> bool:
        """Validate AWB format based on carrier patterns."""
        
        if not awb or len(awb.strip()) < 6:
            return False
        
        awb = awb.strip().upper()
        
        # Common AWB patterns
        patterns = [
            r'^XF\d{10}$',      # XFas Self Network: XF1234567890
            r'^FX\d{10}$',      # FedEx: FX1234567890
            r'^DH\d{10}$',      # DHL: DH1234567890
            r'^AR\d{10}$',      # Aramex: AR1234567890
            r'^UP\d{10}$',      # UPS: UP1234567890
            r'^\d{10,15}$',     # Generic numeric: 1234567890
        ]
        
        return any(re.match(pattern, awb) for pattern in patterns)
    
    async def get_tracking_analytics(self, user_id: Optional[str], db) -> Dict[str, Any]:
        """Get tracking analytics for dashboard."""
        
        query = {}
        if user_id:
            query["user_id"] = user_id
        
        # Get all shipments
        shipments_cursor = db.shipments.find(query)
        shipments_data = await shipments_cursor.to_list(length=1000)
        
        if not shipments_data:
            return {"total_shipments": 0}
        
        analytics = {
            "total_shipments": len(shipments_data),
            "status_breakdown": {},
            "carrier_performance": {},
            "monthly_trends": {},
            "average_delivery_time": 0,
            "delivery_success_rate": 0
        }
        
        # Status breakdown
        for shipment_data in shipments_data:
            status = shipment_data.get('status', 'unknown')
            analytics["status_breakdown"][status] = analytics["status_breakdown"].get(status, 0) + 1
        
        # Calculate delivery success rate
        completed_statuses = [ShipmentStatus.DELIVERED, ShipmentStatus.RETURNED]
        completed_count = sum(analytics["status_breakdown"].get(status, 0) for status in completed_statuses)
        analytics["delivery_success_rate"] = (completed_count / len(shipments_data)) * 100 if shipments_data else 0
        
        return analytics
    
    async def sync_all_carriers(self, db, carrier_name: Optional[str] = None) -> Dict[str, Any]:
        """Sync tracking updates for all or specific carriers (placeholder implementation)."""
        
        try:
            # This is a placeholder implementation
            # In production, this would integrate with actual carrier APIs
            
            result = {
                "total_carriers": 5,
                "synced_carriers": 5,
                "failed_carriers": 0,
                "updated_shipments": random.randint(10, 50),
                "errors": []
            }
            
            if carrier_name:
                result["total_carriers"] = 1
                result["synced_carriers"] = 1
                result["updated_shipments"] = random.randint(2, 10)
            
            # Simulate some tracking updates
            await self._simulate_tracking_updates(db)
            
            logger.info(f"Sync completed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error in sync_all_carriers: {str(e)}")
            raise
    
    async def _simulate_tracking_updates(self, db):
        """Simulate some tracking updates for demo purposes."""
        
        try:
            # Get some active shipments
            cursor = db.shipments.find({
                "status": {"$in": [
                    ShipmentStatus.BOOKED.value,
                    ShipmentStatus.PICKED_UP.value,
                    ShipmentStatus.IN_TRANSIT.value
                ]}
            }).limit(5)
            
            shipments = await cursor.to_list(length=5)
            
            for shipment in shipments:
                # Simulate random status progression
                current_status = shipment.get("status")
                new_status = self._get_next_status(current_status)
                
                if new_status and new_status != current_status:
                    await db.shipments.update_one(
                        {"id": shipment["id"]},
                        {
                            "$set": {
                                "status": new_status,
                                "updated_at": datetime.utcnow().isoformat(),
                                "last_tracking_update": datetime.utcnow().isoformat()
                            }
                        }
                    )
                    
                    # Create a tracking event
                    from models.admin import TrackingEvent
                    tracking_event = TrackingEvent(
                        shipment_id=shipment["id"],
                        tracking_number=shipment.get("carrier_info", {}).get("tracking_number", ""),
                        event_time=datetime.utcnow(),
                        event_code=new_status.upper(),
                        event_description=f"Status updated to {new_status.replace('_', ' ').title()}",
                        location="Processing Center",
                        carrier_name=shipment.get("carrier_info", {}).get("carrier_name", "XFas Self Network")
                    )
                    
                    await db.tracking_events.insert_one(tracking_event.dict())
                    
        except Exception as e:
            logger.error(f"Error simulating tracking updates: {str(e)}")
    
    def _get_next_status(self, current_status: str) -> Optional[str]:
        """Get the next logical status for simulation."""
        
        status_progression = {
            ShipmentStatus.BOOKED.value: ShipmentStatus.PICKUP_SCHEDULED.value,
            ShipmentStatus.PICKUP_SCHEDULED.value: ShipmentStatus.PICKED_UP.value,
            ShipmentStatus.PICKED_UP.value: ShipmentStatus.IN_TRANSIT.value,
            ShipmentStatus.IN_TRANSIT.value: ShipmentStatus.OUT_FOR_DELIVERY.value,
            ShipmentStatus.OUT_FOR_DELIVERY.value: ShipmentStatus.DELIVERED.value
        }
        
        # Random chance to progress (30% chance)
        if random.random() < 0.3:
            return status_progression.get(current_status)
        
        return None
