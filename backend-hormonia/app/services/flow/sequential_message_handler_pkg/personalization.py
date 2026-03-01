import asyncio
import difflib
import hashlib
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.models.patient import Patient
from app.services.template_loader_pkg import MessageTemplate as FlowMessageTemplate

if TYPE_CHECKING:
    from app.services.enhanced_flow_engine import EnhancedFlowEngine

logger = logging.getLogger(__name__)


class PersonalizationMixin:
    def _get_ai_engine(self) -> "EnhancedFlowEngine":
        """Lazy initialization of AI engine."""
        if self._enhanced_flow_engine is None:
            from app.services.enhanced_flow_engine import EnhancedFlowEngine

            self._enhanced_flow_engine = EnhancedFlowEngine(self.db)
        return self._enhanced_flow_engine

    def _normalize_text(self, text: str) -> str:
        """Normalize text for similarity checks (lowercase, collapse spaces)."""
        normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
        return normalized

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful tokens from base content to validate AI grounding."""
        cleaned = re.sub(r"\[[^\]]+\]|\{[^}]+\}", " ", text or "")
        tokens = re.findall(r"[a-zA-ZÀ-ÿ]+", cleaned.lower())
        return [t for t in tokens if len(t) >= 4]

    def _personalization_is_grounded(self, base_content: str, personalized: str) -> bool:
        """Check if AI output stays anchored to the base template."""
        base_norm = self._normalize_text(base_content)
        personalized_norm = self._normalize_text(personalized)
        if not base_norm or not personalized_norm:
            return False

        similarity = difflib.SequenceMatcher(None, base_norm, personalized_norm).ratio()
        base_keywords = set(self._extract_keywords(base_content))
        if not base_keywords:
            return similarity >= 0.35

        personalized_tokens = set(self._extract_keywords(personalized))
        overlap_ratio = len(base_keywords & personalized_tokens) / max(len(base_keywords), 1)

        return overlap_ratio >= 0.2 or similarity >= 0.6

    async def _personalize_message_ai(
        self,
        message: Dict[str, Any],
        patient: Patient,
        day_number: int,
        flow_kind: str,
        day_config: Optional[Dict] = None,
        message_index: Optional[int] = None,
    ) -> str:
        """
        Personalize message using AI (EnhancedFlowEngine).
        Falls back to simple/template personalization when AI fails.
        """
        content = message.get("content", "") if isinstance(message, dict) else ""
        expects_response = (
            message.get("expects_response") if isinstance(message, dict) else None
        )
        fallback_content = self._build_fallback_content(
            message=message,
            patient=patient,
            content=content,
            flow_kind=flow_kind,
            day_number=day_number,
            message_index=message_index,
            expects_response=expects_response,
        )
        if not self.use_ai_personalization:
            return fallback_content
        if expects_response is False:
            return fallback_content

        try:
            engine = self._get_ai_engine()
            intent = (
                (message or {}).get("intent")
                or (day_config or {}).get("intent")
                or f"day_{day_number}_message"
            )
            personalization_hints = (
                (message or {}).get("personalization_hints")
                or (day_config or {}).get("personalization_hints")
                or ["patient_name"]
            )
            ai_instructions = (message or {}).get("ai_instructions") or (
                day_config or {}
            ).get("ai_instructions")
            variations = (message or {}).get("variations") or []

            template = FlowMessageTemplate(
                day=day_number,
                intent=intent,
                base_content=content,
                personalization_hints=personalization_hints,
                ai_instructions=ai_instructions,
                variations=variations,
            )

            personalized = await engine.generate_flow_message(
                patient_id=patient.id,
                day=day_number,
                message_template=template,
                strict=True,
                use_sync_agents=self.use_sync_agent_bridge,
            )
            if not personalized:
                logger.warning(
                    "AI personalization returned empty content, using fallback",
                    extra={
                        "patient_id": str(patient.id),
                        "day": day_number,
                        "flow_kind": flow_kind,
                    },
                )
                return fallback_content

            if not self._personalization_is_grounded(content, personalized):
                logger.warning(
                    "AI personalization not grounded to base template, using fallback",
                    extra={
                        "patient_id": str(patient.id),
                        "day": day_number,
                        "flow_kind": flow_kind,
                    },
                )
                return fallback_content

            logger.debug("AI personalized message for patient %s", patient.id)
            return personalized
        except asyncio.TimeoutError:
            logger.exception(
                "AI personalization timed out, using fallback",
                extra={
                    "patient_id": str(patient.id),
                    "day": day_number,
                    "flow_kind": flow_kind,
                },
            )
            return fallback_content
        except (ValueError, RuntimeError):
            logger.exception(
                "AI personalization failed, using fallback",
                extra={
                    "patient_id": str(patient.id),
                    "day": day_number,
                    "flow_kind": flow_kind,
                },
            )
            return fallback_content
        except Exception:
            logger.exception(
                "Unexpected AI personalization failure, using fallback",
                extra={
                    "patient_id": str(patient.id),
                    "day": day_number,
                    "flow_kind": flow_kind,
                },
            )
            return fallback_content

    def _build_fallback_content(
        self,
        *,
        message: Dict[str, Any],
        patient: Patient,
        content: str,
        flow_kind: str,
        day_number: int,
        message_index: Optional[int],
        expects_response: Optional[bool],
    ) -> str:
        """
        Build deterministic fallback content with light anti-repetition.

        Priority:
        1) Template-provided variations (if present)
        2) Placeholder substitution
        3) Lightweight question reformulation for response-expected prompts
        """
        candidate = self._select_template_variation(
            message=message,
            content=content,
            patient=patient,
            flow_kind=flow_kind,
            day_number=day_number,
            message_index=message_index,
        )
        personalized = self._personalize_message_simple(candidate, patient)
        if expects_response is False:
            return personalized
        return self._lightly_rephrase_question(
            personalized,
            day_number=day_number,
            message_index=message_index,
        )

    def _select_template_variation(
        self,
        *,
        message: Dict[str, Any],
        content: str,
        patient: Patient,
        flow_kind: str,
        day_number: int,
        message_index: Optional[int],
    ) -> str:
        """Pick a deterministic variation when templates provide alternatives."""
        variations = message.get("variations") if isinstance(message, dict) else None
        if not isinstance(variations, list):
            return content

        normalized_base = self._normalize_text(content)
        candidates: List[str] = []
        for raw in variations:
            if not isinstance(raw, str):
                continue
            candidate = raw.strip()
            if not candidate:
                continue
            if self._normalize_text(candidate) == normalized_base:
                continue
            if candidate in candidates:
                continue
            candidates.append(candidate)

        if not candidates:
            return content

        seed = (
            f"{patient.id}:{flow_kind}:{day_number}:"
            f"{message_index if message_index is not None else 0}"
        )
        selected_index = (
            int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(candidates)
        )
        return candidates[selected_index]

    def _lightly_rephrase_question(
        self,
        content: str,
        *,
        day_number: int,
        message_index: Optional[int],
    ) -> str:
        """Apply a subtle wrapper to reduce repetitive question phrasing."""
        question = (content or "").strip()
        if not question or "?" not in question:
            return content

        normalized = self._normalize_text(question)
        existing_prefixes = (
            "queria te perguntar:",
            "só para confirmar com você:",
            "para acompanharmos melhor:",
        )
        if normalized.startswith(existing_prefixes):
            return content

        wrappers = (
            "Queria te perguntar:",
            "Só para confirmar com você:",
            "Para acompanharmos melhor:",
        )
        offset = day_number + (message_index if isinstance(message_index, int) else 0)
        prefix = wrappers[offset % len(wrappers)]
        return f"{prefix} {question}"

    def _personalize_message_simple(self, content: str, patient: Patient) -> str:
        """Simple placeholder replacement (fallback)."""
        name = patient.name or patient.preferred_name or "Paciente"

        content = content.replace("[NOME]", name)
        content = content.replace("[nome]", name)
        content = content.replace("{patient_name}", name)

        return content


__all__ = ["PersonalizationMixin"]
