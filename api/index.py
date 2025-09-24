"""
Vercel entry point for XFas Logistics Backend
"""
import os
import sys
from pathlib import Path

# Add the parent directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import the FastAPI app from server.py
from server import app

# Export the app for Vercel
handler = app
