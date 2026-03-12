"""Contract tests for public password recovery endpoints.

These tests are intentionally written before the implementation cutover.
They should stay red until `/api/v2/auth/password/reset-request` and
`/api/v2/auth/password/reset-confirm` satisfy the slice's recovery contract.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import status

from app.core.security import create_password_reset_token
from app.models.user import AuthProvider
from app.services import notification_service as notification_service_module
from tests.conftest import create_test_user

pytestmark = [pytest.mark.api, pytest.mark.auth]

RESET_REQUEST_SUCCESS_MESSAGE = "If the account exists, a recovery email has been sent."
RESET_CONFIRM_SUCCESS_MESSAGE = "Password reset successful"
RESET_DELIVERY_ERROR = "AUTH_PASSWORD_RESET_DELIVERY_FAILED"
RESET_WEAK_PASSWORD_ERROR = "AUTH_PASSWORD_WEAK"
RESET_TOKEN_ERROR = "AUTH_RESET_TOKEN_INVALID_OR_EXPIRED"


class EmailCapture:
    """Small notification double that records attempted reset emails."""

    def __init__(self):
        self.calls: list[dict] = []

    async def send(self, _service, subject, message, recipients, template_data):
        self.calls.append(
            {
                "subject": subject,
                "message": message,
                "recipients": list(recipients or []),
                "template_data": template_data,
            }
        )
        return f"message-{len(self.calls)}"


def _collect_keys(payload) -> set[str]:
    if isinstance(payload, dict):
        keys = set(payload.keys())
        for value in payload.values():
            keys.update(_collect_keys(value))
        return keys
    if isinstance(payload, list):
        keys: set[str] = set()
        for value in payload:
            keys.update(_collect_keys(value))
        return keys
    return set()


def _assert_no_secret_fields(payload) -> None:
    forbidden = {"temporary_password", "reset_token", "raw_token", "token", "password"}
    assert forbidden.isdisjoint(_collect_keys(payload))


def _assert_stable_auth_error(payload: dict, error_code: str) -> None:
    assert payload["error"] == error_code
    assert "request_id" in payload
    assert "timestamp" in payload
    _assert_no_secret_fields(payload)


@pytest.fixture
def recovery_user(db_session):
    password = "RecoverMe123!"
    email = f"reset-user-{uuid4().hex[:8]}@example.com"
    user = create_test_user(
        db_session,
        email=email,
        password=password,
        full_name="Dra. Recovery Contract",
        firebase_uid=None,
        is_active=True,
    )
    user.auth_provider = AuthProvider.LOCAL
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def email_capture(monkeypatch):
    capture = EmailCapture()
    monkeypatch.setattr(
        notification_service_module.NotificationService,
        "_send_email",
        capture.send,
    )
    return capture


def test_reset_request_returns_generic_success_and_dispatches_email(client, recovery_user, email_capture):
    response = client.post(
        "/api/v2/auth/password/reset-request",
        json={"email": recovery_user.email},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    data = response.json()

    assert data == {
        "success": True,
        "message": RESET_REQUEST_SUCCESS_MESSAGE,
    }
    assert len(email_capture.calls) == 1
    assert email_capture.calls[0]["recipients"] == [recovery_user.email]
    _assert_no_secret_fields(data)


def test_reset_request_does_not_enumerate_unknown_accounts(client, recovery_user, email_capture):
    known_response = client.post(
        "/api/v2/auth/password/reset-request",
        json={"email": recovery_user.email},
    )
    unknown_response = client.post(
        "/api/v2/auth/password/reset-request",
        json={"email": f"missing-{uuid4().hex[:8]}@example.com"},
    )

    assert known_response.status_code == status.HTTP_202_ACCEPTED, known_response.text
    assert unknown_response.status_code == status.HTTP_202_ACCEPTED, unknown_response.text

    known_data = known_response.json()
    unknown_data = unknown_response.json()

    assert known_data == {
        "success": True,
        "message": RESET_REQUEST_SUCCESS_MESSAGE,
    }
    assert unknown_data == known_data
    assert len(email_capture.calls) == 1
    _assert_no_secret_fields(unknown_data)


def test_reset_request_surfaces_delivery_failures_with_redacted_diagnostics(
    client,
    recovery_user,
    monkeypatch,
):
    async def _failing_send_email(_service, subject, message, recipients, template_data):
        _ = subject, message, recipients, template_data
        raise RuntimeError("smtp offline")

    monkeypatch.setattr(
        notification_service_module.NotificationService,
        "_send_email",
        _failing_send_email,
    )

    response = client.post(
        "/api/v2/auth/password/reset-request",
        json={"email": recovery_user.email},
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE, response.text
    data = response.json()

    _assert_stable_auth_error(data, RESET_DELIVERY_ERROR)


def test_reset_confirm_rejects_weak_password_with_stable_diagnostics(client, recovery_user):
    response = client.post(
        "/api/v2/auth/password/reset-confirm",
        json={
            "token": create_password_reset_token(recovery_user.email),
            "new_password": "weakpass",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    data = response.json()

    _assert_stable_auth_error(data, RESET_WEAK_PASSWORD_ERROR)


def test_reset_confirm_rejects_invalid_token_with_stable_diagnostics(client):
    response = client.post(
        "/api/v2/auth/password/reset-confirm",
        json={
            "token": "not-a-valid-reset-token",
            "new_password": "StrongPass123!",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    data = response.json()

    _assert_stable_auth_error(data, RESET_TOKEN_ERROR)


def test_reset_confirm_rejects_expired_token_with_stable_diagnostics(client, recovery_user):
    response = client.post(
        "/api/v2/auth/password/reset-confirm",
        json={
            "token": create_password_reset_token(
                recovery_user.email,
                expires_delta=timedelta(seconds=-1),
            ),
            "new_password": "StrongPass123!",
        },
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST, response.text
    data = response.json()

    _assert_stable_auth_error(data, RESET_TOKEN_ERROR)
