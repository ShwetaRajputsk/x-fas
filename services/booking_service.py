from typing import Optional, List
from datetime import datetime, timedelta
import random
import string

from models.shipment import (
    Shipment, ShipmentCreate, ShipmentResponse, 
    CarrierInfo, PaymentInfo, TrackingEvent,
    ShipmentStatus, PaymentStatus, ServiceType
)
from models.quote import CarrierQuote

class BookingService:
    def __init__(self):
        pass
    
    async def create_booking(self, booking_request: ShipmentCreate, user_id: str, carrier_quote: Optional[CarrierQuote] = None) -> Shipment:
        """Create a new shipment booking."""
        
        # Generate AWB/tracking number
        awb = self._generate_awb(booking_request.carrier_name)
        
        # Create carrier info
        carrier_info = CarrierInfo(
            carrier_name=booking_request.carrier_name,
            service_type=booking_request.service_type,
            tracking_number=awb,
            estimated_delivery=datetime.utcnow() + timedelta(days=self._get_estimated_days(booking_request.carrier_name)),
            carrier_reference=f"{booking_request.carrier_name}_{awb}"
        )
        
        # Calculate payment amount (use quote if available, otherwise estimate)
        if carrier_quote:
            payment_amount = carrier_quote.total_cost
        else:
            payment_amount = self._estimate_cost(booking_request)
        
        # Create payment info (initially pending)
        payment_info = PaymentInfo(
            amount=payment_amount,
            status=PaymentStatus.PENDING
        )
        
        # Create initial tracking event
        initial_event = TrackingEvent(
            timestamp=datetime.utcnow(),
            status="Booking Confirmed",
            location="XFas Logistics Hub",
            description=f"Shipment booked with {booking_request.carrier_name}. AWB: {awb}"
        )
        
        # Create shipment
        shipment = Shipment(
            user_id=user_id,
            quote_id=booking_request.quote_id,
            sender=booking_request.sender,
            recipient=booking_request.recipient,
            package_info=booking_request.package_info,
            carrier_info=carrier_info,
            status=ShipmentStatus.BOOKED,
            tracking_events=[initial_event],
            payment_info=payment_info,
            insurance_required=booking_request.insurance_required,
            signature_required=booking_request.signature_required,
            notes=booking_request.notes,
            custom_reference=booking_request.custom_reference
        )
        
        return shipment
    
    def _generate_awb(self, carrier_name: str) -> str:
        """Generate a mock AWB/tracking number."""
        prefix_map = {
            "XFas Self Network": "XF",
            "FedEx International": "FX",
            "DHL Express": "DH", 
            "Aramex International": "AR",
            "UPS Worldwide": "UP"
        }
        
        prefix = prefix_map.get(carrier_name, "XF")
        random_digits = ''.join(random.choices(string.digits, k=10))
        return f"{prefix}{random_digits}"
    
    def _get_estimated_days(self, carrier_name: str) -> int:
        """Get estimated delivery days for carrier."""
        days_map = {
            "XFas Self Network": 3,
            "FedEx International": 3,
            "DHL Express": 2,
            "Aramex International": 5,
            "UPS Worldwide": 4
        }
        return days_map.get(carrier_name, 5)
    
    def _estimate_cost(self, booking_request: ShipmentCreate) -> float:
        """Estimate cost if no quote provided."""
        # Basic cost estimation
        weight = booking_request.package_info.dimensions.weight
        base_cost = weight * 150  # ₹150 per kg base rate
        
        # Carrier-specific multipliers
        carrier_multipliers = {
            "XFas Self Network": 0.8,
            "FedEx International": 1.3,
            "DHL Express": 1.4,
            "Aramex International": 1.1,
            "UPS Worldwide": 1.2
        }
        
        multiplier = carrier_multipliers.get(booking_request.carrier_name, 1.0)
        return max(base_cost * multiplier, 200)  # Minimum ₹200
    
    async def update_shipment_status(self, shipment: Shipment, new_status: ShipmentStatus, location: str = "In Transit", description: str = "") -> Shipment:
        """Update shipment status and add tracking event."""
        
        if not description:
            description = f"Shipment status updated to {new_status.value}"
        
        # Create tracking event
        tracking_event = TrackingEvent(
            timestamp=datetime.utcnow(),
            status=new_status.value.replace('_', ' ').title(),
            location=location,
            description=description
        )
        
        # Update shipment
        shipment.status = new_status
        shipment.tracking_events.append(tracking_event)
        shipment.updated_at = datetime.utcnow()
        
        # Set delivery date if delivered
        if new_status == ShipmentStatus.DELIVERED:
            shipment.delivery_date = datetime.utcnow()
        
        return shipment
    
    def process_shipment_response(self, shipment: Shipment) -> ShipmentResponse:
        """Process shipment into response format."""
        return ShipmentResponse(
            id=shipment.id,
            shipment_number=shipment.shipment_number,
            status=shipment.status,
            sender=shipment.sender,
            recipient=shipment.recipient,
            package_info=shipment.package_info,
            carrier_info=shipment.carrier_info,
            payment_info=shipment.payment_info,
            tracking_events=shipment.tracking_events,
            created_at=shipment.created_at,
            estimated_delivery=shipment.carrier_info.estimated_delivery
        )
    
    async def simulate_shipment_progress(self, shipment: Shipment) -> Shipment:
        """Simulate shipment progress for demo purposes."""
        # This would be called by a background job in real implementation
        # For now, we'll use it to manually progress shipments
        
        current_status = shipment.status
        
        status_progression = [
            ShipmentStatus.BOOKED,
            ShipmentStatus.PICKUP_SCHEDULED,
            ShipmentStatus.PICKED_UP,
            ShipmentStatus.IN_TRANSIT,
            ShipmentStatus.OUT_FOR_DELIVERY,
            ShipmentStatus.DELIVERED
        ]
        
        try:
            current_index = status_progression.index(current_status)
            if current_index < len(status_progression) - 1:
                next_status = status_progression[current_index + 1]
                return await self.update_shipment_status(
                    shipment, 
                    next_status,
                    location="Transit Hub",
                    description=f"Shipment progressed to {next_status.value.replace('_', ' ').title()}"
                )
        except ValueError:
            pass
        
        return shipment