"""Focused tests for audit cleanup Taskiq tasks."""

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch


def _scoped_session(db):
    @contextmanager
    def _ctx():
        yield db

    return _ctx()


def _scalar_result(value):
    result = Mock()
    result.scalar.return_value = value
    return result


async def test_cleanup_expired_logs_uses_scoped_session_and_preserves_result_shape():
    from app.tasks.audit_taskiq import cleanup_expired_logs

    fixed_now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    db = Mock()
    db.execute.return_value = SimpleNamespace(rowcount=4)
    audit_service = Mock()
    audit_service.cleanup_expired_logs.return_value = 6

    with patch(
        "app.tasks.audit_taskiq.get_scoped_session", return_value=_scoped_session(db)
    ) as scoped_session, patch(
        "app.tasks.audit_taskiq.AuditService", return_value=audit_service
    ), patch(
        "app.tasks.audit_taskiq.now_sao_paulo", return_value=fixed_now
    ):
        result = await cleanup_expired_logs()

    assert result["status"] == "success"
    assert result["deleted_audit_logs"] == 6
    assert result["deleted_cache_logs"] == 4
    assert result["total_deleted"] == 10
    assert result["duration_seconds"] == 0.0
    scoped_session.assert_called_once()
    db.commit.assert_called_once()


async def test_refresh_ai_performance_metrics_uses_scoped_session():
    from app.tasks.audit_taskiq import refresh_ai_performance_metrics

    fixed_now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    db = Mock()

    with patch(
        "app.tasks.audit_taskiq.get_scoped_session", return_value=_scoped_session(db)
    ) as scoped_session, patch(
        "app.tasks.audit_taskiq.now_sao_paulo", return_value=fixed_now
    ):
        result = await refresh_ai_performance_metrics()

    assert result["status"] == "success"
    assert result["duration_seconds"] == 0.0
    db.execute.assert_called_once_with("SELECT refresh_ai_metrics();")
    db.commit.assert_called_once()
    scoped_session.assert_called_once()


async def test_generate_daily_report_uses_scoped_session():
    from app.tasks.audit_taskiq import generate_daily_report

    fixed_now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    db = Mock()
    security_event = SimpleNamespace(
        event_type="ai_security_warning",
        timestamp=fixed_now,
        severity="warning",
        result="blocked",
    )
    audit_service = Mock()
    audit_service.get_ai_performance_metrics.return_value = {"total_requests": 42}
    audit_service.get_ai_security_events.return_value = [security_event]

    with patch(
        "app.tasks.audit_taskiq.get_scoped_session", return_value=_scoped_session(db)
    ) as scoped_session, patch(
        "app.tasks.audit_taskiq.AuditService", return_value=audit_service
    ), patch(
        "app.tasks.audit_taskiq.now_sao_paulo", return_value=fixed_now
    ):
        result = await generate_daily_report()

    assert result["performance_metrics"]["total_requests"] == 42
    assert result["security_events_count"] == 1
    assert len(result["high_severity_events"]) == 1
    scoped_session.assert_called_once()


async def test_check_hipaa_compliance_uses_scoped_session():
    from app.tasks.audit_taskiq import check_hipaa_compliance

    fixed_now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    db = Mock()
    db.execute.side_effect = [_scalar_result(0), _scalar_result(0), _scalar_result(0)]

    with patch(
        "app.tasks.audit_taskiq.get_scoped_session", return_value=_scoped_session(db)
    ) as scoped_session, patch(
        "app.tasks.audit_taskiq.now_sao_paulo", return_value=fixed_now
    ):
        result = await check_hipaa_compliance()

    assert result["compliant"] is True
    assert result["issues"]["missing_retention_dates"] == 0
    assert result["issues"]["missing_legal_basis"] == 0
    assert result["issues"]["excessive_retention_periods"] == 0
    scoped_session.assert_called_once()
