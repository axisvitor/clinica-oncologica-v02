from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4
import sys

import pytest

from app.domain.messaging.scheduling.message_scheduler.models import SchedulingWindow
from app.domain.messaging.scheduling.message_scheduler.models import TaskSchedulingError
from app.domain.messaging.scheduling.message_scheduler.metrics import MetricsCollector
from app.domain.messaging.scheduling.message_scheduler.retry_handler import RetryHandler
from app.domain.messaging.scheduling.message_scheduler.scheduler import MessageScheduler
from app.models.message import DeliveryStatus, MessageStatus
from app.utils.timezone import now_sao_paulo


@pytest.mark.asyncio
async def test_schedule_message_creates_pending_status():
    db = Mock()
    scheduler = MessageScheduler(db=None)
    scheduler.db = db
    scheduler.patient_repo = Mock()
    scheduler.patient_repo.get.return_value = SimpleNamespace(id=uuid4())
    scheduler.timezone_handler.calculate_optimal_delivery_time = AsyncMock(
        return_value=now_sao_paulo() + timedelta(hours=1)
    )
    scheduler.task_scheduler.schedule_celery_task = AsyncMock(
        return_value={"task_id": "task-123"}
    )

    patient_id = uuid4()
    result = await scheduler.schedule_message(
        patient_id=patient_id,
        message_content="Mensagem agendada",
        scheduling_window=SchedulingWindow.BUSINESS_HOURS,
    )

    created_message = db.add.call_args.args[0]
    assert created_message.status == MessageStatus.PENDING
    assert result["task_id"] == "task-123"


@pytest.mark.asyncio
async def test_reschedule_message_keeps_message_claimable():
    db = Mock()
    scheduler = MessageScheduler(db=None)
    scheduler.db = db
    scheduler.message_repo = Mock()
    scheduler.task_scheduler.cancel_celery_task = Mock()
    scheduler.task_scheduler.schedule_celery_task = AsyncMock(
        return_value={"task_id": "task-new"}
    )

    message = SimpleNamespace(
        id=uuid4(),
        status=MessageStatus.SCHEDULED,
        message_metadata={"celery_task_id": "task-old"},
        scheduled_for=now_sao_paulo(),
    )
    scheduler.message_repo.get.return_value = message

    await scheduler.reschedule_message(
        message_id=message.id,
        new_delivery_time=now_sao_paulo() + timedelta(hours=2),
        reason="patient_window_change",
    )

    assert message.status == MessageStatus.PENDING
    assert message.message_metadata["celery_task_id"] == "task-new"


@pytest.mark.asyncio
async def test_schedule_existing_message_keeps_pending_status():
    db = Mock()
    scheduler = MessageScheduler(db=None)
    scheduler.db = db
    scheduler.message_repo = Mock()
    scheduler.task_scheduler.schedule_celery_task = AsyncMock(
        return_value={"task_id": "task-existing"}
    )

    message = SimpleNamespace(
        id=uuid4(),
        status=MessageStatus.SCHEDULED,
        message_metadata={},
    )
    scheduler.message_repo.get.return_value = message

    result = await scheduler.schedule_existing_message(
        message_id=message.id,
        send_time=now_sao_paulo() + timedelta(minutes=30),
        priority=2,
    )

    assert result is True
    assert message.status == MessageStatus.PENDING
    assert message.message_metadata["scheduling_status"] == "success"


@pytest.mark.asyncio
async def test_on_delivery_failure_sets_retry_status_to_pending():
    db = Mock()
    scheduler = MessageScheduler(db=None)
    scheduler.db = db
    scheduler.message_repo = Mock()
    scheduler.retry_handler.calculate_retry_delay = Mock(return_value=timedelta(minutes=5))
    scheduler.retry_handler.schedule_retry = AsyncMock(return_value=None)

    message = SimpleNamespace(
        id=uuid4(),
        patient_id=uuid4(),
        content="Mensagem teste",
        retry_count=0,
        next_retry_at=None,
        message_metadata={},
        delivery_status=DeliveryStatus.SENDING,
        status=MessageStatus.SENDING,
        failure_reason=None,
        last_retry_at=None,
    )
    scheduler.message_repo.get.return_value = message

    result = await scheduler.on_delivery_failure(
        message_id=message.id,
        failure_reason="provider_timeout",
    )

    assert result["status"] == "retry_scheduled"
    assert message.status == MessageStatus.PENDING
    assert message.delivery_status == DeliveryStatus.QUEUED
    assert message.next_retry_at is not None


