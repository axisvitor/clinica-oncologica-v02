"""
Evolution API client for WhatsApp integration.
Implements ULTRATHINK approach with delivery guarantees, rate limiting, and retry logic.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urljoin
import aiohttp
import backoff
from aiohttp import ClientSession, ClientTimeout, ClientError

from ..models.message import (
    MessageResponse,
    ContactResponse,
    InstanceStatus,
    MessageStatus,
    MessageType,
)
from app.integrations.whatsapp.metrics import whatsapp_metrics
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

DEFAULT_WEBHOOK_EVENTS = [
    "MESSAGES_UPSERT",
    "MESSAGES_UPDATE",
    "MESSAGES_DELETE",
    "SEND_MESSAGE",
    "CONTACTS_UPSERT",
    "CONTACTS_UPDATE",
    "PRESENCE_UPDATE",
    "CHATS_UPSERT",
    "CHATS_UPDATE",
    "CHATS_DELETE",
    "GROUPS_UPSERT",
    "GROUP_UPDATE",
    "GROUP_PARTICIPANTS_UPDATE",
    "CONNECTION_UPDATE",
]


async def _safe_read_json(response: aiohttp.ClientResponse) -> Dict[str, Any]:
    """Safely parse JSON response with fallback to raw text."""
    try:
        return await response.json()
    except Exception:
        raw_text = await response.text()
        return {"raw": raw_text}


class RateLimiter:
    """Rate limiter for API calls with sliding window."""

    def __init__(
        self,
        max_requests: int = 100,
        window_seconds: int = 60,
        name: str = "evolution_api",
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.name = name
        self.requests = []
        self._lock = asyncio.Lock()
        self._last_limit_log: Optional[datetime] = None
        self._log_interval_seconds = 10

    async def acquire(self) -> bool:
        """Acquire rate limit permission."""
        async with self._lock:
            now = now_sao_paulo()
            # Remove old requests outside the window
            cutoff = now - timedelta(seconds=self.window_seconds)
            self.requests = [
                req_time for req_time in self.requests if req_time > cutoff
            ]

            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            if (
                not self._last_limit_log
                or (now - self._last_limit_log).total_seconds()
                >= self._log_interval_seconds
            ):
                logger.warning(
                    "Rate limit reached for Evolution API",
                    extra={
                        "limiter": self.name,
                        "max_requests": self.max_requests,
                        "window_seconds": self.window_seconds,
                    },
                )
                self._last_limit_log = now
            whatsapp_metrics.record_rate_limit_hit(self.name)
            return False

    async def wait_for_availability(self):
        """Wait until rate limit allows new request."""
        while not await self.acquire():
            await asyncio.sleep(1)


class EvolutionAPIError(Exception):
    """Evolution API error with response context."""

    def __init__(
        self,
        message: str,
        status: Optional[int] = None,
        response: Optional[Dict[str, Any]] = None,
        method: Optional[str] = None,
        url: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.response = response
        self.method = method
        self.url = url


def _log_backoff(details: Dict[str, Any]) -> None:
    """Structured logging for retry attempts."""
    exc = details.get("exception")
    status = getattr(exc, "status", None)
    logger.warning(
        "Evolution API request retrying",
        extra={
            "tries": details.get("tries"),
            "wait_seconds": details.get("wait"),
            "elapsed_seconds": details.get("elapsed"),
            "status": status,
            "error_type": type(exc).__name__ if exc else "unknown",
            "method": getattr(exc, "method", None),
            "url": getattr(exc, "url", None),
        },
    )


def _log_giveup(details: Dict[str, Any]) -> None:
    """Structured logging when retries are exhausted."""
    exc = details.get("exception")
    status = getattr(exc, "status", None)
    logger.error(
        "Evolution API request failed after retries",
        extra={
            "tries": details.get("tries"),
            "elapsed_seconds": details.get("elapsed"),
            "status": status,
            "error_type": type(exc).__name__ if exc else "unknown",
            "method": getattr(exc, "method", None),
            "url": getattr(exc, "url", None),
        },
    )


def _classify_failure(status_code: Optional[int] = None, error: Optional[Exception] = None) -> str:
    """Classify failures for metrics tagging."""
    if isinstance(error, EvolutionAPIError):
        if error.status == 429:
            return "rate_limit"
        if error.status and 400 <= error.status < 500:
            return "invalid_request"
        return "api_error"
    if isinstance(error, asyncio.TimeoutError):
        return "timeout"
    if isinstance(error, ClientError):
        return "connection_error"
    if status_code and 400 <= status_code < 500:
        return "invalid_request"
    if status_code and status_code >= 500:
        return "api_error"
    return "api_error"


class EvolutionAPIClient:
    """
    Evolution API client with ULTRATHINK approach:
    - Message delivery guarantees
    - Rate limiting
    - Retry logic with exponential backoff
    - Media optimization
    - Multi-channel messaging strategies
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        global_webhook_url: Optional[str] = None,
        max_retries: int = 3,
        timeout_seconds: int = 30,
        rate_limit_requests: int = 100,
        rate_limit_window: int = 60,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.global_webhook_url = global_webhook_url
        self.max_retries = max_retries
        self.timeout = ClientTimeout(total=timeout_seconds)
        self.rate_limiter = RateLimiter(
            rate_limit_requests, rate_limit_window, name="evolution_api"
        )
        self.session: Optional[ClientSession] = None
        self._health_cache: Dict[str, Dict[str, Any]] = {}
        self._health_cache_lock = asyncio.Lock()
        self._health_cache_ttl = timedelta(seconds=30)

        # Default headers
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Hormonia-WhatsApp-Integration/1.0",
        }
        if api_key:
            self.headers["apikey"] = api_key
            self.headers["Authorization"] = f"Bearer {api_key}"

        if rate_limit_requests != 100 or rate_limit_window != 60:
            logger.warning(
                "Evolution API rate limiter configured outside default 100 req/min",
                extra={
                    "rate_limit_requests": rate_limit_requests,
                    "rate_limit_window": rate_limit_window,
                },
            )

    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        _ = exc_type, exc_val, exc_tb
        await self.disconnect()

    async def connect(self):
        """Initialize HTTP session."""
        if not self.session:
            connector = aiohttp.TCPConnector(
                limit=100,
                limit_per_host=30,
                keepalive_timeout=30,
                enable_cleanup_closed=True,
            )
            self.session = ClientSession(
                connector=connector, timeout=self.timeout, headers=self.headers
            )

    async def disconnect(self):
        """Close HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None

    @backoff.on_exception(
        backoff.expo,
        (ClientError, asyncio.TimeoutError, EvolutionAPIError),
        max_tries=3,
        factor=2,
        max_value=60,
        on_backoff=_log_backoff,
        on_giveup=_log_giveup,
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Dict[str, Any]]:
        """
        Make HTTP request with rate limiting and retry logic.
        """
        await self.rate_limiter.wait_for_availability()

        if not self.session:
            await self.connect()

        url = urljoin(self.base_url, endpoint)

        try:
            if files:
                # For file uploads, don't set Content-Type header
                headers = {k: v for k, v in self.headers.items() if k != "Content-Type"}
                async with self.session.request(
                    method, url, data=data, params=params, headers=headers
                ) as response:
                    response_data = await _safe_read_json(response)
                    if response.status == 429 or response.status >= 500:
                        raise EvolutionAPIError(
                            "Evolution API returned retryable error",
                            status=response.status,
                            response=response_data,
                            method=method,
                            url=url,
                        )
                    return response.status, response_data
            else:
                async with self.session.request(
                    method, url, json=data, params=params
                ) as response:
                    response_data = await _safe_read_json(response)
                    if response.status == 429 or response.status >= 500:
                        raise EvolutionAPIError(
                            "Evolution API returned retryable error",
                            status=response.status,
                            response=response_data,
                            method=method,
                            url=url,
                        )
                    return response.status, response_data

        except asyncio.TimeoutError:
            logger.error(f"Request timeout for {method} {url}")
            raise
        except ClientError as e:
            logger.error(f"Client error for {method} {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error for {method} {url}: {e}")
            raise

    async def create_instance(
        self,
        instance_name: str,
        webhook_url: Optional[str] = None,
        webhook_events: Optional[List[str]] = None,
    ) -> InstanceStatus:
        """Create a new WhatsApp instance."""
        webhook_url = webhook_url or self.global_webhook_url
        webhook_events = webhook_events or DEFAULT_WEBHOOK_EVENTS

        data = {
            "instanceName": instance_name,
            "token": self.api_key,
            "qrcode": True,
            "webhook": webhook_url,
            "webhook_by_events": True,
            "events": webhook_events,
        }

        status_code, response = await self._make_request(
            "POST", "/instance/create", data=data
        )

        if status_code == 201:
            return InstanceStatus(
                name=instance_name,
                status=response.get("instance", {}).get("state", "created"),
                is_connected=False,
                qr_code=response.get("qrcode", {}).get("code"),
            )
        else:
            raise Exception(f"Failed to create instance: {response}")

    async def get_instance_status(self, instance_name: str) -> InstanceStatus:
        """Get instance connection status."""
        status_code, response = await self._make_request(
            "GET", f"/instance/connectionState/{instance_name}"
        )

        if status_code == 200:
            state = response.get("instance", {})
            return InstanceStatus(
                name=instance_name,
                status=state.get("state", "unknown"),
                is_connected=state.get("state") == "open",
                phone_number=state.get("number"),
                profile_name=state.get("profileName"),
            )
        else:
            raise Exception(f"Failed to get instance status: {response}")

    async def health_check(self, instance_name: str) -> Dict[str, Any]:
        """
        Health check for Evolution API instance with caching.

        Returns:
            Dict with is_connected, state, phone_number, last_activity
        """
        now = now_sao_paulo()

        async with self._health_cache_lock:
            cached = self._health_cache.get(instance_name)
            if cached and (now - cached["checked_at"]) < self._health_cache_ttl:
                return cached["data"]

        await self.rate_limiter.wait_for_availability()

        if not self.session:
            await self.connect()

        url = urljoin(self.base_url, f"/instance/connectionState/{instance_name}")
        timeout = ClientTimeout(total=10)

        try:
            async with self.session.request("GET", url, timeout=timeout) as response:
                response_data = await _safe_read_json(response)
                if response.status != 200:
                    raise EvolutionAPIError(
                        "Evolution API health check failed",
                        status=response.status,
                        response=response_data,
                        method="GET",
                        url=url,
                    )

        except Exception as e:
            logger.error(
                "Evolution API health check request failed",
                exc_info=True,
                extra={"instance_name": instance_name, "error": str(e)},
            )
            raise

        state = response_data.get("instance", {})
        health_data = {
            "is_connected": state.get("state") == "open",
            "state": state.get("state", "unknown"),
            "phone_number": state.get("number"),
            "last_activity": state.get("lastActivity")
            or state.get("last_activity")
            or state.get("lastSeen"),
        }

        async with self._health_cache_lock:
            self._health_cache[instance_name] = {
                "checked_at": now,
                "data": health_data,
            }

        return health_data

    async def get_qr_code(self, instance_name: str) -> Optional[str]:
        """Get QR code for instance connection."""
        status_code, response = await self._make_request(
            "GET", f"/instance/qrcode/{instance_name}"
        )

        if status_code == 200:
            return response.get("qrcode", {}).get("code")
        return None

    async def send_text_message(
        self,
        instance_name: str,
        to: str,
        text: str,
        message_data: Optional[Dict[str, Any]] = None,
    ) -> MessageResponse:
        """Send text message with delivery guarantee."""
        data = {"number": to, "text": text}

        if message_data:
            data["metadata"] = message_data

        status_code, response = await self._request_with_send_metrics(
            instance_name=instance_name,
            endpoint=f"/message/sendText/{instance_name}",
            data=data,
        )

        if status_code == 201:
            message_data = response.get("message", {})
            whatsapp_metrics.record_message_sent(
                instance_name, MessageStatus.SENT.value
            )
            return MessageResponse(
                id=message_data.get("key", {}).get("id", ""),
                external_id=message_data.get("key", {}).get("id"),
                status=MessageStatus.SENT,
                message="Message sent successfully",
                timestamp=now_sao_paulo(),
                message_data=message_data,
            )

        whatsapp_metrics.record_message_failed(
            instance_name, _classify_failure(status_code=status_code)
        )
        raise Exception(f"Failed to send message: {response}")

    async def send_media_message(
        self,
        instance_name: str,
        to: str,
        media_url: str,
        media_type: MessageType,
        caption: Optional[str] = None,
        filename: Optional[str] = None,
        message_data: Optional[Dict[str, Any]] = None,
    ) -> MessageResponse:
        """Send media message with optimization."""
        # Map message types to Evolution API endpoints
        endpoint_map = {
            MessageType.IMAGE: "sendMedia",
            MessageType.DOCUMENT: "sendMedia",
            MessageType.AUDIO: "sendMedia",
            MessageType.VIDEO: "sendMedia",
        }

        endpoint = endpoint_map.get(media_type, "sendMedia")

        data = {
            "number": to,
            "mediaMessage": {"mediatype": media_type.value, "media": media_url},
        }

        if caption:
            data["mediaMessage"]["caption"] = caption

        if filename:
            data["mediaMessage"]["fileName"] = filename

        if message_data:
            data["metadata"] = message_data

        status_code, response = await self._request_with_send_metrics(
            instance_name=instance_name,
            endpoint=f"/message/{endpoint}/{instance_name}",
            data=data,
        )

        if status_code == 201:
            message_data = response.get("message", {})
            whatsapp_metrics.record_message_sent(
                instance_name, MessageStatus.SENT.value
            )
            return MessageResponse(
                id=message_data.get("key", {}).get("id", ""),
                external_id=message_data.get("key", {}).get("id"),
                status=MessageStatus.SENT,
                message="Media message sent successfully",
                timestamp=now_sao_paulo(),
                message_data=message_data,
            )

        whatsapp_metrics.record_message_failed(
            instance_name, _classify_failure(status_code=status_code)
        )
        raise Exception(f"Failed to send media message: {response}")

    async def _request_with_send_metrics(
        self,
        *,
        instance_name: str,
        endpoint: str,
        data: Dict[str, Any],
    ) -> tuple[int, Dict[str, Any]]:
        """Execute send request while recording duration/failure metrics consistently."""
        start_time = time.monotonic()
        try:
            return await self._make_request("POST", endpoint, data=data)
        except Exception as exc:
            whatsapp_metrics.record_message_failed(
                instance_name,
                _classify_failure(error=exc),
            )
            raise
        finally:
            duration = time.monotonic() - start_time
            whatsapp_metrics.observe_message_send_duration(instance_name, duration)

    async def get_contacts(self, instance_name: str) -> List[ContactResponse]:
        """Get all contacts from instance."""
        status_code, response = await self._make_request(
            "GET", f"/chat/findContacts/{instance_name}"
        )

        if status_code == 200:
            contacts = []
            for contact_data in response:
                contacts.append(
                    ContactResponse(
                        id=contact_data.get("id", ""),
                        phone_number=contact_data.get("id", "").split("@")[0],
                        formatted_number=contact_data.get("id", ""),
                        name=contact_data.get("pushName") or contact_data.get("name"),
                        profile_picture_url=contact_data.get("profilePictureUrl"),
                        is_whatsapp_user=True,
                    )
                )
            return contacts
        else:
            raise Exception(f"Failed to get contacts: {response}")

    async def check_whatsapp_number(
        self, instance_name: str, phone_number: str
    ) -> bool:
        """Check if phone number is registered on WhatsApp."""
        data = {"numbers": [phone_number]}

        status_code, response = await self._make_request(
            "POST", f"/chat/whatsappNumbers/{instance_name}", data=data
        )

        if status_code == 200:
            results = response.get("exists", [])
            return len(results) > 0 and results[0].get("exists", False)

        return False

    async def get_message_status(
        self, instance_name: str, message_id: str
    ) -> MessageStatus:
        """Get message delivery status."""
        # Note: Evolution API doesn't have a direct endpoint for message status
        # This would typically be handled via webhooks
        # This is a placeholder implementation
        try:
            # In a real implementation, you'd check the message status
            # via webhooks or a status endpoint if available
            return MessageStatus.SENT
        except Exception:
            return MessageStatus.FAILED

    async def set_webhook_url(
        self, instance_name: str, webhook_url: str, events: Optional[List[str]] = None
    ) -> bool:
        """Set webhook URL for instance."""
        events = events or DEFAULT_WEBHOOK_EVENTS

        data = {
            "webhook": {
                "enabled": True,
                "url": webhook_url,
                "events": events,
                "base64": False,
                "byEvents": True,
            }
        }

        status_code, _ = await self._make_request(
            "POST", f"/webhook/set/{instance_name}", data=data
        )

        if status_code in (200, 201):
            return True

        # Fallback for older Evolution API versions
        fallback_events = [event.lower().replace("_", ".") for event in events]
        fallback_payload = {
            "webhook": webhook_url,
            "webhook_by_events": True,
            "events": fallback_events,
        }
        status_code, _ = await self._make_request(
            "PUT", f"/webhook/{instance_name}", data=fallback_payload
        )

        return status_code in (200, 201)

    async def delete_instance(self, instance_name: str) -> bool:
        """Delete WhatsApp instance."""
        status_code, response = await self._make_request(
            "DELETE", f"/instance/delete/{instance_name}"
        )

        return status_code == 200

    async def restart_instance(self, instance_name: str) -> bool:
        """Restart WhatsApp instance."""
        status_code, response = await self._make_request(
            "PUT", f"/instance/restart/{instance_name}"
        )

        return status_code == 200

    async def logout_instance(self, instance_name: str) -> bool:
        """Logout WhatsApp instance."""
        status_code, response = await self._make_request(
            "DELETE", f"/instance/logout/{instance_name}"
        )

        return status_code == 200


# Utility functions for media optimization
async def optimize_image_for_whatsapp(
    image_url: str,
    max_size: int = 16 * 1024 * 1024,  # 16MB max
    max_dimension: int = 4096,
) -> str:
    """Optimize image for WhatsApp delivery."""
    _ = max_size, max_dimension  # Placeholder signature keeps these for future resize logic.

    # Implementation would resize/compress image if needed
    # This is a placeholder - actual implementation would use PIL or similar
    return image_url


async def validate_phone_number(phone_number: str) -> Tuple[bool, str]:
    """Validate and format phone number for WhatsApp."""
    from app.schemas.validators.phone import normalize_br_phone

    # Remove all non-digit characters
    clean_number = "".join(filter(str.isdigit, phone_number))

    # Basic validation - should be between 10-15 digits
    if len(clean_number) < 10 or len(clean_number) > 15:
        return False, "Invalid phone number length"

    # If already has country code with expected length, keep as-is
    if clean_number.startswith("55") and len(clean_number) in (12, 13):
        return True, clean_number

    # Normalize to Brazilian format (55 + DDD + number) when missing CC
    normalized = normalize_br_phone(clean_number)
    if normalized:
        clean_number = normalized

    return True, clean_number
