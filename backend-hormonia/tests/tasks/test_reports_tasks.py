"""Focused tests for report Celery tasks."""

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4


def _scoped_session(db):
    @contextmanager
    def _ctx():
        yield db

    return _ctx()


def test_get_system_actor_uuid_is_deterministic_and_non_zero():
    from app.tasks.reports import _get_system_actor_uuid

    first = _get_system_actor_uuid()
    second = _get_system_actor_uuid()

    assert first == second
    assert first.int != 0


def test_generate_patient_report_uses_scoped_session_and_system_actor_uuid(tmp_path):
    from app.tasks.reports import _get_system_actor_uuid, generate_patient_report

    patient_id = str(uuid4())
    report_id = uuid4()
    db = Mock()

    service = Mock()
    service.generate_report = AsyncMock(return_value=SimpleNamespace(id=report_id))
    service.generate_pdf_report.return_value = b"%PDF-1.7"

    with patch(
        "app.tasks.reports.get_scoped_session", return_value=_scoped_session(db)
    ) as scoped_session, patch(
        "app.tasks.reports.ReportService", return_value=service
    ), patch("app.tasks.reports.settings.UPLOAD_DIRECTORY", str(tmp_path)):
        result = generate_patient_report.run(patient_id=patient_id, report_type="medical")

    assert result["status"] == "completed"
    assert result["report_id"] == str(report_id)
    assert Path(result["output_path"]).exists()

    scoped_session.assert_called_once()
    called_request, called_actor_id = service.generate_report.call_args.args
    assert called_request.patient_id == UUID(patient_id)
    assert called_actor_id == _get_system_actor_uuid()
    assert called_actor_id.int != 0
    assert called_actor_id != UUID(int=0)


def test_generate_scheduled_reports_uses_scoped_session():
    from app.tasks.reports import generate_scheduled_reports

    db = Mock()
    service = Mock()
    service.get_scheduled_reports.return_value = [
        {"patient_id": uuid4(), "report_type": "medical"},
        {"patient_id": uuid4()},
    ]

    queued_tasks = [SimpleNamespace(id="task-1"), SimpleNamespace(id="task-2")]

    with patch(
        "app.tasks.reports.get_scoped_session", return_value=_scoped_session(db)
    ) as scoped_session, patch(
        "app.tasks.reports.ReportService", return_value=service
    ), patch(
        "app.tasks.reports.generate_patient_report.apply_async",
        side_effect=queued_tasks,
    ) as apply_async:
        result = generate_scheduled_reports.run()

    assert result == {"status": "scheduled", "tasks": ["task-1", "task-2"], "count": 2}
    scoped_session.assert_called_once()
    assert apply_async.call_count == 2


def test_generate_patient_report_uses_run_async_bridge(tmp_path):
    from app.tasks.reports import generate_patient_report

    patient_id = str(uuid4())
    report_id = uuid4()

    db = Mock()
    report_service = Mock()
    report_service.generate_report.return_value = "generate-report-coro"
    report_service.generate_pdf_report.return_value = b"%PDF-1.7"

    with patch(
        "app.tasks.reports.get_scoped_session", return_value=_scoped_session(db)
    ), patch("app.tasks.reports.ReportService", return_value=report_service), patch(
        "app.tasks.reports.run_async", return_value=SimpleNamespace(id=report_id)
    ) as run_async_mock, patch(
        "app.tasks.reports.settings.UPLOAD_DIRECTORY", str(tmp_path)
    ):
        result = generate_patient_report.run(patient_id=patient_id, report_type="medical")

    assert result["status"] == "completed"
    run_async_mock.assert_called_once_with("generate-report-coro")
