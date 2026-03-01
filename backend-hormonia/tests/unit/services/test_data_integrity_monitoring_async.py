import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.services.data_integrity_monitoring import (
    DataIntegrityMonitoringService,
    IntegrityIssue,
    IntegrityIssueType,
    IntegritySeverity,
)
from app.utils.timezone import now_sao_paulo


class _FakeScalarResult:
    def __init__(self, values):
        self._values = list(values)

    def all(self):
        return list(self._values)

    def first(self):
        return self._values[0] if self._values else None


class _FakeExecuteResult:
    def __init__(self, values=None, scalar_value=None):
        self._values = list(values or [])
        self._scalar_value = scalar_value

    def scalars(self):
        return _FakeScalarResult(self._values)

    def scalar_one(self):
        return self._scalar_value


def _issue(entity_type: str) -> IntegrityIssue:
    return IntegrityIssue(
        id=f"{entity_type}-{uuid4()}",
        type=IntegrityIssueType.DATA_CORRUPTION,
        severity=IntegritySeverity.LOW,
        entity_type=entity_type,
        entity_id=str(uuid4()),
        description="test",
        detected_at=now_sao_paulo(),
        metadata={},
    )


def _service_with_async_db() -> tuple[DataIntegrityMonitoringService, SimpleNamespace]:
    db = SimpleNamespace()
    db.query = Mock(side_effect=AssertionError("sync db.query should not be used"))
    db.execute = AsyncMock()
    db.scalars = AsyncMock()
    service = DataIntegrityMonitoringService(db)
    return service, db


@pytest.mark.asyncio
async def test_scan_patient_integrity_uses_async_scalars_and_counts_patient_issues():
    service, db = _service_with_async_db()
    patients = [
        SimpleNamespace(
            id=uuid4(),
            doctor_id=uuid4(),
            cpf=None,
            email=None,
            treatment_start_date=None,
            birth_date=None,
            patient_data={},
        )
    ]
    db.scalars.return_value = _FakeScalarResult(patients)
    service.detected_issues = [_issue("patient"), _issue("flow")]

    service._check_patient_duplicates = AsyncMock()
    service._validate_patient_data_consistency = AsyncMock()
    service._check_patient_orphaned_relationships = AsyncMock()

    result = await service._scan_patient_integrity(limit=1)

    assert result["entities_scanned"] == 1
    assert result["issues_found"] == 1
    assert db.scalars.await_count == 1
    db.query.assert_not_called()


@pytest.mark.asyncio
async def test_scan_flow_integrity_aggregates_referential_issues():
    service, db = _service_with_async_db()
    flow = SimpleNamespace(id=uuid4(), flow_type="onboarding", patient_id=uuid4())
    db.scalars.return_value = _FakeScalarResult([flow])

    service.flow_integrity.validate_flow_consistency = AsyncMock()
    service.flow_integrity.validate_referential_integrity = AsyncMock(
        return_value=["flow missing reference"]
    )

    result = await service._scan_flow_integrity()

    assert result["entities_scanned"] == 1
    assert result["issues_found"] == 1
    assert service.detected_issues[0].type == IntegrityIssueType.REFERENTIAL_BROKEN
    db.query.assert_not_called()


@pytest.mark.asyncio
async def test_scan_message_integrity_aggregates_issue_types_without_sync_query():
    service, db = _service_with_async_db()
    patient_id = uuid4()
    db.execute.return_value = _FakeExecuteResult(values=[patient_id])
    service.message_integrity.validate_conversation_integrity = AsyncMock(
        return_value={
            "overall_integrity": False,
            "issues": ["Checksum mismatch found"],
            "meta": "ok",
        }
    )

    result = await service._scan_message_integrity(limit=1)

    assert result["entities_scanned"] == 1
    assert result["issues_found"] == 1
    assert service.detected_issues[0].type == IntegrityIssueType.CHECKSUM_MISMATCH
    assert db.execute.await_count == 1
    db.query.assert_not_called()


@pytest.mark.asyncio
async def test_check_patient_orphaned_relationships_flags_missing_doctor():
    service, db = _service_with_async_db()
    db.scalars.return_value = _FakeScalarResult([])
    patient = SimpleNamespace(id=uuid4(), doctor_id=uuid4())

    await service._check_patient_orphaned_relationships(patient)

    assert len(service.detected_issues) == 1
    assert service.detected_issues[0].type == IntegrityIssueType.PATIENT_ORPHANED
    db.query.assert_not_called()


@pytest.mark.asyncio
async def test_get_integrity_dashboard_computes_health_score_with_async_counts():
    service, db = _service_with_async_db()
    service.detected_issues = [_issue("patient")]
    db.execute.side_effect = [
        _FakeExecuteResult(scalar_value=10),
        _FakeExecuteResult(scalar_value=5),
        _FakeExecuteResult(scalar_value=5),
    ]

    dashboard = await service.get_integrity_dashboard()

    assert dashboard["system_status"]["total_entities"] == 20
    assert dashboard["health_score"] == 95.0
    assert dashboard["recent_issues"]["total"] == 1
    assert db.execute.await_count == 3
    db.query.assert_not_called()


@pytest.mark.asyncio
async def test_get_integrity_dashboard_returns_error_payload_on_execute_failure(caplog):
    service, db = _service_with_async_db()
    db.execute.side_effect = RuntimeError("boom")

    with caplog.at_level(logging.ERROR):
        result = await service.get_integrity_dashboard()

    assert result["error"] == "boom"
    assert result["health_score"] == 0
    assert "Error generating integrity dashboard: boom" in caplog.text
    db.query.assert_not_called()
