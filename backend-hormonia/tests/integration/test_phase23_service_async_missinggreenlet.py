import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.models.audit_log import AuditEventType
from app.models.consent import ConsentStatus, ConsentType
from app.models.message import MessageStatus, MessageType
from app.models.user import UserRole
from app.services.analytics.flow_analytics import FlowAnalyticsService
from app.services.audit.audit_service import AuditEventContext, AuditService
from app.services.firebase_user_sync_service import FirebaseUserSyncService
from app.services.flow_monitoring_pkg.service import FlowMonitoringService
from app.services.lgpd.consent_service import ConsentService
from app.services.patient.validation_service import PatientValidationService
from app.services.quiz.quiz_service import QuizSessionService
from app.services.unified_whatsapp_service import UnifiedWhatsAppService


@dataclass
class _FakeScalarResult:
    values: list

    def first(self):
        return self.values[0] if self.values else None

    def all(self):
        return list(self.values)


@dataclass
class _FakeExecuteResult:
    rows: list | None = None
    scalar_rows: list | None = None
    scalar_value: object | None = None

    def all(self):
        return list(self.rows or [])

    def first(self):
        rows = self.rows or []
        return rows[0] if rows else None

    def scalars(self):
        return _FakeScalarResult(self.scalar_rows or [])

    def scalar(self):
        return self.scalar_value

    def scalar_one_or_none(self):
        rows = self.scalar_rows or []
        return rows[0] if rows else self.scalar_value


class _QueueAsyncSession:
    def __init__(self, responses=None):
        self._responses = list(responses or [])
        self.execute_calls = []
        self.commit_calls = 0
        self.refresh_calls = []
        self.added = []

    async def execute(self, statement):
        self.execute_calls.append(statement)
        if not self._responses:
            raise AssertionError("Unexpected execute call with no queued response")
        return self._responses.pop(0)

    async def commit(self):
        self.commit_calls += 1

    async def refresh(self, instance):
        self.refresh_calls.append(instance)

    async def rollback(self):
        return None

    def add(self, instance):
        self.added.append(instance)

    def query(self, *args, **kwargs):
        raise AssertionError("sync db.query should not be used")


class _MonitoringRedis:
    def lrange(self, key, _start, _end):
        if key == "response_times":
            return ["1.0", "3.0"]
        return []

    def llen(self, key):
        return 2 if key.startswith("flow_errors:") else 0

    def get(self, key):
        if key == "operations_count_last_hour":
            return "40"
        return None

    def info(self, section):
        if section == "memory":
            return {"used_memory": 50, "maxmemory": 100}
        return {}

    def ping(self):
        return True


