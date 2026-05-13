"""M014/S01 rate-limit fail-closed and trusted-proxy boundary tests."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from app.middleware.distributed_rate_limiter import RateLimitMiddleware
from app.utils.rate_limiter import check_rate_limit_redis, multi_layer_rate_limit


try:
    from app.utils.client_ip import get_client_ip, resolve_client_ip
except ImportError:  # pragma: no cover - proves RED before helper exists
    get_client_ip = None
    resolve_client_ip = None


def _request(
    *,
    peer: str | None = "203.0.113.10",
    headers: dict[str, str] | None = None,
    path: str = "/api/v2/webhooks/inbound",
    method: str = "POST",
) -> Request:
    raw_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": raw_headers,
        "client": (peer, 4321) if peer is not None else None,
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


def _build_pipeline(*, result=None, side_effect=None):
    pipeline = Mock()
    pipeline.zremrangebyscore = Mock(return_value=pipeline)
    pipeline.zadd = Mock(return_value=pipeline)
    pipeline.zcard = Mock(return_value=pipeline)
    pipeline.expire = Mock(return_value=pipeline)
    pipeline.execute = AsyncMock(side_effect=side_effect) if side_effect else AsyncMock(return_value=result)
    return pipeline


def _build_redis_client(pipeline):
    redis_client = AsyncMock()
    redis_client.pipeline = Mock(return_value=pipeline)
    redis_client.aclose = AsyncMock()
    return redis_client


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Forwarded-For": "198.51.100.77"},
        {"X-Real-IP": "198.51.100.88"},
        {"X-Forwarded-For": "not-an-ip, 198.51.100.77"},
    ],
)
def test_untrusted_proxy_headers_are_ignored(monkeypatch, headers):
    """Spoofed XFF/X-Real-IP must not control ingress rate-limit identity."""
    assert get_client_ip is not None
    monkeypatch.setenv("RATE_LIMIT_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("RATE_LIMIT_TRUSTED_PROXIES", "10.0.0.0/8")

    request = _request(peer="203.0.113.10", headers=headers)

    assert get_client_ip(request) == "203.0.113.10"


def test_trusted_proxy_xff_first_hop_is_used(monkeypatch):
    """XFF is honored only when the direct peer is in the trusted CIDR list."""
    assert resolve_client_ip is not None
    monkeypatch.setenv("RATE_LIMIT_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("RATE_LIMIT_TRUSTED_PROXIES", "10.0.0.0/8,127.0.0.1/32")

    request = _request(
        peer="10.2.3.4",
        headers={"X-Forwarded-For": "198.51.100.77, 10.2.3.4"},
    )

    resolved = resolve_client_ip(request)
    assert resolved.ip_address == "198.51.100.77"
    assert resolved.source == "x-forwarded-for"
    assert resolved.trusted_proxy is True


@pytest.mark.asyncio
async def test_check_rate_limit_redis_fails_closed_when_redis_missing(monkeypatch, caplog):
    """Manual ingress checks deny when Redis cannot be obtained."""
    caplog.set_level(logging.WARNING)

    with patch("app.utils.rate_limiter.get_redis_client", AsyncMock(return_value=None)):
        allowed, retry_after = await check_rate_limit_redis(
            key="rate_limit:webhook:global",
            max_requests=10,
            window_seconds=60,
            redis_client=None,
        )

    assert allowed is False
    assert retry_after == 60
    assert any(record.reason == "redis_unavailable" for record in caplog.records)
    assert "X-Forwarded-For" not in caplog.text


@pytest.mark.asyncio
async def test_multi_layer_rate_limit_denies_before_endpoint_on_redis_missing(caplog):
    """Webhook decorator must fail closed before endpoint side effects."""
    called = False
    caplog.set_level(logging.WARNING)

    async def endpoint(request: Request):
        nonlocal called
        called = True
        return {"status": "ok"}

    decorated = multi_layer_rate_limit(global_limit=10, identifier_limit=3)(endpoint)
    request = _request(headers={"X-Forwarded-For": "198.51.100.77"})
    request._json = {"phone": "5511999999999"}

    with patch("app.utils.rate_limiter.get_redis_client", AsyncMock(return_value=None)):
        with pytest.raises(HTTPException) as exc_info:
            await decorated(request)

    assert exc_info.value.status_code == 429
    assert called is False
    assert any(record.reason == "redis_unavailable" for record in caplog.records)
    assert "5511999999999" not in caplog.text
    assert "198.51.100.77" not in caplog.text


@pytest.mark.asyncio
async def test_multi_layer_phone_limit_uses_hashed_identifier_and_logs_no_phone(caplog):
    """Per-phone over-limit denials must avoid raw phone identifiers in diagnostics."""
    called = False
    caplog.set_level(logging.WARNING)

    async def endpoint(request: Request):
        nonlocal called
        called = True
        return {"status": "ok"}

    decorated = multi_layer_rate_limit(global_limit=100, identifier_limit=1)(endpoint)
    request = _request()
    request._json = {"phone": "5511999999999"}
    redis_client = _build_redis_client(
        _build_pipeline(
            side_effect=[
                [None, None, 1, None],
                [None, None, 2, None],
            ]
        )
    )

    with patch("app.utils.rate_limiter.get_redis_client", AsyncMock(return_value=redis_client)):
        with pytest.raises(HTTPException) as exc_info:
            await decorated(request)

    assert exc_info.value.status_code == 429
    assert called is False
    assert "5511999999999" not in caplog.text
    assert any(record.scope == "phone" for record in caplog.records)
    assert any(hasattr(record, "client_identity_hash") for record in caplog.records)


def test_rate_limit_middleware_fails_closed_before_endpoint_on_redis_error(caplog):
    """Distributed middleware must turn Redis errors into 429 before handler work."""
    caplog.set_level(logging.WARNING)
    app = FastAPI()
    calls = {"count": 0}

    @app.get("/limited")
    async def limited_endpoint():
        calls["count"] += 1
        return {"ok": True}

    redis = Mock()
    redis.register_script = Mock(return_value=Mock(side_effect=Exception("redis down")))
    app.add_middleware(
        RateLimitMiddleware,
        redis=redis,
        default_limit=1,
        default_window=60,
        whitelist_ips=[],
        exempt_paths=["/health"],
    )

    response = TestClient(app).get(
        "/limited",
        headers={"X-Forwarded-For": "198.51.100.77"},
    )

    assert response.status_code == 429
    assert calls["count"] == 0
    assert "198.51.100.77" not in caplog.text
    assert any(record.reason == "rate_limiter_error" for record in caplog.records)


def test_rate_limit_middleware_uses_trusted_proxy_identity(monkeypatch):
    """The middleware keys by resolved trusted-proxy identity, not the proxy peer."""
    monkeypatch.setenv("RATE_LIMIT_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("RATE_LIMIT_TRUSTED_PROXIES", "testclient,127.0.0.1/32")

    app = FastAPI()
    redis = Mock()
    redis.register_script = Mock(return_value=Mock(return_value=[1, 1]))
    captured_identifiers: list[str] = []

    @app.get("/limited")
    async def limited_endpoint():
        return {"ok": True}

    async def fake_check_rate_limit(identifier, limit, window, increment=True):
        captured_identifiers.append(identifier)
        from app.middleware.rate_limit_core import RateLimitResult
        from datetime import datetime, timezone

        return RateLimitResult(
            allowed=True,
            limit=limit,
            remaining=limit - 1,
            reset_at=datetime.now(timezone.utc),
        )

    with patch(
        "app.middleware.distributed_rate_limiter.DistributedRateLimiter.check_rate_limit",
        AsyncMock(side_effect=fake_check_rate_limit),
    ):
        app.add_middleware(
            RateLimitMiddleware,
            redis=redis,
            whitelist_ips=[],
            exempt_paths=["/health"],
        )
        response = TestClient(app).get(
            "/limited",
            headers={"X-Forwarded-For": "198.51.100.77, 127.0.0.1"},
        )

    assert response.status_code == 200
    assert captured_identifiers == ["ip:198.51.100.77"]
