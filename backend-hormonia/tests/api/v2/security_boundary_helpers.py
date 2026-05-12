"""Reusable fixtures for patient ownership boundary API tests.

This module is intentionally not named ``test_*`` so pytest does not collect it.
It creates two doctors, one admin, one patient/message per doctor, and helpers to
switch the FastAPI auth dependency override to a selected user.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable
from uuid import uuid4

from fastapi import Request

from app.dependencies import RequestContext, get_request_context
from app.dependencies.auth_dependencies import (
    get_current_user,
    get_current_user_from_session,
    get_current_user_object_from_session,
    get_optional_user,
)
from app.main import app
from app.middleware.csrf import get_csrf_token
from app.models.message import Message, MessageDirection, MessageStatus, MessageType
from app.models.patient import Patient
from app.models.user import User, UserRole
from tests.conftest import TestUser, create_test_patient, create_test_user


@dataclass(frozen=True)
class MessageOwnershipBoundary:
    doctor_a: User
    doctor_b: User
    admin: User
    patient_a: Patient
    patient_b: Patient
    message_a: Message
    message_b: Message


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}@example.test"


def create_message_ownership_boundary(db_session) -> MessageOwnershipBoundary:
    """Create Doctor A/B, Admin, Patient A/B, and one unread message per patient."""
    doctor_a = create_test_user(
        db_session,
        email=_unique_email("doctor-a"),
        role=UserRole.DOCTOR,
        full_name="Boundary Doctor A",
    )
    doctor_b = create_test_user(
        db_session,
        email=_unique_email("doctor-b"),
        role=UserRole.DOCTOR,
        full_name="Boundary Doctor B",
    )
    admin = create_test_user(
        db_session,
        email=_unique_email("admin"),
        role=UserRole.ADMIN,
        full_name="Boundary Admin",
    )

    patient_a = create_test_patient(
        db_session,
        doctor=doctor_a,
        name="Boundary Patient A",
    )
    patient_b = create_test_patient(
        db_session,
        doctor=doctor_b,
        name="Boundary Patient B Secret",
    )

    message_a = Message(
        patient_id=patient_a.id,
        direction=MessageDirection.INBOUND,
        type=MessageType.TEXT,
        content="Doctor A readable boundary message",
        status=MessageStatus.DELIVERED,
    )
    message_b = Message(
        patient_id=patient_b.id,
        direction=MessageDirection.INBOUND,
        type=MessageType.TEXT,
        content="Doctor B secret boundary message",
        status=MessageStatus.DELIVERED,
    )
    db_session.add_all([message_a, message_b])
    db_session.commit()
    db_session.refresh(message_a)
    db_session.refresh(message_b)

    return MessageOwnershipBoundary(
        doctor_a=doctor_a,
        doctor_b=doctor_b,
        admin=admin,
        patient_a=patient_a,
        patient_b=patient_b,
        message_a=message_a,
        message_b=message_b,
    )


def headers_for_user(user: User) -> dict[str, str]:
    """Override FastAPI auth dependencies for ``user`` and return request headers."""
    session_id = f"boundary-session-{user.id}"
    session_user = TestUser(user, "testpass123").session_dict()

    async def _override_session(request: Request):
        request.state.user_id = session_user.get("id")
        request.state.user_role = session_user.get("role")
        request.state.session_id = session_id
        return session_user

    async def _override_current_user(request: Request):
        request.state.user = user
        request.state.user_id = str(user.id)
        request.state.user_role = (
            user.role.value if hasattr(user.role, "value") else str(user.role)
        )
        request.state.session_id = session_id
        return user

    async def _override_current_user_object():
        return user

    async def _override_optional_user(credentials=None, services=None):
        return user

    async def _override_request_context(request: Request):
        return RequestContext(
            ip_address="127.0.0.1",
            user_agent="pytest",
            user_id=user.id,
            session_id=session_id,
        )

    app.dependency_overrides[get_current_user_from_session] = _override_session
    app.dependency_overrides[get_current_user_object_from_session] = (
        _override_current_user_object
    )
    app.dependency_overrides[get_current_user] = _override_current_user
    app.dependency_overrides[get_optional_user] = _override_optional_user
    app.dependency_overrides[get_request_context] = _override_request_context

    csrf_token = get_csrf_token()
    return {
        "X-Session-ID": session_id,
        "Authorization": f"Bearer boundary-token-{user.id}",
        "X-CSRF-Token": csrf_token,
        "Cookie": f"csrf_token={csrf_token}",
    }


def assert_response_excludes_values(response, forbidden_values: Iterable[object]) -> None:
    """Assert a response body does not leak selected PHI/message values."""
    try:
        body = json.dumps(response.json(), ensure_ascii=False, default=str)
    except Exception:
        body = response.text

    for value in forbidden_values:
        if value is None:
            continue
        assert str(value) not in body
