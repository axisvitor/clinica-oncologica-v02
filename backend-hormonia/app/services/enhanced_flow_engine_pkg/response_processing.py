from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

import sentry_sdk
from sqlalchemy import select

from app.core.exceptions import FeatureNotAvailableError
from app.exceptions import NotFoundError
from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.models.patient_flow_response import PatientFlowResponse
from app.services.ai.output_profiles import JSON_SENTIMENT
from app.services.flow.context_parsing import parse_optional_int, parse_optional_str
from app.utils.db_retry import with_db_retry
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class FlowResponseMixin:
    """Response-processing behavior for EnhancedFlowEngine."""

    def _normalize_response_context(
        self, response_context: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Normalize inbound response context for downstream correlation."""
        context = dict(response_context or {})
        prompt_message_id = parse_optional_str(context.get("prompt_message_id"))
        response_message_id = parse_optional_str(context.get("response_message_id"))
        normalized_context = {
            "prompt_message_id": prompt_message_id,
            "response_message_id": response_message_id,
            "flow_day": parse_optional_int(
                context.get("flow_day", context.get("current_flow_day"))
            ),
            "flow_kind": parse_optional_str(context.get("flow_kind")),
            "message_index": parse_optional_int(
                context.get(
                    "message_index",
                    context.get("current_message_index", context.get("current_day_message_index")),
                )
            ),
            "awaiting_response": context.get("awaiting_response"),
        }
        for key, value in context.items():
            normalized_context.setdefault(key, value)
        return {key: value for key, value in normalized_context.items() if value is not None}

    def _calculate_engagement_score(
        self, sentiment_analysis: dict[str, Any], response_text: str
    ) -> float:
        """
        Calculate engagement score based on sentiment and response characteristics.

        Score range: 0.0 to 1.0
        Base: 0.5
        """
        score = 0.5

        sentiment = sentiment_analysis.get("sentiment", "neutral")
        if sentiment == "positive":
            score += 0.2
        elif sentiment == "negative":
            score -= 0.1

        length = len(response_text)
        if length > 50:
            score += 0.1
        elif length > 10:
            score += 0.05

        indicators = sentiment_analysis.get("emotional_indicators", [])
        score += min(len(indicators) * 0.05, 0.2)

        return max(0.0, min(1.0, score))

    @with_db_retry(max_retries=3)
    async def process_patient_response(
        self,
        patient_id: UUID,
        response_text: str,
        response_context: dict[str, Any] | None = None,
        use_sync_agents: bool = False,
    ) -> dict[str, Any]:
        """
        Process patient response with AI analysis.

        Args:
            patient_id: Patient UUID
            response_text: Patient's response text

        Returns:
            Response processing result
        """
        try:
            gemini_client: Any = self.gemini_client
            result = await self.db.execute(select(Patient).filter(Patient.id == patient_id))
            patient = result.scalar_one_or_none()
            if not patient:
                raise NotFoundError(f"Patient {patient_id} not found")

            result = await self.db.execute(
                select(PatientFlowState).filter(
                    PatientFlowState.patient_id == patient_id,
                    PatientFlowState.status == "active",
                )
            )
            flow_state = result.scalar_one_or_none()
            if not flow_state:
                logger.warning(
                    f"No active flow for patient {patient_id}, processing response anyway"
                )

            context = self._normalize_response_context(response_context)
            flow_day = context.get("flow_day")
            flow_day = parse_optional_int(flow_day)

            message_index = context.get("message_index")
            message_index = parse_optional_int(message_index)
            flow_kind = context.get("flow_kind")
            if flow_state:
                state_data_snapshot = flow_state.state_data or {}
                if flow_day is None:
                    flow_day = state_data_snapshot.get("current_flow_day")
                if message_index is None:
                    message_index = state_data_snapshot.get("current_day_message_index")
                if flow_kind is None:
                    flow_kind = state_data_snapshot.get("flow_kind")
            if flow_day is not None:
                context["flow_day"] = flow_day
            if message_index is not None:
                context["message_index"] = message_index
            if flow_kind is not None:
                context["flow_kind"] = flow_kind

            patient_context = {
                "name": patient.name,
                "treatment_type": getattr(patient, "treatment_type", "hormone_therapy"),
                "current_day": flow_day or await self.calculate_patient_day(patient_id),
            }

            sentiment_analysis: dict[str, Any] | None = None
            sentiment_analyzer: Any = getattr(gemini_client, "analyze_response_sentiment", None)
            if callable(sentiment_analyzer):
                try:
                    if use_sync_agents:
                        sync_sentiment_analyzer: Any = getattr(
                            gemini_client, "analyze_response_sentiment_sync", None
                        )
                        if not callable(sync_sentiment_analyzer):
                            raise FeatureNotAvailableError(
                                "sync sentiment method unavailable",
                                "sentiment",
                                "process_patient_response",
                            )
                        sentiment_analysis = await asyncio.to_thread(
                            sync_sentiment_analyzer,
                            response_text,
                            patient_context,
                        )
                    else:
                        sentiment_result: Any = sentiment_analyzer(response_text, patient_context)
                        if asyncio.iscoroutine(sentiment_result):
                            sentiment_result = await sentiment_result
                        sentiment_analysis = (
                            sentiment_result if isinstance(sentiment_result, dict) else None
                        )
                except TypeError:
                    if use_sync_agents:
                        sync_sentiment_analyzer: Any = getattr(
                            gemini_client, "analyze_response_sentiment_sync", None
                        )
                        if not callable(sync_sentiment_analyzer):
                            raise
                        sentiment_analysis = await asyncio.to_thread(
                            sync_sentiment_analyzer,
                            response_text,
                            {},
                        )
                    else:
                        sentiment_result: Any = sentiment_analyzer(response_text)
                        if asyncio.iscoroutine(sentiment_result):
                            sentiment_result = await sentiment_result
                        sentiment_analysis = (
                            sentiment_result if isinstance(sentiment_result, dict) else None
                        )
                except Exception:
                    logger.warning(
                        "Gemini sentiment analysis failed; falling back to LangGraph node",
                        exc_info=True,
                    )

            if not isinstance(sentiment_analysis, dict):
                from app.ai.agents.helpers import _parse_sentiment_analysis, build_sentiment_prompt
                from app.ai.context_compactor import compact_patient_context

                try:
                    context_snapshot = compact_patient_context(patient_context)
                    sentiment_prompt = build_sentiment_prompt(
                        response=response_text,
                        context_snapshot=context_snapshot,
                    )
                    analysis_text = await self.gemini_client.generate_content(
                        sentiment_prompt,
                        profile=JSON_SENTIMENT,
                    )
                    if not analysis_text:
                        raise FeatureNotAvailableError(
                            "sentiment analysis returned no output",
                            "sentiment",
                            "analyze_flow_sentiment",
                        )
                    sentiment_analysis = _parse_sentiment_analysis(analysis_text)
                except FeatureNotAvailableError as exc:
                    sentry_sdk.capture_exception(exc)
                    logger.error(
                        "Sentiment analysis failed, using neutral fallback: %s",
                        exc,
                        extra={"feature": "sentiment"},
                    )
                    sentiment_analysis = {"sentiment": "neutral", "confidence": 0.0}

            engagement_score = self._calculate_engagement_score(
                sentiment_analysis, response_text
            )
            await self.conversation_memory.update_last_pattern_engagement(
                patient_id, engagement_score
            )

            await self.conversation_memory.store_message_pattern(patient_id, response_text)

            follow_up_message = None
            if sentiment_analysis.get("requires_attention") or sentiment_analysis.get(
                "medical_concerns"
            ):
                conversation_history = await self._get_conversation_history(patient_id)
                if use_sync_agents:
                    sync_follow_up: Any = getattr(
                        gemini_client, "create_empathetic_follow_up_sync", None
                    )
                    if not callable(sync_follow_up):
                        raise FeatureNotAvailableError(
                            "sync empathy method unavailable",
                            "empathy",
                            "process_patient_response",
                        )
                    follow_up_message = await asyncio.to_thread(
                        sync_follow_up,
                        response_text,
                        conversation_history,
                        patient_context,
                    )
                else:
                    async_follow_up: Any = getattr(
                        gemini_client, "create_empathetic_follow_up", None
                    )
                    if not callable(async_follow_up):
                        raise FeatureNotAvailableError(
                            "async empathy method unavailable",
                            "empathy",
                            "process_patient_response",
                        )
                    follow_up_result = async_follow_up(
                        response_text, conversation_history, patient_context
                    )
                    if asyncio.iscoroutine(follow_up_result):
                        follow_up_result = await follow_up_result
                    follow_up_message = (
                        follow_up_result if isinstance(follow_up_result, str) else None
                    )

            commit_needed = False
            state_data = {}
            if flow_state:
                state_data = dict(flow_state.state_data or {})
                state_data.setdefault("responses", {})
                state_data.setdefault("step_timestamps", {})
                state_data.setdefault("flags", {})

                current_step = flow_state.current_step
                if current_step is None or current_step == 0:
                    current_step = state_data.get("current_step") or flow_day
                if current_step:
                    state_data["responses"][f"step_{current_step}"] = response_text
                    state_data["step_timestamps"][f"step_{current_step}"] = (
                        now_sao_paulo().isoformat()
                    )

                if flow_day is not None:
                    response_key = (
                        f"day_{flow_day}_msg_{message_index}"
                        if message_index is not None
                        else f"day_{flow_day}"
                    )
                else:
                    response_key = (
                        f"msg_{message_index}" if message_index is not None else "latest"
                    )

                state_data.setdefault("responses_by_message", {})
                state_data["responses_by_message"][response_key] = {
                    "prompt_message_id": context.get("prompt_message_id"),
                    "response_message_id": context.get("response_message_id"),
                    "timestamp": now_sao_paulo().isoformat(),
                    "flow_day": flow_day,
                    "flow_kind": flow_kind,
                    "message_index": message_index,
                    "response_text": response_text,
                    "sentiment": sentiment_analysis,
                }

                state_data["flags"]["needs_attention"] = sentiment_analysis.get(
                    "requires_attention", False
                )
                state_data["flags"]["high_risk"] = bool(
                    sentiment_analysis.get("medical_concerns", [])
                )

                state_data["last_response"] = {
                    "prompt_message_id": context.get("prompt_message_id"),
                    "response_message_id": context.get("response_message_id"),
                    "timestamp": now_sao_paulo().isoformat(),
                    "sentiment": sentiment_analysis,
                    "text_length": len(response_text),
                    "engagement_score": engagement_score,
                }
                flow_state.state_data = state_data
                flow_state.last_interaction_at = now_sao_paulo()
                commit_needed = True

            # Persist structured response to dedicated table (dual-write).
            # Runs even when flow_state is None — flow_state_id is nullable.
            flow_response = PatientFlowResponse(
                flow_state_id=flow_state.id if flow_state else None,
                patient_id=patient_id,
                day_number=flow_day,
                message_index=message_index,
                response_text=response_text,
                responded_at=now_sao_paulo(),
                prompt_message_id=context.get("prompt_message_id"),
                response_message_id=context.get("response_message_id"),
            )
            self.db.add(flow_response)
            commit_needed = True

            reminder_result = None
            try:
                reminder_result = await self._get_reminder_handler().handle_response(
                    patient=patient,
                    response_text=response_text,
                    flow_state=flow_state,
                    state_data=state_data if flow_state else {},
                    response_context=context,
                )
            except Exception as exc:
                logger.warning("Reminder handling failed: %s", exc)

            if reminder_result and reminder_result.follow_up_message:
                deferred = False
                if flow_state and reminder_result.action == "pending":
                    current_step_data = flow_state.step_data or {}
                    if not current_step_data.get("day_complete"):
                        current_step_data = dict(current_step_data)
                        current_step_data.setdefault("deferred_followups", [])
                        dedupe_key = (
                            "reminder",
                            reminder_result.reminder_id,
                            reminder_result.follow_up_message,
                        )
                        exists = False
                        for existing in current_step_data["deferred_followups"]:
                            existing_key = (
                                (existing or {}).get("type"),
                                (existing or {}).get("reminder_id"),
                                (existing or {}).get("message"),
                            )
                            if existing_key == dedupe_key:
                                exists = True
                                break
                        if not exists:
                            current_step_data["deferred_followups"].append(
                                {
                                    "type": "reminder",
                                    "message": reminder_result.follow_up_message,
                                    "reminder_id": reminder_result.reminder_id,
                                    "flow_day": flow_day,
                                    "flow_kind": flow_kind,
                                    "created_at": now_sao_paulo().isoformat(),
                                }
                            )
                        flow_state.step_data = current_step_data
                        commit_needed = True
                        deferred = True

                if not deferred and not follow_up_message:
                    follow_up_message = reminder_result.follow_up_message

            if reminder_result and flow_state:
                flow_state.state_data = state_data
            if reminder_result and reminder_result.commit_needed:
                commit_needed = True

            if commit_needed:
                await self.db.commit()

            return {
                "status": "processed",
                "patient_id": str(patient_id),
                "sentiment_analysis": sentiment_analysis,
                "engagement_score": engagement_score,
                "follow_up_message": follow_up_message,
                "requires_attention": sentiment_analysis.get("requires_attention", False),
                "medical_concerns": sentiment_analysis.get("medical_concerns", []),
            }

        except Exception as e:
            logger.error(f"Failed to process patient response: {e}")
            return {"status": "error", "patient_id": str(patient_id), "error": str(e)}


__all__ = ["FlowResponseMixin"]
