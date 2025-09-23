import os
import requests
import logging
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

class SMSProvider(ABC):
    """Abstract base class for SMS providers."""
    
    @abstractmethod
    async def send_sms(self, phone: str, message: str) -> Dict[str, Any]:
        """Send SMS message to phone number."""
        pass

class Fast2SMSProvider(SMSProvider):
    """Fast2SMS provider implementation (Popular in India)."""
    
    def __init__(self):
        self.api_key = os.getenv('FAST2SMS_API_KEY')
        self.sender_id = os.getenv('FAST2SMS_SENDER_ID', 'XFASLO')
        self.base_url = 'https://www.fast2sms.com/dev/bulkV2'
    
    async def send_sms(self, phone: str, message: str) -> Dict[str, Any]:
        if not self.api_key:
            return {
                'success': False,
                'error': 'Fast2SMS API key not configured',
                'provider': 'fast2sms'
            }
        
        try:
            # Clean phone number (remove +91 or 91 prefix for Indian numbers)
            clean_phone = phone.replace('+91', '').replace('91', '').replace('-', '').replace(' ', '')
            if len(clean_phone) == 10 and clean_phone.startswith(('6', '7', '8', '9')):
                phone_number = clean_phone
            else:
                return {
                    'success': False,
                    'error': 'Invalid Indian phone number format',
                    'provider': 'fast2sms'
                }
            
            headers = {
                'authorization': self.api_key,
                'Content-Type': 'application/json'
            }
            
            data = {
                'sender_id': self.sender_id,
                'message': message,
                'numbers': phone_number,
                'route': 'otp',
                'flash': 0
            }
            
            response = requests.post(self.base_url, json=data, headers=headers, timeout=30)
            response_data = response.json()
            
            if response.status_code == 200 and response_data.get('return', False):
                return {
                    'success': True,
                    'message': 'SMS sent successfully',
                    'provider': 'fast2sms',
                    'response': response_data
                }
            else:
                return {
                    'success': False,
                    'error': response_data.get('message', 'Failed to send SMS'),
                    'provider': 'fast2sms',
                    'response': response_data
                }
                
        except Exception as e:
            logger.error(f"Fast2SMS error: {str(e)}")
            return {
                'success': False,
                'error': f'Fast2SMS API error: {str(e)}',
                'provider': 'fast2sms'
            }

class MSG91Provider(SMSProvider):
    """MSG91 provider implementation (Popular in India)."""
    
    def __init__(self):
        self.auth_key = os.getenv('MSG91_AUTH_KEY')
        self.sender_id = os.getenv('MSG91_SENDER_ID', 'XFASLO')
        self.template_id = os.getenv('MSG91_TEMPLATE_ID')
        self.base_url = 'https://control.msg91.com/api/v5/otp'
    
    async def send_sms(self, phone: str, message: str) -> Dict[str, Any]:
        if not self.auth_key:
            return {
                'success': False,
                'error': 'MSG91 auth key not configured',
                'provider': 'msg91'
            }
        
        try:
            # Clean phone number
            clean_phone = phone.replace('+', '').replace('-', '').replace(' ', '')
            if not clean_phone.startswith('91') and len(clean_phone) == 10:
                clean_phone = '91' + clean_phone
            
            headers = {
                'authkey': self.auth_key,
                'Content-Type': 'application/json'
            }
            
            # Extract OTP from message (assuming format like "Your OTP is: 123456")
            otp_code = ''
            for word in message.split():
                if word.isdigit() and len(word) >= 4:
                    otp_code = word
                    break
            
            if self.template_id and otp_code:
                # Use template-based sending
                data = {
                    'template_id': self.template_id,
                    'recipients': [
                        {
                            'mobiles': clean_phone,
                            'otp': otp_code
                        }
                    ]
                }
                url = f"{self.base_url}"
            else:
                # Use promotional SMS
                data = {
                    'sender': self.sender_id,
                    'route': '4',
                    'country': '91',
                    'sms': [
                        {
                            'message': message,
                            'to': [clean_phone]
                        }
                    ]
                }
                url = 'https://control.msg91.com/api/v5/flow/'
            
            response = requests.post(url, json=data, headers=headers, timeout=30)
            response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {'message': response.text}
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'message': 'SMS sent successfully',
                    'provider': 'msg91',
                    'response': response_data
                }
            else:
                return {
                    'success': False,
                    'error': response_data.get('message', f'HTTP {response.status_code}'),
                    'provider': 'msg91',
                    'response': response_data
                }
                
        except Exception as e:
            logger.error(f"MSG91 error: {str(e)}")
            return {
                'success': False,
                'error': f'MSG91 API error: {str(e)}',
                'provider': 'msg91'
            }

