"""Flow health summary queries and stalled-flow alerting."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import and_, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings.tasks import (
    FLOW_STALL_ALERT_HOURS,
    FLOW_STALL_ALERT_WEBHOOK_URL,
)
from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)

SQL_TRUTHY_VALUES = ("true", "True", "1", "yes")


def _failed_flow_clause():
    return PatientFlowState.step_data.op("?")("permanently_failed_at")


def _stalled_flow_clause(cutoff: datetime):
    return and_(
        PatientFlowState.step_data["awaiting_response"].astext.in_(SQL_TRUTHY_VALUES),
        PatientFlowState.last_interaction_at.is_not(None),
        PatientFlowState.last_interaction_at < cutoff,
    )


def _serialize_last_interaction_at(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _coerce_hours_stuck(value: Any, last_interaction_at: Any, current_time: datetime) -> float:
    if value is not None:
        return float(value)
    if isinstance(last_interaction_at, datetime):
        delta = current_time - last_interaction_at
        return round(max(delta.total_seconds(), 0) / 3600, 2)
    return float(FLOW_STALL_ALERT_HOURS)


class FlowHealthService:
    """Read-only flow health queries plus stalled-flow alert fan-out."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_health_summary(self) -> dict[str, int]:
        cutoff = now_sao_paulo() - timedelta(hours=FLOW_STALL_ALERT_HOURS)
        failed_clause = _failed_flow_clause()
        stalled_clause = _stalled_flow_clause(cutoff)

        active_result = await self.db.execute(
            select(func.count())
            .select_from(PatientFlowState)
            .join(Patient, Patient.id == PatientFlowState.patient_id)
            .where(
                PatientFlowState.completed_at.is_(None),
                Patient.deleted_at.is_(None),
                not_(failed_clause),
                not_(stalled_clause),
            )
        )
        stalled_result = await self.db.execute(
            select(func.count())
            .select_from(PatientFlowState)
            .join(Patient, Patient.id == PatientFlowState.patient_id)
            .where(
                PatientFlowState.completed_at.is_(None),
                Patient.deleted_at.is_(None),
                stalled_clause,
            )
        )
        failed_result = await self.db.execute(
            select(func.count())
            .select_from(PatientFlowState)
            .join(Patient, Patient.id == PatientFlowState.patient_id)
            .where(
                PatientFlowState.completed_at.is_(None),
                Patient.deleted_at.is_(None),
                failed_clause,
            )
        )
        completed_result = await self.db.execute(
            select(func.count())
            .select_from(PatientFlowState)
            .where(PatientFlowState.completed_at.is_not(None))
        )

        return {
            "active": int(active_result.scalar() or 0),
            "stalled": int(stalled_result.scalar() or 0),
            "failed": int(failed_result.scalar() or 0),
            "completed": int(completed_result.scalar() or 0),
        }

    async def check_and_fire_stall_alerts(self) -> list[dict[str, Any]]:
        current_time = now_sao_paulo()
        cutoff = current_time - timedelta(hours=FLOW_STALL_ALERT_HOURS)
        result = await self.db.execute(
            select(
                PatientFlowState.patient_id.label("patient_id"),
                PatientFlowState.id.label("flow_state_id"),
                PatientFlowState.last_interaction_at.label("last_interaction_at"),
            )
            .select_from(PatientFlowState)
            .join(Patient, Patient.id == PatientFlowState.patient_id)
            .where(
                PatientFlowState.completed_at.is_(None),
                Patient.deleted_at.is_(None),
                _stalled_flow_clause(cutoff),
            )
            .order_by(PatientFlowState.last_interaction_at.asc())
        )
        rows = result.mappings().all()

        stalled_flows: list[dict[str, Any]] = []
        for row in rows:
            last_interaction_at = row.get("last_interaction_at")
            stalled_flow = {
                "patient_id": str(row["patient_id"]),
                "flow_state_id": str(row["flow_state_id"]),
                "last_interaction_at": _serialize_last_interaction_at(last_interaction_at),
                "hours_stuck": _coerce_hours_stuck(
                    row.get("hours_stuck"),
                    last_interaction_at,
                    current_time,
                ),
            }
            stalled_flows.append(stalled_flow)
            logger.warning(
                "flow_stall_alert",
                extra={
                    "patient_id": stalled_flow["patient_id"],
                    "flow_state_id": stalled_flow["flow_state_id"],
                    "hours_stuck": stalled_flow["hours_stuck"],
                    "alert_type": "flow_stall",
                },
            )

        if stalled_flows and FLOW_STALL_ALERT_WEBHOOK_URL:
            payload = {
                "stalled_flows": stalled_flows,
                "alert_time": current_time.isoformat(),
                "threshold_hours": FLOW_STALL_ALERT_HOURS,
            }
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(
                        url=FLOW_STALL_ALERT_WEBHOOK_URL,
                        json=payload,
                    )
                    response.raise_for_status()
            except httpx.HTTPError:
                logger.exception(
                    "flow_stall_webhook_failed",
                    extra={
                        "webhook_url": FLOW_STALL_ALERT_WEBHOOK_URL,
                        "stalled_count": len(stalled_flows),
                    },
                )

        return stalled_flows


__all__ = ["FlowHealthService"]
