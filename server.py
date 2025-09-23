# Suppress bcrypt version warning
import warnings
warnings.filterwarnings("ignore", message=".*trapped.*error reading bcrypt version.*", category=UserWarning, module="passlib.handlers.bcrypt")

from fastapi import FastAPI, APIRouter, Depends
from fastapi.security import HTTPBearer
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
import uuid
from datetime import datetime

# Import route modules
from routes.auth import router as auth_router
from routes.quotes import router as quotes_router
from routes.shipments import router as shipments_router
from routes.booking import router as booking_router
from routes.tracking import router as tracking_router
from routes.dashboard import router as dashboard_router
from routes.admin import router as admin_router
from routes.blog import router as blog_router
from routes.payment import router as payment_router
from routes.payments import router as payments_router
from routes.profile import router as profile_router
from routes.orders import router as orders_router
from routes.address_book import router as address_book_router

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
# Add SSL parameters for better compatibility
if 'mongodb+srv://' in mongo_url:
    # For MongoDB Atlas, add SSL parameters
    separator = '&' if '?' in mongo_url else '?'
    mongo_url = f"{mongo_url}{separator}ssl=true&ssl_cert_reqs=CERT_NONE&tlsAllowInvalidCertificates=true"

client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
db = client[os.environ.get('DB_NAME', 'xfas_logistics')]

# Create the main app
app = FastAPI(
    title="XFas Logistics API",
    description="Multi-channel parcel delivery platform API",
    version="1.0.0"
)

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Database dependency
async def get_database() -> AsyncIOMotorDatabase:
    return db

# Define Models (legacy)
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class StatusCheckCreate(BaseModel):
    client_name: str

# Legacy routes
@api_router.get("/")
async def root():
    return {
        "message": "XFas Logistics API",
        "version": "1.0.0",
        "status": "operational"
    }

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    _ = await db.status_checks.insert_one(status_obj.dict())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

# Health check endpoint
@api_router.get("/health")
async def health_check():
    try:
        # Test database connection
        await db.command("ping")
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.utcnow()
        }

# Include all routers under the /api prefix
api_router.include_router(auth_router)
api_router.include_router(profile_router)
api_router.include_router(quotes_router)
api_router.include_router(shipments_router)
api_router.include_router(booking_router)
api_router.include_router(tracking_router)
api_router.include_router(dashboard_router)
api_router.include_router(admin_router)
api_router.include_router(blog_router)
api_router.include_router(payment_router)
api_router.include_router(payments_router)
api_router.include_router(orders_router)
api_router.include_router(address_book_router)

# Include the main API router in the app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Filter out bcrypt warning from passlib
class BcryptWarningFilter(logging.Filter):
    def filter(self, record):
        return not (record.name == 'passlib.handlers.bcrypt' and 'error reading bcrypt version' in record.getMessage())

# Apply filter to root logger
logging.getLogger('passlib.handlers.bcrypt').addFilter(BcryptWarningFilter())
logging.getLogger('passlib.handlers.bcrypt').setLevel(logging.ERROR)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
