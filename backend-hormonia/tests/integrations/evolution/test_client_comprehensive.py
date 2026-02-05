"""
Comprehensive unit tests for the Evolution API client.

Tests cover:
- Message sending (text, button, list, media)
- Rate limiting enforcement
- Retry logic with exponential backoff
- Connection health checks
- Error handling (400, 401, 429, 500 responses)
- Phone number validation/formatting
- Webhook signature validation
"""

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.integrations.evolution.client import (
    EvolutionClient,
    get_evolution_client,
    close_evolution_client,
)
from app.integrations.evolution.rate_limiter import RateLimiter
from app.integrations.evolution.request_handler import RequestHandler
from app.integrations.evolution.message_sender import MessageSender
from app.integrations.evolution.webhook_handler import WebhookHandler
from app.integrations.evolution.validators import (
    format_phone_number,
    validate_message_content,
)
from app.integrations.evolution.models import EvolutionAPIError


# =============================================================================
# TEST FIXTURES
# =============================================================================


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch("app.integrations.evolution.client.settings") as mock:
        mock.WHATSAPP_EVOLUTION_API_URL = "http://test-evolution-api.local"
        mock.WHATSAPP_EVOLUTION_INSTANCE_NAME = "test_instance"
        mock.WHATSAPP_EVOLUTION_API_KEY = "test_api_key_12345"
        mock.WHATSAPP_EVOLUTION_WEBHOOK_SECRET = "test_webhook_secret"
        mock.EVOLUTION_RATE_LIMIT = 10
        mock.ENVIRONMENT = "development"
        mock.RAILWAY_ENVIRONMENT = False
        yield mock


@pytest.fixture
def mock_httpx_client():
    """Mock httpx AsyncClient."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.timeout = MagicMock()
    mock_client.timeout.read = 30.0
    return mock_client


@pytest.fixture
def rate_limiter():
    """Create a rate limiter for testing."""
    return RateLimiter(requests_per_second=10)


@pytest.fixture
def request_handler(mock_httpx_client, rate_limiter):
    """Create a request handler for testing."""
    return RequestHandler(
        client=mock_httpx_client,
        base_url="http://test-evolution-api.local",
        rate_limiter=rate_limiter,
        max_retries=3,
        retry_delay=0.01,  # Fast retries for testing
        use_mock=False,
    )


@pytest.fixture
def message_sender(request_handler):
    """Create a message sender for testing."""
    return MessageSender(
        request_handler=request_handler,
        instance_name="test_instance",
    )


@pytest.fixture
def webhook_handler():
    """Create a webhook handler for testing."""
    return WebhookHandler(
        webhook_secret="test_webhook_secret",
        api_key="test_api_key",
        instance_name="test_instance",
        environment="development",
    )


@pytest.fixture
async def evolution_client(mock_settings):
    """Create an Evolution client for testing."""
    client = EvolutionClient(
        base_url="http://test-evolution-api.local",
        instance_name="test_instance",
        api_key="test_api_key_12345",
        webhook_secret="test_webhook_secret",
        timeout=30,
        max_retries=3,
        retry_delay=0.01,
        use_mock=True,  # Use mock mode for basic tests
    )
    yield client
    await client.close()


# =============================================================================
# API RESPONSE FIXTURES
# =============================================================================


@pytest.fixture
def success_text_response():
    """Successful text message response."""
    return {
        "status": "success",
        "data": {
            "id": "msg_123456789",
            "status": "pending",
            "timestamp": int(time.time() * 1000),
        },
    }


@pytest.fixture
def success_button_response():
    """Successful button message response."""
    return {
        "status": "success",
        "data": {
            "id": "btn_msg_123456789",
            "status": "pending",
            "timestamp": int(time.time() * 1000),
        },
    }


@pytest.fixture
def success_list_response():
    """Successful list message response."""
    return {
        "status": "success",
        "data": {
            "id": "list_msg_123456789",
            "status": "pending",
            "timestamp": int(time.time() * 1000),
        },
    }


@pytest.fixture
def success_media_response():
    """Successful media message response."""
    return {
        "status": "success",
        "data": {
            "id": "media_msg_123456789",
            "status": "pending",
            "timestamp": int(time.time() * 1000),
        },
    }


@pytest.fixture
def success_instance_status_response():
    """Successful instance status response."""
    return {
        "status": "success",
        "data": {
            "state": "open",
            "connected": True,
        },
    }


@pytest.fixture
def error_400_response():
    """Bad request error response."""
    return {
        "status": "error",
        "message": "Invalid request parameters",
        "code": 400,
    }


@pytest.fixture
def error_401_response():
    """Unauthorized error response."""
    return {
        "status": "error",
        "message": "Invalid API key",
        "code": 401,
    }


@pytest.fixture
def error_429_response():
    """Rate limit exceeded response."""
    return {
        "status": "error",
        "message": "Too many requests",
        "code": 429,
    }


@pytest.fixture
def error_500_response():
    """Server error response."""
    return {
        "status": "error",
        "message": "Internal server error",
        "code": 500,
    }


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_mock_response(
    status_code: int = 200,
    json_data: Optional[Dict[str, Any]] = None,
    content: bytes = b"",
    headers: Optional[Dict[str, str]] = None,
) -> MagicMock:
    """Create a mock httpx Response."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = status_code
    mock_response.content = content or json.dumps(json_data or {}).encode()
    mock_response.text = mock_response.content.decode()
    mock_response.headers = headers or {"content-type": "application/json"}
    mock_response.json.return_value = json_data or {}
    return mock_response


