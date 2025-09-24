"""
Vercel-optimized server for XFas Logistics Backend
"""
import os
import sys
from pathlib import Path
from datetime import datetime
import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
ROOT_DIR = Path(__file__).parent
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection for Vercel
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'xfas_logistics')

# Create FastAPI app
app = FastAPI(
    title="XFas Logistics API",
    description="Multi-channel parcel delivery platform API",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get('CORS_ORIGINS', 'http://localhost:3000').split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global MongoDB client (will be created on first use)
client = None
db = None

def get_mongo_client():
    """Get MongoDB client, creating it if needed"""
    global client, db
    
    if client is None:
        try:
            # Use synchronous client for Vercel compatibility
            client = MongoClient(
                mongo_url,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=5000,
                maxPoolSize=5
            )
            db = client[db_name]
            logger.info("MongoDB client created successfully")
        except Exception as e:
            logger.error(f"Failed to create MongoDB client: {e}")
            client = None
            db = None
    
    return client, db

# Database dependency
def get_database():
    """Get database connection"""
    client, database = get_mongo_client()
    if database is None:
        raise HTTPException(status_code=503, detail="Database not available")
    return database

# Health check endpoint
@app.get("/api/health")
def health_check():
    try:
        client, database = get_mongo_client()
        if database is None:
            return {
                "status": "unhealthy", 
                "database": "not_initialized",
                "error": "Database client not initialized",
                "timestamp": datetime.utcnow()
            }
        
        # Test database connection
        client.admin.command('ping')
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

# Root endpoint
@app.get("/api/")
def root():
    return {
        "message": "XFas Logistics API",
        "version": "1.0.0",
        "status": "operational"
    }

# Include other routers (simplified for Vercel)
try:
    from routes.auth import router as auth_router
    app.include_router(auth_router, prefix="/api")
except ImportError as e:
    logger.warning(f"Could not import auth router: {e}")

try:
    from routes.quotes import router as quotes_router
    app.include_router(quotes_router, prefix="/api")
except ImportError as e:
    logger.warning(f"Could not import quotes router: {e}")

# Shutdown handler
@app.on_event("shutdown")
def shutdown_db_client():
    global client
    if client is not None:
        client.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