class TwilioProvider(SMSProvider):
    """Twilio provider implementation (International)."""
    
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_FROM_NUMBER')
    
    async def send_sms(self, phone: str, message: str) -> Dict[str, Any]:
        if not all([self.account_sid, self.auth_token, self.from_number]):
            return {
                'success': False,
                'error': 'Twilio credentials not configured',
                'provider': 'twilio'
            }
        
        try:
            from twilio.rest import Client
            
            client = Client(self.account_sid, self.auth_token)
            
            # Ensure phone number has country code
            if not phone.startswith('+'):
                if phone.startswith('91'):
                    phone = '+' + phone
                elif len(phone) == 10:
                    phone = '+91' + phone
                else:
                    phone = '+' + phone
            
            message_instance = client.messages.create(
                body=message,
                from_=self.from_number,
                to=phone
            )
            
            return {
                'success': True,
                'message': 'SMS sent successfully',
                'provider': 'twilio',
                'response': {
                    'sid': message_instance.sid,
                    'status': message_instance.status
                }
            }
            
        except ImportError:
            return {
                'success': False,
                'error': 'Twilio library not installed. Run: pip install twilio',
                'provider': 'twilio'
            }
        except Exception as e:
            logger.error(f"Twilio error: {str(e)}")
            return {
                'success': False,
                'error': f'Twilio API error: {str(e)}',
                'provider': 'twilio'
            }

class ConsoleSMSProvider(SMSProvider):
    """Console provider for development/testing."""
    
    async def send_sms(self, phone: str, message: str) -> Dict[str, Any]:
        print("\n" + "="*50)
        print("📱 SMS OTP (Development Mode)")
        print("="*50)
        print(f"To: {phone}")
        print(f"Message: {message}")
        print("="*50 + "\n")
        
        logger.info(f"Console SMS sent to {phone}: {message}")
        
        return {
            'success': True,
            'message': 'SMS sent successfully (console mode)',
            'provider': 'console'
        }

class SMSService:
    """Main SMS service that handles provider selection and fallback."""
    
    def __init__(self):
        self.providers = []
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize SMS providers based on environment configuration."""
        
        # Development/Testing mode
        if os.getenv('SMS_MODE', 'development').lower() == 'development':
            self.providers.append(ConsoleSMSProvider())
            logger.info("SMS Service initialized in development mode (console output)")
            return
        
        # Production providers (in order of preference)
        preferred_provider = os.getenv('SMS_PROVIDER', 'fast2sms').lower()
        
        if preferred_provider == 'fast2sms':
            self.providers = [Fast2SMSProvider(), MSG91Provider(), TwilioProvider()]
        elif preferred_provider == 'msg91':
            self.providers = [MSG91Provider(), Fast2SMSProvider(), TwilioProvider()]
        elif preferred_provider == 'twilio':
            self.providers = [TwilioProvider(), Fast2SMSProvider(), MSG91Provider()]
        else:
            # Default fallback order
            self.providers = [Fast2SMSProvider(), MSG91Provider(), TwilioProvider()]
        
        # Add console as last fallback
        self.providers.append(ConsoleSMSProvider())
        
        logger.info(f"SMS Service initialized with providers: {[p.__class__.__name__ for p in self.providers]}")
    
    async def send_sms(self, phone: str, message: str) -> Dict[str, Any]:
        """Send SMS using the first available provider."""
        
        last_error = None
        
        for provider in self.providers:
            try:
                result = await provider.send_sms(phone, message)
                
                if result['success']:
                    logger.info(f"SMS sent successfully using {result['provider']}")
                    return result
                else:
                    last_error = result
                    logger.warning(f"SMS failed with {result['provider']}: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                last_error = {
                    'success': False,
                    'error': f'Provider {provider.__class__.__name__} failed: {str(e)}',
                    'provider': provider.__class__.__name__.lower().replace('provider', '')
                }
                logger.error(f"SMS provider {provider.__class__.__name__} failed: {str(e)}")
        
        # If all providers failed, return the last error
        return last_error or {
            'success': False,
            'error': 'All SMS providers failed',
            'provider': 'none'
        }

# Global SMS service instance
sms_service = SMSService()