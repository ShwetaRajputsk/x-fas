import os
import logging
from typing import Optional, Dict, Any, Literal
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class TwilioVerifyService:
    """
    Twilio Verify service for phone and email verification.
    Uses Twilio's Verify API which handles OTP generation, delivery, and verification.
    """
    
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.verify_service_sid = os.getenv('TWILIO_VERIFY_SERVICE_SID')
        self.client = None
        
        # Initialize Twilio client if credentials are available
        if all([self.account_sid, self.auth_token, self.verify_service_sid]):
            try:
                from twilio.rest import Client
                self.client = Client(self.account_sid, self.auth_token)
                logger.info("Twilio Verify service initialized successfully")
            except ImportError:
                logger.error("Twilio library not installed. Run: pip install twilio")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {str(e)}")
        else:
            logger.warning("Twilio credentials not configured")
    
    def is_configured(self) -> bool:
        """Check if Twilio Verify service is properly configured."""
        return self.client is not None
    
    async def send_verification(
        self, 
        to: str, 
        channel: Literal['sms', 'call', 'email'] = 'sms',
        custom_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send verification code via Twilio Verify API.
        
        Args:
            to: Phone number (with country code) or email address
            channel: Verification channel ('sms', 'call', 'email')
            custom_message: Custom message template (optional)
            
        Returns:
            Dict with verification result
        """
        if not self.is_configured():
            return {
                'success': False,
                'error': 'Twilio Verify service not configured',
                'provider': 'twilio_verify'
            }
        
        try:
            # Format phone number for SMS/call
            if channel in ['sms', 'call']:
                formatted_to = self._format_phone_number(to)
                if not formatted_to:
                    return {
                        'success': False,
                        'error': 'Invalid phone number format',
                        'provider': 'twilio_verify'
                    }
                to = formatted_to
            
            # Create verification request
            verification_params = {
                'to': to,
                'channel': channel
            }
            
            # Add custom message if provided
            if custom_message:
                verification_params['custom_message'] = custom_message
            
            # Send verification
            verification = self.client.verify.v2.services(
                self.verify_service_sid
            ).verifications.create(**verification_params)
            
            logger.info(f"Twilio verification sent successfully to {to} via {channel}")
            
            return {
                'success': True,
                'message': f'Verification code sent successfully via {channel}',
                'provider': 'twilio_verify',
                'sid': verification.sid,
                'status': verification.status,
                'to': verification.to,
                'channel': verification.channel,
                'valid': verification.valid
            }
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Twilio verification failed: {error_msg}")
            
            # Parse Twilio error messages for user-friendly responses
            if "Invalid parameter" in error_msg:
                user_error = "Invalid phone number or email address"
            elif "Rate limit" in error_msg:
                user_error = "Too many verification attempts. Please try again later."
            elif "Blocked" in error_msg:
                user_error = "This number is blocked from receiving messages"
            else:
                user_error = "Failed to send verification code"
            
            return {
                'success': False,
                'error': user_error,
                'provider': 'twilio_verify',
                'details': error_msg
            }
    
    async def check_verification(
        self, 
        to: str, 
        code: str
    ) -> Dict[str, Any]:
        """
        Check/verify the verification code via Twilio Verify API.
        
        Args:
            to: Phone number or email address used for verification
            code: Verification code entered by user
            
        Returns:
            Dict with verification result
        """
        if not self.is_configured():
            return {
                'success': False,
                'error': 'Twilio Verify service not configured',
                'provider': 'twilio_verify'
            }
        
        try:
            # Format phone number if it's a phone verification
            if self._is_phone_number(to):
                formatted_to = self._format_phone_number(to)
                if formatted_to:
                    to = formatted_to
            
            # Check verification
            verification_check = self.client.verify.v2.services(
                self.verify_service_sid
            ).verification_checks.create(
                to=to,
                code=code
            )
            
            if verification_check.status == 'approved':
                logger.info(f"Twilio verification approved for {to}")
                return {
                    'success': True,
                    'message': 'Verification successful',
                    'provider': 'twilio_verify',
                    'status': verification_check.status,
                    'valid': verification_check.valid
                }
            else:
                logger.warning(f"Twilio verification failed for {to}: {verification_check.status}")
                return {
                    'success': False,
                    'error': 'Invalid or expired verification code',
                    'provider': 'twilio_verify',
                    'status': verification_check.status,
                    'valid': verification_check.valid
                }
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Twilio verification check failed: {error_msg}")
            
            # Parse Twilio error messages
            if "20404" in error_msg:  # Not found
                user_error = "No verification request found or code expired"
            elif "Invalid parameter" in error_msg:
                user_error = "Invalid verification code format"
            elif "Max check attempts reached" in error_msg:
                user_error = "Maximum verification attempts exceeded"
            else:
                user_error = "Verification failed"
            
            return {
                'success': False,
                'error': user_error,
                'provider': 'twilio_verify',
                'details': error_msg
            }
    
    def _format_phone_number(self, phone: str) -> Optional[str]:
        """Format phone number for Twilio (must include country code)."""
        if not phone:
            return None
        
        # Clean the phone number
        clean_phone = ''.join(filter(str.isdigit, phone))
        
        # Handle Indian numbers
        if len(clean_phone) == 10 and clean_phone[0] in '6789':
            return f"+91{clean_phone}"
        elif len(clean_phone) == 12 and clean_phone.startswith('91'):
            return f"+{clean_phone}"
        elif len(clean_phone) == 13 and clean_phone.startswith('91'):
            return f"+{clean_phone[1:]}"  # Remove extra digit if present
        elif phone.startswith('+'):
            return phone
        
        # For other countries, assume the number already has country code
        if len(clean_phone) >= 10:
            return f"+{clean_phone}"
        
        return None
    
    def _is_phone_number(self, contact: str) -> bool:
        """Check if the contact is a phone number (vs email)."""
        return '@' not in contact and any(char.isdigit() for char in contact)

# Global Twilio Verify service instance
twilio_verify_service = TwilioVerifyService()