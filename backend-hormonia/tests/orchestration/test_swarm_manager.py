import asyncio
import threading
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.orchestration.swarm_manager as swarm_module
from app.agents.base import AgentStatus
from app.utils.timezone import now_sao_paulo


@pytest.mark.asyncio
async def test_singleton_bootstrap_is_concurrency_safe(monkeypatch) -> None:
    swarm_module._swarm_manager = None
    swarm_module._swarm_manager_lock = threading.Lock()
    start_calls = 0

    async def fake_start(self) -> None:
        nonlocal start_calls
        start_calls += 1

    monkeypatch.setattr(swarm_module.SwarmManager, "start", fake_start)

    managers = await asyncio.gather(
        *(swarm_module.get_swarm_manager() for _ in range(8))
    )

    assert len({id(manager) for manager in managers}) == 1
    assert start_calls == 8


@pytest.mark.asyncio
async def test_start_is_idempotent_and_does_not_duplicate_background_tasks(
    monkeypatch,
) -> None:
    manager = swarm_module.SwarmManager()

    async def fake_health_monitor():
        return SimpleNamespace()

    async def blocker():
        await asyncio.sleep(3600)

    created_tasks = []

    def fake_create_background_task(coro, name):
        task = asyncio.create_task(coro, name=name)
        created_tasks.append(task)
        return task

    monkeypatch.setattr(swarm_module, "get_system_health_monitor", fake_health_monitor)
    monkeypatch.setattr(manager, "_task_processor", blocker)
    monkeypatch.setattr(manager, "_health_monitor", blocker)
    monkeypatch.setattr(manager, "_message_router", blocker)
    monkeypatch.setattr(manager, "_metrics_collector", blocker)
    monkeypatch.setattr(manager, "_create_background_task", fake_create_background_task)

    await manager.start()
    first_background_tasks = list(manager.background_tasks)

    await manager.start()

    assert manager.background_tasks == first_background_tasks
    assert len(created_tasks) == 4

    await manager.stop()


@pytest.mark.asyncio
async def test_complete_task_uses_finished_task_counters_for_success_rate() -> None:
    manager = swarm_module.SwarmManager()
    agent_id = "agent-1"
    manager.agent_health[agent_id] = swarm_module.AgentHealth(
        agent_id=agent_id,
        status=AgentStatus.ACTIVE,
        last_heartbeat=now_sao_paulo(),
        response_time=0.2,
        success_rate=1.0,
        active_tasks=2,
        tasks_completed=0,
        tasks_failed=0,
        error_count=0,
        uptime=timedelta(),
    )

    task_success = swarm_module.SwarmTask(
        task_id="task-success",
        task_type="analysis",
        payload={},
        priority=swarm_module.MessagePriority.NORMAL,
        required_capabilities=[],
        assigned_agent=agent_id,
        status=swarm_module.TaskStatus.IN_PROGRESS,
    )
    manager.tasks[task_success.task_id] = task_success

    await manager.complete_task(task_success.task_id, result={"ok": True})

    health = manager.agent_health[agent_id]
    assert health.tasks_completed == 1
    assert health.tasks_failed == 0
    assert health.success_rate == 1.0

    task_failed = swarm_module.SwarmTask(
        task_id="task-failed",
        task_type="analysis",
        payload={},
        priority=swarm_module.MessagePriority.NORMAL,
        required_capabilities=[],
        assigned_agent=agent_id,
        status=swarm_module.TaskStatus.IN_PROGRESS,
    )
    manager.tasks[task_failed.task_id] = task_failed

    await manager.complete_task(task_failed.task_id, error="boom")

    health = manager.agent_health[agent_id]
    assert health.tasks_completed == 1
    assert health.tasks_failed == 1
    assert health.error_count == 1
    assert health.success_rate == 0.5


@pytest.mark.asyncio
async def test_metrics_collector_uses_completed_and_failed_task_counters(
    monkeypatch,
) -> None:
    manager = swarm_module.SwarmManager()
    agent_id = "agent-1"
    manager.status = swarm_module.SwarmStatus.ACTIVE
    manager.agents[agent_id] = SimpleNamespace()
    manager.agent_health[agent_id] = swarm_module.AgentHealth(
        agent_id=agent_id,
        status=AgentStatus.ACTIVE,
        last_heartbeat=now_sao_paulo(),
        response_time=0.1,
        success_rate=0.6,
        active_tasks=10,
        tasks_completed=3,
        tasks_failed=2,
        error_count=2,
        uptime=timedelta(),
    )

    update_agent_metrics = AsyncMock()
    manager.health_monitor = SimpleNamespace(update_agent_metrics=update_agent_metrics)

    async def fake_send_message_to_agent(*_args, **_kwargs):
        manager.status = swarm_module.SwarmStatus.SHUTDOWN

    sleep_mock = AsyncMock(return_value=None)

    monkeypatch.setattr(manager, "send_message_to_agent", fake_send_message_to_agent)
    monkeypatch.setattr(swarm_module.asyncio, "sleep", sleep_mock)

    await manager._metrics_collector()

    call_kwargs = update_agent_metrics.await_args.kwargs
    assert call_kwargs["tasks_completed"] == 3
    assert call_kwargs["tasks_failed"] == 2


@pytest.mark.asyncio
async def test_assign_task_uses_task_type_payload_contract() -> None:
    manager = swarm_module.SwarmManager()
    agent_id = "agent-1"
    manager.agent_health[agent_id] = swarm_module.AgentHealth(
        agent_id=agent_id,
        status=AgentStatus.ACTIVE,
        last_heartbeat=now_sao_paulo(),
        response_time=0.1,
        success_rate=1.0,
        active_tasks=0,
        tasks_completed=0,
        tasks_failed=0,
        error_count=0,
        uptime=timedelta(),
    )

    task = swarm_module.SwarmTask(
        task_id="task-1",
        task_type="analysis",
        payload={"foo": "bar"},
        priority=swarm_module.MessagePriority.NORMAL,
        required_capabilities=[],
    )

    manager.send_message_to_agent = AsyncMock()
    manager._emit_event = AsyncMock()

    await manager._assign_task_to_agent(task, agent_id)

    payload = manager.send_message_to_agent.await_args.args[2]
    assert payload["task_data"]["task_type"] == "analysis"
    assert "type" not in payload["task_data"]