@pytest.mark.asyncio
async def test_phase23_service_groups_async_load_emit_zero_missinggreenlet_logs(
    monkeypatch, caplog
):
    doctor = SimpleNamespace(id=uuid4(), role=UserRole.DOCTOR)
    patient_db = _QueueAsyncSession([_FakeExecuteResult(scalar_rows=[doctor]) for _ in range(3)])
    patient_service = PatientValidationService(db=patient_db)

    active_session = SimpleNamespace(id=uuid4(), patient_id=uuid4(), status="started")
    quiz_db = _QueueAsyncSession(
        [_FakeExecuteResult(scalar_rows=[active_session]) for _ in range(3)]
    )
    quiz_service = QuizSessionService(db=quiz_db, repository=MagicMock())

    analytics_db = _QueueAsyncSession(
        [_FakeExecuteResult(rows=[SimpleNamespace(sent=12, received=9)]) for _ in range(3)]
    )
    analytics_service = FlowAnalyticsService(analytics_db)

    communication_db = _QueueAsyncSession([_FakeExecuteResult() for _ in range(3)])
    communication_service = UnifiedWhatsAppService(
        db=communication_db,
        redis_url="redis://localhost:6379/0",
    )
    monkeypatch.setattr("app.services.websocket_events.websocket_events", None)
    message = SimpleNamespace(
        id=uuid4(),
        patient_id=uuid4(),
        direction=SimpleNamespace(value="outbound"),
        type=MessageType.TEXT,
        content="hello",
        status=MessageStatus.PENDING,
        whatsapp_id=None,
        message_metadata={},
    )

    monkeypatch.setattr(
        "app.services.firebase_user_sync_service.get_firebase_security_config",
        lambda: {
            "allowed_domains": ["hospital.org"],
            "block_public_domains": True,
            "public_domains_blocklist": ["gmail.com"],
            "require_custom_claims": True,
            "allowed_roles": ["admin", "doctor"],
            "enable_audit_logging": False,
        },
    )
    monkeypatch.setattr(
        "app.services.firebase_user_sync_service.get_settings",
        lambda: SimpleNamespace(FIREBASE_ADMIN_SDK_TIMEOUT=1),
    )
    monkeypatch.setattr(
        "app.services.firebase_user_sync_service._get_redis_client",
        AsyncMock(return_value=None),
    )
    firebase_user = SimpleNamespace(firebase_uid="uid-1", is_active=True, role=UserRole.ADMIN)
    auth_db = _QueueAsyncSession([_FakeExecuteResult(scalar_rows=[firebase_user]) for _ in range(3)])
    auth_service = FirebaseUserSyncService(db=auth_db, firebase_service=SimpleNamespace())

    consents = [
        SimpleNamespace(
            id=uuid4(),
            patient_id=uuid4(),
            consent_type=ConsentType.COMMUNICATION,
            status=ConsentStatus.PENDING,
            granted_at=None,
            consented_by_id=None,
            signature_data=None,
        )
        for _ in range(3)
    ]
    infrastructure_db = _QueueAsyncSession(
        [_FakeExecuteResult(scalar_rows=[item]) for item in consents]
    )
    consent_service = ConsentService(infrastructure_db)
    consent_service._log_consent_operation = AsyncMock()
    audit_service = AuditService(infrastructure_db)

    now = datetime.now(timezone.utc)
    completed_flow = SimpleNamespace(started_at=now - timedelta(minutes=20), completed_at=now)
    monitoring_db = _QueueAsyncSession(
        [
            _FakeExecuteResult(scalar_value=3),
            _FakeExecuteResult(scalar_value=4),
            _FakeExecuteResult(scalar_value=10),
            _FakeExecuteResult(rows=[("onboarding", 5)]),
            _FakeExecuteResult(rows=[("onboarding", 3)]),
            _FakeExecuteResult(rows=[("onboarding", 2)]),
            _FakeExecuteResult(rows=[("onboarding", completed_flow)]),
            _FakeExecuteResult(scalar_value=3),
            _FakeExecuteResult(scalar_value=4),
            _FakeExecuteResult(scalar_value=10),
            _FakeExecuteResult(rows=[("onboarding", 5)]),
            _FakeExecuteResult(rows=[("onboarding", 3)]),
            _FakeExecuteResult(rows=[("onboarding", 2)]),
            _FakeExecuteResult(rows=[("onboarding", completed_flow)]),
            _FakeExecuteResult(scalar_value=3),
            _FakeExecuteResult(scalar_value=4),
            _FakeExecuteResult(scalar_value=10),
            _FakeExecuteResult(rows=[("onboarding", 5)]),
            _FakeExecuteResult(rows=[("onboarding", 3)]),
            _FakeExecuteResult(rows=[("onboarding", 2)]),
            _FakeExecuteResult(rows=[("onboarding", completed_flow)]),
        ]
    )
    monitoring_service = FlowMonitoringService(
        db=monitoring_db,
        redis=_MonitoringRedis(),
        flow_repository=SimpleNamespace(),
        corruption_detector=SimpleNamespace(
            detect_bulk_corruption=AsyncMock(return_value=[])
        ),
    )

    with caplog.at_level(logging.ERROR):
        await asyncio.gather(
            *[
                patient_service._validate_doctor_exists_async(doctor.id)
                for _ in range(3)
            ],
            *[
                quiz_service.get_active_session_async(active_session.patient_id)
                for _ in range(3)
            ],
            *[
                analytics_service.calculate_engagement_metrics(
                    date_range=(
                        datetime.now(timezone.utc) - timedelta(days=7),
                        datetime.now(timezone.utc),
                    )
                )
                for _ in range(3)
            ],
            *[
                communication_service._mark_message_failed(
                    message,
                    {"reason": "gateway timeout"},
                )
                for _ in range(3)
            ],
            *[
                auth_service.validate_firebase_user(
                    "uid-1",
                    required_role=UserRole.ADMIN,
                )
                for _ in range(3)
            ],
            *[
                consent_service.grant_consent(item.id, user_id=uuid4())
                for item in consents
            ],
            *[
                audit_service.log_event(
                    event_type=AuditEventType.LOGIN_SUCCESS,
                    event_category="AUTHENTICATION",
                    context=AuditEventContext(
                        user_id=uuid4(),
                        endpoint="/api/v2/auth/login",
                        operation="READ",
                        status="SUCCESS",
                    ),
                )
                for _ in range(3)
            ],
            *[monitoring_service.collect_performance_metrics() for _ in range(3)],
        )

    missing_greenlet_logs = [
        rec for rec in caplog.records if "missinggreenlet" in rec.getMessage().lower()
    ]

    assert not missing_greenlet_logs
    assert len(patient_db.execute_calls) == 3
    assert len(quiz_db.execute_calls) == 3
    assert len(analytics_db.execute_calls) == 3
    assert len(communication_db.execute_calls) == 3
    assert len(auth_db.execute_calls) == 3
    assert len(infrastructure_db.execute_calls) == 3
    assert len(monitoring_db.execute_calls) == 21