# =============================================================================
# TEST: PHONE NUMBER VALIDATION/FORMATTING
# =============================================================================


class TestPhoneNumberValidation:
    """Tests for phone number validation and formatting."""

    def test_format_phone_number_with_country_code(self):
        """Test phone number already has country code."""
        result = format_phone_number("5511999999999")
        assert result == "5511999999999"

    def test_format_phone_number_without_country_code_mobile(self):
        """Test mobile phone number without country code."""
        result = format_phone_number("11999999999")
        assert result == "5511999999999"

    def test_format_phone_number_without_country_code_landline(self):
        """Test landline phone number without country code."""
        result = format_phone_number("1133333333")
        assert result == "551133333333"

    def test_format_phone_number_removes_special_chars(self):
        """Test phone number with special characters."""
        result = format_phone_number("+55 (11) 99999-9999")
        assert result == "5511999999999"

    def test_format_phone_number_removes_spaces(self):
        """Test phone number with spaces."""
        result = format_phone_number("55 11 99999 9999")
        assert result == "5511999999999"

    def test_format_phone_number_empty_string(self):
        """Test empty phone number."""
        result = format_phone_number("")
        assert result == ""

    def test_format_phone_number_only_digits(self):
        """Test phone number extracts only digits."""
        result = format_phone_number("abc11999999999xyz")
        assert result == "5511999999999"


class TestMessageContentValidation:
    """Tests for message content validation."""

    def test_validate_message_content_valid(self):
        """Test valid message content."""
        # Should not raise
        validate_message_content("Hello, World!")

    def test_validate_message_content_empty_raises(self):
        """Test empty message raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_message_content("")
        assert "Cannot send empty message" in str(exc_info.value)

    def test_validate_message_content_whitespace_only_raises(self):
        """Test whitespace-only message raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_message_content("   ")
        assert "Cannot send empty message" in str(exc_info.value)

    def test_validate_message_content_none_raises(self):
        """Test None message raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            validate_message_content(None)
        assert "Cannot send empty message" in str(exc_info.value)

    def test_validate_message_content_unicode(self):
        """Test unicode message content."""
        # Should not raise
        validate_message_content("Ola! Como voce esta?")

    def test_validate_message_content_emoji(self):
        """Test emoji in message content."""
        # Should not raise - note: emojis are valid in messages to users
        validate_message_content("Hello! Ola!")


# =============================================================================
# TEST: RATE LIMITER
# =============================================================================


class TestRateLimiter:
    """Tests for rate limiter functionality."""

    def test_rate_limiter_allows_requests_under_limit(self):
        """Test rate limiter allows requests under the limit."""
        limiter = RateLimiter(requests_per_second=5)

        for _ in range(5):
            assert limiter.check_rate_limit() is True

    def test_rate_limiter_blocks_requests_over_limit(self):
        """Test rate limiter blocks requests over the limit."""
        limiter = RateLimiter(requests_per_second=3)

        # Use up the quota
        for _ in range(3):
            assert limiter.check_rate_limit() is True

        # Next request should be blocked
        assert limiter.check_rate_limit() is False

    def test_rate_limiter_resets_after_one_second(self):
        """Test rate limiter resets after one second."""
        limiter = RateLimiter(requests_per_second=2)

        # Use up the quota
        assert limiter.check_rate_limit() is True
        assert limiter.check_rate_limit() is True
        assert limiter.check_rate_limit() is False

        # Wait for reset
        time.sleep(1.1)

        # Should be allowed again
        assert limiter.check_rate_limit() is True

    def test_rate_limiter_get_remaining_quota(self):
        """Test getting remaining quota."""
        limiter = RateLimiter(requests_per_second=5)

        assert limiter.get_remaining_quota() == 5

        limiter.check_rate_limit()
        assert limiter.get_remaining_quota() == 4

        limiter.check_rate_limit()
        limiter.check_rate_limit()
        assert limiter.get_remaining_quota() == 2

    def test_rate_limiter_quota_never_negative(self):
        """Test remaining quota never goes negative."""
        limiter = RateLimiter(requests_per_second=2)

        # Exhaust quota
        for _ in range(10):
            limiter.check_rate_limit()

        assert limiter.get_remaining_quota() == 0


# =============================================================================
# TEST: SEND TEXT MESSAGE
# =============================================================================


class TestSendTextMessage:
    """Tests for send_text_message functionality."""

    @pytest.mark.asyncio
    async def test_send_text_message_success(self, evolution_client):
        """Test successful text message sending."""
        result = await evolution_client.send_text_message(
            phone_number="5511999999999",
            message="Hello, World!",
        )

        assert result["status"] == "success"
        assert "data" in result
        assert "id" in result["data"]

    @pytest.mark.asyncio
    async def test_send_text_message_with_delay(self, evolution_client):
        """Test text message with delay parameter."""
        result = await evolution_client.send_text_message(
            phone_number="5511999999999",
            message="Delayed message",
            delay=5000,
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_send_text_message_formats_phone_number(
        self, request_handler, success_text_response
    ):
        """Test phone number is formatted before sending."""
        message_sender = MessageSender(
            request_handler=request_handler,
            instance_name="test_instance",
        )

        # Mock the request handler
        request_handler.make_request = AsyncMock(return_value=success_text_response)

        await message_sender.send_text_message(
            phone_number="(11) 99999-9999",
            message="Test message",
        )

        # Verify the formatted number was used
        call_args = request_handler.make_request.call_args
        payload = call_args[0][2]  # Third argument is data
        assert payload["number"] == "5511999999999"

    @pytest.mark.asyncio
    async def test_send_text_message_empty_raises(self, evolution_client):
        """Test empty message raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            await evolution_client.send_text_message(
                phone_number="5511999999999",
                message="",
            )
        assert "Cannot send empty message" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_text_message_payload_format(
        self, request_handler, success_text_response
    ):
        """Test text message payload format."""
        message_sender = MessageSender(
            request_handler=request_handler,
            instance_name="test_instance",
        )

        request_handler.make_request = AsyncMock(return_value=success_text_response)

        await message_sender.send_text_message(
            phone_number="5511999999999",
            message="Test message content",
        )

        call_args = request_handler.make_request.call_args
        method, endpoint, payload = call_args[0]

        assert method == "POST"
        assert "sendText" in endpoint
        assert payload["number"] == "5511999999999"
        assert payload["text"] == "Test message content"

    @pytest.mark.asyncio
    async def test_send_text_message_unicode_encoding(
        self, request_handler, success_text_response
    ):
        """Test unicode characters in message."""
        message_sender = MessageSender(
            request_handler=request_handler,
            instance_name="test_instance",
        )

        request_handler.make_request = AsyncMock(return_value=success_text_response)

        unicode_message = "Ola! Como vai voce?"
        await message_sender.send_text_message(
            phone_number="5511999999999",
            message=unicode_message,
        )

        call_args = request_handler.make_request.call_args
        payload = call_args[0][2]
        assert payload["text"] == unicode_message


