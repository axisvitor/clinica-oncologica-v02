"""Celery task for detecting and recovering stuck patient flows."""

from __future__ import annotations

import logging
from typing import Any

from app.core.redis_manager import get_redis_manager
from app.database import get_scoped_session
from app.services.flow.recovery import attempt_recovery, find_stuck_flows
from app.task_queue import task_queue as celery_app
from app.utils.timezone import now_sao_paulo

from .base import FlowTaskBase

logger = logging.getLogger(__name__)

_SKIPPED_RECOVERY_STATUSES = {
    "already_recovering",
    "max_attempts_exceeded",
    "no_longer_stuck",
}


@celery_app.task(
    bind=True,
    base=FlowTaskBase,
    name="app.tasks.flows.stuck_detection.detect_stuck_flows",
    max_retries=1,
    acks_late=True,
    reject_on_worker_lost=True,
)
def detect_stuck_flows(self) -> dict[str, Any]:
    """Detect stuck flows and attempt bounded recovery for each one."""
    summary: dict[str, Any] = {
        "detected_count": 0,
        "recovered_count": 0,
        "skipped_count": 0,
        "failed_count": 0,
        "timestamp": now_sao_paulo().isoformat(),
    }

    with get_scoped_session() as db:
        redis_client = get_redis_manager().get_sync_client()
        stuck_flows = find_stuck_flows(db)
        summary["detected_count"] = len(stuck_flows)

        if not stuck_flows:
            logger.info("No stuck flows detected", extra=summary)
            return summary

        for flow_state in stuck_flows:
            try:
                result = attempt_recovery(db, flow_state, redis_client)
            except Exception:
                summary["failed_count"] += 1
                logger.exception(
                    "Failed to recover stuck flow",
                    extra={
                        "flow_state_id": str(flow_state.id),
                        "patient_id": str(flow_state.patient_id),
                    },
                )
                continue

            status = result.get("status")
            if status == "recovered":
                summary["recovered_count"] += 1
            elif status in _SKIPPED_RECOVERY_STATUSES:
                summary["skipped_count"] += 1
            else:
                summary["failed_count"] += 1
                logger.warning(
                    "Stuck flow recovery returned unexpected status",
                    extra={
                        "flow_state_id": str(flow_state.id),
                        "patient_id": str(flow_state.patient_id),
                        "status": status,
                    },
                )

        logger.info("Completed stuck flow detection run", extra=summary)
        return summary


__all__ = ["detect_stuck_flows"]
