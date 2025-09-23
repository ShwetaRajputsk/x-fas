from typing import List, Optional
import asyncio
from datetime import datetime, timedelta
import random

from models.quote import Quote, QuoteRequest, CarrierQuote, ServiceLevel, QuoteResponse
from services.carrier_service import CarrierService

class QuoteService:
    def __init__(self):
        self.carrier_service = CarrierService()
    
    async def generate_quote(self, request: QuoteRequest, user_id: Optional[str] = None) -> Quote:
        """Generate quotes from multiple carriers for a shipment request."""
        
        # Get quotes from all available carriers
        carrier_quotes = await self._get_carrier_quotes(request)
        
        # Create quote object
        quote = Quote(
            user_id=user_id,
            request=request,
            carrier_quotes=carrier_quotes
        )
        
        return quote
    
    async def _get_carrier_quotes(self, request: QuoteRequest) -> List[CarrierQuote]:
        """Get quotes from all available carriers."""
        
        # For now, we'll simulate carrier API calls with mock data
        # In production, this would make actual API calls to carrier systems
        
        carriers = [
            "XFas Self Network",
            "FedEx International", 
            "DHL Express",
            "Aramex International",
            "UPS Worldwide"
        ]
        
        quotes = []
        
        for carrier in carriers:
            try:
                quote = await self._get_mock_carrier_quote(carrier, request)
                if quote:
                    quotes.append(quote)
            except Exception as e:
                # Log error but don't fail entire quote process
                print(f"Error getting quote from {carrier}: {e}")
                continue
        
        # Sort by total cost
        quotes.sort(key=lambda x: x.total_cost)
        
        return quotes
    
    async def _get_mock_carrier_quote(self, carrier_name: str, request: QuoteRequest) -> Optional[CarrierQuote]:
        """Generate a mock quote for a carrier (replace with real API calls)."""
        
        # Simulate API call delay
        await asyncio.sleep(0.1)
        
        # Skip some carriers randomly to simulate availability
        if random.random() < 0.1:  # 10% chance to skip
            return None
        
        # Base rate calculation (mock logic)
        base_rate = self._calculate_base_rate(carrier_name, request)
        
        # Add surcharges
        fuel_surcharge = base_rate * 0.15  # 15% fuel surcharge
        insurance_cost = request.declared_value * 0.01 if request.insurance_required else 0
        additional_fees = 50 if request.signature_required else 0
        
        # Calculate total
        total_cost = base_rate + fuel_surcharge + insurance_cost + additional_fees
        
        # Determine service level and delivery time
        service_level, delivery_days = self._get_service_info(carrier_name)
        
        # Generate estimated delivery date
        estimated_delivery = datetime.utcnow() + timedelta(days=delivery_days)
        
        # Carrier-specific features
        features = self._get_carrier_features(carrier_name, service_level)
        
        return CarrierQuote(
            carrier_name=carrier_name,
            service_name=f"{carrier_name} {service_level.title()}",
            service_level=service_level,
            base_rate=base_rate,
            fuel_surcharge=fuel_surcharge,
            insurance_cost=insurance_cost,
            additional_fees=additional_fees,
            total_cost=total_cost,
            estimated_delivery_days=delivery_days,
            estimated_delivery_date=estimated_delivery,
            features=features,
            rate_id=f"{carrier_name}_{service_level}_{request.from_country}_{request.to_country}"
        )
    
    def _calculate_base_rate(self, carrier_name: str, request: QuoteRequest) -> float:
        """Calculate base shipping rate (mock implementation)."""
        
        # Base rates per kg by carrier (mock data)
        carrier_rates = {
            "XFas Self Network": 85,
            "FedEx International": 165,
            "DHL Express": 180,
            "Aramex International": 140,
            "UPS Worldwide": 170
        }
        
        base_rate_per_kg = carrier_rates.get(carrier_name, 150)
        
        # International vs domestic multiplier
        if request.from_country != request.to_country:
            base_rate_per_kg *= 2.5
        
        # Calculate by weight
        weight = max(request.weight, 0.5)  # Minimum 0.5kg
        
        # Volumetric weight calculation
        if request.length and request.width and request.height:
            volumetric_weight = (request.length * request.width * request.height) / 5000  # cm³ to kg
            weight = max(weight, volumetric_weight)
        
        base_rate = weight * base_rate_per_kg
        
        # Minimum charge
        minimum_charge = 200 if request.from_country != request.to_country else 100
        
        return max(base_rate, minimum_charge)
    
    def _get_service_info(self, carrier_name: str) -> tuple[ServiceLevel, int]:
        """Get service level and delivery days for carrier."""
        
        service_map = {
            "XFas Self Network": (ServiceLevel.STANDARD, 3),
            "FedEx International": (ServiceLevel.EXPRESS, 3),
            "DHL Express": (ServiceLevel.EXPRESS, 2),
            "Aramex International": (ServiceLevel.STANDARD, 5),
            "UPS Worldwide": (ServiceLevel.STANDARD, 4)
        }
        
        return service_map.get(carrier_name, (ServiceLevel.STANDARD, 5))
    
    def _get_carrier_features(self, carrier_name: str, service_level: ServiceLevel) -> List[str]:
        """Get features for carrier service."""
        
        features = ["Real-time tracking", "Insurance available"]
        
        if service_level in [ServiceLevel.EXPRESS, ServiceLevel.OVERNIGHT]:
            features.extend(["Priority handling", "SMS notifications"])
        
        if carrier_name in ["DHL Express", "FedEx International"]:
            features.extend(["Customs clearance", "Duty management"])
        
        if carrier_name == "XFas Self Network":
            features.extend(["COD available", "Hyperlocal delivery", "Dedicated support"])
        
        if carrier_name == "UPS Worldwide":
            features.append("Carbon neutral shipping")
        
        return features
    
    def process_quote_response(self, quote: Quote) -> QuoteResponse:
        """Process quote into response format with additional insights."""
        
        carrier_quotes = quote.carrier_quotes
        
        # Find best options
        cheapest_quote = min(carrier_quotes, key=lambda x: x.total_cost) if carrier_quotes else None
        fastest_quote = min(carrier_quotes, key=lambda x: x.estimated_delivery_days) if carrier_quotes else None
        
        # AI-driven recommendations
        recommended_quote = self._get_ai_recommendation(carrier_quotes, quote.request)
        
        return QuoteResponse(
            id=quote.id,
            request=quote.request,
            carrier_quotes=carrier_quotes,
            status=quote.status,
            created_at=quote.created_at,
            expires_at=quote.expires_at,
            total_quotes=len(carrier_quotes),
            cheapest_quote=cheapest_quote,
            fastest_quote=fastest_quote,
            recommended_quote=recommended_quote
        )
    
    def _get_ai_recommendation(self, carrier_quotes: List[CarrierQuote], request: QuoteRequest) -> Optional[CarrierQuote]:
        """AI-driven recommendation based on request characteristics."""
        if not carrier_quotes:
            return None
        
        # Score each carrier based on multiple factors
        scored_quotes = []
        
        for quote in carrier_quotes:
            score = 0
            
            # Base scoring factors
            if quote.service_level == ServiceLevel.EXPRESS:
                score += 3
            elif quote.service_level == ServiceLevel.STANDARD:
                score += 2
            else:
                score += 1
            
            # Cost efficiency (inverse relationship)
            max_cost = max(q.total_cost for q in carrier_quotes)
            min_cost = min(q.total_cost for q in carrier_quotes)
            if max_cost > min_cost:
                cost_score = 5 * (1 - (quote.total_cost - min_cost) / (max_cost - min_cost))
                score += cost_score
            
            # Speed factor
            min_days = min(q.estimated_delivery_days for q in carrier_quotes)
            max_days = max(q.estimated_delivery_days for q in carrier_quotes)
            if max_days > min_days:
                speed_score = 3 * (1 - (quote.estimated_delivery_days - min_days) / (max_days - min_days))
                score += speed_score
            
            # Carrier-specific bonuses
            if quote.carrier_name == "XFas Self Network":
                score += 2  # Bonus for own network
            
            # High-value shipment considerations
            if request.declared_value and request.declared_value > 10000:
                if "Insurance available" in quote.features:
                    score += 2
                if quote.service_level == ServiceLevel.EXPRESS:
                    score += 1
            
            # International shipment considerations
            if request.from_country != request.to_country:
                if "Customs clearance" in quote.features:
                    score += 2
            
            scored_quotes.append((quote, score))
        
        # Return the highest scored quote
        return max(scored_quotes, key=lambda x: x[1])[0]