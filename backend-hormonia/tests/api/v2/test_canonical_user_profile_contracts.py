"""Focused canonical user/profile/preferences contract proof for S02."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v2.routers.auth import _serialize_authenticated_user
from app.models.user import User


pytestmark = [pytest.mark.api, pytest.mark.auth]


def test_canonical_profile_users_me_returns_canonical_profile_fields(
    client: TestClient,
    db_session: Session,
    auth_headers_doctor: dict,
    test_doctor_user: User,
):
    canonical_last_login = datetime(2026, 3, 15, 12, 30, tzinfo=timezone.utc)
    test_doctor_user.last_login = canonical_last_login
    test_doctor_user.display_name = "Dra. Perfil Canonical"
    test_doctor_user.photo_url = "https://example.com/canonical-photo.png"
    test_doctor_user.email_verified = True
    test_doctor_user.preferences = {"theme": "dark", "language": "en-US"}
    db_session.commit()
    db_session.refresh(test_doctor_user)

    response = client.get("/api/v2/users/me", headers=auth_headers_doctor)

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["last_login"].startswith("2026-03-15T12:30:00"), (
        "canonical_profile surface=users_me canonical_last_login_missing=true"
    )
    assert payload["display_name"] == "Dra. Perfil Canonical", (
        "canonical_profile surface=users_me canonical_display_name_missing=true"
    )
    assert payload["photo_url"] == "https://example.com/canonical-photo.png", (
        "canonical_profile surface=users_me canonical_photo_url_missing=true"
    )
    assert payload["email_verified"] is True, (
        "canonical_profile surface=users_me canonical_email_verified_missing=true"
    )
    assert payload["preferences"]["theme"] == "dark", (
        "canonical_profile surface=users_me canonical_preferences_missing=true"
    )
    assert "firebase_uid" not in payload, (
        "canonical_profile surface=users_me firebase_uid_present=true"
    )


def test_canonical_preferences_patch_persists_canonical_storage(
    client: TestClient,
    db_session: Session,
    auth_headers_doctor: dict,
    test_doctor_user: User,
):
    test_doctor_user.preferences = {}
    db_session.commit()

    response = client.patch(
        "/api/v2/users/preferences",
        headers=auth_headers_doctor,
        json={"theme": "dark", "language": "en-US", "notification_email": False},
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    db_session.refresh(test_doctor_user)

    assert payload["preferences"]["theme"] == "dark", (
        "canonical_preferences surface=preferences response_theme_missing=true"
    )
    assert test_doctor_user.preferences["theme"] == "dark", (
        "canonical_preferences surface=preferences canonical_theme_not_updated=true"
    )
    assert test_doctor_user.preferences["language"] == "en-US", (
        "canonical_preferences surface=preferences canonical_language_not_updated=true"
    )
    assert test_doctor_user.preferences["notification_email"] is False, (
        "canonical_preferences surface=preferences canonical_notification_email_not_updated=true"
    )


def test_canonical_profile_auth_user_payload_prefers_canonical_fields(test_doctor_user: User):
    test_doctor_user.last_login = datetime(2026, 3, 15, 14, 0, tzinfo=timezone.utc)
    test_doctor_user.photo_url = "https://example.com/auth-canonical-photo.png"

    payload = _serialize_authenticated_user(test_doctor_user)

    assert payload["last_login"] == test_doctor_user.last_login, (
        "canonical_profile surface=auth_user_payload canonical_last_login_missing=true"
    )
    assert payload["photo_url"] == test_doctor_user.photo_url, (
        "canonical_profile surface=auth_user_payload canonical_photo_url_missing=true"
    )
    assert "firebase_uid" not in payload, (
        "canonical_profile surface=auth_user_payload firebase_uid_present=true"
    )


def test_canonical_profile_physician_detail_uses_canonical_field_names(
    client: TestClient,
    db_session: Session,
    admin_headers: dict,
    test_doctor_user: User,
):
    test_doctor_user.display_name = "Dra. Canonical Physician"
    test_doctor_user.photo_url = "https://example.com/physician-canonical-photo.png"
    test_doctor_user.email_verified = True
    test_doctor_user.last_login = datetime(2026, 3, 15, 16, 0, tzinfo=timezone.utc)
    db_session.commit()
    db_session.refresh(test_doctor_user)

    response = client.get(
        f"/api/v2/physicians/{test_doctor_user.id}",
        headers=admin_headers,
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["display_name"] == "Dra. Canonical Physician", (
        "canonical_profile surface=physician_detail canonical_display_name_missing=true"
    )
    assert payload["photo_url"] == "https://example.com/physician-canonical-photo.png", (
        "canonical_profile surface=physician_detail canonical_photo_url_missing=true"
    )
    assert payload["email_verified"] is True, (
        "canonical_profile surface=physician_detail canonical_email_verified_missing=true"
    )
    assert payload["last_login"].startswith("2026-03-15T16:00:00"), (
        "canonical_profile surface=physician_detail canonical_last_login_missing=true"
    )
    assert "firebase_display_name" not in payload, (
        "canonical_profile surface=physician_detail legacy_display_name_present=true"
    )
    assert "firebase_photo_url" not in payload, (
        "canonical_profile surface=physician_detail legacy_photo_url_present=true"
    )
