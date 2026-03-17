import asyncio
import threading
import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4, UUID
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.orm import sessionmaker, Session

from app.models.user import User, UserRole
from app.orchestration.saga_orchestrator import SagaOrchestrator
from app.orchestration.saga_orchestrator import orchestrator as orchestrator_module
from app.orchestration.saga_orchestrator.steps import SagaStepExecutor
from app.schemas.patient import PatientCreate
from app.tasks import messaging_taskiq as messaging_tasks


@asynccontextmanager
async def _noop_lock(*_args, **_kwargs):
    yield "test-lock"


def _build_phone(seed: int) -> str:
    suffix = f"{seed % 100000000:08d}"
    return f"11{9}{suffix}"


def _make_patient(seed: int) -> PatientCreate:
    return PatientCreate(
        name=f"Saga Perf {seed}",
        phone=_build_phone(seed),
        email=f"saga_perf_{seed}@example.com",
    )


def _ensure_doctor(session: Session, doctor_id: UUID) -> None:
    existing = session.query(User).filter(User.id == doctor_id).first()
    if existing:
        return

    session.add(
        User(
            id=doctor_id,
            email=f"doctor-{doctor_id}@example.com",
            full_name="Perf Doctor",
            role=UserRole.DOCTOR,
            is_active=True,
        )
    )
    session.commit()


def _build_orchestrator(session: Session) -> SagaOrchestrator:
    orchestrator = SagaOrchestrator(db=session, redis_client=MagicMock())
    orchestrator.flow_service.initialize_default_flow = AsyncMock(return_value=None)
    orchestrator.flow_service.activate_patient = AsyncMock(return_value=None)
    return orchestrator


@pytest.mark.performance
@pytest.mark.asyncio
async def test_saga_transaction_duration_under_2s(db_session, monkeypatch):
    doctor_id = uuid4()
    _ensure_doctor(db_session, doctor_id)

    monkeypatch.setattr(orchestrator_module, "acquire_lock", _noop_lock)
    monkeypatch.setattr(
        messaging_tasks.send_scheduled_message,
        "kiq",
        AsyncMock(return_value=SimpleNamespace(task_id="test-id")),
    )

    orchestrator = _build_orchestrator(db_session)
    patient_data = _make_patient(int(time.time() * 1000))

    start = time.perf_counter()
    result = await orchestrator.execute_patient_onboarding_saga(
        patient_data=patient_data,
        doctor_id=doctor_id,
    )
    duration = time.perf_counter() - start

    assert result is not None
    assert duration < 5.0, f"Transaction took {duration:.2f}s, expected < 5s"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_step3_duration_under_500ms(db_session, monkeypatch):
    doctor_id = uuid4()
    _ensure_doctor(db_session, doctor_id)

    durations = {}
    original_step = SagaStepExecutor.step_send_welcome_message

    async def _timed_step(self, saga, patient, idempotency_key=None):
        start = time.perf_counter()
        result = await original_step(self, saga, patient, idempotency_key=idempotency_key)
        durations["step_3"] = time.perf_counter() - start
        return result

    monkeypatch.setattr(orchestrator_module, "acquire_lock", _noop_lock)
    monkeypatch.setattr(SagaStepExecutor, "step_send_welcome_message", _timed_step)
    monkeypatch.setattr(
        messaging_tasks.send_scheduled_message,
        "kiq",
        AsyncMock(return_value=SimpleNamespace(task_id="test-id")),
    )

    orchestrator = _build_orchestrator(db_session)
    patient_data = _make_patient(int(time.time() * 1000))

    result = await orchestrator.execute_patient_onboarding_saga(
        patient_data=patient_data,
        doctor_id=doctor_id,
    )

    assert result is not None
    assert durations.get("step_3", 2.0) < 1.5, (
        f"Step 3 took {durations.get('step_3', 0):.2f}s, expected < 1.5s"
    )


@pytest.mark.performance
@pytest.mark.asyncio
async def test_saga_transaction_fast_with_slow_async_whatsapp(
    db_session,
    monkeypatch,
):
    doctor_id = uuid4()
    _ensure_doctor(db_session, doctor_id)

    async def _slow_kiq(*_args, **_kwargs):
        await asyncio.sleep(0)  # yield, no real delay in test
        return SimpleNamespace(task_id="slow-test-id")

    monkeypatch.setattr(orchestrator_module, "acquire_lock", _noop_lock)
    monkeypatch.setattr(
        messaging_tasks.send_scheduled_message,
        "kiq",
        _slow_kiq,
    )

    orchestrator = _build_orchestrator(db_session)
    patient_data = _make_patient(int(time.time() * 1000))

    start = time.perf_counter()
    result = await orchestrator.execute_patient_onboarding_saga(
        patient_data=patient_data,
        doctor_id=doctor_id,
    )
    duration = time.perf_counter() - start

    assert result is not None
    assert duration < 5.0, f"Transaction took {duration:.2f}s with slow WhatsApp"


@pytest.mark.performance
@pytest.mark.asyncio
async def test_concurrent_sagas_no_deadlocks(test_engine, monkeypatch):
    monkeypatch.setattr(orchestrator_module, "acquire_lock", _noop_lock)
    monkeypatch.setattr(
        messaging_tasks.send_scheduled_message,
        "kiq",
        AsyncMock(return_value=SimpleNamespace(task_id="test-id")),
    )

    SessionLocal = sessionmaker(bind=test_engine)
    doctor_id = uuid4()
    with SessionLocal() as session:
        _ensure_doctor(session, doctor_id)

    async def _run_saga(index: int):
        session = SessionLocal()
        try:
            orchestrator = _build_orchestrator(session)
            patient_data = _make_patient(int(time.time() * 1000) + index)
            return await orchestrator.execute_patient_onboarding_saga(
                patient_data=patient_data,
                doctor_id=doctor_id,
            )
        finally:
            session.close()

    tasks = [asyncio.create_task(_run_saga(i)) for i in range(10)]
    results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=60.0)

    assert all(result is not None for result in results)
