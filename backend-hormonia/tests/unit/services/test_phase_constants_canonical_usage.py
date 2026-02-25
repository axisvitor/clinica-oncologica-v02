"""Regression tests to keep service flow math aligned to canonical helpers."""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.agents.patient.flow_coordinator.constants import resolve_flow_type_and_day
from app.services.hive_mind_integration import HiveMindIntegrationService
from app.services.manual_correction import ManualCorrectionService
import app.services.manual_correction as manual_correction_module


@pytest.mark.asyncio
async def test_langgraph_routing_uses_canonical_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_calls: list[tuple[str, str, int]] = []

    class FakeSequentialMessageHandler:
        def __init__(self, _db_session: object) -> None:
            pass

        async def send_day_messages(self, patient_id, day_number: int, flow_kind: str):
            captured_calls.append((str(patient_id), flow_kind, day_number))
            return {"status": "ok"}

    monkeypatch.setitem(
        sys.modules,
        "app.services.flow.sequential_message_handler",
        SimpleNamespace(SequentialMessageHandler=FakeSequentialMessageHandler),
    )

    service = HiveMindIntegrationService(db_session=object())
    from app.utils.timezone import now_sao_paulo

    boundary_days = [15, 45, 46, 75]
    patients = []
    expected_by_patient_id: dict[str, tuple[str, int]] = {}

    for day in boundary_days:
        patient_id = uuid4()
        enrollment_date = now_sao_paulo().date() - timedelta(days=day - 1)
        patient = SimpleNamespace(
            id=patient_id,
            enrollment_date=enrollment_date,
            created_at=enrollment_date,
        )
        patients.append((patient, object()))
        expected_by_patient_id[str(patient_id)] = resolve_flow_type_and_day(day)

    result = await service._process_with_langgraph(patients)

    assert result["processed"] == len(boundary_days)
    assert result["errors"] == []
    for patient_id, flow_kind, day_number in captured_calls:
        assert (flow_kind, day_number) == expected_by_patient_id[patient_id]


@pytest.mark.asyncio
async def test_manual_correction_uses_compute_cycle_number_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDB:
        def __init__(self) -> None:
            self.commits = 0
            self.rollbacks = 0

        def commit(self) -> None:
            self.commits += 1

        def rollback(self) -> None:
            self.rollbacks += 1

    db = FakeDB()
    service = ManualCorrectionService(
        db=db,
        redis=SimpleNamespace(),
        flow_repository=SimpleNamespace(),
        corruption_detector=SimpleNamespace(),
    )

    from app.utils.timezone import now_sao_paulo

    expected_cycle = {46: (4, 6), 75: (7, 3)}

    def fake_compute_cycle_number(days_since_enrollment: int) -> tuple[int, int]:
        return expected_cycle[days_since_enrollment]

    monkeypatch.setattr(
        manual_correction_module,
        "compute_cycle_number",
        fake_compute_cycle_number,
    )

    for days_since_enrollment, (cycle_number, day_in_cycle) in expected_cycle.items():
        flow_state = SimpleNamespace(
            enrollment_date=now_sao_paulo() - timedelta(days=days_since_enrollment - 1),
            current_day=1,
            flow_type="onboarding",
            monthly_cycle=None,
            updated_at=None,
        )

        result = await service._reset_to_calculated_day(uuid4(), flow_state, {})

        assert result["success"] is True
        assert flow_state.monthly_cycle == cycle_number
        assert flow_state.current_day == day_in_cycle

    assert db.commits == len(expected_cycle)
    assert db.rollbacks == 0


def test_legacy_hardcoded_phase_math_patterns_not_reintroduced() -> None:
    hive_path = Path("app/services/hive_mind_integration.py")
    manual_path = Path("app/services/manual_correction.py")

    hive_source = hive_path.read_text(encoding="utf-8")
    manual_source = manual_path.read_text(encoding="utf-8")

    banned_patterns = [
        "if current_day <= 15:",
        "elif current_day <= 45:",
        "(current_day - 46) % 30",
        "monthly_cycle = ((days_since_enrollment - 46) // 30) + 1",
        "new_day = ((days_since_enrollment - 46) % 30) + 1",
    ]

    assert banned_patterns[0] not in hive_source
    assert banned_patterns[1] not in hive_source
    assert banned_patterns[2] not in hive_source
    assert banned_patterns[3] not in manual_source
    assert banned_patterns[4] not in manual_source
