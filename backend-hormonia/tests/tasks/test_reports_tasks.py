"""Focused tests for report Taskiq tasks."""

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
    from app.tasks.helpers.reports_helpers import _get_system_actor_uuid

    first = _get_system_actor_uuid()
    second = _get_system_actor_uuid()

    assert first == second
    assert first.int != 0


async def test_generate_patient_report_uses_scoped_session_and_system_actor_uuid(tmp_path):
    from app.tasks.helpers.reports_helpers import _get_system_actor_uuid
    from app.tasks.reports_taskiq import generate_patient_report

    patient_id = str(uuid4())
    report_id = uuid4()
    db = Mock()

    service = Mock()
    service.generate_report = AsyncMock(return_value=SimpleNamespace(id=report_id))
    service.generate_pdf_report.return_value = b"%PDF-1.7"

    with patch(
        "app.tasks.reports_taskiq.get_scoped_session", return_value=_scoped_session(db)
    ) as scoped_session, patch(
        "app.tasks.reports_taskiq.ReportService", return_value=service
    ), patch("app.tasks.reports_taskiq.settings.UPLOAD_DIRECTORY", str(tmp_path)):
        result = await generate_patient_report(patient_id=patient_id, report_type="medical")

    assert result["status"] == "completed"
    assert result["report_id"] == str(report_id)
    assert Path(result["output_path"]).exists()

    scoped_session.assert_called_once()
    called_request, called_actor_id = service.generate_report.call_args.args
    assert called_request.patient_id == UUID(patient_id)
    assert called_actor_id == _get_system_actor_uuid()
    assert called_actor_id.int != 0
    assert called_actor_id != UUID(int=0)


async def test_generate_scheduled_reports_uses_scoped_session():
    from app.tasks.reports_taskiq import generate_patient_report, generate_scheduled_reports

    db = Mock()
    service = Mock()
    service.get_scheduled_reports.return_value = [
        {"patient_id": uuid4(), "report_type": "medical"},
        {"patient_id": uuid4()},
    ]

    queued_tasks = [SimpleNamespace(id="task-1"), SimpleNamespace(id="task-2")]

    with patch(
        "app.tasks.reports_taskiq.get_scoped_session", return_value=_scoped_session(db)
    ) as scoped_session, patch(
        "app.tasks.reports_taskiq.ReportService", return_value=service
    ), patch.object(
        generate_patient_report,
        "kiq",
        new_callable=AsyncMock,
        side_effect=queued_tasks,
    ) as kiq_mock:
        result = await generate_scheduled_reports()

    assert result == {"status": "scheduled", "tasks": ["task-1", "task-2"], "count": 2}
    scoped_session.assert_called_once()
    assert kiq_mock.call_count == 2
