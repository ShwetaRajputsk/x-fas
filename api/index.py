"""
Vercel entry point for XFas Logistics Backend
"""
import os
import sys
from pathlib import Path

# Add the parent directory to the Python path
sys.path.append(str(Path(__file__).parent.parent))

# Import the Vercel-optimized server
from server_vercel import app

# Export the app for Vercel
handler = app

# For debugging
if __name__ == "__main__":
    print("Vercel entry point loaded successfully")
    print(f"Python path: {sys.path}")
    print(f"Current directory: {os.getcwd()}")
    print(f"App: {app}")
