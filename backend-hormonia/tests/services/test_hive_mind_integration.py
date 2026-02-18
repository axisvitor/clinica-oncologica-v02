from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import app.services.hive_mind_integration as integration_module
from app.services.hive_mind_integration import HiveMindIntegrationService
from app.utils.timezone import now_sao_paulo


class _DummyAgent:
    def __init__(self, *_args, **_kwargs):
        self.initialize_calls = 0

    async def initialize(self):
        self.initialize_calls += 1


@pytest.mark.asyncio
async def test_initialize_agents_registers_all_expected_agents(monkeypatch):
    service = HiveMindIntegrationService(
        db_session=MagicMock(),
        template_loader=MagicMock(),
    )
    service.swarm_manager = SimpleNamespace(register_agent=AsyncMock(return_value=True))

    import app.agents.patient.flow_coordinator as flow_coordinator_module
    import app.domain.agents.quiz as quiz_module
    import app.agents.communication.message_composer as message_composer_module
    import app.agents.patient.patient_monitor as patient_monitor_module
    import app.agents.analytics.alert_analyzer as alert_analyzer_module
    import app.agents.communication.response_processor as response_processor_module

    monkeypatch.setattr(
        flow_coordinator_module, "FlowCoordinatorAgent", _DummyAgent
    )
    monkeypatch.setattr(quiz_module, "QuizConductor", _DummyAgent)
    monkeypatch.setattr(message_composer_module, "MessageComposerAgent", _DummyAgent)
    monkeypatch.setattr(patient_monitor_module, "PatientMonitorAgent", _DummyAgent)
    monkeypatch.setattr(alert_analyzer_module, "AlertAnalyzerAgent", _DummyAgent)
    monkeypatch.setattr(
        response_processor_module, "ResponseProcessorAgent", _DummyAgent
    )

    await service._initialize_agents()

    assert service.swarm_manager.register_agent.await_count == 6
    assert set(service.agents.keys()) == {
        "flow_coordinator",
        "quiz_conductor",
        "message_composer",
        "patient_monitor",
        "alert_analyzer",
        "response_processor",
    }


@pytest.mark.asyncio
async def test_process_with_agents_tracks_all_tasks_without_skipping(monkeypatch):
    service = HiveMindIntegrationService(
        db_session=MagicMock(),
        template_loader=MagicMock(),
    )
    task_ids = iter(["task-1", "task-2", "task-3"])
    submit_task = AsyncMock(side_effect=lambda **_kwargs: next(task_ids))
    get_task_status = AsyncMock(
        side_effect=lambda task_id: {"status": "completed", "task_id": task_id}
    )
    service.swarm_manager = SimpleNamespace(
        submit_task=submit_task,
        get_task_status=get_task_status,
    )

    sleep_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(integration_module.asyncio, "sleep", sleep_mock)

    patients = [
        (
            SimpleNamespace(id=uuid4(), enrollment_date=None, created_at=now_sao_paulo()),
            SimpleNamespace(id=uuid4()),
        ),
        (
            SimpleNamespace(id=uuid4(), enrollment_date=None, created_at=now_sao_paulo()),
            SimpleNamespace(id=uuid4()),
        ),
        (
            SimpleNamespace(id=uuid4(), enrollment_date=None, created_at=now_sao_paulo()),
            SimpleNamespace(id=uuid4()),
        ),
    ]

    result = await service._process_with_agents(patients)

    assert result["processed"] == 3
    assert result["errors"] == []
    assert submit_task.await_count == 3
    assert get_task_status.await_count >= 3
