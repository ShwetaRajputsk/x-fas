from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel
from datetime import datetime
import io
import uuid

from models.user import User
from models.shipment import Shipment, ShipmentStatus, ShipmentUpdate
from services.tracking_service import TrackingService
from services.notification_service import NotificationService
from utils.auth import get_current_user

# Database dependency
async def get_database() -> AsyncIOMotorDatabase:
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    return client[os.environ.get('DB_NAME', 'xfas_logistics')]

router = APIRouter(prefix="/orders", tags=["Order Management"])

class CancelOrderRequest(BaseModel):
    reason: str
    refund_requested: bool = True

class RescheduleOrderRequest(BaseModel):
    new_pickup_date: datetime
    reason: Optional[str] = None

@router.get("/my-shipments")
async def get_user_shipments(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user's shipments with filtering and pagination."""
    
    try:
        # Build query
        query = {"user_id": current_user.id}
        
        if status_filter:
            query["status"] = status_filter
        
        # Get shipments with pagination
        shipments_cursor = db.shipments.find(query).sort("created_at", -1).limit(limit).skip(offset)
        shipments_data = await shipments_cursor.to_list(length=limit)
        
        # Get total count
        total_count = await db.shipments.count_documents(query)
        
        # Process shipments with enhanced tracking info
        tracking_service = TrackingService()
        processed_shipments = []
        
        for shipment_data in shipments_data:
            shipment = Shipment(**shipment_data)
            enhanced_info = tracking_service.get_enhanced_tracking_info(shipment)
            
            # Add order management specific info
            enhanced_info.update({
                "can_cancel": shipment.status in [ShipmentStatus.DRAFT, ShipmentStatus.BOOKED, ShipmentStatus.PICKUP_SCHEDULED],
                "can_reschedule": shipment.status in [ShipmentStatus.BOOKED, ShipmentStatus.PICKUP_SCHEDULED],
                "invoice_available": shipment.status not in [ShipmentStatus.DRAFT, ShipmentStatus.CANCELLED],
                "label_available": shipment.status not in [ShipmentStatus.DRAFT, ShipmentStatus.CANCELLED],
                "payment_status": shipment.payment_info.status,
                "total_amount": shipment.payment_info.amount
            })
            
            processed_shipments.append(enhanced_info)
        
        # Get status summary
        status_summary = await _get_user_status_summary(current_user.id, db)
        
        return {
            "success": True,
            "data": {
                "shipments": processed_shipments,
                "pagination": {
                    "total_count": total_count,
                    "limit": limit,
                    "offset": offset,
                    "has_more": total_count > (offset + limit)
                },
                "status_summary": status_summary
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching shipments: {str(e)}"
        )

@router.get("/{shipment_id}")
async def get_shipment_details(
    shipment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get detailed information about a specific shipment."""
    
    try:
        # Find shipment
        shipment_data = await db.shipments.find_one({
            "id": shipment_id,
            "user_id": current_user.id
        })
        
        if not shipment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found"
            )
        
        shipment = Shipment(**shipment_data)
        tracking_service = TrackingService()
        
        # Get enhanced tracking info
        enhanced_info = tracking_service.get_enhanced_tracking_info(shipment)
        
        # Add detailed order management info
        enhanced_info.update({
            "can_cancel": shipment.status in [ShipmentStatus.DRAFT, ShipmentStatus.BOOKED, ShipmentStatus.PICKUP_SCHEDULED],
            "can_reschedule": shipment.status in [ShipmentStatus.BOOKED, ShipmentStatus.PICKUP_SCHEDULED],
            "invoice_available": shipment.status not in [ShipmentStatus.DRAFT, ShipmentStatus.CANCELLED],
            "label_available": shipment.status not in [ShipmentStatus.DRAFT, ShipmentStatus.CANCELLED],
            "cancellation_deadline": _get_cancellation_deadline(shipment),
            "reschedule_options": _get_reschedule_options(shipment),
            "payment_details": {
                "amount": shipment.payment_info.amount,
                "currency": shipment.payment_info.currency,
                "status": shipment.payment_info.status,
                "method": shipment.payment_info.payment_method,
                "transaction_id": shipment.payment_info.transaction_id
            },
            "documents": {
                "invoice_url": f"/orders/{shipment_id}/invoice",
                "label_url": f"/orders/{shipment_id}/label",
                "receipt_url": f"/orders/{shipment_id}/receipt"
            }
        })
        
        return {
            "success": True,
            "data": enhanced_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching shipment details: {str(e)}"
        )

@router.post("/{shipment_id}/cancel")
async def cancel_shipment(
    shipment_id: str,
    cancel_request: CancelOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Cancel a shipment."""
    
    try:
        # Find and validate shipment
        shipment_data = await db.shipments.find_one({
            "id": shipment_id,
            "user_id": current_user.id
        })
        
        if not shipment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found"
            )
        
        shipment = Shipment(**shipment_data)
        
        # Check if cancellation is allowed
        if shipment.status not in [ShipmentStatus.DRAFT, ShipmentStatus.BOOKED, ShipmentStatus.PICKUP_SCHEDULED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shipment cannot be cancelled at this stage"
            )
        
        # Update shipment status
        cancellation_data = {
            "status": ShipmentStatus.CANCELLED.value,
            "updated_at": datetime.utcnow(),
            "cancellation_reason": cancel_request.reason,
            "cancelled_at": datetime.utcnow(),
            "cancelled_by": current_user.id,
            "refund_requested": cancel_request.refund_requested
        }
        
        await db.shipments.update_one(
            {"id": shipment_id},
            {"$set": cancellation_data}
        )
        
        # Add tracking event
        from models.shipment import TrackingEvent
        tracking_event = TrackingEvent(
            timestamp=datetime.utcnow(),
            status="CANCELLED",
            location="Customer Request",
            description=f"Shipment cancelled by customer. Reason: {cancel_request.reason}"
        )
        
        await db.shipments.update_one(
            {"id": shipment_id},
            {"$push": {"tracking_events": tracking_event.dict()}}
        )
        
        # Process refund if requested
        refund_status = "pending"
        if cancel_request.refund_requested:
            # TODO: Integrate with payment gateway for refund processing
            refund_status = "processing"
        
        # Send cancellation notification
        notification_service = NotificationService()
        # TODO: Add cancellation notification template
        
        return {
            "success": True,
            "data": {
                "message": "Shipment cancelled successfully",
                "shipment_id": shipment_id,
                "status": "cancelled",
                "refund_status": refund_status,
                "estimated_refund_time": "3-5 business days" if cancel_request.refund_requested else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error cancelling shipment: {str(e)}"
        )

@router.post("/{shipment_id}/reschedule")
async def reschedule_shipment(
    shipment_id: str,
    reschedule_request: RescheduleOrderRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Reschedule a shipment pickup."""
    
    try:
        # Find and validate shipment
        shipment_data = await db.shipments.find_one({
            "id": shipment_id,
            "user_id": current_user.id
        })
        
        if not shipment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found"
            )
        
        shipment = Shipment(**shipment_data)
        
        # Check if rescheduling is allowed
        if shipment.status not in [ShipmentStatus.BOOKED, ShipmentStatus.PICKUP_SCHEDULED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shipment cannot be rescheduled at this stage"
            )
        
        # Validate new pickup date
        if reschedule_request.new_pickup_date <= datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New pickup date must be in the future"
            )
        
        # Update shipment
        reschedule_data = {
            "pickup_date": reschedule_request.new_pickup_date,
            "updated_at": datetime.utcnow(),
            "rescheduled_at": datetime.utcnow(),
            "reschedule_reason": reschedule_request.reason,
            "reschedule_count": shipment_data.get("reschedule_count", 0) + 1
        }
        
        await db.shipments.update_one(
            {"id": shipment_id},
            {"$set": reschedule_data}
        )
        
        # Add tracking event
        from models.shipment import TrackingEvent
        tracking_event = TrackingEvent(
            timestamp=datetime.utcnow(),
            status="RESCHEDULED",
            location="Customer Request",
            description=f"Pickup rescheduled to {reschedule_request.new_pickup_date.strftime('%B %d, %Y')}"
        )
        
        await db.shipments.update_one(
            {"id": shipment_id},
            {"$push": {"tracking_events": tracking_event.dict()}}
        )
        
        # Send reschedule notification
        # TODO: Add reschedule notification template
        
        return {
            "success": True,
            "data": {
                "message": "Shipment rescheduled successfully",
                "shipment_id": shipment_id,
                "new_pickup_date": reschedule_request.new_pickup_date,
                "status": "rescheduled"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error rescheduling shipment: {str(e)}"
        )

@router.get("/{shipment_id}/invoice")
async def download_invoice(
    shipment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Download shipment invoice."""
    
    try:
        # Find shipment
        shipment_data = await db.shipments.find_one({
            "id": shipment_id,
            "user_id": current_user.id
        })
        
        if not shipment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found"
            )
        
        shipment = Shipment(**shipment_data)
        
        # Check if invoice is available
        if shipment.status in [ShipmentStatus.DRAFT, ShipmentStatus.CANCELLED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invoice not available for this shipment"
            )
        
        # Generate invoice (mock implementation)
        invoice_content = _generate_invoice_pdf(shipment)
        
        return Response(
            content=invoice_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=invoice_{shipment.shipment_number}.pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating invoice: {str(e)}"
        )

@router.get("/{shipment_id}/label")
async def download_shipping_label(
    shipment_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Download shipping label."""
    
    try:
        # Find shipment
        shipment_data = await db.shipments.find_one({
            "id": shipment_id,
            "user_id": current_user.id
        })
        
        if not shipment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Shipment not found"
            )
        
        shipment = Shipment(**shipment_data)
        
        # Check if label is available
        if shipment.status in [ShipmentStatus.DRAFT, ShipmentStatus.CANCELLED]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Shipping label not available for this shipment"
            )
        
        # Generate shipping label (mock implementation)
        label_content = _generate_shipping_label_pdf(shipment)
        
        return Response(
            content=label_content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=label_{shipment.carrier_info.tracking_number}.pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating shipping label: {str(e)}"
        )

@router.get("/analytics/summary")
async def get_order_analytics(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get order analytics summary for user."""
    
    try:
        from datetime import timedelta
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Get shipments in date range
        query = {
            "user_id": current_user.id,
            "created_at": {"$gte": start_date}
        }
        
        shipments_cursor = db.shipments.find(query)
        shipments_data = await shipments_cursor.to_list(length=1000)
        
        analytics = {
            "period": f"Last {days} days",
            "total_shipments": len(shipments_data),
            "total_spent": 0,
            "status_breakdown": {},
            "carrier_usage": {},
            "average_shipment_value": 0,
            "delivery_success_rate": 0
        }
        
        if shipments_data:
            total_amount = 0
            delivered_count = 0
            
            for shipment_data in shipments_data:
                # Status breakdown
                status = shipment_data.get('status', 'unknown')
                analytics["status_breakdown"][status] = analytics["status_breakdown"].get(status, 0) + 1
                
                # Carrier usage
                carrier = shipment_data.get('carrier_info', {}).get('carrier_name', 'unknown')
                analytics["carrier_usage"][carrier] = analytics["carrier_usage"].get(carrier, 0) + 1
                
                # Total spent
                amount = shipment_data.get('payment_info', {}).get('amount', 0)
                total_amount += amount
                
                # Delivery success
                if status == ShipmentStatus.DELIVERED.value:
                    delivered_count += 1
            
            analytics["total_spent"] = total_amount
            analytics["average_shipment_value"] = total_amount / len(shipments_data)
            analytics["delivery_success_rate"] = (delivered_count / len(shipments_data)) * 100
        
        return {
            "success": True,
            "data": analytics
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching analytics: {str(e)}"
        )

# Helper functions
async def _get_user_status_summary(user_id: str, db) -> Dict[str, int]:
    """Get user's shipment status summary."""
    
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1}
        }}
    ]
    
    cursor = db.shipments.aggregate(pipeline)
    status_data = await cursor.to_list(length=20)
    
    summary = {}
    for item in status_data:
        summary[item["_id"]] = item["count"]
    
    return summary

