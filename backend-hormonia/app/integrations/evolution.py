"""
Evolution API client for WhatsApp Business integration.
Handles message sending, webhook validation, and API communication.
"""
import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
from urllib.parse import urljoin
import structlog

import httpx
from pydantic import BaseModel, Field, validator

from app.config import settings
from app.exceptions import ExternalServiceError


# Configure structured logging for Railway
logger = structlog.get_logger(__name__)
std_logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Supported message types for Evolution API."""
    TEXT = "text"
    BUTTON = "button"
    LIST = "list"
    MEDIA = "media"
    LOCATION = "location"


class MessageStatus(str, Enum):
    """Message delivery status."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class TextMessage(BaseModel):
    """Text message payload."""
    text: str = Field(..., description="Message text content")


class ButtonMessage(BaseModel):
    """Button message payload."""
    text: str = Field(..., description="Message text")
    buttons: List[Dict[str, str]] = Field(..., description="Button definitions")


class ListMessage(BaseModel):
    """List message payload."""
    text: str = Field(..., description="Message text")
    title: str = Field(..., description="List title")
    sections: List[Dict[str, Any]] = Field(..., description="List sections")


class MediaMessage(BaseModel):
    """Media message payload."""
    media_url: str = Field(..., description="Media file URL")
    caption: Optional[str] = Field(None, description="Media caption")
    media_type: str = Field(..., description="Media type (image, video, audio, document)")


