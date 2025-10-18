import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app


def test_no_v1_routes_mounted_except_exceptions():
    """
    Ensure that no /api/v1 routes are mounted except the allowed exceptions.

    Allowed exceptions:
    - /api/v1/redis/health (critical health check)
    - /api/v1/csrf-token (only if CSRF is configured)
    """
    v1_paths = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            path = route.path
            if path.startswith("/api/v1/"):
                v1_paths.add(path)

    allowed = {"/api/v1/redis/health", "/api/v1/csrf-token"}
    unexpected = v1_paths - allowed

    assert not unexpected, f"Unexpected /api/v1 routes mounted: {sorted(unexpected)}"


def test_redis_health_route_present_and_works(client: TestClient):
    """The Redis health route should be present and return JSON with status and timestamp."""
    resp = client.get("/api/v1/redis/health")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, dict)
    assert "status" in body
    assert "timestamp" in body
