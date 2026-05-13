"""Focused tests for report Taskiq tasks."""

from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID, uuid4

import pytest

from app.api.v2.routers.upload import config as upload_config


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


@pytest.mark.parametrize(
    ("raw_report_type", "expected"),
    [
        ("../..", "medical"),
        ("", "medical"),
        ("   ", "medical"),
        ("../Follow Up", "followup"),
        ("CARDIO_v2-2026", "cardio_v2-2026"),
    ],
)
def test_sanitize_report_type_falls_back_and_removes_path_segments(raw_report_type, expected):
    from app.tasks.helpers.reports_helpers import _sanitize_report_type

    assert _sanitize_report_type(raw_report_type) == expected


def test_build_safe_report_path_uses_report_id_only_and_blocks_type_traversal(tmp_path):
    from app.tasks.helpers.reports_helpers import _build_safe_report_path

    report_id = uuid4()
    base_dir = tmp_path / "private" / "reports"

    output_path = _build_safe_report_path(base_dir, report_id, "../Oncology Summary!?/../../")

    assert output_path.parent == base_dir.resolve(strict=False)
    assert output_path.name == f"{report_id}.pdf"
    assert "oncology" not in output_path.name.lower()
    assert "summary" not in output_path.name.lower()
    assert ".." not in output_path.name
    assert "/" not in output_path.name
    assert "\\" not in output_path.name


def _assert_report_type_fragments_not_exposed(caplog, result: dict, fragments: list[str]) -> None:
    output_path = result.get("output_path", "")
    output_name = Path(output_path).name
    caplog_text = caplog.text.lower()
    structured_log_values = " ".join(
        str(value).lower()
        for record in caplog.records
        for key, value in record.__dict__.items()
        if key not in {"pathname", "filename", "module", "name", "msg", "args", "message"}
    )

    for fragment in fragments:
        normalized = fragment.lower()
        assert normalized not in output_name.lower()
        assert normalized not in output_path.lower()
        assert normalized not in caplog_text
        assert normalized not in structured_log_values


@pytest.mark.parametrize(
    ("raw_report_type", "leaking_fragments"),
    [
        ("medical/../../patient-name", ["patient-name", "medicalpatient-name"]),
        (
            "Jane Doe +551199999999 secret-token",
            ["jane", "doe", "551199999999", "secret-token", "secrettoken"],
        ),
        ("../../outside/escape-token", ["outside", "escape-token", "escape"]),
    ],
)
async def test_generate_patient_report_does_not_expose_free_form_report_type(
    raw_report_type,
    leaking_fragments,
    tmp_path,
    monkeypatch,
    caplog,
):
    from app.tasks.reports_taskiq import generate_patient_report

    public_upload_root = tmp_path / "uploads"
    monkeypatch.setattr(upload_config, "UPLOAD_DIR", public_upload_root)

    patient_id = str(uuid4())
    report_id = uuid4()
    db = Mock()

    service = Mock()
    service.generate_report = AsyncMock(return_value=SimpleNamespace(id=report_id))
    service.generate_pdf_report.return_value = b"%PDF-1.7"

    caplog.set_level("INFO", logger="app.tasks")
    caplog.set_level("WARNING", logger="app.tasks.reports_taskiq")

    with patch(
        "app.tasks.reports_taskiq.get_scoped_session", return_value=_scoped_session(db)
    ), patch("app.tasks.reports_taskiq.ReportService", return_value=service):
        result = await generate_patient_report(
            patient_id=patient_id,
            report_type=raw_report_type,
        )

    output_path = Path(result["output_path"]).resolve()
    private_report_root = (tmp_path / ".uploads_private" / "reports").resolve()

    assert result["status"] == "completed"
    assert result["report_id"] == str(report_id)
    assert output_path.exists()
    assert output_path.parent == private_report_root
    assert output_path.name == f"{report_id}.pdf"
    _assert_report_type_fragments_not_exposed(caplog, result, leaking_fragments)


async def test_generate_patient_report_uses_private_non_identifying_artifact_path(
    tmp_path,
    monkeypatch,
    caplog,
):
    from app.tasks.helpers.reports_helpers import _get_system_actor_uuid
    from app.tasks.reports_taskiq import generate_patient_report

    public_upload_root = tmp_path / "uploads"
    monkeypatch.setattr(upload_config, "UPLOAD_DIR", public_upload_root)

    patient_id = str(uuid4())
    report_id = uuid4()
    db = Mock()

    service = Mock()
    service.generate_report = AsyncMock(return_value=SimpleNamespace(id=report_id))
    service.generate_pdf_report.return_value = b"%PDF-1.7"

    caplog.set_level("INFO", logger="app.tasks")
    caplog.set_level("WARNING", logger="app.tasks.reports_taskiq")

    with patch(
        "app.tasks.reports_taskiq.get_scoped_session", return_value=_scoped_session(db)
    ) as scoped_session, patch(
        "app.tasks.reports_taskiq.ReportService", return_value=service
    ):
        result = await generate_patient_report(
            patient_id=patient_id,
            report_type="medical/../../patient-name",
        )

    output_path = Path(result["output_path"]).resolve()
    private_report_root = (tmp_path / ".uploads_private" / "reports").resolve()

    assert result["status"] == "completed"
    assert result["report_id"] == str(report_id)
    assert output_path.exists()
    assert output_path.read_bytes() == b"%PDF-1.7"
    assert output_path.parent == private_report_root
    assert output_path.name == f"{report_id}.pdf"
    assert patient_id not in output_path.name
    assert UUID(patient_id).hex not in output_path.name
    assert public_upload_root.resolve() not in output_path.parents
    _assert_report_type_fragments_not_exposed(
        caplog,
        result,
        ["patient-name", "medicalpatient-name"],
    )

    scoped_session.assert_called_once()
    called_request, called_actor_id = service.generate_report.call_args.args
    assert called_request.patient_id == UUID(patient_id)
    assert called_actor_id == _get_system_actor_uuid()
    assert called_actor_id.int != 0
    assert called_actor_id != UUID(int=0)
    assert patient_id not in caplog.text
    assert str(output_path) not in caplog.text


async def test_generate_patient_report_invalid_patient_id_fails_without_artifact_root(
    tmp_path,
    monkeypatch,
    caplog,
):
    from app.tasks.reports_taskiq import generate_patient_report

    public_upload_root = tmp_path / "uploads"
    monkeypatch.setattr(upload_config, "UPLOAD_DIR", public_upload_root)
    invalid_patient_id = "not-a-patient-uuid"

    caplog.set_level("INFO", logger="app.tasks")
    caplog.set_level("WARNING", logger="app.tasks.reports_taskiq")

    result = await generate_patient_report(
        patient_id=invalid_patient_id,
        report_type="../../medical",
    )

    assert result == {"status": "failed", "error": "invalid_patient_id"}
    assert not (tmp_path / ".uploads_private").exists()
    assert invalid_patient_id not in caplog.text
    _assert_report_type_fragments_not_exposed(
        caplog,
        {"output_path": ""},
        ["medical", "../../medical"],
    )


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
