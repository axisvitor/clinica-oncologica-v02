"""
State Management Module - Flow State Operations and Caching

Handles flow state creation, retrieval, caching, and transitions.
Provides centralized state management for the FlowOrchestrator.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.flow import PatientFlowState
from app.models.patient import Patient
from app.repositories.flow import FlowStateRepository


logger = logging.getLogger(__name__)


class FlowStateManager:
    """
    Manages flow state lifecycle including creation, caching, and transitions.

    Responsibilities:
    - Flow state creation and initialization
    - State caching for performance optimization
    - Flow type transitions
    - Cache invalidation management
    """

    def __init__(self, db: Session, flow_state_repo: FlowStateRepository):
        """
        Initialize FlowStateManager.

        Args:
            db: Database session
            flow_state_repo: Flow state repository
        """
        self.db = db
        self.flow_state_repo = flow_state_repo

        # Flow state cache for performance
        self._flow_state_cache: Dict[UUID, PatientFlowState] = {}
        self._cache_ttl = timedelta(minutes=10)
        self._last_cache_clear = datetime.utcnow()

        logger.info("FlowStateManager initialized")

    def get_cached_flow_state(self, patient_id: UUID) -> Optional[PatientFlowState]:
        """
        Get flow state from cache or database.

        Args:
            patient_id: Patient UUID

        Returns:
            PatientFlowState or None if not found
        """
        # Clean expired cache entries
        if datetime.utcnow() - self._last_cache_clear > self._cache_ttl:
            self._flow_state_cache.clear()
            self._last_cache_clear = datetime.utcnow()
            logger.debug("Flow state cache cleared due to TTL expiration")

        # Check cache first
        if patient_id in self._flow_state_cache:
            logger.debug(f"Flow state cache hit for patient {patient_id}")
            return self._flow_state_cache[patient_id]

        # Load from database
        flow_state = self.flow_state_repo.get_active_flow(patient_id)
        if flow_state:
            self._flow_state_cache[patient_id] = flow_state
            logger.debug(
                f"Flow state loaded from DB and cached for patient {patient_id}"
            )

        return flow_state

    def invalidate_flow_cache(self, patient_id: UUID):
        """
        Invalidate cached flow state for patient.

        Args:
            patient_id: Patient UUID
        """
        removed = self._flow_state_cache.pop(patient_id, None)
        if removed:
            logger.debug(f"Flow state cache invalidated for patient {patient_id}")

    def create_flow_state(
        self,
        patient: Patient,
        flow_type: str,
        current_day: int,
        operation: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> PatientFlowState:
        """
        Create new flow state for patient.

        Args:
            patient: Patient object
            flow_type: Flow type identifier
            current_day: Current treatment day
            operation: Operation type that triggered creation
            metadata: Additional metadata

        Returns:
            Created PatientFlowState
        """
        flow_state = PatientFlowState(
            patient_id=patient.id,
            flow_type=flow_type,
            current_step=current_day,
            started_at=datetime.utcnow(),
            state_data={
                "status": "active",
                "created_by": "flow_orchestrator",
                "operation": operation,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat(),
            },
        )

        self.db.add(flow_state)
        self.db.commit()
        self.db.refresh(flow_state)

        # Cache the new flow state
        self._flow_state_cache[patient.id] = flow_state

        logger.info(
            f"Created flow state {flow_state.id} for patient {patient.id} (type: {flow_type})"
        )
        return flow_state

    async def transition_flow_type(
        self,
        flow_state: PatientFlowState,
        new_flow_type: str,
        patient_id: UUID,
        current_day: int,
        analytics_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Transition flow to new type.

        Args:
            flow_state: Current flow state
            new_flow_type: New flow type to transition to
            patient_id: Patient UUID
            current_day: Current treatment day
            analytics_callback: Optional callback for tracking

        Returns:
            Transition result dictionary
        """
        try:
            old_flow_type = flow_state.flow_type

            # Update flow state
            flow_state.flow_type = new_flow_type
            flow_state.state_data = flow_state.state_data or {}
            flow_state.state_data.update(
                {
                    "transitioned_from": old_flow_type,
                    "transitioned_to": new_flow_type,
                    "transition_date": datetime.utcnow().isoformat(),
                    "status": "active",
                }
            )

            self.db.commit()
            self.invalidate_flow_cache(patient_id)

            # Track transition if callback provided
            if analytics_callback:
                await analytics_callback(
                    patient_id=patient_id,
                    event_type="flow_type_transition",
                    flow_type=new_flow_type,
                    current_day=current_day,
                    metadata={
                        "from_flow_type": old_flow_type,
                        "to_flow_type": new_flow_type,
                    },
                )

            logger.info(
                f"Flow transitioned from {old_flow_type} to {new_flow_type} for patient {patient_id}"
            )

            return {
                "success": True,
                "from_flow_type": old_flow_type,
                "to_flow_type": new_flow_type,
            }

        except Exception as e:
            logger.error(f"Error transitioning flow type: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def update_flow_state_status(
        self,
        flow_state: PatientFlowState,
        status: str,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update flow state status.

        Args:
            flow_state: Flow state to update
            status: New status
            reason: Reason for status change
            metadata: Additional metadata

        Returns:
            True if successful
        """
        try:
            flow_state.state_data = flow_state.state_data or {}
            flow_state.state_data.update(
                {
                    "status": status,
                    f"{status}_at": datetime.utcnow().isoformat(),
                    f"{status}_reason": reason,
                    f"{status}_metadata": metadata or {},
                }
            )

            self.db.commit()
            self.invalidate_flow_cache(flow_state.patient_id)

            logger.info(
                f"Flow state updated to {status} for patient {flow_state.patient_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error updating flow state status: {e}", exc_info=True)
            self.db.rollback()
            return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "flow_state_cache_size": len(self._flow_state_cache),
            "cache_ttl_minutes": self._cache_ttl.total_seconds() / 60,
            "last_cache_clear": self._last_cache_clear.isoformat(),
        }
