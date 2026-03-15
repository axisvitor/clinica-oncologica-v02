"""Focused admin extension audit contract tests for the canonical runtime."""

from __future__ import annotations

import csv
import io
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v2.routers.admin_extensions.utils import serialize_audit_log
from app.models.audit_log import AuditEventType, AuditLog
from app.schemas.v2.admin_extensions import AuditLogResponse
from app.utils.timezone import now_sao_paulo_naive


@pytest.fixture
def audit_logs(db_session: Session, test_admin_user):
    logs: list[AuditLog] = []

    for index in range(3):
        log = AuditLog(
            id=uuid4(),
            event_type=(
                AuditEventType.LOGIN_SUCCESS
                if index == 0
                else AuditEventType.ADMIN_AUDIT_EXPORT
            ),
            event_category="AUTHENTICATION" if index == 0 else "ADMIN",
            event_status="success",
            status="SUCCESS",
            user_id=test_admin_user.id,
            user_email=test_admin_user.email,
            user_role="admin",
            ip_address=f"192.168.1.{index + 1}",
            user_agent="TestAgent/1.0",
            resource="/api/v2/auth/login" if index == 0 else "/api/v2/admin-extensions/audit-logs/export",
            action="READ",
            event_metadata={
                "session_source": "cookie",
                "api_token": f"secret-token-{index}",
                "firebase_uid": f"legacy-firebase-{index}",
            },
            message=f"Audit log {index}",
            error_details=None,
            created_at=now_sao_paulo_naive() - timedelta(minutes=index),
            updated_at=now_sao_paulo_naive() - timedelta(minutes=index),
        )
        db_session.add(log)
        logs.append(log)

    db_session.commit()
    return logs


class TestAdminAuditSerialization:
    def test_serialize_audit_log_omits_firebase_fields(self, audit_logs):
        payload = serialize_audit_log(audit_logs[0], redact_sensitive=True)

        assert "firebase_uid" not in payload
        assert "firebase_uid" not in payload["event_metadata"]
        assert payload["event_metadata"]["api_token"] == "[REDACTED]"
        assert payload["user_id"] == audit_logs[0].user_id

    def test_audit_log_response_schema_omits_firebase_uid_examples(self):
        assert "firebase_uid" not in AuditLogResponse.model_fields
        example = AuditLogResponse.model_config["json_schema_extra"]["example"]
        assert "firebase_uid" not in example
        assert example["user_id"] == "660e8400-e29b-41d4-a716-446655440000"


class TestAdminAuditEndpoints:
    def test_list_audit_logs_hides_firebase_uid(
        self,
        client: TestClient,
        admin_headers,
        audit_logs,
    ):
        response = client.get(
            "/api/v2/admin-extensions/audit-logs",
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()
        assert payload["data"]

        first = payload["data"][0]
        assert "firebase_uid" not in first
        assert "firebase_uid" not in first["event_metadata"]
        assert first["user_id"] == str(audit_logs[0].user_id)
        assert first["event_metadata"]["session_source"] == "cookie"

    def test_get_audit_log_hides_firebase_uid_and_redacts_metadata(
        self,
        client: TestClient,
        admin_headers,
        audit_logs,
    ):
        response = client.get(
            f"/api/v2/admin-extensions/audit-logs/{audit_logs[0].id}?redact_sensitive=true",
            headers=admin_headers,
        )

        assert response.status_code == status.HTTP_200_OK
        payload = response.json()

        assert "firebase_uid" not in payload
        assert "firebase_uid" not in payload["event_metadata"]
        assert payload["event_metadata"]["api_token"] == "[REDACTED]"
        assert payload["user_id"] == str(audit_logs[0].user_id)

    def test_export_audit_logs_json_omits_firebase_uid(
        self,
        client: TestClient,
        admin_headers,
        audit_logs,
    ):
        response = client.post(
            "/api/v2/admin-extensions/audit-logs/export",
            headers=admin_headers,
            json={"format": "json", "redact_sensitive": True},
        )

        assert response.status_code == status.HTTP_200_OK
        exported = json.loads(response.content)
        assert exported
        assert all("firebase_uid" not in row for row in exported)
        assert all("firebase_uid" not in row.get("event_metadata", {}) for row in exported)

    def test_export_audit_logs_csv_default_headers_omit_firebase_uid(
        self,
        client: TestClient,
        admin_headers,
        audit_logs,
    ):
        response = client.post(
            "/api/v2/admin-extensions/audit-logs/export",
            headers=admin_headers,
            json={"format": "csv", "redact_sensitive": True},
        )

        assert response.status_code == status.HTTP_200_OK
        reader = csv.DictReader(io.StringIO(response.content.decode("utf-8")))
        assert reader.fieldnames is not None
        assert "firebase_uid" not in reader.fieldnames
