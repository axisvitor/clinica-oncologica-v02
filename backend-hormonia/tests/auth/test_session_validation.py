"""Retirement proof for the legacy root ``/session/*`` surface."""

from __future__ import annotations

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.main import app
from app.middleware.csrf import get_csrf_token
from app.routers.auth_session import (
    AUTH_LEGACY_SESSION_ROUTE_RETIRED,
    LEGACY_SESSION_ROUTE_MESSAGE,
)

pytestmark = [pytest.mark.auth]


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _csrf_request_kwargs() -> dict:
    csrf_token = get_csrf_token()
    return {
        "headers": {"X-CSRF-Token": csrf_token},
        "cookies": {"csrf_token": csrf_token},
    }


@pytest.mark.parametrize(
    ("method", "path", "request_kwargs"),
    [
        ("GET", "/session/validate", {}),
        ("POST", "/session", {**_csrf_request_kwargs(), "json": {"firebase_token": "ignored"}}),
        ("DELETE", "/session/logout", _csrf_request_kwargs()),
        ("GET", "/session/not-a-real-endpoint", {}),
    ],
)
def test_retired_root_session_routes_return_explicit_tombstone(
    client: TestClient,
    method: str,
    path: str,
    request_kwargs: dict,
) -> None:
    response = client.request(method, path, **request_kwargs)

    assert response.status_code == status.HTTP_410_GONE, response.text

    data = response.json()
    assert data["error"] == AUTH_LEGACY_SESSION_ROUTE_RETIRED
    assert data["message"] == LEGACY_SESSION_ROUTE_MESSAGE
    assert data["status_code"] == status.HTTP_410_GONE
    assert data["details"]["retired_path"] == path
    assert data["details"]["replacement_prefix"] == "/api/v2/auth"
    assert data["details"]["required_transport"] == "session_cookie"
    assert data["details"]["request_method"] == method


def test_retired_root_session_routes_ignore_legacy_headers_and_cookies(client: TestClient) -> None:
    csrf_token = get_csrf_token()

    response = client.get(
        "/session/validate",
        headers={
            "X-Session-ID": "legacy-header-session",
            "Authorization": "Bearer legacy-bearer-session",
            "X-CSRF-Token": csrf_token,
        },
        cookies={
            "session_id": "legacy-cookie-session",
            "csrf_token": csrf_token,
        },
    )

    assert response.status_code == status.HTTP_410_GONE, response.text

    data = response.json()
    assert data["error"] == AUTH_LEGACY_SESSION_ROUTE_RETIRED
    assert data["message"] == LEGACY_SESSION_ROUTE_MESSAGE
    assert data["details"]["retired_path"] == "/session/validate"
    assert data["details"]["replacement_prefix"] == "/api/v2/auth"
    assert data["details"]["required_transport"] == "session_cookie"
    assert data["details"]["request_method"] == "GET"
