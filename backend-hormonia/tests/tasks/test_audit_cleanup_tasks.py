"""Focused tests for audit cleanup Celery tasks."""

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


def test_cleanup_expired_audit_logs_uses_scoped_session_and_preserves_result_shape():
    from app.tasks.audit_cleanup import cleanup_expired_audit_logs

    fixed_now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    db = Mock()
    db.execute.return_value = SimpleNamespace(rowcount=4)
    audit_service = Mock()
    audit_service.cleanup_expired_logs.return_value = 6

    with patch(
        "app.tasks.audit_cleanup.get_scoped_session", return_value=_scoped_session(db)
    ) as scoped_session, patch(
        "app.tasks.audit_cleanup.AuditService", return_value=audit_service
    ), patch(
        "app.tasks.audit_cleanup.now_sao_paulo", return_value=fixed_now
    ):
        result = cleanup_expired_audit_logs.run()

    assert result["status"] == "success"
    assert result["deleted_audit_logs"] == 6
    assert result["deleted_cache_logs"] == 4
    assert result["total_deleted"] == 10
    assert result["duration_seconds"] == 0.0
    scoped_session.assert_called_once()
    db.commit.assert_called_once()


def test_refresh_ai_performance_metrics_uses_scoped_session():
    from app.tasks.audit_cleanup import refresh_ai_performance_metrics

    fixed_now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    db = Mock()

    with patch(
        "app.tasks.audit_cleanup.get_scoped_session", return_value=_scoped_session(db)
    ) as scoped_session, patch(
        "app.tasks.audit_cleanup.now_sao_paulo", return_value=fixed_now
    ):
        result = refresh_ai_performance_metrics.run()

    assert result["status"] == "success"
    assert result["duration_seconds"] == 0.0
    db.execute.assert_called_once_with("SELECT refresh_ai_metrics();")
    db.commit.assert_called_once()
    scoped_session.assert_called_once()


def test_generate_daily_audit_report_uses_scoped_session():
    from app.tasks.audit_cleanup import generate_daily_audit_report

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
        "app.tasks.audit_cleanup.get_scoped_session", return_value=_scoped_session(db)
    ) as scoped_session, patch(
        "app.tasks.audit_cleanup.AuditService", return_value=audit_service
    ), patch(
        "app.tasks.audit_cleanup.now_sao_paulo", return_value=fixed_now
    ):
        result = generate_daily_audit_report.run()

    assert result["performance_metrics"]["total_requests"] == 42
    assert result["security_events_count"] == 1
    assert len(result["high_severity_events"]) == 1
    scoped_session.assert_called_once()


def test_check_hipaa_compliance_uses_scoped_session():
    from app.tasks.audit_cleanup import check_hipaa_compliance

    fixed_now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    db = Mock()
    db.execute.side_effect = [_scalar_result(0), _scalar_result(0), _scalar_result(0)]

    with patch(
        "app.tasks.audit_cleanup.get_scoped_session", return_value=_scoped_session(db)
    ) as scoped_session, patch(
        "app.tasks.audit_cleanup.now_sao_paulo", return_value=fixed_now
    ):
        result = check_hipaa_compliance.run()

    assert result["compliant"] is True
    assert result["issues"]["missing_retention_dates"] == 0
    assert result["issues"]["missing_legal_basis"] == 0
    assert result["issues"]["excessive_retention_periods"] == 0
    scoped_session.assert_called_once()