def _get_cancellation_deadline(shipment: Shipment) -> Optional[datetime]:
    """Get cancellation deadline for a shipment."""
    
    if shipment.pickup_date:
        # Allow cancellation up to 2 hours before pickup
        from datetime import timedelta
        return shipment.pickup_date - timedelta(hours=2)
    
    return None

def _get_reschedule_options(shipment: Shipment) -> Dict[str, Any]:
    """Get reschedule options for a shipment."""
    
    from datetime import timedelta
    
    today = datetime.utcnow()
    
    return {
        "earliest_date": today + timedelta(days=1),
        "latest_date": today + timedelta(days=30),
        "excluded_dates": [],  # Holidays, weekends, etc.
        "time_slots": [
            {"slot": "morning", "time": "9:00 AM - 12:00 PM"},
            {"slot": "afternoon", "time": "1:00 PM - 5:00 PM"},
            {"slot": "evening", "time": "5:00 PM - 8:00 PM"}
        ]
    }

def _generate_invoice_pdf(shipment: Shipment) -> bytes:
    """Generate professional invoice PDF using reportlab."""
    
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib import colors
    from reportlab.lib.units import inch, cm
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
    from reportlab.graphics.shapes import Drawing, Line
    from reportlab.platypus.flowables import HRFlowable
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4,
        topMargin=1*inch,
        bottomMargin=0.8*inch,
        leftMargin=0.8*inch,
        rightMargin=0.8*inch
    )
    
    # Custom styles
    styles = getSampleStyleSheet()
    
    # Company header style
    company_style = ParagraphStyle(
        'CompanyHeader',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.HexColor('#1a365d'),
        spaceAfter=6,
        fontName='Helvetica-Bold'
    )
    
    # Invoice title style
    invoice_title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Title'],
        fontSize=14,
        textColor=colors.HexColor('#2d3748'),
        spaceAfter=20,
        fontName='Helvetica-Bold',
        alignment=TA_RIGHT
    )
    
    # Section heading style
    section_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontSize=12,
        textColor=colors.HexColor('#2d3748'),
        spaceAfter=8,
        spaceBefore=15,
        fontName='Helvetica-Bold',
        backColor=colors.HexColor('#f7fafc'),
        borderPadding=8
    )
    
    # Address style
    address_style = ParagraphStyle(
        'AddressStyle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#4a5568'),
        fontName='Helvetica'
    )
    
    # Build content
    content = []
    
    # Header section with company info and invoice details
    company_info = ParagraphStyle(
        'CompanyInfo',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#1a365d'),
        fontName='Helvetica'
    )
    
    invoice_details = ParagraphStyle(
        'InvoiceDetails',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#2d3748'),
        fontName='Helvetica',
        alignment=TA_RIGHT
    )
    
    header_data = [[
        Paragraph("<b>XFas Logistics Private Limited</b><br/>Logistics &amp; Supply Chain Solutions<br/>Mumbai, Maharashtra 400001<br/>India<br/>GST: 27XXXXX1234X1ZX<br/>Phone: +91-22-1234-5678<br/>Email: billing@xfaslogistics.com", company_info),
        Paragraph(f"<b>INVOICE</b><br/><br/><b>Invoice No:</b> INV-{shipment.shipment_number}<br/><b>Invoice Date:</b> {datetime.utcnow().strftime('%d %B, %Y')}<br/><b>AWB No:</b> {shipment.carrier_info.tracking_number or 'N/A'}<br/><b>Due Date:</b> {datetime.utcnow().strftime('%d %B, %Y')}", invoice_details)
    ]]
    
    header_table = Table(header_data, colWidths=[4*inch, 3*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
    ]))
    
    content.append(header_table)
    content.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#e2e8f0')))
    content.append(Spacer(1, 20))
    
    # Bill To and Ship From sections
    section_header_style = ParagraphStyle(
        'SectionHeader',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#2d3748'),
        fontName='Helvetica-Bold',
        spaceAfter=5
    )
    
    addresses_data = [[
        Paragraph("BILL TO:", section_header_style),
        Paragraph("SHIP FROM:", section_header_style)
    ], [
        Paragraph(f"<b>{shipment.recipient.name}</b><br/>{shipment.recipient.street}<br/>{shipment.recipient.city}, {shipment.recipient.state} {shipment.recipient.postal_code}<br/>Phone: {shipment.recipient.phone}<br/>Email: {shipment.recipient.email}", address_style),
        Paragraph(f"<b>{shipment.sender.name}</b><br/>{shipment.sender.street}<br/>{shipment.sender.city}, {shipment.sender.state} {shipment.sender.postal_code}<br/>Phone: {shipment.sender.phone}<br/>Email: {shipment.sender.email}", address_style)
    ]]
    
    addresses_table = Table(addresses_data, colWidths=[3.5*inch, 3.5*inch])
    addresses_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f7fafc')),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
    ]))
    
    content.append(addresses_table)
    content.append(Spacer(1, 25))
    
    # Service details table
    service_data = [
        ['Service Description', 'Carrier', 'AWB Number', 'Amount (₹)'],
        [f"{shipment.carrier_info.service_type.value.title() if hasattr(shipment.carrier_info.service_type, 'value') else str(shipment.carrier_info.service_type).title()} Shipping", shipment.carrier_info.carrier_name, shipment.carrier_info.tracking_number or 'N/A', f"{shipment.payment_info.amount:.2f}"]
    ]
    
    service_table = Table(service_data, colWidths=[2.5*inch, 1.5*inch, 2*inch, 1*inch])
    service_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d3748')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ffffff')),
    ]))
    
    content.append(service_table)
    content.append(Spacer(1, 15))
    
    # Package details
    package_data = [
        ['Package Details', 'Value'],
        ['Weight', f"{shipment.package_info.dimensions.weight} kg"],
        ['Dimensions (L×W×H)', f"{shipment.package_info.dimensions.length}×{shipment.package_info.dimensions.width}×{shipment.package_info.dimensions.height} cm"],
        ['Declared Value', f"₹{shipment.package_info.declared_value:.2f}"],
        ['Package Type', shipment.package_info.type.value if hasattr(shipment.package_info.type, 'value') else str(shipment.package_info.type).title()]
    ]
    
    package_table = Table(package_data, colWidths=[3*inch, 2*inch])
    package_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f7fafc')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
    ]))
    
    content.append(package_table)
    content.append(Spacer(1, 25))
    
    # Payment summary
    summary_data = [
        ['', 'Subtotal:', f"₹{shipment.payment_info.amount:.2f}"],
        ['', 'Tax (18% GST):', f"₹{shipment.payment_info.amount * 0.18:.2f}"],
        ['', 'TOTAL AMOUNT:', f"₹{shipment.payment_info.amount * 1.18:.2f}"]
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch, 1.5*inch])
    summary_table.setStyle(TableStyle([
        ('FONTNAME', (1, 0), (-1, 1), 'Helvetica'),
        ('FONTNAME', (1, 2), (-1, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (1, 0), (-1, -1), 11),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (1, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (1, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (1, 0), (-1, -1), 8),
        ('BACKGROUND', (1, 2), (-1, 2), colors.HexColor('#2d3748')),
        ('TEXTCOLOR', (1, 2), (-1, 2), colors.whitesmoke),
        ('LINEABOVE', (1, 2), (-1, 2), 2, colors.HexColor('#2d3748')),
    ]))
    
    content.append(summary_table)
    content.append(Spacer(1, 30))
    
    # Payment information
    payment_info = f"""
    <b>Payment Information:</b><br/>
    Payment Method: {(shipment.payment_info.payment_method or 'N/A').title()}<br/>
    Payment Status: <b>{shipment.payment_info.status.value.title() if hasattr(shipment.payment_info.status, 'value') else str(shipment.payment_info.status).title()}</b><br/>
    Transaction ID: {shipment.payment_info.transaction_id or 'N/A'}<br/>
    Currency: {shipment.payment_info.currency}
    """
    
    content.append(Paragraph(payment_info, address_style))
    content.append(Spacer(1, 20))
    
    # Terms and footer
    terms_text = """
    <b>Terms & Conditions:</b><br/>
    • Payment is due within 30 days of invoice date<br/>
    • All shipments are subject to XFas Logistics terms and conditions<br/>
    • For any queries, please contact our customer service at support@xfaslogistics.com<br/>
    • This is a computer-generated invoice and does not require a signature
    """
    
    content.append(Paragraph(terms_text, ParagraphStyle(
        'Terms',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#718096'),
        fontName='Helvetica',
        spaceAfter=15
    )))
    
    # Footer
    footer_text = f"Generated on {datetime.utcnow().strftime('%d %B, %Y at %I:%M %p IST')} | XFas Logistics Private Limited"
    content.append(Paragraph(footer_text, ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#a0aec0'),
        fontName='Helvetica',
        alignment=TA_CENTER
    )))
    
    # Build PDF
    doc.build(content)
    buffer.seek(0)
    return buffer.getvalue()

def _generate_shipping_label_pdf(shipment: Shipment) -> bytes:
    """Generate professional shipping label PDF using reportlab."""
    
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch, cm
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
    from reportlab.graphics.shapes import Drawing, Rect, String
    from reportlab.graphics import renderPDF
    from reportlab.platypus.flowables import HRFlowable
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        topMargin=0.3*inch,
        bottomMargin=0.3*inch,
        leftMargin=0.3*inch,
        rightMargin=0.3*inch
    )
    
    # Custom styles
    styles = getSampleStyleSheet()
    
    # Title style for shipping label
    title_style = ParagraphStyle(
        'LabelTitle',
        parent=styles['Title'],
        fontSize=16,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1a365d'),
        alignment=TA_CENTER,
        spaceAfter=10
    )
    
    # Company header style
    company_style = ParagraphStyle(
        'CompanyHeader',
        parent=styles['Normal'],
        fontSize=12,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#2d3748'),
        alignment=TA_CENTER,
        spaceAfter=15
    )
    
    # AWB style
    awb_style = ParagraphStyle(
        'AWBStyle',
        parent=styles['Normal'],
        fontSize=14,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1a365d'),
        alignment=TA_CENTER,
        spaceAfter=5
    )
    
    # Address styles
    address_header_style = ParagraphStyle(
        'AddressHeader',
        parent=styles['Normal'],
        fontSize=12,
        fontName='Helvetica-Bold',
        textColor=colors.whitesmoke,
        alignment=TA_CENTER
    )
    
    address_content_style = ParagraphStyle(
        'AddressContent',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica',
        textColor=colors.HexColor('#2d3748')
    )
    
    # Build content
    content = []
    
    # Header with company info
    content.append(Paragraph("XFAS LOGISTICS", company_style))
    content.append(Paragraph("SHIPPING LABEL", title_style))
    content.append(HRFlowable(width="100%", thickness=3, color=colors.HexColor('#1a365d')))
    content.append(Spacer(1, 15))
    
    # AWB number with barcode simulation
    content.append(Paragraph(f"AWB: {shipment.carrier_info.tracking_number or 'N/A'}", awb_style))
    
    # Barcode placeholder (using text representation)
    barcode_text = f"||||| {shipment.carrier_info.tracking_number} |||||"
    content.append(Paragraph(barcode_text, ParagraphStyle(
        'Barcode',
        parent=styles['Normal'],
        fontSize=14,
        fontName='Courier-Bold',
        alignment=TA_CENTER,
        spaceAfter=20
    )))
    
    # Service information bar  
    service_data = [[
        f"Carrier: {shipment.carrier_info.carrier_name}",
        f"Service: {shipment.carrier_info.service_type.value.title() if hasattr(shipment.carrier_info.service_type, 'value') else str(shipment.carrier_info.service_type).title()}",
        f"Date: {datetime.utcnow().strftime('%d %b %Y')}"
    ]]
    
    service_table = Table(service_data, colWidths=[2.2*inch, 2.2*inch, 2.2*inch])
    service_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f7fafc')),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#e2e8f0')),
    ]))
    
    content.append(service_table)
    content.append(Spacer(1, 20))
    
    # From and To addresses in professional layout
    addresses_data = [
        [Paragraph("FROM", address_header_style), Paragraph("TO", address_header_style)],
        [
            Paragraph(f"{shipment.sender.name}<br/>{shipment.sender.street}<br/>{shipment.sender.city}, {shipment.sender.state}<br/>{shipment.sender.postal_code}<br/>Phone: {shipment.sender.phone}", address_content_style),
            Paragraph(f"{shipment.recipient.name}<br/>{shipment.recipient.street}<br/>{shipment.recipient.city}, {shipment.recipient.state}<br/>{shipment.recipient.postal_code}<br/>Phone: {shipment.recipient.phone}", address_content_style)
        ]
    ]
    
    addresses_table = Table(addresses_data, colWidths=[3.2*inch, 3.2*inch])
    addresses_table.setStyle(TableStyle([
        # Header row styling
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d3748')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        
        # Content styling
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        
        # General styling
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 1), (-1, -1), 20),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 20),
        ('GRID', (0, 0), (-1, -1), 2, colors.HexColor('#2d3748')),
    ]))
    
    content.append(addresses_table)
    content.append(Spacer(1, 20))
    
    # Package details in a professional grid
    package_data = [
        ["PACKAGE INFORMATION", "", "", ""],
        ["Weight", f"{shipment.package_info.dimensions.weight} kg", "Dimensions", f"{shipment.package_info.dimensions.length}×{shipment.package_info.dimensions.width}×{shipment.package_info.dimensions.height} cm"],
        ["Package Type", shipment.package_info.type.value if hasattr(shipment.package_info.type, 'value') else str(shipment.package_info.type).title(), "Declared Value", f"₹{shipment.package_info.declared_value:.2f}"],
        ["Special Instructions", "Handle with care - Fragile contents", "COD Amount", "N/A"]
    ]
    
    package_table = Table(package_data, colWidths=[1.6*inch, 1.6*inch, 1.6*inch, 1.6*inch])
    package_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a365d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('SPAN', (0, 0), (3, 0)),
        ('ALIGN', (0, 0), (3, 0), 'CENTER'),
        
        # Content
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),  # Labels
        ('FONTNAME', (2, 1), (2, -1), 'Helvetica-Bold'),  # Labels
        ('FONTNAME', (1, 1), (1, -1), 'Helvetica'),       # Values
        ('FONTNAME', (3, 1), (3, -1), 'Helvetica'),       # Values
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        
        # General styling
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#cbd5e0')),
        
        # Alternating row colors
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f7fafc')),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#f7fafc')),
    ]))
    
    content.append(package_table)
    content.append(Spacer(1, 25))
    
    # Important notices
    notices_data = [
        ["IMPORTANT NOTICES"],
        ["• This label must be securely attached to the package"],
        ["• Package contents should match the declared description"],
        ["• Contact customer service for any delivery issues: 1800-XFA-SHIP"],
        ["• For tracking updates, visit www.xfaslogistics.com or call +91-22-1234-5678"]
    ]
    
    notices_table = Table(notices_data, colWidths=[6.5*inch])
    notices_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#fed7d7')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#742a2a')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#744210')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#fc8181')),
    ]))
    
    content.append(notices_table)
    content.append(Spacer(1, 15))
    
    # Footer with generation info
    footer_table_data = [[
        f"Generated: {datetime.utcnow().strftime('%d %B %Y, %I:%M %p IST')}",
        "XFas Logistics Pvt Ltd",
        "www.xfaslogistics.com"
    ]]
    
    footer_table = Table(footer_table_data, colWidths=[2.2*inch, 2.2*inch, 2.2*inch])
    footer_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#718096')),
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    
    content.append(footer_table)
    
    # Build PDF
    doc.build(content)
    buffer.seek(0)
    return buffer.getvalue()
