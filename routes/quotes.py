from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from models.quote import QuoteRequest, Quote, QuoteResponse
from models.user import User
from services.quote_service import QuoteService
from utils.auth import get_current_user, get_optional_current_user

# Database dependency
async def get_database() -> AsyncIOMotorDatabase:
    from motor.motor_asyncio import AsyncIOMotorClient
    import os
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    return client[os.environ.get('DB_NAME', 'xfas_logistics')]

router = APIRouter(prefix="/quotes", tags=["Quotes"])

@router.post("/", response_model=QuoteResponse)
async def create_quote(
    request: QuoteRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Generate shipping quotes from multiple carriers."""
    
    try:
        # Create quote service
        quote_service = QuoteService()
        
        # Generate quote
        user_id = current_user.id if current_user else None
        quote = await quote_service.generate_quote(request, user_id)
        
        # Save to database
        await db.quotes.insert_one(quote.dict())
        
        # Process and return response
        response = quote_service.process_quote_response(quote)
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating quote: {str(e)}"
        )

@router.get("/", response_model=list[QuoteResponse])
async def get_user_quotes(
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
    limit: int = 20,
    skip: int = 0
):
    """Get user's quote history."""
    
    # Find user's quotes
    quotes_cursor = db.quotes.find(
        {"user_id": current_user.id}
    ).sort("created_at", -1).limit(limit).skip(skip)
    
    quotes_data = await quotes_cursor.to_list(length=limit)
    
    # Convert to Quote objects and process responses
    quote_service = QuoteService()
    responses = []
    
    for quote_data in quotes_data:
        quote = Quote(**quote_data)
        response = quote_service.process_quote_response(quote)
        responses.append(response)
    
    return responses

@router.get("/{quote_id}", response_model=QuoteResponse)
async def get_quote(
    quote_id: str,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get a specific quote by ID."""
    
    # Find quote
    quote_data = await db.quotes.find_one({"id": quote_id})
    if not quote_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )
    
    quote = Quote(**quote_data)
    
    # Check if user has access to this quote
    if quote.user_id and current_user and quote.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Process and return response
    quote_service = QuoteService()
    response = quote_service.process_quote_response(quote)
    
    return response

@router.delete("/{quote_id}")
async def delete_quote(
    quote_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete a quote."""
    
    # Find and verify ownership
    quote_data = await db.quotes.find_one({"id": quote_id})
    if not quote_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )
    
    quote = Quote(**quote_data)
    
    if quote.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    # Delete quote
    result = await db.quotes.delete_one({"id": quote_id})
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quote not found"
        )
    
    return {"message": "Quote deleted successfully"}