"""Contract tests for admin first-access provisioning and recovery.

These tests are intentionally written before the implementation cutover.
They should stay red until admin provisioning uses the same email-backed
recovery contract as public password reset.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import status

from app.core.security import create_password_reset_token
from app.models.user import AuthProvider, User, UserRole
from app.services import notification_service as notification_service_module
from app.utils.timezone import now_sao_paulo

pytestmark = [pytest.mark.api, pytest.mark.auth]

RESET_CONFIRM_SUCCESS_MESSAGE = "Password reset successful"


class EmailCapture:
    """Small notification double that records attempted first-access emails."""

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


def _assert_no_plaintext_password_fields(payload) -> None:
    forbidden = {"temporary_password", "password", "new_password", "reset_token", "raw_token"}
    assert forbidden.isdisjoint(_collect_keys(payload))


@pytest.fixture
def email_capture(monkeypatch):
    capture = EmailCapture()
    monkeypatch.setattr(
        notification_service_module.NotificationService,
        "_send_email",
        capture.send,
    )
    return capture


@pytest.fixture
def recoverable_admin_created_user(db_session):
    user = User(
        email=f"first-access-{uuid4().hex[:8]}@example.com",
        hashed_password=None,
        full_name="Dr. First Access",
        role=UserRole.DOCTOR,
        is_active=True,
        firebase_uid=None,
        auth_provider=AuthProvider.LOCAL,
        force_change_password=True,
        last_password_change=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_admin_can_provision_passwordless_first_access_user_without_plaintext_password_response(
    client,
    db_session,
    auth_headers_admin,
    email_capture,
):
    email = f"new-first-access-{uuid4().hex[:8]}@example.com"

    response = client.post(
        "/api/v2/admin/users",
        headers=auth_headers_admin,
        json={
            "email": email,
            "full_name": "Dra. Nova Conta",
            "role": "doctor",
            "is_active": True,
            "send_activation_email": True,
        },
    )

    assert response.status_code == status.HTTP_201_CREATED, response.text
    data = response.json()

    assert data["email"] == email
    assert data["role"] == "doctor"
    assert data["first_access"]["required"] is True
    assert data["first_access"]["delivery"] in {"queued", "sent"}
    _assert_no_plaintext_password_fields(data)

    created_user = db_session.query(User).filter(User.email == email).first()
    assert created_user is not None
    assert created_user.hashed_password is None
    assert created_user.force_change_password is True
    assert len(email_capture.calls) == 1
    assert email_capture.calls[0]["recipients"] == [email]


def test_admin_triggered_recovery_returns_delivery_metadata_without_plaintext_password(
    client,
    auth_headers_admin,
    recoverable_admin_created_user,
    email_capture,
):
    response = client.post(
        f"/api/v2/admin/users/{recoverable_admin_created_user.id}/reset-password",
        headers=auth_headers_admin,
        json={"send_email": True},
    )

    assert response.status_code == status.HTTP_202_ACCEPTED, response.text
    data = response.json()

    assert data["success"] is True
    assert data["user_id"] == str(recoverable_admin_created_user.id)
    assert data["delivery"]["channel"] == "email"
    assert data["delivery"]["status"] in {"queued", "sent"}
    _assert_no_plaintext_password_fields(data)
    assert len(email_capture.calls) == 1
    assert email_capture.calls[0]["recipients"] == [recoverable_admin_created_user.email]


def test_admin_created_user_completes_public_reset_confirm_and_logs_in_locally(
    client,
    db_session,
    auth_headers_admin,
    email_capture,
):
    email = f"activate-local-{uuid4().hex[:8]}@example.com"

    create_response = client.post(
        "/api/v2/admin/users",
        headers=auth_headers_admin,
        json={
            "email": email,
            "full_name": "Dr. Ready After Reset",
            "role": "doctor",
            "is_active": True,
            "send_activation_email": True,
        },
    )

    assert create_response.status_code == status.HTTP_201_CREATED, create_response.text
    create_data = create_response.json()
    _assert_no_plaintext_password_fields(create_data)

    created_user = db_session.query(User).filter(User.email == email).first()
    assert created_user is not None
    assert created_user.hashed_password is None
    assert created_user.force_change_password is True

    new_password = "FirstAccess123!"
    confirm_response = client.post(
        "/api/v2/auth/password/reset-confirm",
        json={
            "token": create_password_reset_token(email),
            "new_password": new_password,
        },
    )

    assert confirm_response.status_code == status.HTTP_200_OK, confirm_response.text
    assert confirm_response.json() == {
        "success": True,
        "message": RESET_CONFIRM_SUCCESS_MESSAGE,
    }

    db_session.expire_all()
    updated_user = db_session.query(User).filter(User.id == created_user.id).first()
    assert updated_user is not None
    assert updated_user.force_change_password is False
    assert updated_user.last_password_change is not None
    assert updated_user.auth_provider == AuthProvider.LOCAL

    login_response = client.post(
        "/api/v2/auth/login",
        json={
            "email": email,
            "password": new_password,
            "remember_me": False,
        },
    )

    assert login_response.status_code == status.HTTP_200_OK, login_response.text
    login_data = login_response.json()
    assert login_data["valid"] is True
    assert login_data["user"]["email"] == email
    assert len(email_capture.calls) == 1