# =============================================================================
# TEST: SEND BUTTON MESSAGE
# =============================================================================


class TestSendButtonMessage:
    """Tests for send_button_message functionality."""

    @pytest.mark.asyncio
    async def test_send_button_message_success(self, evolution_client):
        """Test successful button message sending."""
        buttons = [
            {"displayText": "Option 1", "id": "opt1"},
            {"displayText": "Option 2", "id": "opt2"},
        ]

        result = await evolution_client.send_button_message(
            phone_number="5511999999999",
            text="Please select an option:",
            buttons=buttons,
        )

        assert result["status"] == "success"
        assert "data" in result

    @pytest.mark.asyncio
    async def test_send_button_message_payload_structure(
        self, request_handler, success_button_response
    ):
        """Test button message payload structure."""
        message_sender = MessageSender(
            request_handler=request_handler,
            instance_name="test_instance",
        )

        request_handler.make_request = AsyncMock(return_value=success_button_response)

        buttons = [
            {"displayText": "Confirm", "id": "confirm"},
            {"displayText": "Cancel", "id": "cancel"},
        ]

        await message_sender.send_button_message(
            phone_number="5511999999999",
            text="Please confirm your choice:",
            buttons=buttons,
        )

        call_args = request_handler.make_request.call_args
        method, endpoint, payload = call_args[0]

        assert method == "POST"
        assert "sendButtons" in endpoint
        assert "buttonMessage" in payload
        assert payload["buttonMessage"]["text"] == "Please confirm your choice:"
        assert "buttons" in payload["buttonMessage"]

    @pytest.mark.asyncio
    async def test_send_button_message_button_formatting(
        self, request_handler, success_button_response
    ):
        """Test buttons are formatted correctly with index."""
        message_sender = MessageSender(
            request_handler=request_handler,
            instance_name="test_instance",
        )

        request_handler.make_request = AsyncMock(return_value=success_button_response)

        buttons = [
            {"displayText": "Button A", "id": "a"},
            {"displayText": "Button B", "id": "b"},
        ]

        await message_sender.send_button_message(
            phone_number="5511999999999",
            text="Select:",
            buttons=buttons,
        )

        call_args = request_handler.make_request.call_args
        payload = call_args[0][2]
        formatted_buttons = payload["buttonMessage"]["buttons"]

        assert len(formatted_buttons) == 2
        assert formatted_buttons[0]["index"] == 1
        assert formatted_buttons[1]["index"] == 2
        assert "urlButton" in formatted_buttons[0]

    @pytest.mark.asyncio
    async def test_send_button_message_with_delay(
        self, request_handler, success_button_response
    ):
        """Test button message with delay."""
        message_sender = MessageSender(
            request_handler=request_handler,
            instance_name="test_instance",
        )

        request_handler.make_request = AsyncMock(return_value=success_button_response)

        await message_sender.send_button_message(
            phone_number="5511999999999",
            text="Select:",
            buttons=[{"displayText": "OK", "id": "ok"}],
            delay=3000,
        )

        call_args = request_handler.make_request.call_args
        payload = call_args[0][2]
        assert payload["delay"] == 3000


# =============================================================================
# TEST: SEND LIST MESSAGE
# =============================================================================