@pytest.mark.asyncio
async def test_schedule_message_marks_failed_when_celery_task_not_created():
    db = Mock()
    scheduler = MessageScheduler(db=None)
    scheduler.db = db
    scheduler.patient_repo = Mock()
    scheduler.patient_repo.get.return_value = SimpleNamespace(id=uuid4())
    scheduler.timezone_handler.calculate_optimal_delivery_time = AsyncMock(
        return_value=now_sao_paulo() + timedelta(hours=1)
    )
    scheduler.task_scheduler.schedule_celery_task = AsyncMock(
        return_value={"task_id": None, "error": "broker unavailable"}
    )

    patient_id = uuid4()
    with pytest.raises(TaskSchedulingError):
        await scheduler.schedule_message(
            patient_id=patient_id,
            message_content="Mensagem com falha de agendamento",
            scheduling_window=SchedulingWindow.BUSINESS_HOURS,
        )

    created_message = db.add.call_args.args[0]
    assert created_message.status == MessageStatus.FAILED
    assert created_message.message_metadata["scheduling_status"] == "failed"
    assert created_message.message_metadata["scheduling_error"] == "broker unavailable"


@pytest.mark.asyncio
async def test_cancel_scheduled_message_initializes_null_metadata():
    db = Mock()
    scheduler = MessageScheduler(db=None)
    scheduler.db = db
    scheduler.message_repo = Mock()
    scheduler.task_scheduler.cancel_celery_task = Mock()

    message = SimpleNamespace(
        id=uuid4(),
        status=MessageStatus.PENDING,
        message_metadata=None,
    )
    scheduler.message_repo.get.return_value = message

    result = await scheduler.cancel_scheduled_message(message.id)

    assert result is True
    assert isinstance(message.message_metadata, dict)
    assert "cancelled_at" in message.message_metadata


@pytest.mark.asyncio
async def test_update_delivery_status_initializes_null_metadata():
    db = Mock()
    scheduler = MessageScheduler(db=None)
    scheduler.db = db
    scheduler.message_repo = Mock()

    message = SimpleNamespace(
        id=uuid4(),
        status=MessageStatus.PENDING,
        message_metadata=None,
        sent_at=None,
        delivered_at=None,
        read_at=None,
        whatsapp_id=None,
    )
    scheduler.message_repo.get.return_value = message

    result = await scheduler.update_delivery_status(
        message_id=message.id,
        status=DeliveryStatus.SENT,
        delivery_info={"provider": "test"},
    )

    assert result is True
    assert message.status == MessageStatus.SENT
    assert message.message_metadata["delivery_status"] == DeliveryStatus.SENT.value
    assert message.message_metadata["delivery_tracking"]["provider"] == "test"


@pytest.mark.asyncio
async def test_retry_handler_schedule_retry_initializes_null_metadata(monkeypatch):
    handler = RetryHandler(db=Mock())
    message = SimpleNamespace(id=uuid4(), message_metadata=None)

    send_scheduled_message = SimpleNamespace(
        apply_async=Mock(return_value=SimpleNamespace(id="retry-task-1"))
    )
    fake_tasks_module = SimpleNamespace(send_scheduled_message=send_scheduled_message)
    monkeypatch.setitem(sys.modules, "app.tasks.messaging", fake_tasks_module)

    await handler.schedule_retry(
        message=message, retry_time=now_sao_paulo() + timedelta(minutes=10)
    )

    assert message.message_metadata["retry_task_id"] == "retry-task-1"
    assert "retry_scheduled_at" in message.message_metadata


@pytest.mark.asyncio
async def test_metrics_collector_handles_null_message_metadata():
    db = Mock()
    collector = MetricsCollector(db)

    now = now_sao_paulo()
    message = SimpleNamespace(
        id=uuid4(),
        patient_id=uuid4(),
        content="Mensagem com metadata nula",
        scheduled_for=now,
        created_at=now,
        message_metadata=None,
        status=MessageStatus.SCHEDULED,
    )

    query = Mock()
    query.filter.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = [message]
    db.query.return_value = query

    result = await collector.get_scheduled_messages()

    assert len(result) == 1
    assert result[0]["metadata"] == {}
    assert message.message_metadata == {}
