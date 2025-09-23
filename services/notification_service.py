from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import json
import logging

from models.shipment import Shipment, ShipmentStatus

logger = logging.getLogger(__name__)

class NotificationType(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"

class NotificationTemplate(str, Enum):
    BOOKING_CONFIRMATION = "booking_confirmation"
    STATUS_UPDATE = "status_update"
    DELIVERY_ALERT = "delivery_alert"
    DELAY_NOTIFICATION = "delay_notification"
    DELIVERED_CONFIRMATION = "delivered_confirmation"

class NotificationService:
    def __init__(self):
        self.email_enabled = True  # Set to False if no email service configured
        self.sms_enabled = True    # Set to False if no SMS service configured
        self.templates = self._load_templates()
    
    def _load_templates(self) -> Dict[str, Dict[str, str]]:
        """Load notification templates."""
        
        return {
            NotificationTemplate.BOOKING_CONFIRMATION: {
                "email_subject": "Booking Confirmed - {shipment_number}",
                "email_body": """
                <h2>Your shipment has been booked successfully!</h2>
                <p>Dear {recipient_name},</p>
                <p>Your shipment has been booked with XFas Logistics.</p>
                
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3>Shipment Details</h3>
                    <p><strong>AWB Number:</strong> {awb}</p>
                    <p><strong>Shipment Number:</strong> {shipment_number}</p>
                    <p><strong>Carrier:</strong> {carrier}</p>
                    <p><strong>Service:</strong> {service_type}</p>
                    <p><strong>Estimated Delivery:</strong> {estimated_delivery}</p>
                </div>
                
                <p><strong>Sender:</strong> {sender_name}, {sender_city}</p>
                <p><strong>Recipient:</strong> {recipient_name}, {recipient_city}</p>
                
                <p>You can track your shipment anytime at: <a href="{tracking_url}">Track Shipment</a></p>
                
                <p>Thank you for choosing XFas Logistics!</p>
                """,
                "sms_body": "XFas Logistics: Your shipment {shipment_number} is booked! AWB: {awb}. Track at {tracking_url}"
            },
            
            NotificationTemplate.STATUS_UPDATE: {
                "email_subject": "Shipment Update - {shipment_number}",
                "email_body": """
                <h2>Shipment Status Update</h2>
                <p>Dear {recipient_name},</p>
                <p>Your shipment status has been updated.</p>
                
                <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3>Current Status: {status}</h3>
                    <p><strong>AWB:</strong> {awb}</p>
                    <p><strong>Location:</strong> {location}</p>
                    <p><strong>Update Time:</strong> {update_time}</p>
                    <p><strong>Description:</strong> {description}</p>
                </div>
                
                <p>Track your shipment: <a href="{tracking_url}">View Details</a></p>
                """,
                "sms_body": "XFas Update: {awb} - {status} at {location}. Track: {tracking_url}"
            },
            
            NotificationTemplate.DELIVERY_ALERT: {
                "email_subject": "Out for Delivery - {shipment_number}",
                "email_body": """
                <h2>Your package is out for delivery!</h2>
                <p>Dear {recipient_name},</p>
                <p>Great news! Your package is out for delivery and will arrive today.</p>
                
                <div style="background: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3>Delivery Information</h3>
                    <p><strong>AWB:</strong> {awb}</p>
                    <p><strong>Expected Delivery:</strong> Today by {delivery_time}</p>
                    <p><strong>Delivery Address:</strong> {delivery_address}</p>
                </div>
                
                <p><strong>Important:</strong> Please ensure someone is available to receive the package.</p>
                <p>Track live delivery: <a href="{tracking_url}">Live Tracking</a></p>
                """,
                "sms_body": "XFas Delivery: Your package {awb} is out for delivery! Expected today by {delivery_time}. Be available to receive."
            },
            
            NotificationTemplate.DELIVERED_CONFIRMATION: {
                "email_subject": "Delivered Successfully - {shipment_number}",
                "email_body": """
                <h2>Package Delivered Successfully!</h2>
                <p>Dear {recipient_name},</p>
                <p>Your package has been delivered successfully.</p>
                
                <div style="background: #e8f5e8; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3>Delivery Confirmation</h3>
                    <p><strong>AWB:</strong> {awb}</p>
                    <p><strong>Delivered On:</strong> {delivery_time}</p>
                    <p><strong>Delivered To:</strong> {delivered_to}</p>
                    <p><strong>Location:</strong> {delivery_location}</p>
                </div>
                
                <p>Thank you for choosing XFas Logistics! We hope to serve you again.</p>
                <p><a href="{feedback_url}">Rate Your Experience</a></p>
                """,
                "sms_body": "XFas Delivered: Package {awb} delivered successfully on {delivery_time}. Thank you!"
            },
            
            NotificationTemplate.DELAY_NOTIFICATION: {
                "email_subject": "Shipment Delayed - {shipment_number}",
                "email_body": """
                <h2>Shipment Delay Notification</h2>
                <p>Dear {recipient_name},</p>
                <p>We regret to inform you that your shipment has been delayed.</p>
                
                <div style="background: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0;">
                    <h3>Delay Information</h3>
                    <p><strong>AWB:</strong> {awb}</p>
                    <p><strong>Original Delivery Date:</strong> {original_date}</p>
                    <p><strong>New Estimated Delivery:</strong> {new_date}</p>
                    <p><strong>Reason:</strong> {delay_reason}</p>
                </div>
                
                <p>We sincerely apologize for the inconvenience. Our team is working to ensure your package reaches you as soon as possible.</p>
                <p>For any concerns, contact: contact@xfas.in</p>
                """,
                "sms_body": "XFas Delay: {awb} delayed. New delivery: {new_date}. Reason: {delay_reason}. Sorry for inconvenience."
            }
        }
    
    async def send_booking_confirmation(self, shipment: Shipment, tracking_url: str) -> Dict[str, bool]:
        """Send booking confirmation notifications."""
        
        template_data = {
            "recipient_name": shipment.recipient.name,
            "sender_name": shipment.sender.name,
            "sender_city": shipment.sender.city,
            "recipient_city": shipment.recipient.city,
            "awb": shipment.carrier_info.tracking_number,
            "shipment_number": shipment.shipment_number,
            "carrier": shipment.carrier_info.carrier_name,
            "service_type": shipment.carrier_info.service_type,
            "estimated_delivery": shipment.carrier_info.estimated_delivery.strftime("%B %d, %Y") if shipment.carrier_info.estimated_delivery else "TBD",
            "tracking_url": tracking_url
        }
        
        results = {}
        
        # Send email notification
        if self.email_enabled:
            email_sent = await self._send_email(
                to_email=shipment.recipient.email,
                template=NotificationTemplate.BOOKING_CONFIRMATION,
                data=template_data
            )
            results["email"] = email_sent
        
        # Send SMS notification
        if self.sms_enabled:
            sms_sent = await self._send_sms(
                to_phone=shipment.recipient.phone,
                template=NotificationTemplate.BOOKING_CONFIRMATION,
                data=template_data
            )
            results["sms"] = sms_sent
        
        return results
    
    async def send_status_update(self, shipment: Shipment, latest_event, tracking_url: str) -> Dict[str, bool]:
        """Send status update notifications."""
        
        template_data = {
            "recipient_name": shipment.recipient.name,
            "awb": shipment.carrier_info.tracking_number,
            "shipment_number": shipment.shipment_number,
            "status": latest_event.status,
            "location": latest_event.location,
            "description": latest_event.description,
            "update_time": latest_event.timestamp.strftime("%B %d, %Y at %I:%M %p"),
            "tracking_url": tracking_url
        }
        
        results = {}
        
        # Send email notification
        if self.email_enabled:
            email_sent = await self._send_email(
                to_email=shipment.recipient.email,
                template=NotificationTemplate.STATUS_UPDATE,
                data=template_data
            )
            results["email"] = email_sent
        
        # Send SMS for important status updates only
        important_statuses = [
            ShipmentStatus.PICKED_UP,
            ShipmentStatus.OUT_FOR_DELIVERY,
            ShipmentStatus.DELIVERED
        ]
        
        if self.sms_enabled and shipment.status in important_statuses:
            sms_sent = await self._send_sms(
                to_phone=shipment.recipient.phone,
                template=NotificationTemplate.STATUS_UPDATE,
                data=template_data
            )
            results["sms"] = sms_sent
        
        return results
    
    async def send_delivery_alert(self, shipment: Shipment, tracking_url: str) -> Dict[str, bool]:
        """Send out for delivery alert."""
        
        template_data = {
            "recipient_name": shipment.recipient.name,
            "awb": shipment.carrier_info.tracking_number,
            "shipment_number": shipment.shipment_number,
            "delivery_time": "6:00 PM",  # Default delivery time
            "delivery_address": f"{shipment.recipient.street}, {shipment.recipient.city}",
            "tracking_url": tracking_url
        }
        
        results = {}
        
        # Send both email and SMS for delivery alerts
        if self.email_enabled:
            email_sent = await self._send_email(
                to_email=shipment.recipient.email,
                template=NotificationTemplate.DELIVERY_ALERT,
                data=template_data
            )
            results["email"] = email_sent
        
        if self.sms_enabled:
            sms_sent = await self._send_sms(
                to_phone=shipment.recipient.phone,
                template=NotificationTemplate.DELIVERY_ALERT,
                data=template_data
            )
            results["sms"] = sms_sent
        
        return results
    
    async def send_delivered_confirmation(self, shipment: Shipment, feedback_url: str, tracking_url: str) -> Dict[str, bool]:
        """Send delivery confirmation."""
        
        template_data = {
            "recipient_name": shipment.recipient.name,
            "awb": shipment.carrier_info.tracking_number,
            "shipment_number": shipment.shipment_number,
            "delivery_time": shipment.delivery_date.strftime("%B %d, %Y at %I:%M %p") if shipment.delivery_date else "Recently",
            "delivered_to": shipment.recipient.name,
            "delivery_location": f"{shipment.recipient.city}, {shipment.recipient.state}",
            "feedback_url": feedback_url,
            "tracking_url": tracking_url
        }
        
        results = {}
        
        if self.email_enabled:
            email_sent = await self._send_email(
                to_email=shipment.recipient.email,
                template=NotificationTemplate.DELIVERED_CONFIRMATION,
                data=template_data
            )
            results["email"] = email_sent
        
        if self.sms_enabled:
            sms_sent = await self._send_sms(
                to_phone=shipment.recipient.phone,
                template=NotificationTemplate.DELIVERED_CONFIRMATION,
                data=template_data
            )
            results["sms"] = sms_sent
        
        return results
    
    async def _send_email(self, to_email: str, template: NotificationTemplate, data: Dict[str, Any]) -> bool:
        """Send email notification (mock implementation)."""
        
        try:
            template_content = self.templates[template]
            subject = template_content["email_subject"].format(**data)
            body = template_content["email_body"].format(**data)
            
            # Mock email sending - replace with actual email service
            logger.info(f"Sending email to {to_email}")
            logger.info(f"Subject: {subject}")
            logger.info(f"Body: {body[:100]}...")  # Log first 100 chars
            
            # TODO: Integrate with actual email service (SendGrid, SES, etc.)
            # Example:
            # await email_client.send(to=to_email, subject=subject, html=body)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    async def _send_sms(self, to_phone: str, template: NotificationTemplate, data: Dict[str, Any]) -> bool:
        """Send SMS notification (mock implementation)."""
        
        try:
            template_content = self.templates[template]
            message = template_content["sms_body"].format(**data)
            
            # Mock SMS sending - replace with actual SMS service
            logger.info(f"Sending SMS to {to_phone}")
            logger.info(f"Message: {message}")
            
            # TODO: Integrate with actual SMS service (Twilio, AWS SNS, etc.)
            # Example:
            # await sms_client.send(to=to_phone, message=message)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send SMS to {to_phone}: {str(e)}")
            return False
    
    def get_notification_preferences(self, user_id: str) -> Dict[str, bool]:
        """Get user notification preferences (mock implementation)."""
        
        # TODO: Implement user preference storage
        return {
            "email_booking_confirmation": True,
            "email_status_updates": True,
            "email_delivery_alerts": True,
            "sms_delivery_alerts": True,
            "sms_important_updates": True,
            "push_notifications": False
        }
    
    async def queue_notification(self, notification_data: Dict[str, Any]) -> bool:
        """Queue notification for background processing."""
        
        try:
            # TODO: Implement notification queue (Redis, Celery, etc.)
            logger.info(f"Queuing notification: {notification_data}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue notification: {str(e)}")
            return False
    
    async def setup_tracking_notifications(
        self, 
        shipment_id: str, 
        email: Optional[str] = None, 
        phone: Optional[str] = None,
        notification_types: List[str] = ['email', 'sms'],
        db = None
    ) -> Dict[str, Any]:
        """Setup tracking notifications for a specific shipment."""
        
        try:
            import uuid
            notification_id = str(uuid.uuid4())
            
            # Create notification subscription record
            subscription = {
                "id": notification_id,
                "shipment_id": shipment_id,
                "email": email,
                "phone": phone,
                "notification_types": notification_types,
                "subscribed_at": datetime.utcnow(),
                "active": True,
                "preferences": {
                    "status_updates": True,
                    "delivery_alerts": True,
                    "delay_notifications": True
                }
            }
            
            if db:
                await db.notification_subscriptions.insert_one(subscription)
            
            logger.info(f"Setup tracking notifications for shipment {shipment_id}")
            
            return {
                "notification_id": notification_id,
                "shipment_id": shipment_id,
                "status": "active"
            }
            
        except Exception as e:
            logger.error(f"Failed to setup tracking notifications: {str(e)}")
            raise
    
    async def send_bulk_notifications(self, shipment_ids: List[str], template: NotificationTemplate, db = None) -> Dict[str, Any]:
        """Send bulk notifications for multiple shipments."""
        
        try:
            results = {
                "total_shipments": len(shipment_ids),
                "notifications_sent": 0,
                "notifications_failed": 0,
                "details": []
            }
            
            for shipment_id in shipment_ids:
                try:
                    # Get shipment data
                    if db:
                        shipment_data = await db.shipments.find_one({"id": shipment_id})
                        if shipment_data:
                            from models.shipment import Shipment
                            shipment = Shipment(**shipment_data)
                            
                            # Send notification based on template
                            tracking_url = f"https://xfas.in/track/{shipment.carrier_info.tracking_number}"
                            
                            if template == NotificationTemplate.STATUS_UPDATE and shipment.tracking_events:
                                notification_result = await self.send_status_update(
                                    shipment, shipment.tracking_events[-1], tracking_url
                                )
                            elif template == NotificationTemplate.DELIVERY_ALERT:
                                notification_result = await self.send_delivery_alert(shipment, tracking_url)
                            elif template == NotificationTemplate.DELIVERED_CONFIRMATION:
                                feedback_url = "https://xfas.in/feedback"
                                notification_result = await self.send_delivered_confirmation(
                                    shipment, feedback_url, tracking_url
                                )
                            else:
                                notification_result = await self.send_booking_confirmation(shipment, tracking_url)
                            
                            results["notifications_sent"] += 1
                            results["details"].append({
                                "shipment_id": shipment_id,
                                "awb": shipment.carrier_info.tracking_number,
                                "status": "sent",
                                "result": notification_result
                            })
                        
                except Exception as e:
                    results["notifications_failed"] += 1
                    results["details"].append({
                        "shipment_id": shipment_id,
                        "status": "failed",
                        "error": str(e)
                    })
            
            logger.info(f"Bulk notification completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to send bulk notifications: {str(e)}")
            raise