class TestSendListMessage:
    """Tests for send_list_message functionality."""

    @pytest.mark.asyncio
    async def test_send_list_message_success(self, evolution_client):
        """Test successful list message sending."""
        sections = [
            {
                "title": "Section 1",
                "rows": [
                    {"title": "Item 1", "description": "Description 1", "rowId": "row1"},
                    {"title": "Item 2", "description": "Description 2", "rowId": "row2"},
                ],
            }
        ]

        result = await evolution_client.send_list_message(
            phone_number="5511999999999",
            text="Please select from the list:",
            title="Options",
            sections=sections,
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_send_list_message_payload_structure(
        self, request_handler, success_list_response
    ):
        """Test list message payload structure."""
        message_sender = MessageSender(
            request_handler=request_handler,
            instance_name="test_instance",
        )

        request_handler.make_request = AsyncMock(return_value=success_list_response)

        sections = [
            {
                "title": "Products",
                "rows": [
                    {"title": "Product A", "description": "Desc A", "rowId": "prod_a"},
                ],
            },
            {
                "title": "Services",
                "rows": [
                    {"title": "Service B", "description": "Desc B", "rowId": "svc_b"},
                ],
            },
        ]

        await message_sender.send_list_message(
            phone_number="5511999999999",
            text="Choose an item:",
            title="Menu",
            sections=sections,
        )

        call_args = request_handler.make_request.call_args
        method, endpoint, payload = call_args[0]

        assert method == "POST"
        assert "sendList" in endpoint
        assert "listMessage" in payload
        assert payload["listMessage"]["text"] == "Choose an item:"
        assert payload["listMessage"]["title"] == "Menu"
        assert len(payload["listMessage"]["sections"]) == 2

    @pytest.mark.asyncio
    async def test_send_list_message_with_delay(
        self, request_handler, success_list_response
    ):
        """Test list message with delay."""
        message_sender = MessageSender(
            request_handler=request_handler,
            instance_name="test_instance",
        )

        request_handler.make_request = AsyncMock(return_value=success_list_response)

        await message_sender.send_list_message(
            phone_number="5511999999999",
            text="Select:",
            title="Options",
            sections=[{"title": "Section", "rows": []}],
            delay=2000,
        )

        call_args = request_handler.make_request.call_args
        payload = call_args[0][2]
        assert payload["delay"] == 2000


# =============================================================================
# TEST: SEND MEDIA MESSAGE
# =============================================================================


class TestSendMediaMessage:
    """Tests for send_media_message functionality."""

    @pytest.mark.asyncio
    async def test_send_media_message_image(self, evolution_client):
        """Test sending image message."""
        result = await evolution_client.send_media_message(
            phone_number="5511999999999",
            media_url="https://example.com/image.jpg",
            media_type="image",
            caption="Check out this image!",
        )

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_send_media_message_video(
        self, request_handler, success_media_response
    ):
        """Test sending video message."""
        message_sender = MessageSender(
            request_handler=request_handler,
            instance_name="test_instance",
        )

        request_handler.make_request = AsyncMock(return_value=success_media_response)

        await message_sender.send_media_message(
            phone_number="5511999999999",
            media_url="https://example.com/video.mp4",
            media_type="video",
            caption="Watch this video",
        )

        call_args = request_handler.make_request.call_args
        payload = call_args[0][2]

        assert payload["mediaMessage"]["mediatype"] == "video"
        assert payload["mediaMessage"]["media"] == "https://example.com/video.mp4"

    @pytest.mark.asyncio
    async def test_send_media_message_audio(
        self, request_handler, success_media_response
    ):
        """Test sending audio message."""
        message_sender = MessageSender(
            request_handler=request_handler,
            instance_name="test_instance",
        )

        request_handler.make_request = AsyncMock(return_value=success_media_response)

        await message_sender.send_media_message(
            phone_number="5511999999999",
            media_url="https://example.com/audio.mp3",
            media_type="audio",
        )

        call_args = request_handler.make_request.call_args
        payload = call_args[0][2]

        assert payload["mediaMessage"]["mediatype"] == "audio"
        assert "caption" not in payload["mediaMessage"]

    @pytest.mark.asyncio
    async def test_send_media_message_document(
        self, request_handler, success_media_response
    ):
        """Test sending document message."""
        message_sender = MessageSender(
            request_handler=request_handler,
            instance_name="test_instance",
        )

        request_handler.make_request = AsyncMock(return_value=success_media_response)

        await message_sender.send_media_message(
            phone_number="5511999999999",
            media_url="https://example.com/document.pdf",
            media_type="document",
            caption="Important document",
        )

        call_args = request_handler.make_request.call_args
        payload = call_args[0][2]

        assert payload["mediaMessage"]["mediatype"] == "document"
        assert payload["mediaMessage"]["caption"] == "Important document"

    @pytest.mark.asyncio
    async def test_send_media_message_payload_structure(
        self, request_handler, success_media_response
    ):
        """Test media message payload structure."""
        message_sender = MessageSender(
            request_handler=request_handler,
            instance_name="test_instance",
        )

        request_handler.make_request = AsyncMock(return_value=success_media_response)

        await message_sender.send_media_message(
            phone_number="5511999999999",
            media_url="https://example.com/file.jpg",
            media_type="image",
            caption="A caption",
            delay=1000,
        )

        call_args = request_handler.make_request.call_args
        method, endpoint, payload = call_args[0]

        assert method == "POST"
        assert "sendMedia" in endpoint
        assert payload["number"] == "5511999999999"
        assert "mediaMessage" in payload
        assert payload["mediaMessage"]["mediatype"] == "image"
        assert payload["mediaMessage"]["media"] == "https://example.com/file.jpg"
        assert payload["mediaMessage"]["caption"] == "A caption"
        assert payload["delay"] == 1000


# =============================================================================
# TEST: RETRY LOGIC WITH EXPONENTIAL BACKOFF
# =============================================================================


class TestRetryLogic:
    """Tests for retry logic with exponential backoff."""

    @pytest.mark.asyncio
    async def test_retry_on_500_error(
        self, mock_httpx_client, rate_limiter, error_500_response
    ):
        """Test retry on 500 server error."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=3,
            retry_delay=0.01,
        )

        # First two calls fail, third succeeds
        mock_httpx_client.request.side_effect = [
            create_mock_response(500, error_500_response),
            create_mock_response(500, error_500_response),
            create_mock_response(200, {"status": "success", "data": {}}),
        ]

        result = await request_handler.make_request("GET", "/test")

        assert result["status"] == "success"
        assert mock_httpx_client.request.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_429_rate_limit(
        self, mock_httpx_client, rate_limiter, error_429_response
    ):
        """Test retry on 429 rate limit error."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=2,
            retry_delay=0.01,
        )

        # First call fails with 429, second succeeds
        mock_httpx_client.request.side_effect = [
            create_mock_response(429, error_429_response),
            create_mock_response(200, {"status": "success", "data": {}}),
        ]

        result = await request_handler.make_request("GET", "/test")

        assert result["status"] == "success"
        assert mock_httpx_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(
        self, mock_httpx_client, rate_limiter, error_500_response
    ):
        """Test error raised when max retries exceeded."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=2,
            retry_delay=0.01,
        )

        # All calls fail
        mock_httpx_client.request.return_value = create_mock_response(
            500, error_500_response
        )

        with pytest.raises(EvolutionAPIError) as exc_info:
            await request_handler.make_request("GET", "/test")

        assert "500" in str(exc_info.value)
        assert mock_httpx_client.request.call_count == 3  # Initial + 2 retries

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, mock_httpx_client, rate_limiter):
        """Test retry on timeout error."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=2,
            retry_delay=0.01,
        )

        # First call times out, second succeeds
        mock_httpx_client.request.side_effect = [
            httpx.TimeoutException("Connection timed out"),
            create_mock_response(200, {"status": "success", "data": {}}),
        ]

        result = await request_handler.make_request("GET", "/test")

        assert result["status"] == "success"
        assert mock_httpx_client.request.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_network_error(self, mock_httpx_client, rate_limiter):
        """Test retry on network error."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=2,
            retry_delay=0.01,
        )

        # First call has network error, second succeeds
        mock_httpx_client.request.side_effect = [
            httpx.ConnectError("Connection refused"),
            create_mock_response(200, {"status": "success", "data": {}}),
        ]

        result = await request_handler.make_request("GET", "/test")

        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_no_retry_on_400_error(
        self, mock_httpx_client, rate_limiter, error_400_response
    ):
        """Test no retry on 400 client error."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=3,
            retry_delay=0.01,
        )

        mock_httpx_client.request.return_value = create_mock_response(
            400, error_400_response
        )

        with pytest.raises(EvolutionAPIError) as exc_info:
            await request_handler.make_request("GET", "/test")

        assert "400" in str(exc_info.value)
        # Should not retry on 4xx (except 429)
        assert mock_httpx_client.request.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retry_on_401_error(
        self, mock_httpx_client, rate_limiter, error_401_response
    ):
        """Test no retry on 401 unauthorized error."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=3,
            retry_delay=0.01,
        )

        mock_httpx_client.request.return_value = create_mock_response(
            401, error_401_response
        )

        with pytest.raises(EvolutionAPIError) as exc_info:
            await request_handler.make_request("GET", "/test")

        assert "401" in str(exc_info.value)
        # Should not retry on 401
        assert mock_httpx_client.request.call_count == 1


# =============================================================================
# TEST: CONNECTION HEALTH CHECK
# =============================================================================


class TestHealthCheck:
    """Tests for connection health check."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, evolution_client):
        """Test health check returns healthy status."""
        result = await evolution_client.health_check()

        assert result["service"] == "evolution_api"
        assert result["healthy"] is True
        assert "timestamp" in result
        assert "details" in result
        assert result["details"]["instance_name"] == "test_instance"

    @pytest.mark.asyncio
    async def test_health_check_connected_state(
        self, mock_httpx_client, rate_limiter, success_instance_status_response
    ):
        """Test health check detects connected state."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=1,
            retry_delay=0.01,
        )

        mock_httpx_client.request.return_value = create_mock_response(
            200, success_instance_status_response
        )

        with patch("app.integrations.evolution.client.settings") as mock_settings:
            mock_settings.WHATSAPP_EVOLUTION_API_URL = "http://test-api.local"
            mock_settings.WHATSAPP_EVOLUTION_INSTANCE_NAME = "test"
            mock_settings.WHATSAPP_EVOLUTION_API_KEY = "key"
            mock_settings.EVOLUTION_RATE_LIMIT = 10
            mock_settings.ENVIRONMENT = "development"
            mock_settings.RAILWAY_ENVIRONMENT = False

            client = EvolutionClient(use_mock=False)
            client.request_handler = request_handler

            result = await client.health_check()

            assert result["healthy"] is True
            assert result["details"]["connected"] is True

            await client.close()

    @pytest.mark.asyncio
    async def test_health_check_disconnected_state(
        self, mock_httpx_client, rate_limiter
    ):
        """Test health check detects disconnected state."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=1,
            retry_delay=0.01,
        )

        disconnected_response = {
            "status": "success",
            "data": {"state": "close", "connected": False},
        }

        mock_httpx_client.request.return_value = create_mock_response(
            200, disconnected_response
        )

        with patch("app.integrations.evolution.client.settings") as mock_settings:
            mock_settings.WHATSAPP_EVOLUTION_API_URL = "http://test-api.local"
            mock_settings.WHATSAPP_EVOLUTION_INSTANCE_NAME = "test"
            mock_settings.WHATSAPP_EVOLUTION_API_KEY = "key"
            mock_settings.EVOLUTION_RATE_LIMIT = 10
            mock_settings.ENVIRONMENT = "development"
            mock_settings.RAILWAY_ENVIRONMENT = False

            client = EvolutionClient(use_mock=False)
            client.request_handler = request_handler

            result = await client.health_check()

            assert result["healthy"] is False
            assert result["details"]["connected"] is False

            await client.close()

    @pytest.mark.asyncio
    async def test_health_check_error_handling(
        self, mock_httpx_client, rate_limiter
    ):
        """Test health check handles errors gracefully."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=1,
            retry_delay=0.01,
        )

        mock_httpx_client.request.side_effect = httpx.ConnectError("Connection refused")

        with patch("app.integrations.evolution.client.settings") as mock_settings:
            mock_settings.WHATSAPP_EVOLUTION_API_URL = "http://test-api.local"
            mock_settings.WHATSAPP_EVOLUTION_INSTANCE_NAME = "test"
            mock_settings.WHATSAPP_EVOLUTION_API_KEY = "key"
            mock_settings.EVOLUTION_RATE_LIMIT = 10
            mock_settings.ENVIRONMENT = "development"
            mock_settings.RAILWAY_ENVIRONMENT = False

            client = EvolutionClient(use_mock=False)
            client.request_handler = request_handler

            result = await client.health_check()

            assert result["healthy"] is False
            assert "error" in result["details"]

            await client.close()


# =============================================================================
# TEST: ERROR HANDLING
# =============================================================================


class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_error_400_bad_request(
        self, mock_httpx_client, rate_limiter, error_400_response
    ):
        """Test 400 Bad Request error handling."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=1,
            retry_delay=0.01,
        )

        mock_httpx_client.request.return_value = create_mock_response(
            400, error_400_response
        )

        with pytest.raises(EvolutionAPIError) as exc_info:
            await request_handler.make_request("POST", "/test", {"data": "invalid"})

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_error_401_unauthorized(
        self, mock_httpx_client, rate_limiter, error_401_response
    ):
        """Test 401 Unauthorized error handling."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=1,
            retry_delay=0.01,
        )

        mock_httpx_client.request.return_value = create_mock_response(
            401, error_401_response
        )

        with pytest.raises(EvolutionAPIError) as exc_info:
            await request_handler.make_request("GET", "/test")

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_error_429_rate_limit_exhausted(
        self, mock_httpx_client, rate_limiter, error_429_response
    ):
        """Test 429 Rate Limit error when retries exhausted."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=1,
            retry_delay=0.01,
        )

        mock_httpx_client.request.return_value = create_mock_response(
            429, error_429_response
        )

        with pytest.raises(EvolutionAPIError) as exc_info:
            await request_handler.make_request("GET", "/test")

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_error_500_server_error(
        self, mock_httpx_client, rate_limiter, error_500_response
    ):
        """Test 500 Server Error handling."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=1,
            retry_delay=0.01,
        )

        mock_httpx_client.request.return_value = create_mock_response(
            500, error_500_response
        )

        with pytest.raises(EvolutionAPIError) as exc_info:
            await request_handler.make_request("GET", "/test")

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_error_timeout(self, mock_httpx_client, rate_limiter):
        """Test timeout error handling."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=1,
            retry_delay=0.01,
        )

        mock_httpx_client.request.side_effect = httpx.TimeoutException("Timeout")

        with pytest.raises(EvolutionAPIError) as exc_info:
            await request_handler.make_request("GET", "/test")

        assert "timeout" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_error_network(self, mock_httpx_client, rate_limiter):
        """Test network error handling."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=1,
            retry_delay=0.01,
        )

        mock_httpx_client.request.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(EvolutionAPIError) as exc_info:
            await request_handler.make_request("GET", "/test")

        assert "network error" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_error_response_data_preserved(
        self, mock_httpx_client, rate_limiter
    ):
        """Test error response data is preserved in exception."""
        request_handler = RequestHandler(
            client=mock_httpx_client,
            base_url="http://test-api.local",
            rate_limiter=rate_limiter,
            max_retries=1,
            retry_delay=0.01,
        )

        error_data = {
            "status": "error",
            "message": "Validation failed",
            "errors": [{"field": "phone", "message": "Invalid format"}],
        }

        mock_httpx_client.request.return_value = create_mock_response(400, error_data)

        with pytest.raises(EvolutionAPIError) as exc_info:
            await request_handler.make_request("POST", "/test", {})

        assert exc_info.value.response_data == error_data

    @pytest.mark.asyncio
    async def test_rate_limit_error_from_limiter(self):
        """Test rate limit error from internal rate limiter."""
        # Create a mock rate limiter that always returns False
        mock_rate_limiter = MagicMock(spec=RateLimiter)
        mock_rate_limiter.check_rate_limit.return_value = False

        mock_client = AsyncMock(spec=httpx.AsyncClient)

        request_handler = RequestHandler(
            client=mock_client,
            base_url="http://test-api.local",
            rate_limiter=mock_rate_limiter,
            max_retries=0,
            retry_delay=0.01,
        )

        with pytest.raises(EvolutionAPIError) as exc_info:
            await request_handler.make_request("GET", "/test")

        assert "rate limit" in str(exc_info.value).lower()


# =============================================================================
# TEST: WEBHOOK SIGNATURE VALIDATION
# =============================================================================


class TestWebhookValidation:
    """Tests for webhook signature validation."""

    def test_validate_signature_sha256(self, webhook_handler):
        """Test SHA256 signature validation."""
        payload = b'{"event": "message.received", "data": {}}'
        secret = "test_webhook_secret"

        # Calculate correct signature
        expected_signature = hmac.new(
            secret.encode(), payload, hashlib.sha256
        ).hexdigest()

        result = webhook_handler.validate_signature(
            payload, expected_signature, secret
        )

        assert result is True

    def test_validate_signature_sha256_with_prefix(self, webhook_handler):
        """Test SHA256 signature with sha256= prefix."""
        payload = b'{"event": "message.received"}'
        secret = "test_webhook_secret"

        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        signature_with_prefix = f"sha256={signature}"

        result = webhook_handler.validate_signature(
            payload, signature_with_prefix, secret
        )

        assert result is True

    def test_validate_signature_sha1(self, webhook_handler):
        """Test SHA1 signature validation (legacy support)."""
        payload = b'{"event": "test"}'
        secret = "test_webhook_secret"

        signature = hmac.new(secret.encode(), payload, hashlib.sha1).hexdigest()

        result = webhook_handler.validate_signature(payload, signature, secret)

        assert result is True

    def test_validate_signature_invalid(self, webhook_handler):
        """Test invalid signature is rejected."""
        payload = b'{"event": "message.received"}'
        invalid_signature = "invalid_signature_12345"

        result = webhook_handler.validate_signature(
            payload, invalid_signature, "test_webhook_secret"
        )

        assert result is False

    def test_validate_signature_no_secret_development(self):
        """Test no secret allows validation in development."""
        handler = WebhookHandler(
            webhook_secret=None,
            api_key=None,
            environment="development",
        )

        result = handler.validate_signature(b'{"data": {}}', "any_signature")

        # Development mode allows without secret
        assert result is True

    def test_validate_signature_no_secret_production(self):
        """Test no secret fails validation in production."""
        handler = WebhookHandler(
            webhook_secret=None,
            api_key=None,
            environment="production",
        )

        result = handler.validate_signature(b'{"data": {}}', "any_signature")

        # Production mode requires secret
        assert result is False

    def test_validate_signature_uses_api_key_fallback(self):
        """Test API key is used as fallback for validation."""
        handler = WebhookHandler(
            webhook_secret=None,
            api_key="api_key_as_secret",
            environment="development",
        )

        payload = b'{"event": "test"}'
        signature = hmac.new(
            b"api_key_as_secret", payload, hashlib.sha256
        ).hexdigest()

        result = handler.validate_signature(payload, signature)

        assert result is True


# =============================================================================
# TEST: WEBHOOK EVENT PARSING
# =============================================================================


class TestWebhookEventParsing:
    """Tests for webhook event parsing."""

    def test_parse_event_full_payload(self, webhook_handler):
        """Test parsing full webhook payload."""
        payload = {
            "event": "message.received",
            "instance": "test_instance",
            "data": {
                "message": {
                    "from": "5511999999999",
                    "body": "Hello",
                }
            },
        }

        event = webhook_handler.parse_event(payload)

        assert event.event == "message.received"
        assert event.instance == "test_instance"
        assert event.data["message"]["body"] == "Hello"

    def test_parse_event_infers_message_received(self, webhook_handler):
        """Test event type inference for message received."""
        payload = {
            "instance": "test_instance",
            "data": {
                "message": {"body": "Test message"},
            },
        }

        event = webhook_handler.parse_event(payload)

        assert event.event == "message.received"

    def test_parse_event_infers_message_status(self, webhook_handler):
        """Test event type inference for message status."""
        payload = {
            "instance": "test_instance",
            "data": {
                "status": "delivered",
            },
        }

        event = webhook_handler.parse_event(payload)

        assert event.event == "message.status"

    def test_parse_event_unknown_type(self, webhook_handler):
        """Test unknown event type handling."""
        payload = {
            "instance": "test_instance",
            "data": {"custom": "data"},
        }

        event = webhook_handler.parse_event(payload)

        assert event.event == "unknown"

    def test_parse_event_uses_default_instance(self, webhook_handler):
        """Test default instance name is used when not provided."""
        payload = {
            "event": "message.received",
            "data": {},
        }

        event = webhook_handler.parse_event(payload)

        assert event.instance == "test_instance"  # Default from handler

    def test_parse_event_invalid_payload(self, webhook_handler):
        """Test parsing invalid payload raises error."""
        with pytest.raises(EvolutionAPIError) as exc_info:
            webhook_handler.parse_event({"invalid": "missing required fields"})

        assert "Invalid webhook payload" in str(exc_info.value)


# =============================================================================
# TEST: CLIENT LIFECYCLE
# =============================================================================


class TestClientLifecycle:
    """Tests for client lifecycle management."""

    @pytest.mark.asyncio
    async def test_client_context_manager(self, mock_settings):
        """Test client works as async context manager."""
        async with EvolutionClient(use_mock=True) as client:
            result = await client.send_text_message(
                phone_number="5511999999999",
                message="Test",
            )
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_client_close(self, mock_settings):
        """Test client closes properly."""
        client = EvolutionClient(use_mock=True)

        # Client should work
        result = await client.send_text_message(
            phone_number="5511999999999",
            message="Test",
        )
        assert result["status"] == "success"

        # Close client
        await client.close()

    @pytest.mark.asyncio
    async def test_get_evolution_client_singleton(self, mock_settings):
        """Test global client is singleton."""
        # Reset global state
        import app.integrations.evolution.client as client_module
        client_module._evolution_client = None

        client1 = await get_evolution_client()
        client2 = await get_evolution_client()

        assert client1 is client2

        await close_evolution_client()


# =============================================================================
# TEST: REQUEST HANDLER URL BUILDING
# =============================================================================


class TestRequestHandlerUrlBuilding:
    """Tests for URL building in request handler."""

    def test_get_endpoint_url_simple(self, request_handler):
        """Test simple endpoint URL building."""
        url = request_handler._get_endpoint_url("test/endpoint")
        assert url == "http://test-evolution-api.local/test/endpoint"

    def test_get_endpoint_url_with_leading_slash(self, request_handler):
        """Test endpoint with leading slash."""
        url = request_handler._get_endpoint_url("/test/endpoint")
        assert url == "http://test-evolution-api.local/test/endpoint"

    def test_get_endpoint_url_complex_path(self, request_handler):
        """Test complex endpoint path."""
        url = request_handler._get_endpoint_url("message/sendText/instance_name")
        assert url == "http://test-evolution-api.local/message/sendText/instance_name"


# =============================================================================
# TEST: MOCK MODE
# =============================================================================


class TestMockMode:
    """Tests for mock mode functionality."""

    @pytest.mark.asyncio
    async def test_mock_mode_send_text(self, mock_settings):
        """Test mock mode for send text."""
        client = EvolutionClient(use_mock=True)

        result = await client.send_text_message(
            phone_number="5511999999999",
            message="Test message",
        )

        assert result["status"] == "success"
        assert "id" in result["data"]
        assert result["data"]["id"].startswith("mock_")

        await client.close()

    @pytest.mark.asyncio
    async def test_mock_mode_connection_state(self, mock_settings):
        """Test mock mode for connection state."""
        client = EvolutionClient(use_mock=True)

        result = await client.get_instance_status()

        assert result["status"] == "success"
        assert result["data"]["connected"] is True

        await client.close()


# =============================================================================
# TEST: EVOLUTION API ERROR
# =============================================================================


class TestEvolutionAPIError:
    """Tests for EvolutionAPIError exception."""

    def test_error_with_message_only(self):
        """Test error with message only."""
        error = EvolutionAPIError("Something went wrong")

        assert "Something went wrong" in str(error)
        assert error.status_code is None
        assert error.response_data is None

    def test_error_with_status_code(self):
        """Test error with status code."""
        error = EvolutionAPIError("Bad request", status_code=400)

        assert error.status_code == 400

    def test_error_with_response_data(self):
        """Test error with response data."""
        response_data = {"errors": ["Invalid phone"]}
        error = EvolutionAPIError(
            "Validation failed",
            status_code=400,
            response_data=response_data,
        )

        assert error.response_data == response_data
        assert error.status_code == 400


# =============================================================================
# TEST: CLIENT INITIALIZATION
# =============================================================================


class TestClientInitialization:
    """Tests for client initialization."""

    @pytest.mark.asyncio
    async def test_client_default_values(self, mock_settings):
        """Test client uses default values from settings."""
        client = EvolutionClient()

        assert client.instance_name == "test_instance"
        assert client.api_key == "test_api_key_12345"
        assert client.timeout == 30

        await client.close()

    @pytest.mark.asyncio
    async def test_client_custom_values(self, mock_settings):
        """Test client accepts custom values."""
        client = EvolutionClient(
            base_url="http://custom-api.local",
            instance_name="custom_instance",
            api_key="custom_key",
            timeout=60,
            max_retries=5,
        )

        assert client.base_url == "http://custom-api.local"
        assert client.instance_name == "custom_instance"
        assert client.api_key == "custom_key"
        assert client.timeout == 60
        assert client.max_retries == 5

        await client.close()

    @pytest.mark.asyncio
    async def test_client_headers_include_api_key(self, mock_settings):
        """Test client headers include API key."""
        client = EvolutionClient(api_key="test_key")

        headers = client.client.headers
        assert "apikey" in headers
        assert headers["apikey"] == "test_key"

        await client.close()

    @pytest.mark.asyncio
    async def test_client_strips_trailing_slash_from_url(self, mock_settings):
        """Test client strips trailing slash from base URL."""
        client = EvolutionClient(base_url="http://api.local/")

        assert client.base_url == "http://api.local"

        await client.close()
