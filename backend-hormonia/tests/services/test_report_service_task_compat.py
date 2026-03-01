"""Compatibility tests for task-facing report service methods."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from app.services.reporting.report import ReportGenerationError, ReportService


@pytest.mark.asyncio
async def test_generate_report_creates_cached_artifact_for_tasks():
    service = ReportService(db=Mock())
    patient_id = uuid4()
    user_id = uuid4()

    request = SimpleNamespace(
        patient_id=patient_id,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        format="pdf",
    )

    payload = {
        "patient_id": str(patient_id),
        "patient_name": "Paciente Teste",
        "doctor_name": "Dr. Teste",
        "flow_state": "active",
    }
    service.generate_patient_report = AsyncMock(return_value=payload)

    generated = await service.generate_report(request, user_id)

    assert generated.id
    assert generated.patient_id == patient_id
    assert generated.generated_by == user_id
    assert generated.data == payload
    assert str(generated.id) in service._query_cache

    service.generate_patient_report.assert_awaited_once_with(
        patient_id=patient_id,
        user_id=user_id,
        include_messages=True,
        include_analytics=True,
    )


def test_generate_pdf_report_uses_cached_artifact():
    service = ReportService(db=Mock())
    report_id = uuid4()
    patient_id = uuid4()

    service._query_cache[str(report_id)] = {
        "id": report_id,
        "patient_id": patient_id,
        "period_start": date(2026, 1, 1),
        "period_end": date(2026, 1, 31),
        "generated_by": uuid4(),
        "format": "pdf",
        "status": "completed",
        "data": {
            "patient_id": str(patient_id),
            "patient_name": "Paciente Teste",
            "doctor_name": "Dr. Teste",
            "flow_state": "active",
            "current_day": 12,
            "message_count": 5,
        },
    }

    fake_pdf_generator = Mock()
    fake_pdf_generator.generate_summary_report.return_value = b"%PDF-1.4 test"

    with patch(
        "app.services.reporting.report.get_pdf_generator",
        return_value=fake_pdf_generator,
    ):
        pdf_bytes = service.generate_pdf_report(report_id)

    assert pdf_bytes == b"%PDF-1.4 test"
    assert fake_pdf_generator.generate_summary_report.call_count == 1


def test_generate_pdf_report_raises_when_artifact_is_missing():
    service = ReportService(db=Mock())
    with pytest.raises(ReportGenerationError):
        service.generate_pdf_report(uuid4())

