import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select, text

from app.models.flow import PatientFlowState
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class StateMixin:
    async def _get_day_config(self, flow_kind: str, day: int) -> Optional[Dict]:
        """
        Get the configuration for a specific day in a flow.

        Uses Redis cache to reduce database load with multiple patients.
        Cache TTL: 1 hour (templates rarely change)
        """
        import json

        from app.core.redis_manager import get_sync_redis_client

        cache_key = f"flow_template:{flow_kind}:steps"
        cache_ttl = 3600

        try:
            redis_client = get_sync_redis_client()
            if redis_client:
                cached_data = redis_client.get(cache_key)
                if cached_data:
                    logger.debug("Cache hit for %s", cache_key)
                    steps = json.loads(cached_data)
                    for step in steps:
                        if step.get("day") == day:
                            return step
                    return None
        except Exception as exc:
            logger.warning("Redis cache error (falling back to DB): %s", exc)

        result_proxy = await self.db.execute(
            text(
                """
            SELECT ftv.steps
            FROM flow_template_versions ftv
            JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id
            WHERE fk.kind_key = :kind AND ftv.is_active = true
        """
            ),
            {"kind": flow_kind},
        )
        result = result_proxy.fetchone()

        if not result or not result[0]:
            return None

        steps = result[0]

        try:
            redis_client = get_sync_redis_client()
            if redis_client:
                redis_client.setex(cache_key, cache_ttl, json.dumps(steps, ensure_ascii=False))
                logger.debug("Cached %s with TTL %ss", cache_key, cache_ttl)
        except Exception as exc:
            logger.warning("Failed to cache flow template: %s", exc)

        for step in steps:
            if step.get("day") == day:
                return step

        return None

    async def _get_or_create_flow_state(
        self,
        patient_id: UUID,
        flow_kind: str,
    ) -> PatientFlowState:
        """Get or create patient flow state."""
        active_result = await self.db.execute(
            select(PatientFlowState).filter(
                PatientFlowState.patient_id == patient_id,
                PatientFlowState.status == "active",
            )
        )
        flow_state = active_result.scalar_one_or_none()

        if not flow_state:
            result_proxy = await self.db.execute(
                text(
                    """
                SELECT ftv.id
                FROM flow_template_versions ftv
                JOIN flow_kinds fk ON ftv.flow_kind_id = fk.id
                WHERE fk.kind_key = :kind AND ftv.is_active = true
            """
                ),
                {"kind": flow_kind},
            )
            result = result_proxy.fetchone()

            if result:
                flow_state = PatientFlowState(
                    patient_id=patient_id,
                    flow_template_version_id=result[0],
                    status="active",
                    step_data={"flow_kind": flow_kind},
                )
                self.db.add(flow_state)
                await self.db.commit()

        return flow_state

    def _mark_last_message_sent(self, step_data: Dict[str, Any]) -> None:
        """Persist canonical last-message timestamps."""
        timestamp = now_sao_paulo().isoformat()
        step_data["last_message_sent_at"] = timestamp
        step_data["last_message_sent"] = timestamp

    def _resolve_sent_message_id(
        self,
        *,
        patient_id: UUID,
        flow_kind: str,
        day_number: int,
        message_index: int,
    ) -> Optional[str]:
        """Resolve persisted message id for deterministic response correlation."""
        idempotency_key = self._build_idempotency_key(
            patient_id, flow_kind, day_number, message_index
        )
        try:
            message = self.message_repo.get_by_idempotency_key(patient_id, idempotency_key)
        except Exception:
            logger.exception("Failed to resolve sent message id for flow correlation")
            return None

        message_id = getattr(message, "id", None)
        return str(message_id) if message_id else None

    async def _set_flow_progress(
        self,
        flow_state: PatientFlowState,
        *,
        message_index: int,
        awaiting_response: bool,
        mark_last_sent: bool = False,
        last_response_at: bool = False,
        flow_day: Optional[int] = None,
        flow_kind: Optional[str] = None,
        pending_message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Persist flow progress updates in a single commit."""
        step_data = flow_state.step_data or {}
        step_data["current_day_message_index"] = message_index
        step_data["awaiting_response"] = awaiting_response
        if flow_day is not None:
            step_data["current_flow_day"] = flow_day
        if flow_kind is not None:
            step_data["flow_kind"] = flow_kind

        if awaiting_response:
            step_data["pending_response_context"] = {
                "flow_day": step_data.get("current_flow_day"),
                "flow_kind": step_data.get("flow_kind"),
                "message_index": message_index,
                "prompt_message_id": pending_message_id,
            }
        else:
            step_data.pop("pending_response_context", None)

        if mark_last_sent:
            self._mark_last_message_sent(step_data)
        if last_response_at:
            step_data["last_response_at"] = now_sao_paulo().isoformat()
        flow_state.step_data = step_data
        flow_state.last_interaction_at = now_sao_paulo()
        await self.db.commit()
        return step_data


__all__ = ["StateMixin"]
