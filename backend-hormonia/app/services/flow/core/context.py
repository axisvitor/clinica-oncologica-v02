"""
Context storage helpers for Flow Services (QW-021).

The consolidated architecture keeps FlowContext persistence behind a
repository abstraction so we can toggle between in-memory storage and
the production database without changing orchestration code.
"""

from __future__ import annotations

# Standard library imports
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

# Third-party imports
from pydantic import ValidationError

# Local application imports
from app.repositories.flow import FlowStateRepository
from ..types import FlowContext, FlowStatus, FlowType

logger = logging.getLogger(__name__)


@dataclass
class ContextPersistenceResult:
    """
    Outcome of a save/delete operation.

    Attributes:
        persisted: Whether the operation succeeded.
        reason: Optional reason for failure.
    """

    persisted: bool
    reason: Optional[str] = None


class FlowContextRepository:
    """
    Repository responsible for loading and storing FlowContext objects.

    Persists data to patient_flow_states while keeping an in-memory cache
    for quick lookups inside the FlowManager lifecycle.

    Attributes:
        _memory_store: In-memory cache of flow contexts.
        _db_repo: Database repository for persistence.
    """

    def __init__(self, db: Any):
        """
        Initialize the flow context repository.

        Args:
            db: Database session for persistence.
        """
        self._memory_store: Dict[UUID, FlowContext] = {}
        self._db_repo = FlowStateRepository(db)

    async def get(self, flow_id: UUID) -> Optional[FlowContext]:
        """
        Return context from cache or database.

        Args:
            flow_id: Flow instance UUID.

        Returns:
            Flow context or None if not found.
        """
        cached = self._memory_store.get(flow_id)
        if cached:
            return cached

        db_context = await self._load_from_db(flow_id)
        if db_context:
            self._memory_store[flow_id] = db_context
        return db_context

    async def save(
        self,
        context: FlowContext,
        template: Optional[Dict[str, Any]] = None,
    ) -> ContextPersistenceResult:
        """
        Persist/refresh the FlowContext.

        Args:
            context: Flow execution context to persist.
            template: Optional template metadata (used to resolve version IDs).

        Returns:
            Result of persistence operation.
        """
        self._memory_store[context.flow_instance_id] = context

        persisted, reason = await self._persist_to_db(context, template)
        return ContextPersistenceResult(persisted=persisted, reason=reason)

    async def delete(self, flow_id: UUID) -> ContextPersistenceResult:
        """
        Remove context from storage.

        Args:
            flow_id: Flow instance UUID.

        Returns:
            Result of deletion operation.
        """
        self._memory_store.pop(flow_id, None)

        deleted = self._db_repo.delete(flow_id)
        return ContextPersistenceResult(deleted, None if deleted else "not-found")

    async def _load_from_db(self, flow_id: UUID) -> Optional[FlowContext]:
        """
        Load context from the database if we have matching metadata.

        Args:
            flow_id: Flow instance UUID.

        Returns:
            Flow context or None if not found.
        """
        state = self._db_repo.get(flow_id)
        if not state:
            return None

        if state.flow_metadata:
            try:
                data = dict(state.flow_metadata)
                data.setdefault("flow_instance_id", state.id)
                data.setdefault("patient_id", state.patient_id)
                if isinstance(data.get("flow_type"), str):
                    data["flow_type"] = self._coerce_flow_type(data["flow_type"])
                return FlowContext(**data)
            except ValidationError as exc:
                logger.warning(
                    "Failed to hydrate FlowContext from flow_metadata for %s: %s",
                    flow_id,
                    exc,
                )

        return self._build_context_from_state(state)

    def _build_context_from_state(self, state) -> FlowContext:
        """
        Create a FlowContext from PatientFlowState columns.

        Args:
            state: PatientFlowState database record.

        Returns:
            Reconstructed FlowContext.
        """
        flow_type_value = (
            state.template_version.kind.flow_type
            if state.template_version and state.template_version.kind
            else None
        )
        flow_type = self._coerce_flow_type(flow_type_value or FlowType.CUSTOM.value)
        status = self._coerce_status(state.status)

        metadata = {
            "template_version_id": str(state.template_version_id)
            if state.template_version_id
            else None
        }

        context = FlowContext(
            flow_instance_id=state.id,
            flow_type=flow_type,
            patient_id=state.patient_id,
            current_step_id=str(state.current_step) if state.current_step else None,
            status=status,
            flow_data=state.state_data or {},
            variables={},
            steps_completed=[],
            steps_history=[],
            started_at=state.started_at,
            completed_at=state.completed_at,
            metadata=metadata,
        )
        return context

    async def _persist_to_db(
        self,
        context: FlowContext,
        template: Optional[Dict[str, Any]],
    ) -> Tuple[bool, Optional[str]]:
        """
        Persist context into patient_flow_states if possible.

        Args:
            context: Flow execution context.
            template: Optional template metadata.

        Returns:
            Tuple of (success, failure_reason).
        """
        template_version_id = None
        if template:
            template_version_id = template.get("metadata", {}).get(
                "template_version_id"
            ) or template.get("template_version_id")
        if not template_version_id:
            template_version_id = context.metadata.get("template_version_id")

        if not template_version_id:
            # Without a backing template version we only keep the in-memory cache.
            logger.debug(
                "Skipping DB persistence for flow %s (missing template_version_id)",
                context.flow_instance_id,
            )
            return False, "missing-template-version"

        payload = {
            "patient_id": context.patient_id,
            "template_version_id": UUID(template_version_id)
            if not isinstance(template_version_id, UUID)
            else template_version_id,
            "current_step": self._resolve_step_index(template, context),
            "status": context.status.value,
            "state_data": context.flow_data or {},
            "flow_metadata": context.model_dump(mode="json"),
            "started_at": context.started_at,
            "completed_at": context.completed_at,
            "updated_at": datetime.now(timezone.utc),
        }

        existing = self._db_repo.get(context.flow_instance_id)
        if existing:
            self._db_repo.update(existing, payload)
        else:
            payload["id"] = context.flow_instance_id
            payload.setdefault("started_at", datetime.now(timezone.utc))
            self._db_repo.create(payload)

        return True, None

    def _resolve_step_index(
        self,
        template: Optional[Dict[str, Any]],
        context: FlowContext,
    ) -> Optional[int]:
        """
        Best-effort step index calculation for persisting current_step.

        Args:
            template: Flow template.
            context: Flow execution context.

        Returns:
            Step index or None if not found.
        """
        if not template or not template.get("steps") or not context.current_step_id:
            return None

        steps = template.get("steps", [])
        for index, step in enumerate(steps):
            if step.get("step_id") == context.current_step_id:
                return index
        return None

    def _coerce_flow_type(self, value: str) -> FlowType:
        try:
            return FlowType(value)
        except ValueError:
            return FlowType.CUSTOM

    def _coerce_status(self, value: Optional[str]) -> FlowStatus:
        if not value:
            return FlowStatus.ACTIVE
        try:
            return FlowStatus(value)
        except ValueError:
            return FlowStatus.ACTIVE


__all__ = ["FlowContextRepository", "ContextPersistenceResult"]
