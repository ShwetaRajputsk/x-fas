#!/usr/bin/env python3
"""
Script to create admin users for the XFas Logistics platform
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from utils.auth import get_password_hash
from models.user import User, UserType, UserRole
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

async def create_admin_user():
    """Create an admin user in the database"""
    
    # Database connection
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get('DB_NAME', 'xfas_logistics')]
    
    # Admin user details
    admin_email = "admin@xfas.com"
    admin_password = "XFasAdmin@2024"  # Change this to a secure password
    
    try:
        # Check if admin already exists
        existing_admin = await db.users.find_one({"email": admin_email})
        if existing_admin:
            print(f"❌ Admin user with email {admin_email} already exists!")
            return
        
        # Hash password
        hashed_password = get_password_hash(admin_password)
        
        # Create admin user
        admin_user = User(
            email=admin_email,
            password_hash=hashed_password,
            first_name="Admin",
            last_name="User",
            phone="+1234567890",
            user_type=UserType.BUSINESS,
            role=UserRole.SUPER_ADMIN,  # Set admin role
            is_verified=True,
            is_email_verified=True,
            is_phone_verified=True,
            is_active=True,
            email_verified_at=datetime.utcnow(),
            phone_verified_at=datetime.utcnow()
        )
        
        # Insert into database
        await db.users.insert_one(admin_user.dict())
        
        print("✅ Admin user created successfully!")
        print(f"📧 Email: {admin_email}")
        print(f"🔐 Password: {admin_password}")
        print(f"👑 Role: {UserRole.SUPER_ADMIN}")
        print("\n⚠️  IMPORTANT: Change the password after first login!")
        
    except Exception as e:
        print(f"❌ Error creating admin user: {str(e)}")
    
    finally:
        client.close()

async def create_manager_user():
    """Create a manager user in the database"""
    
    # Database connection
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get('DB_NAME', 'xfas_logistics')]
    
    # Manager user details
    manager_email = "manager@xfas.com"
    manager_password = "XFasManager@2024"  # Change this to a secure password
    
    try:
        # Check if manager already exists
        existing_manager = await db.users.find_one({"email": manager_email})
        if existing_manager:
            print(f"❌ Manager user with email {manager_email} already exists!")
            return
        
        # Hash password
        hashed_password = get_password_hash(manager_password)
        
        # Create manager user
        manager_user = User(
            email=manager_email,
            password_hash=hashed_password,
            first_name="Manager",
            last_name="User",
            phone="+1234567891",
            user_type=UserType.BUSINESS,
            role=UserRole.MANAGER,  # Set manager role
            is_verified=True,
            is_email_verified=True,
            is_phone_verified=True,
            is_active=True,
            email_verified_at=datetime.utcnow(),
            phone_verified_at=datetime.utcnow()
        )
        
        # Insert into database
        await db.users.insert_one(manager_user.dict())
        
        print("✅ Manager user created successfully!")
        print(f"📧 Email: {manager_email}")
        print(f"🔐 Password: {manager_password}")
        print(f"👔 Role: {UserRole.MANAGER}")
        print("\n⚠️  IMPORTANT: Change the password after first login!")
        
    except Exception as e:
        print(f"❌ Error creating manager user: {str(e)}")
    
    finally:
        client.close()

async def list_admin_users():
    """List all admin users in the database"""
    
    # Database connection
    mongo_url = os.environ['MONGO_URL']
    client = AsyncIOMotorClient(mongo_url)
    db = client[os.environ.get('DB_NAME', 'xfas_logistics')]
    
    try:
        # Find all admin users
        admin_users = await db.users.find({
            "role": {"$in": [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER]}
        }).to_list(length=100)
        
        if not admin_users:
            print("📭 No admin users found in the database.")
            return
        
        print("👑 Admin Users in Database:")
        print("-" * 60)
        for user in admin_users:
            print(f"📧 Email: {user['email']}")
            print(f"👤 Name: {user['first_name']} {user['last_name']}")
            print(f"🎭 Role: {user.get('role', 'USER')}")
            print(f"✅ Active: {user['is_active']}")
            print(f"📅 Created: {user['created_at']}")
            print("-" * 60)
            
    except Exception as e:
        print(f"❌ Error listing admin users: {str(e)}")
    
    finally:
        client.close()

async def main():
    """Main function"""
    print("🚀 XFas Logistics Admin User Setup")
    print("=" * 40)
    
    while True:
        print("\nWhat would you like to do?")
        print("1. Create Super Admin User")
        print("2. Create Manager User")
        print("3. List Admin Users")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ").strip()
        
        if choice == "1":
            await create_admin_user()
        elif choice == "2":
            await create_manager_user()
        elif choice == "3":
            await list_admin_users()
        elif choice == "4":
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    asyncio.run(main())