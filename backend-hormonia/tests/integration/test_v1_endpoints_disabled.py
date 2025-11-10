import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app


def test_no_v1_routes_mounted():
    """
    Ensure that no /api/v1 routes are mounted anywhere in the application.
    """
    v1_paths = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            path = route.path
            if path.startswith("/api/v1/"):
                v1_paths.add(path)

    assert not v1_paths, f"Unexpected /api/v1 routes mounted: {sorted(v1_paths)}"


def test_redis_health_route_present_and_works(client: TestClient):
    """The Redis health route should be present (now in /api/v2) and return JSON with status and timestamp."""
    resp = client.get("/api/v2/redis/health")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, dict)
    assert "status" in body
    assert "timestamp" in body
