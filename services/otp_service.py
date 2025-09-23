import random
import string
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

logger = logging.getLogger(__name__)

class OTPService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.otp_expiry_minutes = 10
        
    def generate_otp(self, length: int = 6) -> str:
        """Generate a random OTP code."""
        return ''.join(random.choices(string.digits, k=length))
    
    async def create_otp(self, identifier: str, purpose: str, identifier_type: str = "email") -> Dict[str, Any]:
        """
        Create and store an OTP for email or phone verification.
        
        Args:
            identifier: Email address or phone number
            purpose: Purpose of OTP (registration, login, verify_email, verify_phone)
            identifier_type: Type of identifier (email or phone)
        """
        otp_code = self.generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=self.otp_expiry_minutes)
        
        otp_document = {
            "identifier": identifier,
            "identifier_type": identifier_type,
            "otp_code": otp_code,
            "purpose": purpose,
            "expires_at": expires_at,
            "created_at": datetime.utcnow(),
            "is_used": False,
            "attempts": 0,
            "max_attempts": 3
        }
        
        # Remove any existing unused OTPs for this identifier and purpose
        await self.db.otps.delete_many({
            "identifier": identifier,
            "purpose": purpose,
            "is_used": False
        })
        
        # Store the new OTP
        await self.db.otps.insert_one(otp_document)
        
        return {
            "otp_code": otp_code,
            "expires_at": expires_at,
            "identifier": identifier,
            "purpose": purpose
        }
    
    async def verify_otp(self, identifier: str, otp_code: str, purpose: str) -> Dict[str, Any]:
        """
        Verify an OTP code.
        
        Args:
            identifier: Email address or phone number
            otp_code: OTP code to verify
            purpose: Purpose of OTP verification
            
        Returns:
            Dict with verification result
        """
        # Find the OTP
        otp_doc = await self.db.otps.find_one({
            "identifier": identifier,
            "purpose": purpose,
            "is_used": False
        })
        
        if not otp_doc:
            return {
                "success": False,
                "error": "OTP not found or already used"
            }
        
        # Check if OTP is expired
        if datetime.utcnow() > otp_doc["expires_at"]:
            await self.db.otps.update_one(
                {"_id": otp_doc["_id"]},
                {"$set": {"is_used": True}}
            )
            return {
                "success": False,
                "error": "OTP has expired"
            }
        
        # Check attempts
        if otp_doc["attempts"] >= otp_doc["max_attempts"]:
            await self.db.otps.update_one(
                {"_id": otp_doc["_id"]},
                {"$set": {"is_used": True}}
            )
            return {
                "success": False,
                "error": "Maximum verification attempts exceeded"
            }
        
        # Verify OTP code
        if otp_doc["otp_code"] != otp_code:
            await self.db.otps.update_one(
                {"_id": otp_doc["_id"]},
                {"$inc": {"attempts": 1}}
            )
            return {
                "success": False,
                "error": "Invalid OTP code"
            }
        
        # Mark OTP as used
        await self.db.otps.update_one(
            {"_id": otp_doc["_id"]},
            {"$set": {"is_used": True, "verified_at": datetime.utcnow()}}
        )
        
        return {
            "success": True,
            "message": "OTP verified successfully"
        }
    
    async def send_email_otp(self, email: str, otp_code: str, purpose: str) -> bool:
        """
        Send OTP via email.
        
        Args:
            email: Recipient email address
            otp_code: OTP code to send
            purpose: Purpose of the OTP
            
        Returns:
            Boolean indicating success
        """
        try:
            # Email configuration (you should set these in environment variables)
            smtp_host = os.getenv('SMTP_HOST', 'smtp.gmail.com')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_user = os.getenv('SMTP_USER')
            smtp_password = os.getenv('SMTP_PASSWORD')
            from_email = os.getenv('FROM_EMAIL', smtp_user)
            
            if not smtp_user or not smtp_password:
                logger.error("SMTP credentials not configured")
                return False
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = email
            msg['Subject'] = f"XFas Logistics - OTP Verification ({purpose.replace('_', ' ').title()})"
            
            # Email body
            purpose_text = {
                'registration': 'complete your registration',
                'login': 'log in to your account',
                'verify_email': 'verify your email address',
                'verify_phone': 'verify your phone number'
            }.get(purpose, 'verify your identity')
            
            body = f"""
            <html>
            <head>
                <style>
                    .container {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; }}
                    .header {{ background-color: #f97316; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; background-color: #f9f9f9; }}
                    .otp-box {{ background-color: #fff; padding: 20px; text-align: center; margin: 20px 0; border-radius: 8px; border: 2px dashed #f97316; }}
                    .otp-code {{ font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #f97316; }}
                    .footer {{ background-color: #374151; color: white; padding: 15px; text-align: center; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h2>XFas Logistics</h2>
                        <p>Your OTP Verification Code</p>
                    </div>
                    <div class="content">
                        <p>Hello,</p>
                        <p>You requested an OTP to {purpose_text}. Please use the code below:</p>
                        <div class="otp-box">
                            <div class="otp-code">{otp_code}</div>
                        </div>
                        <p><strong>This code will expire in {self.otp_expiry_minutes} minutes.</strong></p>
                        <p>If you didn't request this code, please ignore this email.</p>
                    </div>
                    <div class="footer">
                        <p>&copy; 2024 XFas Logistics. All rights reserved.</p>
                        <p>This is an automated message, please do not reply to this email.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_password)
            text = msg.as_string()
            server.sendmail(from_email, email, text)
            server.quit()
            
            logger.info(f"OTP email sent successfully to {email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send OTP email: {str(e)}")
            return False
    
    async def send_sms_otp(self, phone: str, otp_code: str, purpose: str) -> bool:
        """
        Send OTP via SMS using the SMS service.
        
        Args:
            phone: Recipient phone number
            otp_code: OTP code to send
            purpose: Purpose of the OTP
            
        Returns:
            Boolean indicating success
        """
        try:
            from services.sms_service import sms_service
            
            purpose_text = {
                'registration': 'complete registration',
                'login': 'login',
                'verify_email': 'verify email',
                'verify_phone': 'verify phone'
            }.get(purpose, 'verification')
            
            sms_text = f"Your XFas Logistics OTP for {purpose_text} is: {otp_code}. Valid for {self.otp_expiry_minutes} minutes. Do not share with anyone."
            
            # Send SMS using the SMS service
            result = await sms_service.send_sms(phone, sms_text)
            
            if result['success']:
                logger.info(f"SMS OTP sent successfully to {phone} via {result['provider']}")
                return True
            else:
                logger.error(f"Failed to send SMS OTP to {phone}: {result.get('error', 'Unknown error')}")
                return False
            
        except Exception as e:
            logger.error(f"Failed to send SMS OTP: {str(e)}")
            return False
    
    async def cleanup_expired_otps(self):
        """Clean up expired OTP records."""
        try:
            result = await self.db.otps.delete_many({
                "expires_at": {"$lt": datetime.utcnow()}
            })
            logger.info(f"Cleaned up {result.deleted_count} expired OTP records")
        except Exception as e:
            logger.error(f"Failed to cleanup expired OTPs: {str(e)}")

# Create a global OTP service instance (will be initialized with database)
otp_service = None

def get_otp_service(db: AsyncIOMotorDatabase) -> OTPService:
    """Get or create OTP service instance."""
    global otp_service
    if otp_service is None:
        otp_service = OTPService(db)
    return otp_service