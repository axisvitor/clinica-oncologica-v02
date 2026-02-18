"""Stable API v2 health endpoint tests.

This suite keeps the core contracts and avoids external infra hangs
(Celery/Redis/DB network calls) by mocking readiness internals.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


class TestPublicHealthEndpoints:
    def test_basic_health_check(self, client):
        response = client.get("/api/v2/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "2.0.0"
        assert "timestamp" in data

    def test_liveness_probe(self, client):
        response = client.get("/api/v2/health/live")

        assert response.status_code == 200
        data = response.json()
        assert data["alive"] is True
        assert "uptime_seconds" in data

    def test_readiness_probe_ready(self, client):
        fake_db = MagicMock()
        fake_db.execute.return_value.fetchone.return_value = (1,)

        with patch(
            "app.api.v2.routers.health.core.resolve_health_attr",
            return_value=(lambda: fake_db),
        ), patch(
            "app.api.v2.routers.health.core.asyncio.to_thread",
            new=AsyncMock(return_value={"worker@local": []}),
        ):
            response = client.get("/api/v2/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True
        assert data["checks"]["database"] is True
        assert data["checks"]["workers"] is True

    def test_readiness_probe_db_failure_returns_503(self, client):
        fake_db = MagicMock()
        fake_db.execute.side_effect = Exception("db down")

        with patch(
            "app.api.v2.routers.health.core.resolve_health_attr",
            return_value=(lambda: fake_db),
        ), patch(
            "app.api.v2.routers.health.core.asyncio.to_thread",
            new=AsyncMock(return_value=None),
        ):
            response = client.get("/api/v2/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["ready"] is False
        assert data["checks"]["database"] is False


class TestDetailedHealthEndpoint:
    def test_detailed_health_requires_auth(self, client):
        response = client.get("/api/v2/health/detailed")
        assert response.status_code == 401
