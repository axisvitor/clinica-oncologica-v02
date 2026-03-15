"""Focused runtime audit contract tests for the canonical session cutover."""

from __future__ import annotations

from uuid import uuid4

import pytest
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.hipaa_audit_middleware import HIPAAAuditMiddleware
from app.models.audit_log import AuditEventType
from app.models.user import User, UserRole
from app.services.audit.audit_service import AuditEventContext, AuditService
from app.services.audit_log import AuditLogService as LegacyAuditLogService
from app.utils.security import get_password_hash
from tests.conftest import SyncToAsyncSessionAdapter


@pytest.fixture
def audit_user(db_session):
    user = User(
        id=uuid4(),
        email="audit-user@example.com",
        hashed_password=get_password_hash("AuditPass123"),
        full_name="Audit User",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestCanonicalAuditService:
    @pytest.mark.asyncio
    async def test_log_event_persists_canonical_user_id_and_strips_legacy_firebase_identity(
        self, db_session, audit_user
    ):
        async_db = SyncToAsyncSessionAdapter(db_session)
        audit_service = AuditService(async_db)
        user_id = audit_user.id

        context = AuditEventContext(
            user_id=user_id,
            user_email="operator@example.com",
            user_role="admin",
            session_id="cookie-session",
            status="SUCCESS",
            description="GET /api/v2/patients",
            metadata={
                "session_source": "cookie",
                "firebase_uid": "legacy-firebase-uid",
            },
            resource_identifiers={
                "patient_id": str(uuid4()),
                "firebase_uid": "legacy-firebase-uid",
            },
        )

        audit_log = await audit_service.log_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            event_category="AUTHENTICATION",
            context=context,
        )

        assert audit_log.user_id == user_id
        assert audit_log.session_id == "cookie-session"
        assert audit_log.firebase_uid is None
        assert audit_log.event_metadata == {"session_source": "cookie"}
        assert audit_log.resource_identifiers == {"patient_id": context.resource_identifiers["patient_id"]}

    @pytest.mark.asyncio
    async def test_log_event_calculates_changed_fields_without_legacy_identity_dependency(
        self, db_session, audit_user
    ):
        async_db = SyncToAsyncSessionAdapter(db_session)
        audit_service = AuditService(async_db)

        audit_log = await audit_service.log_event(
            event_type=AuditEventType.SUSPICIOUS_ACTIVITY,
            event_category="DATA_MODIFICATION",
            context=AuditEventContext(
                user_id=audit_user.id,
                resource_type="PATIENT",
                resource_id=uuid4(),
                operation="UPDATE",
                changes_before={"status": "active", "phone": "1111"},
                changes_after={"status": "active", "phone": "2222"},
                status="SUCCESS",
            ),
        )

        assert audit_log.changed_fields == ["phone"]
        assert audit_log.operation == "UPDATE"
        assert audit_log.resource_type == "PATIENT"

    def test_hash_session_token_is_stable(self):
        hashed = AuditService.hash_session_token("my-secret-session-token")

        assert len(hashed) == 64
        assert hashed == AuditService.hash_session_token("my-secret-session-token")
        assert hashed != "my-secret-session-token"


class TestLegacyAuditLogServiceBoundary:
    def test_log_event_persists_null_firebase_uid_and_strips_metadata(self, db_session, audit_user):
        audit_service = LegacyAuditLogService(db_session)

        audit_log = audit_service.log_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            event_status="success",
            user_id=audit_user.id,
            user_email=audit_user.email,
            firebase_uid="masked-legacy-firebase-uid",
            metadata={
                "session_source": "cookie",
                "firebase_uid": "masked-legacy-firebase-uid",
            },
        )

        assert (
            audit_log.firebase_uid is None
        ), "audit_contract surface=legacy_writer persisted_firebase_uid=true"
        assert audit_log.event_metadata == {
            "session_source": "cookie"
        }, "audit_contract surface=legacy_writer metadata_firebase_uid_present=true"

    def test_login_success_helper_keeps_canonical_audit_row_null(self, db_session, audit_user):
        audit_user.firebase_uid = "masked-legacy-firebase-uid"
        db_session.commit()
        db_session.refresh(audit_user)

        audit_service = LegacyAuditLogService(db_session)
        audit_log = audit_service.log_login_success(audit_user)

        assert (
            audit_log.firebase_uid is None
        ), "audit_contract surface=login_success_helper persisted_firebase_uid=true"
        assert audit_log.event_metadata == {}


class TestCanonicalHIPAAAuditMiddleware:
    @staticmethod
    def _make_request(*, cookie_header: str = "session_id=cookie-session") -> Request:
        async def receive() -> dict:
            return {"type": "http.request", "body": b"", "more_body": False}

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v2/patients",
            "raw_path": b"/api/v2/patients",
            "query_string": b"",
            "headers": [
                (b"host", b"testserver"),
                (b"user-agent", b"pytest"),
                (b"cookie", cookie_header.encode()),
            ],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
        }
        return Request(scope, receive)

    @pytest.mark.asyncio
    async def test_dispatch_uses_request_state_user_id_and_session_without_firebase_uid(
        self, monkeypatch
    ):
        captured: dict[str, object] = {}

        class FakeAuditService:
            def __init__(self, db):
                self.db = db

            @staticmethod
            def hash_session_token(token: str) -> str:
                return f"hashed:{token}"

            async def log_event(self, *, event_type, event_category, context):
                captured["event_type"] = event_type
                captured["event_category"] = event_category
                captured["context"] = context

        async def app(_scope, _receive, _send):
            return None

        async def call_next(request: Request) -> Response:
            request.state.user_id = str(user_id)
            request.state.user_role = "admin"
            request.state.session_id = "resolved-session"
            request.state.firebase_uid = "legacy-firebase-uid"
            return Response(status_code=200)

        user_id = uuid4()
        request = self._make_request()
        request.state.db = object()

        monkeypatch.setattr(
            "app.middleware.hipaa_audit_middleware.AuditService", FakeAuditService
        )

        middleware = HIPAAAuditMiddleware(app)
        response = await middleware.dispatch(request, call_next)

        assert response.status_code == 200
        context = captured["context"]
        assert isinstance(context, AuditEventContext)
        assert context.user_id == user_id
        assert context.user_role == "admin"
        assert context.session_id == "resolved-session"
        assert "firebase_uid" not in context.model_dump()
