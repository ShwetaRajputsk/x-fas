#!/usr/bin/env python3
"""
Setup Admin User Script
Creates a proper Super Admin user with correct role and permissions
"""

import asyncio
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.auth import get_password_hash
from models.user import User, UserType, UserRole

# Load environment variables
load_dotenv()

async def setup_admin_user():
    """Create or update admin user with proper Super Admin role"""
    
    try:
        # Database connection
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        db_name = os.environ.get('DB_NAME', 'xfas_logistics')
        
        print(f"🔗 Connecting to MongoDB: {mongo_url}")
        print(f"📊 Database: {db_name}")
        
        client = AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        
        # Test connection
        await client.admin.command('ping')
        print("✅ Database connection successful!")
        
        # Admin credentials
        admin_email = 'admin@xfas.com'
        admin_password = 'XFasAdmin@2024'
        
        # Check if admin already exists
        existing_admin = await db.users.find_one({'email': admin_email})
        
        if existing_admin:
            print(f"👤 Admin user already exists!")
            print(f"📧 Email: {admin_email}")
            print(f"🔐 Password: {admin_password}")
            
            # Update existing admin to Super Admin role
            update_result = await db.users.update_one(
                {'email': admin_email},
                {
                    '$set': {
                        'role': UserRole.SUPER_ADMIN.value,
                        'user_type': UserType.BUSINESS.value,
                        'is_verified': True,
                        'is_email_verified': True,
                        'is_phone_verified': True,
                        'is_active': True,
                        'updated_at': datetime.utcnow().isoformat()
                    }
                }
            )
            
            if update_result.modified_count > 0:
                print("✅ Updated existing admin to Super Admin role!")
            else:
                print("ℹ️  Admin already has correct role")
        else:
            # Create new Super Admin user
            print("👤 Creating new Super Admin user...")
            
            hashed_password = get_password_hash(admin_password)
            
            admin_user = User(
                email=admin_email,
                password_hash=hashed_password,
                first_name='Admin',
                last_name='User',
                phone='+1234567890',
                user_type=UserType.BUSINESS,
                role=UserRole.SUPER_ADMIN,
                is_verified=True,
                is_email_verified=True,
                is_phone_verified=True,
                is_active=True,
                email_verified_at=datetime.utcnow(),
                phone_verified_at=datetime.utcnow()
            )
            
            result = await db.users.insert_one(admin_user.dict())
            
            if result.inserted_id:
                print("✅ Super Admin user created successfully!")
                print(f"📧 Email: {admin_email}")
                print(f"🔐 Password: {admin_password}")
                print(f"🆔 User ID: {admin_user.id}")
            else:
                print("❌ Failed to create admin user")
                return False
        
        # Verify admin user exists and has correct role
        admin_user = await db.users.find_one({'email': admin_email})
        if admin_user:
            print(f"\n📋 Admin User Details:")
            print(f"   📧 Email: {admin_user['email']}")
            print(f"   🏷️  Role: {admin_user.get('role', 'USER')}")
            print(f"   👤 Type: {admin_user.get('user_type', 'INDIVIDUAL')}")
            print(f"   ✅ Active: {admin_user.get('is_active', False)}")
            print(f"   🔐 Verified: {admin_user.get('is_verified', False)}")
        
        # Check database collections
        print(f"\n📊 Database Collections:")
        collections = await db.list_collection_names()
        for collection in collections:
            count = await db[collection].count_documents({})
            print(f"   📁 {collection}: {count} documents")
        
        # Check if we have real data
        user_count = await db.users.count_documents({})
        shipment_count = await db.shipments.count_documents({})
        
        print(f"\n📈 Real Data Summary:")
        print(f"   👥 Total Users: {user_count}")
        print(f"   📦 Total Shipments: {shipment_count}")
        
        if user_count > 0 and shipment_count > 0:
            print("✅ You have real data! Admin panel will show live information.")
        else:
            print("⚠️  Limited data detected. Admin panel may show mostly empty stats.")
            print("   💡 Tip: Create some test users and shipments from your frontend.")
        
        client.close()
        return True
        
    except Exception as e:
        print(f"❌ Error setting up admin user: {str(e)}")
        return False

async def main():
    """Main function"""
    print("🚀 XFas Logistics - Admin User Setup")
    print("=" * 50)
    
    success = await setup_admin_user()
    
    if success:
        print("\n🎉 Setup Complete!")
        print("=" * 50)
        print("📋 Next Steps:")
        print("1. Start your backend server: uvicorn server:app --reload")
        print("2. Start your frontend: npm start")
        print("3. Go to: http://localhost:3000/admin")
        print("4. Login with: admin@xfas.com / XFasAdmin@2024")
        print("5. Your admin panel will now show REAL data! 🎯")
    else:
        print("\n❌ Setup Failed!")
        print("Please check your MongoDB connection and try again.")

if __name__ == "__main__":
    asyncio.run(main())
