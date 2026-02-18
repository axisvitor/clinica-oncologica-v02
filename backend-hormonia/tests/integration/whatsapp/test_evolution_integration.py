"""
Integration tests for Evolution API client behavior.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.integrations.whatsapp.services.evolution_client import RateLimiter, EvolutionAPIClient
from app.integrations.whatsapp.services.mock_evolution import MockEvolutionAPIClient


from app.utils.timezone import now_sao_paulo
@pytest.mark.asyncio
async def test_rate_limiter_throttles_requests():
    limiter = RateLimiter(max_requests=100, window_seconds=60)

    results = []
    for _ in range(150):
        results.append(await limiter.acquire())

    assert results.count(False) == 50


@pytest.mark.asyncio
async def test_retry_logic_retries_on_timeout(monkeypatch):
    async def fast_sleep(*args, **kwargs):
        return None

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    class DummyResponse:
        async def __aenter__(self):
            raise asyncio.TimeoutError()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class DummySession:
        def __init__(self):
            self.calls = 0

        def request(self, *args, **kwargs):
            self.calls += 1
            return DummyResponse()

    client = EvolutionAPIClient(base_url="http://example", api_key="test")
    client.session = DummySession()

    with pytest.raises(asyncio.TimeoutError):
        await client._make_request("GET", "/health")

    assert client.session.calls == 3


@pytest.mark.asyncio
async def test_health_check_connected_and_disconnected():
    client = MockEvolutionAPIClient()
    client.failure_rate = 0
    client.simulate_delays = False

    await client.create_instance("test-instance")

    disconnected = await client.health_check("test-instance")
    assert disconnected["is_connected"] is False

    client.instances["test-instance"]["created_at"] = (
        now_sao_paulo() - timedelta(seconds=20)
    )

    connected = await client.health_check("test-instance")
    assert connected["is_connected"] is True