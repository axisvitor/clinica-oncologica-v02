"""Focused canonical payload and audit boundary tests for quarantined Firebase residue."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit_log import AuditEventType, AuditLog
from app.models.user import User
from app.utils.timezone import now_sao_paulo_naive


MASKED_FIREBASE_UID = "masked-legacy-firebase-uid"


@pytest.fixture
def historical_audit_log(db_session: Session, test_admin_user: User) -> AuditLog:
    log = AuditLog(
        id=uuid4(),
        event_type=AuditEventType.ADMIN_AUDIT_EXPORT,
        event_category="ADMIN",
        event_status="success",
        status="SUCCESS",
        user_id=test_admin_user.id,
        user_email=test_admin_user.email,
        user_role="admin",
        ip_address="127.0.0.1",
        user_agent="pytest",
        resource="/api/v2/admin-extensions/audit-logs/export",
        action="EXPORT",
        event_metadata={
            "session_source": "cookie",
            "firebase_uid": MASKED_FIREBASE_UID,
        },
        message="historical audit export fixture",
        created_at=now_sao_paulo_naive(),
        updated_at=now_sao_paulo_naive(),
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)
    return log


class TestCanonicalPayloadBoundary:
    def test_canonical_payload_users_me_sanitizes_stale_cached_firebase_uid(
        self,
        client: TestClient,
        auth_headers_doctor: dict,
        test_doctor_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ):
        cached_payload = {
            "id": str(test_doctor_user.id),
            "email": test_doctor_user.email,
            "full_name": test_doctor_user.full_name,
            "role": test_doctor_user.role.value,
            "is_active": test_doctor_user.is_active,
            "created_at": test_doctor_user.created_at.isoformat(),
            "updated_at": test_doctor_user.updated_at.isoformat(),
            "last_login": datetime(2025, 1, 17, 12, 0, tzinfo=timezone.utc).isoformat(),
            "photo_url": "https://example.invalid/profile.png",
            "preferences": {"theme": "dark"},
            "firebase_uid": MASKED_FIREBASE_UID,
        }

        class FakeRedis:
            def __init__(self, payload: dict):
                self.payload = payload
                self.rewritten_payload: dict | None = None

            async def get(self, key: str):
                return json.dumps(self.payload)

            async def setex(self, key: str, ttl: int, value: str):
                self.rewritten_payload = json.loads(value)

        fake_redis = FakeRedis(cached_payload)

        async def _fake_get_async_redis_client():
            return fake_redis

        monkeypatch.setattr(
            "app.api.v2.routers.users.get_async_redis_client",
            _fake_get_async_redis_client,
        )

        response = client.get("/api/v2/users/me", headers=auth_headers_doctor)

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert (
            "firebase_uid" not in payload
        ), "canonical_payload surface=users_me cached_firebase_uid_present=true"
        assert payload["photo_url"] == cached_payload["photo_url"], (
            "canonical_payload surface=users_me live_field=photo_url_missing"
        )
        assert payload["last_login"] is not None, (
            "canonical_payload surface=users_me live_field=last_login_missing"
        )
        assert payload["last_login"].startswith("2025-01-17T12:00:00"), (
            "canonical_payload surface=users_me live_field=last_login_malformed"
        )
        assert fake_redis.rewritten_payload is not None
        assert "firebase_uid" not in fake_redis.rewritten_payload

    def test_canonical_payload_admin_user_detail_ignores_requested_firebase_uid_field(
        self,
        client: TestClient,
        admin_headers: dict,
        db_session: Session,
        test_doctor_user: User,
    ):
        test_doctor_user.firebase_last_sign_in = datetime(
            2025, 1, 18, 9, 30, tzinfo=timezone.utc
        )
        db_session.commit()
        db_session.refresh(test_doctor_user)

        response = client.get(
            f"/api/v2/admin/users/{test_doctor_user.id}?fields=id,email,firebase_uid,last_login",
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert (
            "firebase_uid" not in payload
        ), "canonical_payload surface=admin_user_detail leak=firebase_uid"
        assert payload["last_login"] is not None, (
            "canonical_payload surface=admin_user_detail live_field=last_login_missing"
        )

    def test_canonical_payload_physician_detail_omits_firebase_uid_but_keeps_live_profile_fields(
        self,
        client: TestClient,
        admin_headers: dict,
        db_session: Session,
        test_doctor_user: User,
    ):
        test_doctor_user.firebase_display_name = "Dr. Boundary"
        test_doctor_user.firebase_photo_url = "https://example.invalid/doctor.png"
        test_doctor_user.firebase_last_sign_in = datetime(
            2025, 1, 19, 10, 15, tzinfo=timezone.utc
        )
        db_session.commit()
        db_session.refresh(test_doctor_user)

        response = client.get(
            f"/api/v2/physicians/{test_doctor_user.id}",
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert (
            "firebase_uid" not in payload
        ), "canonical_payload surface=physician_detail leak=firebase_uid"
        assert payload["display_name"] == test_doctor_user.get_display_name(), (
            "canonical_payload surface=physician_detail live_field=display_name_missing"
        )
        assert payload["photo_url"] == test_doctor_user.get_photo_url(), (
            "canonical_payload surface=physician_detail live_field=photo_url_missing"
        )
        assert payload["last_login"] is not None, (
            "canonical_payload surface=physician_detail live_field=last_login_missing"
        )


class TestHistoricalAuditReadBoundary:
    def test_audit_export_ignores_requested_firebase_uid_field(
        self,
        client: TestClient,
        admin_headers: dict,
        historical_audit_log: AuditLog,
    ):
        response = client.post(
            "/api/v2/admin-extensions/audit-logs/export",
            headers=admin_headers,
            json={
                "format": "json",
                "fields": ["id", "firebase_uid", "event_metadata", "message"],
                "redact_sensitive": True,
            },
        )

        assert response.status_code == status.HTTP_200_OK
        exported = json.loads(response.content)
        assert exported
        assert all(
            "firebase_uid" not in row for row in exported
        ), "audit_contract surface=admin_audit_export leak=firebase_uid"
        assert all(
            "firebase_uid" not in row.get("event_metadata", {}) for row in exported
        ), "audit_contract surface=admin_audit_export metadata_firebase_uid_present=true"
        assert any(
            row.get("message") == historical_audit_log.message for row in exported
        )
