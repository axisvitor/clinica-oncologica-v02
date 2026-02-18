"""
Evolution API client main orchestration class.
Coordinates message sending, webhook handling, and API communication.
"""

from typing import Dict, List, Optional, Any
import asyncio
import atexit
import os

import httpx
import structlog

from app.config import settings
from app.utils.timezone import now_sao_paulo

from .rate_limiter import RateLimiter
from .request_handler import RequestHandler
from .message_sender import MessageSender
from .webhook_handler import WebhookHandler

logger = structlog.get_logger(__name__)


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
        railway_service: bool = False,
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
        self.railway_service = railway_service or getattr(
            settings, "RAILWAY_ENVIRONMENT", False
        )

        # URL configuration - prioritize Railway internal service
        if self.railway_service and hasattr(settings, "WHATSAPP_EVOLUTION_RAILWAY_URL"):
            self.base_url = settings.WHATSAPP_EVOLUTION_RAILWAY_URL.rstrip("/")
        else:
            env_base_url = os.getenv("WHATSAPP_EVOLUTION_API_URL")
            self.base_url = (
                base_url
                or env_base_url
                or getattr(
                    settings, "WHATSAPP_EVOLUTION_API_URL", "http://localhost:8080"
                )
            ).rstrip("/")

        env_instance = os.getenv("WHATSAPP_EVOLUTION_INSTANCE_NAME")
        self.instance_name = instance_name or env_instance or getattr(
            settings, "WHATSAPP_EVOLUTION_INSTANCE_NAME", "meuwhatsapp"
        )
        env_api_key = os.getenv("WHATSAPP_EVOLUTION_API_KEY")
        self.api_key = api_key or env_api_key or getattr(
            settings, "WHATSAPP_EVOLUTION_API_KEY", None
        )
        env_webhook_secret = os.getenv("WHATSAPP_EVOLUTION_WEBHOOK_SECRET")
        self.webhook_secret = webhook_secret or env_webhook_secret or getattr(
            settings, "WHATSAPP_EVOLUTION_WEBHOOK_SECRET", None
        )
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
            use_mock=self.use_mock,
        )

        # Rate limiting configuration
        rate_limit = getattr(settings, "EVOLUTION_RATE_LIMIT", 10)
        self.rate_limiter = RateLimiter(requests_per_second=rate_limit)

        # HTTP client configuration with proper headers
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Hormonia-System/1.0",
        }

        # Add API key to headers (Evolution uses different header names)
        if self.api_key:
            headers["apikey"] = self.api_key  # Standard Evolution header
            headers["Authorization"] = (
                f"Bearer {self.api_key}"  # Alternative auth method
            )

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers=headers,
            follow_redirects=True,
            limits=httpx.Limits(
                max_keepalive_connections=20, max_connections=100, keepalive_expiry=30.0
            ),
        )

        # Initialize specialized handlers
        self.request_handler = RequestHandler(
            client=self.client,
            base_url=self.base_url,
            rate_limiter=self.rate_limiter,
            max_retries=max_retries,
            retry_delay=retry_delay,
            use_mock=use_mock,
        )

        self.message_sender = MessageSender(
            request_handler=self.request_handler, instance_name=self.instance_name
        )

        environment = getattr(settings, "ENVIRONMENT", "development")
        self.webhook_handler = WebhookHandler(
            webhook_secret=self.webhook_secret,
            api_key=self.api_key,
            instance_name=self.instance_name,
            environment=environment,
        )

        logger.info(
            "Evolution API client initialized",
            instance_name=self.instance_name,
            base_url=self.base_url,
            timeout=timeout,
            max_retries=max_retries,
            rate_limit=rate_limit,
        )

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        _ = exc_type, exc_val, exc_tb
        await self.close()

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Compatibility shim used by legacy tests and call sites.

        Delegates to RequestHandler while preserving historical method name.
        """
        _ = retry_count
        return await self.request_handler.make_request(method, endpoint, data, params)

    # Message sending methods - delegate to MessageSender
    async def send_text_message(
        self, phone_number: str, message: str, delay: Optional[int] = None
    ) -> Dict[str, Any]:
        """Send text message via WhatsApp."""
        return await self.message_sender.send_text_message(phone_number, message, delay)

    async def send_button_message(
        self,
        phone_number: str,
        text: str,
        buttons: List[Dict[str, str]],
        delay: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send button message via WhatsApp."""
        return await self.message_sender.send_button_message(
            phone_number, text, buttons, delay
        )

    async def send_list_message(
        self,
        phone_number: str,
        text: str,
        title: str,
        sections: List[Dict[str, Any]],
        delay: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send list message via WhatsApp."""
        return await self.message_sender.send_list_message(
            phone_number, text, title, sections, delay
        )

    async def send_media_message(
        self,
        phone_number: str,
        media_url: str,
        media_type: str,
        caption: Optional[str] = None,
        delay: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Send media message via WhatsApp."""
        return await self.message_sender.send_media_message(
            phone_number, media_url, media_type, caption, delay
        )

    # Instance and message status methods
    async def get_instance_status(self) -> Dict[str, Any]:
        """
        Get WhatsApp instance connection status.

        Returns:
            Instance status information
        """
        endpoint = f"instance/connectionState/{self.instance_name}"
        return await self.request_handler.make_request("GET", endpoint)

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
        return await self.request_handler.make_request("GET", endpoint, params=params)

    # Webhook methods - delegate to WebhookHandler
    def validate_webhook_signature(
        self, payload: bytes, signature: str, secret: Optional[str] = None
    ) -> bool:
        """Validate webhook signature for security."""
        return self.webhook_handler.validate_signature(payload, signature, secret)

    def parse_webhook_event(self, payload: Dict[str, Any]):
        """Parse webhook event payload."""
        return self.webhook_handler.parse_event(payload)

    async def health_check(self) -> Dict[str, Any]:
        """
        Check Evolution API health and instance status.

        Returns:
            Health check results
        """
        health_status = {
            "service": "evolution_api",
            "healthy": False,
            "timestamp": now_sao_paulo().isoformat(),
            "details": {},
        }

        try:
            # Check instance connection state
            status_response = await self.get_instance_status()

            is_connected = False
            # Evolution APIs can return either {"status": "success", "data": {...}}
            # or {"instance": {...}} depending on deployment/version.
            connection_data = {}
            if status_response.get("status") == "success":
                connection_data = status_response.get("data", {}) or {}
            elif "instance" in status_response:
                connection_data = status_response.get("instance", {}) or {}
            else:
                # Fallback: assume payload is already the connection object
                connection_data = status_response or {}

            is_connected = (
                connection_data.get("connected", False)
                or connection_data.get("state") == "open"
            )

            health_status.update(
                {
                    "healthy": is_connected,
                    "details": {
                        "instance_name": self.instance_name,
                        "base_url": self.base_url,
                        "connected": is_connected,
                        "response": status_response,
                        "railway_service": self.railway_service,
                        "rate_limit_remaining": self.rate_limiter.get_remaining_quota(),
                    },
                }
            )

            logger.info(
                "Evolution API health check completed",
                healthy=is_connected,
                instance=self.instance_name,
            )

        except Exception as e:
            health_status["details"] = {
                "error": str(e),
                "error_type": type(e).__name__,
                "instance_name": self.instance_name,
            }
            logger.error(
                "Evolution API health check failed",
                error=str(e),
                instance=self.instance_name,
            )

        return health_status


# Global client instance with thread safety
_evolution_client: Optional[EvolutionClient] = None
_client_lock: asyncio.Lock = asyncio.Lock()
_shutdown_registered: bool = False


def _sync_cleanup_evolution_client() -> None:
    """
    Synchronous cleanup handler for atexit.

    Called automatically when the Python interpreter exits to ensure
    proper cleanup of HTTP client resources.
    """
    global _evolution_client

    if _evolution_client is not None:
        logger.info("Shutdown: Cleaning up Evolution API client")
        try:
            # Try to get or create an event loop for async cleanup
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop - create a new one for cleanup
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(_evolution_client.close())
                finally:
                    loop.close()
            else:
                # Running loop exists - schedule cleanup
                loop.create_task(_evolution_client.close())
        except Exception as e:
            logger.warning(f"Error during Evolution client cleanup: {e}")
        finally:
            _evolution_client = None


async def get_evolution_client() -> EvolutionClient:
    """
    Get global Evolution API client instance with thread-safe initialization.

    Returns:
        Configured Evolution API client

    Thread-safe: Uses asyncio.Lock to prevent race conditions during initialization

    Resource Management:
    - Registers atexit handler on first initialization
    - Ensures proper cleanup on application shutdown
    """
    global _evolution_client, _shutdown_registered

    # Fast path: client already initialized
    if _evolution_client is not None:
        return _evolution_client

    # Slow path: need to initialize (thread-safe)
    async with _client_lock:
        # Double-check after acquiring lock
        if _evolution_client is None:
            logger.info("Initializing global Evolution API client")
            _evolution_client = EvolutionClient()

            # Register shutdown handler on first initialization
            if not _shutdown_registered:
                atexit.register(_sync_cleanup_evolution_client)
                _shutdown_registered = True
                logger.debug("Registered Evolution client atexit cleanup handler")

            logger.info("Evolution API client initialized successfully")

    return _evolution_client


async def close_evolution_client():
    """Close global Evolution API client."""
    global _evolution_client

    if _evolution_client:
        await _evolution_client.close()
        _evolution_client = None
