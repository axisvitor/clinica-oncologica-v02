"""
State-aware orchestrator mixin for state management and transitions.

This module consolidates duplicate state management patterns (state persistence,
caching, transitions) found across FlowOrchestrator and SagaOrchestrator.

Provides:
- State persistence to database and cache
- State transition validation
- Cache management and invalidation
- State history tracking
"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID
from abc import abstractmethod


logger = logging.getLogger(__name__)


class StateAwareOrchestrator:
    """
    Mixin providing state management capabilities.

    This mixin must be used with BaseOrchestrator to access database session
    and logging. It consolidates state caching from FlowOrchestrator and
    state persistence from SagaOrchestrator.

    Must be used with BaseOrchestrator:
        >>> class MyOrchestrator(BaseOrchestrator, StateAwareOrchestrator):
        ...     def __init__(self, db):
        ...         super().__init__(db, state_cache_enabled=True)
        ...
        ...     async def _persist_to_db(self, entity_id, state_data):
        ...         # Implement database persistence
        ...         pass
        ...
        ...     async def _fetch_from_db(self, entity_id):
        ...         # Implement database fetch
        ...         pass

    Provides:
    1. State persistence (database + cache)
    2. State transition validation
    3. State history tracking
    4. Cache invalidation

    Example:
        >>> # Persist state
        >>> await orchestrator.persist_state(entity_id, {
        ...     "status": "active",
        ...     "current_step": 5,
        ...     "metadata": {"key": "value"}
        ... })
        >>>
        >>> # Retrieve state
        >>> state = await orchestrator.get_state(entity_id)
        >>>
        >>> # Transition state
        >>> success = await orchestrator.transition_state(
        ...     entity_id,
        ...     from_status="pending",
        ...     to_status="active"
        ... )

    Attributes:
        state_cache_enabled (bool): Whether state caching is enabled
        _state_cache (Dict[UUID, Any]): In-memory state cache
    """

    def __init__(self, *args, state_cache_enabled: bool = True, **kwargs):
        """
        Initialize state management features.

        Args:
            state_cache_enabled: Enable in-memory state caching (default: True)
        """
        super().__init__(*args, **kwargs)
        self.state_cache_enabled = state_cache_enabled
        self._state_cache: Dict[UUID, Any] = {}

    # ===============================
    # State Persistence
    # ===============================

    async def persist_state(
        self,
        entity_id: UUID,
        state_data: Dict[str, Any],
        cache: bool = True,
    ) -> bool:
        """
        Persist state to database and optionally cache.

        Args:
            entity_id: Entity UUID
            state_data: State data to persist
            cache: Cache the state in memory (default: True)

        Returns:
            True if successful, False otherwise

        Example:
            >>> success = await orchestrator.persist_state(
            ...     patient_id,
            ...     {"status": "active", "step": 3}
            ... )
        """
        try:
            # Persist to database (implement in subclass)
            await self._persist_to_db(entity_id, state_data)

            # Cache persistence
            if cache and self.state_cache_enabled:
                self._state_cache[entity_id] = state_data

            self.log_info(
                f"State persisted for {entity_id}",
                extra={
                    "entity_id": str(entity_id),
                    "cached": cache and self.state_cache_enabled,
                    "state_keys": list(state_data.keys()),
                },
            )

            return True

        except Exception as e:
            self.log_error(f"State persistence failed for {entity_id}", e)
            return False

    async def get_state(
        self,
        entity_id: UUID,
        from_cache: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Get state from cache or database.

        Args:
            entity_id: Entity UUID
            from_cache: Try cache first (default: True)

        Returns:
            State data dictionary or None if not found

        Example:
            >>> state = await orchestrator.get_state(patient_id)
            >>> if state:
            ...     print(f"Status: {state['status']}")
        """
        # Try cache first
        if from_cache and self.state_cache_enabled:
            cached = self._state_cache.get(entity_id)
            if cached:
                self.log_info(
                    f"State retrieved from cache for {entity_id}",
                    extra={"entity_id": str(entity_id), "source": "cache"},
                )
                return cached

        # Fetch from database
        try:
            state = await self._fetch_from_db(entity_id)

            # Update cache if found
            if state and self.state_cache_enabled:
                self._state_cache[entity_id] = state

            self.log_info(
                f"State retrieved from database for {entity_id}",
                extra={
                    "entity_id": str(entity_id),
                    "source": "database",
                    "found": state is not None,
                },
            )

            return state

        except Exception as e:
            self.log_error(f"State fetch failed for {entity_id}", e)
            return None

    # ===============================
    # State Transitions
    # ===============================

    async def transition_state(
        self,
        entity_id: UUID,
        from_status: str,
        to_status: str,
        validate: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Transition entity state with optional validation.

        Args:
            entity_id: Entity UUID
            from_status: Current status
            to_status: Target status
            validate: Validate transition (default: True)
            metadata: Additional metadata for transition

        Returns:
            True if successful, False otherwise

        Example:
            >>> success = await orchestrator.transition_state(
            ...     flow_id,
            ...     from_status="pending",
            ...     to_status="active",
            ...     metadata={"started_by": "system"}
            ... )
        """
        # Validate transition if requested
        if validate:
            is_valid, error = self.validate_transition(from_status, to_status)
            if not is_valid:
                self.log_warning(
                    f"Invalid transition: {from_status} → {to_status}",
                    extra={
                        "entity_id": str(entity_id),
                        "from_status": from_status,
                        "to_status": to_status,
                        "error": error,
                    },
                )
                return False

        # Get current state
        state = await self.get_state(entity_id)
        if not state:
            self.log_warning(
                f"State not found for transition: {entity_id}",
                extra={"entity_id": str(entity_id)},
            )
            return False

        # Update state
        state["status"] = to_status
        state["previous_status"] = from_status
        if metadata:
            state.setdefault("metadata", {}).update(metadata)

        # Persist updated state
        success = await self.persist_state(entity_id, state)

        if success:
            self.log_info(
                f"State transitioned: {from_status} → {to_status}",
                extra={
                    "entity_id": str(entity_id),
                    "from_status": from_status,
                    "to_status": to_status,
                },
            )

        return success

    def validate_transition(
        self, from_status: str, to_status: str
    ) -> tuple[bool, Optional[str]]:
        """
        Validate state transition (override in subclass for custom logic).

        Default implementation allows all transitions. Subclasses should
        override this to implement specific business rules.

        Args:
            from_status: Current status
            to_status: Target status

        Returns:
            Tuple of (is_valid, error_message)
                - is_valid: True if transition is allowed
                - error_message: None if valid, error description if invalid

        Example:
            >>> # In subclass:
            >>> def validate_transition(self, from_status, to_status):
            ...     allowed = {
            ...         "pending": ["active", "cancelled"],
            ...         "active": ["paused", "completed"],
            ...         "paused": ["active", "cancelled"]
            ...     }
            ...     if to_status not in allowed.get(from_status, []):
            ...         return False, f"Invalid transition: {from_status} → {to_status}"
            ...     return True, None
        """
        # Default: allow all transitions
        return True, None

    # ===============================
    # Cache Management
    # ===============================

    def invalidate_cache(self, entity_id: Optional[UUID] = None):
        """
        Invalidate state cache for entity or all entities.

        Args:
            entity_id: Entity UUID to invalidate (None = invalidate all)

        Example:
            >>> # Invalidate specific entity
            >>> orchestrator.invalidate_cache(patient_id)
            >>>
            >>> # Invalidate all cache
            >>> orchestrator.invalidate_cache()
        """
        if entity_id:
            removed = self._state_cache.pop(entity_id, None)
            if removed:
                self.log_info(
                    f"Cache invalidated for {entity_id}",
                    extra={"entity_id": str(entity_id)},
                )
        else:
            count = len(self._state_cache)
            self._state_cache.clear()
            self.log_info(f"All cache invalidated ({count} entries)")

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Cache stats dictionary with size and hit metrics

        Example:
            >>> stats = orchestrator.get_cache_stats()
            >>> print(f"Cache size: {stats['size']}")
        """
        return {
            "enabled": self.state_cache_enabled,
            "size": len(self._state_cache),
            "entities": [str(entity_id) for entity_id in self._state_cache.keys()],
        }

    # ===============================
    # Abstract Methods (Must Implement)
    # ===============================

    @abstractmethod
    async def _persist_to_db(self, entity_id: UUID, state_data: Dict[str, Any]):
        """
        Persist state to database (implement in subclass).

        Args:
            entity_id: Entity UUID
            state_data: State data to persist

        Raises:
            NotImplementedError: If not implemented in subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _persist_to_db() method"
        )

    @abstractmethod
    async def _fetch_from_db(self, entity_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Fetch state from database (implement in subclass).

        Args:
            entity_id: Entity UUID

        Returns:
            State data dictionary or None if not found

        Raises:
            NotImplementedError: If not implemented in subclass
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _fetch_from_db() method"
        )