class WebhookEvent(BaseModel):
    """Webhook event from Evolution API."""
    event: str = Field(..., description="Event type")
    instance: str = Field(..., description="Instance name")
    data: Dict[str, Any] = Field(..., description="Event data")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class EvolutionAPIError(ExternalServiceError):
    """Evolution API specific error."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(f"Evolution API Error: {message}")
        self.status_code = status_code
        self.response_data = response_data


class EvolutionClient:
    """
    Evolution API client for WhatsApp Business integration.

    Provides methods for sending messages, handling webhooks, and managing
    WhatsApp communication with proper error handling and retry logic.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        instance_name: Optional[str] = None,
        api_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        use_mock: bool = False,
        railway_service: bool = False
    ):
        """
        Initialize Evolution API client.

        Args:
            base_url: Evolution API base URL
            instance_name: WhatsApp instance name
            api_key: API authentication key
            webhook_secret: Secret for webhook validation
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
            retry_delay: Initial delay between retries in seconds
            use_mock: Use mock mode for testing
            railway_service: Whether running as Railway service
        """
        # Configure for Railway or external service
        self.railway_service = railway_service or getattr(settings, 'RAILWAY_ENVIRONMENT', False)

        # URL configuration - prioritize Railway internal service
        if self.railway_service and hasattr(settings, 'EVOLUTION_RAILWAY_URL'):
            self.base_url = settings.EVOLUTION_RAILWAY_URL.rstrip('/')
        else:
            self.base_url = (base_url or getattr(settings, 'EVOLUTION_API_URL', 'https://api.evolution.dev')).rstrip('/')

        self.instance_name = instance_name or getattr(settings, 'EVOLUTION_INSTANCE_NAME', 'hormonia')
        self.api_key = api_key or getattr(settings, 'EVOLUTION_API_KEY', None)
        self.webhook_secret = webhook_secret or getattr(settings, 'EVOLUTION_WEBHOOK_SECRET', None)
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.use_mock = use_mock

        # Railway environment logging
        logger.info(
            "Evolution API client initializing",
            base_url=self.base_url,
            instance_name=self.instance_name,
            has_api_key=bool(self.api_key),
            has_webhook_secret=bool(self.webhook_secret),
            railway_service=self.railway_service,
            use_mock=self.use_mock
        )
        
        # Rate limiting configuration
        self.rate_limiter = {
            'requests_per_second': getattr(settings, 'EVOLUTION_RATE_LIMIT', 10),
            'request_times': [],
            'last_reset': time.time()
        }

        # HTTP client configuration with proper headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Hormonia-System/1.0"
        }

        # Add API key to headers (Evolution uses different header names)
        if self.api_key:
            headers["apikey"] = self.api_key  # Standard Evolution header
            headers["Authorization"] = f"Bearer {self.api_key}"  # Alternative auth method

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers=headers,
            follow_redirects=True,
            limits=httpx.Limits(
                max_keepalive_connections=20,
                max_connections=100,
                keepalive_expiry=30.0
            )
        )

        logger.info(
            "Evolution API client initialized",
            instance_name=self.instance_name,
            base_url=self.base_url,
            timeout=timeout,
            max_retries=max_retries,
            rate_limit=self.rate_limiter['requests_per_second']
        )
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
    
    def _get_endpoint_url(self, endpoint: str) -> str:
        """Build full endpoint URL with proper path joining."""
        # Ensure proper URL construction
        clean_endpoint = endpoint.lstrip('/')
        return urljoin(f"{self.base_url}/", clean_endpoint)

    def _check_rate_limit(self) -> bool:
        """Check and enforce rate limiting with improved efficiency."""
        current_time = time.time()

        # Reset counter every second
        if current_time - self.rate_limiter['last_reset'] > 1:
            self.rate_limiter['request_times'] = []
            self.rate_limiter['last_reset'] = current_time

        # Remove requests older than 1 second (optimization: use list comprehension)
        cutoff_time = current_time - 1
        self.rate_limiter['request_times'] = [
            t for t in self.rate_limiter['request_times'] if t > cutoff_time
        ]

        # Check if we're under the limit
        current_requests = len(self.rate_limiter['request_times'])
        if current_requests >= self.rate_limiter['requests_per_second']:
            logger.warning(
                "Evolution API rate limit exceeded",
                requests_in_last_second=current_requests,
                limit=self.rate_limiter['requests_per_second'],
                wait_time=1.0 - (current_time - min(self.rate_limiter['request_times']))
            )
            return False

        # Record this request
        self.rate_limiter['request_times'].append(current_time)
        return True
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request payload
            params: Query parameters
            retry_count: Current retry attempt
            
        Returns:
            Response data as dictionary
            
        Raises:
            EvolutionAPIError: On API errors or max retries exceeded
        """
        url = self._get_endpoint_url(endpoint)
        
        try:
            # Check rate limit before making request
            if not self._check_rate_limit():
                await asyncio.sleep(1.0)  # Wait for rate limit reset
                if not self._check_rate_limit():
                    raise EvolutionAPIError("Rate limit exceeded")

            # Mock mode for testing
            if self.use_mock:
                return await self._mock_response(method, endpoint, data)

            logger.info(
                "Making Evolution API request",
                method=method,
                url=url,
                attempt=retry_count + 1,
                has_data=bool(data),
                has_params=bool(params)
            )

            start_time = time.time()
            response = await self.client.request(
                method=method,
                url=url,
                json=data,
                params=params
            )
            response_time = time.time() - start_time
            
            # Log response details
            logger.info(
                "Evolution API response received",
                status_code=response.status_code,
                response_time_seconds=round(response_time, 3),
                content_length=len(response.content) if response.content else 0
            )

            # Handle HTTP errors
            if response.status_code >= 400:
                error_data = None
                try:
                    error_data = response.json()
                except:
                    pass

                error_msg = f"HTTP {response.status_code}: {response.text[:200]}..."

                logger.error(
                    "Evolution API error response",
                    status_code=response.status_code,
                    error_data=error_data,
                    url=url,
                    method=method
                )
                
                # Retry on server errors (5xx) and rate limits (429)
                if response.status_code >= 500 or response.status_code == 429:
                    if retry_count < self.max_retries:
                        delay = self.retry_delay * (2 ** retry_count)  # Exponential backoff
                        logger.warning(
                            "Evolution API retrying request",
                            status_code=response.status_code,
                            attempt=retry_count + 1,
                            max_retries=self.max_retries,
                            retry_delay=delay
                        )
                        await asyncio.sleep(delay)
                        return await self._make_request(method, endpoint, data, params, retry_count + 1)
                
                raise EvolutionAPIError(error_msg, response.status_code, error_data)
            
            # Parse response with error handling
            try:
                result = response.json()
                logger.info(
                    "Evolution API request successful",
                    status=result.get('status', 'unknown'),
                    has_data=bool(result.get('data')),
                    response_keys=list(result.keys()) if isinstance(result, dict) else None
                )
                return result
            except json.JSONDecodeError as e:
                logger.warning(
                    "Evolution API returned non-JSON response",
                    content_type=response.headers.get('content-type'),
                    response_preview=response.text[:200] if response.text else None
                )
                return {"status": "success", "data": response.text}
                
        except httpx.TimeoutException as e:
            logger.warning(
                "Evolution API timeout",
                timeout_seconds=self.timeout,
                attempt=retry_count + 1,
                max_retries=self.max_retries
            )

            if retry_count < self.max_retries:
                delay = self.retry_delay * (2 ** retry_count)
                await asyncio.sleep(delay)
                return await self._make_request(method, endpoint, data, params, retry_count + 1)

            raise EvolutionAPIError(f"Request timeout after {self.max_retries} attempts")

        except httpx.RequestError as e:
            logger.warning(
                "Evolution API network error",
                error=str(e),
                error_type=type(e).__name__,
                attempt=retry_count + 1,
                max_retries=self.max_retries
            )

            # Retry on network errors
            if retry_count < self.max_retries:
                delay = self.retry_delay * (2 ** retry_count)
                await asyncio.sleep(delay)
                return await self._make_request(method, endpoint, data, params, retry_count + 1)

            raise EvolutionAPIError(f"Network error after {self.max_retries} attempts: {str(e)}")
    
    async def _mock_response(self, method: str, endpoint: str, data: Optional[Dict]) -> Dict[str, Any]:
        """Generate mock response for testing."""
        await asyncio.sleep(0.1)  # Simulate network delay

        mock_message_id = f"mock_{int(time.time() * 1000)}"

        if "sendText" in endpoint or "sendButtons" in endpoint or "sendList" in endpoint or "sendMedia" in endpoint:
            return {
                "status": "success",
                "data": {
                    "id": mock_message_id,
                    "status": "pending",
                    "timestamp": int(time.time() * 1000)
                }
            }
        elif "connectionState" in endpoint:
            return {
                "status": "success",
                "data": {
                    "state": "open",
                    "connected": True
                }
            }
        else:
            return {"status": "success", "data": {}}

    async def send_text_message(
        self,
        phone_number: str,
        message: str,
        delay: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send text message via WhatsApp.

        Args:
            phone_number: Recipient phone number (with country code, e.g., 5511999999999)
            message: Text message content
            delay: Optional delay in milliseconds

        Returns:
            API response with message ID and status
        """
        # Validate and format phone number
        clean_number = self._format_phone_number(phone_number)

        # Evolution API v2 payload format
        payload = {
            "number": clean_number,
            "textMessage": {
                "text": message
            }
        }

        if delay:
            payload["delay"] = delay

        logger.info(
            "Sending text message",
            phone_number=clean_number,
            message_length=len(message),
            has_delay=bool(delay)
        )

        endpoint = f"message/sendText/{self.instance_name}"
        response = await self._make_request("POST", endpoint, payload)

        logger.info(
            "Text message sent",
            phone_number=clean_number,
            message_id=response.get('data', {}).get('id'),
            status=response.get('status')
        )

        return response

    def _format_phone_number(self, phone_number: str) -> str:
        """Format phone number for Evolution API."""
        # Remove any non-digit characters
        clean_number = ''.join(filter(str.isdigit, phone_number))

        # Ensure Brazilian format (55 + area code + number)
        if not clean_number.startswith('55'):
            if len(clean_number) == 11:  # Area code + 9-digit mobile
                clean_number = '55' + clean_number
            elif len(clean_number) == 10:  # Area code + 8-digit landline
                clean_number = '55' + clean_number

        return clean_number
    
    async def send_button_message(
        self,
        phone_number: str,
        text: str,
        buttons: List[Dict[str, str]],
        delay: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send button message via WhatsApp.
        
        Args:
            phone_number: Recipient phone number
            text: Message text
            buttons: List of button definitions [{"displayText": "Button 1", "id": "btn1"}]
            delay: Optional delay in milliseconds
            
        Returns:
            API response with message ID and status
        """
        # Format phone number and validate buttons
        clean_number = self._format_phone_number(phone_number)

        # Evolution API v2 button format
        formatted_buttons = []
        for i, button in enumerate(buttons):
            if isinstance(button, dict):
                formatted_buttons.append({
                    "index": i + 1,
                    "urlButton": {
                        "displayText": button.get("displayText", button.get("text", f"Opção {i+1}")),
                        "url": button.get("url", f"payload:{button.get('id', f'btn_{i+1}')}")
                    }
                })
            else:
                formatted_buttons.append({
                    "index": i + 1,
                    "urlButton": {
                        "displayText": str(button),
                        "url": f"payload:btn_{i+1}"
                    }
                })

        payload = {
            "number": clean_number,
            "buttonMessage": {
                "text": text,
                "buttons": formatted_buttons
            }
        }
        
        if delay:
            payload["delay"] = delay
        
        logger.info(
            "Sending button message",
            phone_number=clean_number,
            button_count=len(formatted_buttons)
        )

        endpoint = f"message/sendButtons/{self.instance_name}"
        response = await self._make_request("POST", endpoint, payload)

        logger.info(
            "Button message sent",
            phone_number=clean_number,
            message_id=response.get('data', {}).get('id')
        )

        return response
    
    async def send_list_message(
        self,
        phone_number: str,
        text: str,
        title: str,
        sections: List[Dict[str, Any]],
        delay: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send list message via WhatsApp.
        
        Args:
            phone_number: Recipient phone number
            text: Message text
            title: List title
            sections: List sections with rows
            delay: Optional delay in milliseconds
            
        Returns:
            API response with message ID and status
        """
        # Format phone number and sections
        clean_number = self._format_phone_number(phone_number)

        payload = {
            "number": clean_number,
            "listMessage": {
                "text": text,
                "title": title,
                "sections": sections
            }
        }
        
        if delay:
            payload["delay"] = delay
        
        endpoint = f"message/sendList/{self.instance_name}"
        return await self._make_request("POST", endpoint, payload)
    
    async def send_media_message(
        self,
        phone_number: str,
        media_url: str,
        media_type: str,
        caption: Optional[str] = None,
        delay: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send media message via WhatsApp.
        
        Args:
            phone_number: Recipient phone number
            media_url: URL of media file
            media_type: Type of media (image, video, audio, document)
            caption: Optional media caption
            delay: Optional delay in milliseconds
            
        Returns:
            API response with message ID and status
        """
        # Format phone number and media payload
        clean_number = self._format_phone_number(phone_number)

        payload = {
            "number": clean_number,
            "mediaMessage": {
                "mediatype": media_type,
                "media": media_url
            }
        }
        
        if caption:
            payload["mediaMessage"]["caption"] = caption
        
        if delay:
            payload["delay"] = delay
        
        endpoint = f"message/sendMedia/{self.instance_name}"
        return await self._make_request("POST", endpoint, payload)
    
    async def get_instance_status(self) -> Dict[str, Any]:
        """
        Get WhatsApp instance connection status.
        
        Returns:
            Instance status information
        """
        endpoint = f"instance/connectionState/{self.instance_name}"
        return await self._make_request("GET", endpoint)
    
    async def get_message_status(self, message_id: str) -> Dict[str, Any]:
        """
        Get message delivery status.
        
        Args:
            message_id: WhatsApp message ID
            
        Returns:
            Message status information
        """
        endpoint = f"chat/findMessages/{self.instance_name}"
        params = {"id": message_id}
        return await self._make_request("GET", endpoint, params=params)
    
    def validate_webhook_signature(
        self,
        payload: bytes,
        signature: str,
        secret: Optional[str] = None
    ) -> bool:
        """
        Validate webhook signature for security.

        Args:
            payload: Raw webhook payload
            signature: Signature from webhook headers (X-Signature or similar)
            secret: Webhook secret (defaults to webhook secret or API key)

        Returns:
            True if signature is valid
        """
        validation_secret = secret or self.webhook_secret or self.api_key

        if not validation_secret:
            logger.warning(
                "No webhook secret configured - signature validation disabled",
                has_api_key=bool(self.api_key),
                has_webhook_secret=bool(self.webhook_secret)
            )
            # P0 FIX: Enforce signature validation in production
            # In production, reject webhooks without valid signatures for security
            if getattr(settings, 'ENVIRONMENT', 'development') == 'production':
                logger.error("Webhook signature validation required in production but no secret configured")
                return False
            return True  # Allow in development only

        try:
            # Remove common prefixes
            clean_signature = signature
            for prefix in ['sha256=', 'sha1=', 'hmac-sha256=']:
                if signature.startswith(prefix):
                    clean_signature = signature[len(prefix):]
                    break

            # Calculate expected signature (try multiple hash algorithms)
            expected_sha256 = hmac.new(
                validation_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()

            expected_sha1 = hmac.new(
                validation_secret.encode('utf-8'),
                payload,
                hashlib.sha1
            ).hexdigest()

            # Secure comparison with multiple algorithms
            is_valid = (
                hmac.compare_digest(clean_signature, expected_sha256) or
                hmac.compare_digest(clean_signature, expected_sha1)
            )

            logger.info(
                "Webhook signature validation",
                is_valid=is_valid,
                signature_length=len(clean_signature),
                payload_length=len(payload)
            )

            return is_valid

        except Exception as e:
            logger.error(
                "Webhook signature validation error",
                error=str(e),
                error_type=type(e).__name__
            )
            return False
    
    def parse_webhook_event(self, payload: Dict[str, Any]) -> WebhookEvent:
        """
        Parse webhook event payload with comprehensive validation.

        Args:
            payload: Raw webhook payload from Evolution API

        Returns:
            Parsed webhook event
        """
        try:
            # Log incoming webhook for debugging
            logger.info(
                "Parsing webhook event",
                event_type=payload.get('event'),
                instance=payload.get('instance'),
                has_data=bool(payload.get('data')),
                payload_keys=list(payload.keys())
            )

            # Handle Evolution API webhook format variations
            if 'event' not in payload:
                # Try to infer event type from data structure
                if 'message' in payload.get('data', {}):
                    payload['event'] = 'message.received'
                elif 'status' in payload.get('data', {}):
                    payload['event'] = 'message.status'
                else:
                    payload['event'] = 'unknown'

            if 'instance' not in payload:
                payload['instance'] = self.instance_name

            return WebhookEvent(**payload)

        except Exception as e:
            logger.error(
                "Failed to parse webhook event",
                error=str(e),
                payload_preview=str(payload)[:200] if payload else None,
                error_type=type(e).__name__
            )
            raise EvolutionAPIError(f"Invalid webhook payload: {e}")

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Evolution API health and instance status.

        Returns:
            Health check results
        """
        health_status = {
            "service": "evolution_api",
            "healthy": False,
            "timestamp": datetime.utcnow().isoformat(),
            "details": {}
        }

        try:
            # Check instance connection state
            status_response = await self.get_instance_status()

            is_connected = False
            if status_response.get('status') == 'success':
                connection_data = status_response.get('data', {})
                is_connected = connection_data.get('connected', False) or connection_data.get('state') == 'open'

            health_status.update({
                "healthy": is_connected,
                "details": {
                    "instance_name": self.instance_name,
                    "base_url": self.base_url,
                    "connected": is_connected,
                    "response": status_response,
                    "railway_service": self.railway_service,
                    "rate_limit_remaining": self.rate_limiter['requests_per_second'] - len(self.rate_limiter['request_times'])
                }
            })

            logger.info(
                "Evolution API health check completed",
                healthy=is_connected,
                instance=self.instance_name
            )

        except Exception as e:
            health_status["details"] = {
                "error": str(e),
                "error_type": type(e).__name__,
                "instance_name": self.instance_name
            }
            logger.error(
                "Evolution API health check failed",
                error=str(e),
                instance=self.instance_name
            )

        return health_status


# Global client instance
_evolution_client: Optional[EvolutionClient] = None


async def get_evolution_client() -> EvolutionClient:
    """
    Get global Evolution API client instance.
    
    Returns:
        Configured Evolution API client
    """
    global _evolution_client
    
    if _evolution_client is None:
        _evolution_client = EvolutionClient()
    
    return _evolution_client


async def close_evolution_client():
    """Close global Evolution API client."""
    global _evolution_client
    
    if _evolution_client:
        await _evolution_client.close()
        _evolution_client = None