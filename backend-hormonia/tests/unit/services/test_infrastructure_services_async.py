from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.models.audit_log import AuditEventType
from app.models.consent import ConsentStatus, ConsentType
from app.models.lgpd_audit import LGPDActionType, LGPDDataCategory
from app.services.audit.audit_service import AuditEventContext, AuditService
from app.services.cache.flow_template_cache import FlowTemplateCacheService
from app.services.lgpd.consent_service import ConsentService, LGPDAuditService


class _FakeScalarResult:
    def __init__(self, values):
        self._values = list(values)

    def first(self):
        return self._values[0] if self._values else None

    def all(self):
        return list(self._values)


class _FakeResult:
    def __init__(self, *, rows=None, scalar_rows=None):
        self._rows = list(rows or [])
        self._scalar_rows = list(scalar_rows or [])

    def all(self):
        return list(self._rows)

    def scalars(self):
        return _FakeScalarResult(self._scalar_rows)


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

    def add(self, instance):
        self.added.append(instance)

    def query(self, *args, **kwargs):
        raise AssertionError("sync db.query should not be used")


class _FakeRedis:
    def get(self, _key):
        return None

    def setex(self, *_args, **_kwargs):
        return True

    def delete(self, *_keys):
        return 0

    def scan_iter(self, **_kwargs):
        return []

    def incr(self, *_args, **_kwargs):
        return 1


@pytest.mark.asyncio
async def test_consent_grant_uses_async_execute_and_not_sync_query():
    consent = SimpleNamespace(
        id=uuid4(),
        patient_id=uuid4(),
        consent_type=ConsentType.COMMUNICATION,
        status=ConsentStatus.PENDING,
        granted_at=None,
        consented_by_id=None,
        signature_data=None,
    )
    db = _QueueAsyncSession([_FakeResult(scalar_rows=[consent])])
    service = ConsentService(db)
    service._log_consent_operation = AsyncMock()

    updated = await service.grant_consent(consent.id, user_id=uuid4())

    assert updated.status == ConsentStatus.GRANTED
    assert len(db.execute_calls) == 1
    assert db.commit_calls == 1
    assert db.refresh_calls == [consent]
    service._log_consent_operation.assert_awaited_once()


@pytest.mark.asyncio
async def test_audit_log_event_uses_async_commit_refresh_path():
    db = _QueueAsyncSession()
    service = AuditService(db)

    event = await service.log_event(
        event_type=AuditEventType.LOGIN_SUCCESS,
        event_category="AUTHENTICATION",
        context=AuditEventContext(
            user_id=uuid4(),
            endpoint="/api/v2/auth/login",
            operation="READ",
            status="SUCCESS",
        ),
    )

    assert event.event_type == AuditEventType.LOGIN_SUCCESS
    assert db.commit_calls == 1
    assert len(db.refresh_calls) == 1
    assert len(db.added) == 1


@pytest.mark.asyncio
async def test_flow_template_cache_uses_async_db_lookup_and_warm_paths(monkeypatch):
    monkeypatch.setattr(
        "app.services.cache.flow_template_cache.get_redis_client",
        lambda *_args, **_kwargs: _FakeRedis(),
    )

    flow_kind = SimpleNamespace(kind_key="quiz_mensal", is_active=True)
    template_version = SimpleNamespace(
        template_name="Quiz Mensal",
        description="Modelo principal",
        version_number=3,
        steps=[{"id": "s1"}],
        metadata_json={"lang": "pt-BR"},
        is_active=True,
    )

    db = _QueueAsyncSession(
        [
            _FakeResult(scalar_rows=[flow_kind]),
            _FakeResult(scalar_rows=[template_version]),
            _FakeResult(rows=[(flow_kind, template_version)]),
        ]
    )
    service = FlowTemplateCacheService(db=db)

    template = await service.get_template("quiz_mensal", use_cache=False)
    warmed = await service.warm_cache()

    assert template is not None
    assert template["flow_type"] == "quiz_mensal"
    assert template["version_number"] == 3
    assert warmed == 1
    assert len(db.execute_calls) == 3


@pytest.mark.asyncio
async def test_lgpd_audit_log_data_access_uses_async_commit_refresh_path():
    db = _QueueAsyncSession()
    service = LGPDAuditService(db)

    logged = await service.log_data_access(
        user_id=uuid4(),
        patient_id=uuid4(),
        action=LGPDActionType.VIEW,
        data_category=LGPDDataCategory.HEALTH,
        resource_type="patient_record",
        resource_id="abc123",
        fields_accessed=["diagnosis"],
        purpose="care_followup",
        legal_basis="consent",
        request_context={"ip_address": "127.0.0.1"},
    )

    assert logged.resource_type == "patient_record"
    assert db.commit_calls == 1
    assert db.refresh_calls == [logged]
    assert len(db.added) == 1


@pytest.mark.asyncio
async def test_lgpd_audit_history_methods_use_execute_not_sync_query_with_filters_and_limit():
    patient_logs = [SimpleNamespace(id=uuid4())]
    user_logs = [SimpleNamespace(id=uuid4())]
    failed_logs = [SimpleNamespace(id=uuid4())]
    db = _QueueAsyncSession(
        [
            _FakeResult(scalar_rows=patient_logs),
            _FakeResult(scalar_rows=user_logs),
            _FakeResult(scalar_rows=failed_logs),
        ]
    )
    service = LGPDAuditService(db)
    patient_id = uuid4()
    user_id = uuid4()
    start_date = datetime.now(timezone.utc) - timedelta(days=7)
    end_date = datetime.now(timezone.utc)

    patient_history = await service.get_patient_access_history(
        patient_id=patient_id,
        start_date=start_date,
        end_date=end_date,
        limit=25,
    )
    user_history = await service.get_user_access_history(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        limit=15,
    )
    failed_history = await service.get_failed_access_attempts(hours=48, limit=7)

    assert patient_history == patient_logs
    assert user_history == user_logs
    assert failed_history == failed_logs
    assert len(db.execute_calls) == 3

    patient_params = db.execute_calls[0].compile().params
    user_params = db.execute_calls[1].compile().params
    failed_params = db.execute_calls[2].compile().params

    assert patient_id in patient_params.values()
    assert start_date in patient_params.values()
    assert end_date in patient_params.values()
    assert 25 in patient_params.values()

    assert user_id in user_params.values()
    assert start_date in user_params.values()
    assert end_date in user_params.values()
    assert 15 in user_params.values()

    assert 7 in failed_params.values()
    assert any(isinstance(value, datetime) for value in failed_params.values())
