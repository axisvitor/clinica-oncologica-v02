"""
HTTP request handling with retry logic and error handling.
"""

import asyncio
import json
import time
from typing import Dict, Optional, Any
from urllib.parse import urljoin

import httpx
import structlog

from .models import EvolutionAPIError
from .rate_limiter import RateLimiter

logger = structlog.get_logger(__name__)


class RequestHandler:
    """Handles HTTP requests with retry logic and error handling."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        rate_limiter: RateLimiter,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        use_mock: bool = False,
    ):
        """
        Initialize request handler.

        Args:
            client: Async HTTP client
            base_url: API base URL
            rate_limiter: Rate limiter instance
            max_retries: Maximum retry attempts
            retry_delay: Initial delay between retries
            use_mock: Use mock mode for testing
        """
        self.client = client
        self.base_url = base_url
        self.rate_limiter = rate_limiter
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.use_mock = use_mock

    def _get_endpoint_url(self, endpoint: str) -> str:
        """
        Build full endpoint URL with proper path joining.

        Args:
            endpoint: API endpoint path

        Returns:
            Full URL
        """
        clean_endpoint = endpoint.lstrip("/")
        return urljoin(f"{self.base_url}/", clean_endpoint)

    async def make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        retry_count: int = 0,
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
            if not self.rate_limiter.check_rate_limit():
                await asyncio.sleep(1.0)  # Wait for rate limit reset
                if not self.rate_limiter.check_rate_limit():
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
                has_params=bool(params),
            )

            start_time = time.time()
            response = await self.client.request(
                method=method, url=url, json=data, params=params
            )
            response_time = time.time() - start_time

            # Log response details
            logger.info(
                "Evolution API response received",
                status_code=response.status_code,
                response_time_seconds=round(response_time, 3),
                content_length=len(response.content) if response.content else 0,
            )

            # Handle HTTP errors
            if response.status_code >= 400:
                error_data = None
                try:
                    error_data = response.json()
                except (json.JSONDecodeError, ValueError) as e:
                    logger.debug(f"Failed to parse error response as JSON: {e}")

                error_msg = f"HTTP {response.status_code}: {response.text[:200]}..."

                logger.error(
                    "Evolution API error response",
                    status_code=response.status_code,
                    error_data=error_data,
                    url=url,
                    method=method,
                )

                # Retry on server errors (5xx) and rate limits (429)
                if response.status_code >= 500 or response.status_code == 429:
                    if retry_count < self.max_retries:
                        delay = self.retry_delay * (
                            2**retry_count
                        )  # Exponential backoff
                        logger.warning(
                            "Evolution API retrying request",
                            status_code=response.status_code,
                            attempt=retry_count + 1,
                            max_retries=self.max_retries,
                            retry_delay=delay,
                        )
                        await asyncio.sleep(delay)
                        return await self.make_request(
                            method, endpoint, data, params, retry_count + 1
                        )

                raise EvolutionAPIError(error_msg, response.status_code, error_data)

            # Parse response with error handling
            try:
                result = response.json()
                logger.info(
                    "Evolution API request successful",
                    status=result.get("status", "unknown"),
                    has_data=bool(result.get("data")),
                    response_keys=list(result.keys())
                    if isinstance(result, dict)
                    else None,
                )
                return result
            except json.JSONDecodeError:
                logger.warning(
                    "Evolution API returned non-JSON response",
                    content_type=response.headers.get("content-type"),
                    response_preview=response.text[:200] if response.text else None,
                )
                return {"status": "success", "data": response.text}

        except httpx.TimeoutException:
            logger.warning(
                "Evolution API timeout",
                timeout_seconds=self.client.timeout.read,
                attempt=retry_count + 1,
                max_retries=self.max_retries,
            )

            if retry_count < self.max_retries:
                delay = self.retry_delay * (2**retry_count)
                await asyncio.sleep(delay)
                return await self.make_request(
                    method, endpoint, data, params, retry_count + 1
                )

            raise EvolutionAPIError(
                f"Request timeout after {self.max_retries} attempts"
            )

        except httpx.RequestError as e:
            logger.warning(
                "Evolution API network error",
                error=str(e),
                error_type=type(e).__name__,
                attempt=retry_count + 1,
                max_retries=self.max_retries,
            )

            # Retry on network errors
            if retry_count < self.max_retries:
                delay = self.retry_delay * (2**retry_count)
                await asyncio.sleep(delay)
                return await self.make_request(
                    method, endpoint, data, params, retry_count + 1
                )

            raise EvolutionAPIError(
                f"Network error after {self.max_retries} attempts: {str(e)}"
            )

    async def _mock_response(
        self, method: str, endpoint: str, data: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        Generate mock response for testing.

        Args:
            method: HTTP method
            endpoint: API endpoint
            data: Request data

        Returns:
            Mock response data
        """
        await asyncio.sleep(0.1)  # Simulate network delay

        mock_message_id = f"mock_{int(time.time() * 1000)}"

        if (
            "sendText" in endpoint
            or "sendButtons" in endpoint
            or "sendList" in endpoint
            or "sendMedia" in endpoint
        ):
            return {
                "status": "success",
                "data": {
                    "id": mock_message_id,
                    "status": "pending",
                    "timestamp": int(time.time() * 1000),
                },
            }
        elif "connectionState" in endpoint:
            return {"status": "success", "data": {"state": "open", "connected": True}}
        else:
            return {"status": "success", "data": {}}
