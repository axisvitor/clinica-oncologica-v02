import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select, text

from app.models.flow import PatientFlowOverride, PatientFlowState
from app.services.flow.sequential_message_handler_pkg.delivery import (
    build_flow_idempotency_key,
)
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class StateMixin:
    async def _get_day_config(self, flow_kind: str, day: int, patient_flow_state_id: Optional[UUID] = None) -> Optional[Dict]:
        """
        Get the configuration for a specific day in a flow.

        When *patient_flow_state_id* is supplied the method first checks for
        per-patient overrides (Redis cache → DB fallback) before consulting the
        global template.  Override with ``skip=True`` returns ``None`` so the
        caller's existing skip-handling fires.

        Uses Redis cache to reduce database load with multiple patients.
        Cache TTL: 1 hour (templates rarely change)
        """
        import json

        from app.core.redis_manager import get_sync_redis_client

        # ------------------------------------------------------------------
        # Per-patient override lookup (early return when override exists)
        # ------------------------------------------------------------------
        if patient_flow_state_id is not None:
            override_cache_key = f"flow_override:{patient_flow_state_id}:days"
            overrides_dict: Optional[Dict] = None

            try:
                redis_client = get_sync_redis_client()
                if redis_client:
                    cached_overrides = redis_client.get(override_cache_key)
                    if cached_overrides is not None:
                        logger.debug("Override cache hit for flow_state %s", patient_flow_state_id)
                        overrides_dict = json.loads(cached_overrides)
            except Exception as exc:
                logger.warning("Redis override cache error (falling back to DB): %s", exc)

            if overrides_dict is None:
                logger.debug("Override cache miss for flow_state %s, querying DB", patient_flow_state_id)
                try:
                    result_proxy = await self.db.execute(
                        select(PatientFlowOverride).filter(
                            PatientFlowOverride.patient_flow_state_id == patient_flow_state_id
                        )
                    )
                    rows = result_proxy.scalars().all()
                    overrides_dict = {}
                    for row in rows:
                        overrides_dict[str(row.day_number)] = {
                            "content": row.content,
                            "message_type": row.message_type,
                            "expects_response": row.expects_response,
                            "skip": row.skip,
                        }
                except Exception as exc:
                    logger.warning("Failed to query patient overrides (falling back to global): %s", exc)
                    overrides_dict = None

                if overrides_dict is not None:
                    try:
                        redis_client = get_sync_redis_client()
                        if redis_client:
                            redis_client.setex(
                                override_cache_key,
                                3600,
                                json.dumps(overrides_dict, ensure_ascii=False),
                            )
                    except Exception as exc:
                        logger.warning("Failed to cache patient overrides: %s", exc)

            if overrides_dict is not None:
                day_key = str(day)
                override = overrides_dict.get(day_key)
                if override is not None:
                    if override.get("skip"):
                        logger.info(
                            "Day %s skipped by patient override for flow_state %s",
                            day,
                            patient_flow_state_id,
                        )
                        return None
                    return {
                        "day": day,
                        "send_mode": "single",
                        "messages": [
                            {
                                "content": override["content"],
                                "message_type": override.get("message_type", "question"),
                                "expects_response": override.get("expects_response", False),
                            }
                        ],
                    }
                # No override for this specific day — fall through to global template

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
        idempotency_key = build_flow_idempotency_key(
            patient_id=patient_id,
            flow_kind=flow_kind,
            day_number=day_number,
            message_index=message_index,
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
