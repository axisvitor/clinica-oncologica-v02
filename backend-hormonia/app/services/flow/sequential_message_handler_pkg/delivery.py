from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from typing import Any
from uuid import UUID

from app.services.flow.config_validation import DayConfigValidationError

logger = logging.getLogger(__name__)


def delay_enabled() -> bool:
    if os.getenv("FLOW_DISABLE_DELAYS", "").strip().lower() in {"1", "true", "yes", "on"}:
        return False
    return not (os.getenv("TESTING") == "1" or os.getenv("PYTEST_CURRENT_TEST"))


async def await_inter_message_delay(seconds: float) -> None:
    if seconds <= 0 or not delay_enabled():
        return
    await asyncio.sleep(seconds)


def build_flow_idempotency_key(
    *,
    patient_id: UUID,
    flow_kind: str,
    day_number: int,
    message_index: int,
) -> str:
    base = f"flow:{patient_id}:{flow_kind}:{day_number}:{message_index}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]


def build_flow_send_context(
    *,
    flow_kind: str,
    day_number: int,
    message_index: int,
    expects_response: bool,
) -> dict[str, Any]:
    return {
        "flow_type": flow_kind,
        "flow_day": day_number,
        "message_index": message_index,
        "expects_response": expects_response,
        "source": "flow_sequential",
    }


def build_day_config_validation_error_response(
    *,
    patient_id: UUID,
    flow_kind: str,
    day_number: int,
    exc: DayConfigValidationError,
) -> dict[str, Any]:
    logger.warning(
        "Day config validation failed in send_day_messages",
        extra={
            "patient_id": str(patient_id),
            "flow_kind": flow_kind,
            "day_number": day_number,
            "errors": exc.errors,
        },
    )
    return {
        "status": "error",
        "message": str(exc),
        "validation_errors": exc.errors,
    }


async def enqueue_failed_flow_send_retry(
    *,
    message_id: UUID,
    patient_id: UUID,
    flow_kind: str,
    day_number: int,
    message_index: int,
    flow_context: dict[str, Any],
    resend: bool = False,
) -> None:
    from datetime import timedelta, timezone
    from app.tasks.flows_taskiq import retry_failed_flow_send
    from app.tasks.taskiq_base import schedule_task_at
    from app.config.settings.tasks import MESSAGE_RETRY_DELAY
    from datetime import datetime

    await schedule_task_at(
        retry_failed_flow_send,
        datetime.now(timezone.utc) + timedelta(seconds=MESSAGE_RETRY_DELAY),
        str(message_id),
        flow_context=flow_context,
    )
    logger.warning(
        "Flow message resend failed, enqueued retry"
        if resend
        else "Flow message send failed, enqueued retry",
        extra={
            "message_id": str(message_id),
            "patient_id": str(patient_id),
            "flow_kind": flow_kind,
            "day_number": day_number,
            "message_index": message_index,
        },
    )
