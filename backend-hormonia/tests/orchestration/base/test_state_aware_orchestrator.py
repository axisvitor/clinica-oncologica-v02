"""
Tests for StateAwareOrchestrator.

Tests state persistence, transitions, and cache management.
Target: 90%+ code coverage.
"""

import pytest
from typing import Dict, Any, Optional
from uuid import uuid4, UUID
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from app.orchestration.base.base_orchestrator import BaseOrchestrator
from app.orchestration.base.state_aware_orchestrator import StateAwareOrchestrator


# ===============================
# Test Implementation
# ===============================


class TestStateAwareOrchestrator(BaseOrchestrator, StateAwareOrchestrator):
    """Concrete implementation for testing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._db_storage: Dict[UUID, Dict[str, Any]] = {}

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute test logic."""
        return {"success": True}

    def validate(self, context: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate test context."""
        return True, None

    async def _persist_to_db(self, entity_id: UUID, state_data: Dict[str, Any]):
        """Mock database persistence."""
        self._db_storage[entity_id] = state_data.copy()

    async def _fetch_from_db(self, entity_id: UUID) -> Optional[Dict[str, Any]]:
        """Mock database fetch."""
        return self._db_storage.get(entity_id)


# ===============================
# Fixtures
# ===============================


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    db.execute = Mock(return_value=None)
    return db


@pytest.fixture
def orchestrator(mock_db):
    """Create state-aware orchestrator instance."""
    return TestStateAwareOrchestrator(db=mock_db)


@pytest.fixture
def entity_id():
    """Generate test entity ID."""
    return uuid4()


# ===============================
# Initialization Tests
# ===============================


def test_state_aware_initialization_defaults(mock_db):
    """Test state-aware orchestrator initialization with defaults."""
    orchestrator = TestStateAwareOrchestrator(db=mock_db)

    assert orchestrator.state_cache_enabled is True
    assert isinstance(orchestrator._state_cache, dict)
    assert len(orchestrator._state_cache) == 0


def test_state_aware_initialization_cache_disabled(mock_db):
    """Test initialization with cache disabled."""
    orchestrator = TestStateAwareOrchestrator(
        db=mock_db,
        state_cache_enabled=False
    )

    assert orchestrator.state_cache_enabled is False


# ===============================
# State Persistence Tests
# ===============================


@pytest.mark.asyncio
async def test_persist_state_success(orchestrator, entity_id):
    """Test successful state persistence."""
    state_data = {
        "status": "active",
        "step": 5,
        "metadata": {"key": "value"}
    }

    success = await orchestrator.persist_state(entity_id, state_data)

    assert success is True
    # Verify database storage
    assert entity_id in orchestrator._db_storage
    assert orchestrator._db_storage[entity_id] == state_data


@pytest.mark.asyncio
async def test_persist_state_with_cache(orchestrator, entity_id):
    """Test state persistence updates cache."""
    state_data = {"status": "active"}

    await orchestrator.persist_state(entity_id, state_data, cache=True)

    # Verify cache updated
    assert entity_id in orchestrator._state_cache
    assert orchestrator._state_cache[entity_id] == state_data


@pytest.mark.asyncio
async def test_persist_state_without_cache(orchestrator, entity_id):
    """Test state persistence without caching."""
    state_data = {"status": "active"}

    await orchestrator.persist_state(entity_id, state_data, cache=False)

    # Verify not in cache
    assert entity_id not in orchestrator._state_cache
    # But in database
    assert entity_id in orchestrator._db_storage


@pytest.mark.asyncio
async def test_persist_state_cache_disabled(mock_db, entity_id):
    """Test state persistence when cache is globally disabled."""
    orchestrator = TestStateAwareOrchestrator(
        db=mock_db,
        state_cache_enabled=False
    )

    state_data = {"status": "active"}
    await orchestrator.persist_state(entity_id, state_data, cache=True)

    # Should not cache even when requested
    assert entity_id not in orchestrator._state_cache


@pytest.mark.asyncio
async def test_persist_state_failure(orchestrator, entity_id):
    """Test state persistence failure handling."""
    # Make persistence fail
    async def failing_persist(entity_id, state_data):
        raise ValueError("Database error")

    orchestrator._persist_to_db = failing_persist

    success = await orchestrator.persist_state(entity_id, {"status": "active"})

    assert success is False


# ===============================
# State Retrieval Tests
# ===============================


@pytest.mark.asyncio
async def test_get_state_from_cache(orchestrator, entity_id):
    """Test state retrieval from cache."""
    state_data = {"status": "active", "step": 3}

    # Populate cache
    await orchestrator.persist_state(entity_id, state_data)

    # Retrieve from cache
    retrieved = await orchestrator.get_state(entity_id, from_cache=True)

    assert retrieved == state_data


@pytest.mark.asyncio
async def test_get_state_from_database(orchestrator, entity_id):
    """Test state retrieval from database when not in cache."""
    state_data = {"status": "pending"}

    # Store in database only (not cache)
    await orchestrator.persist_state(entity_id, state_data, cache=False)

    # Retrieve should fetch from database
    retrieved = await orchestrator.get_state(entity_id, from_cache=True)

    assert retrieved == state_data
    # Should now be in cache
    assert entity_id in orchestrator._state_cache


@pytest.mark.asyncio
async def test_get_state_skip_cache(orchestrator, entity_id):
    """Test state retrieval directly from database."""
    state_data = {"status": "active"}

    await orchestrator.persist_state(entity_id, state_data)

    # Update database directly (bypass cache)
    new_data = {"status": "paused"}
    orchestrator._db_storage[entity_id] = new_data

    # Retrieve from database
    retrieved = await orchestrator.get_state(entity_id, from_cache=False)

    assert retrieved == new_data


@pytest.mark.asyncio
async def test_get_state_not_found(orchestrator, entity_id):
    """Test state retrieval when entity doesn't exist."""
    retrieved = await orchestrator.get_state(entity_id)

    assert retrieved is None


@pytest.mark.asyncio
async def test_get_state_fetch_error(orchestrator, entity_id):
    """Test state retrieval handles fetch errors."""
    # Make fetch fail
    async def failing_fetch(entity_id):
        raise RuntimeError("Database error")

    orchestrator._fetch_from_db = failing_fetch

    retrieved = await orchestrator.get_state(entity_id)

    assert retrieved is None


# ===============================
# State Transition Tests
# ===============================


@pytest.mark.asyncio
async def test_transition_state_success(orchestrator, entity_id):
    """Test successful state transition."""
    # Setup initial state
    await orchestrator.persist_state(entity_id, {"status": "pending"})

    # Transition
    success = await orchestrator.transition_state(
        entity_id,
        from_status="pending",
        to_status="active"
    )

    assert success is True

    # Verify state updated
    state = await orchestrator.get_state(entity_id)
    assert state["status"] == "active"
    assert state["previous_status"] == "pending"


@pytest.mark.asyncio
async def test_transition_state_with_metadata(orchestrator, entity_id):
    """Test state transition with metadata."""
    await orchestrator.persist_state(entity_id, {"status": "pending"})

    await orchestrator.transition_state(
        entity_id,
        from_status="pending",
        to_status="active",
        metadata={"transitioned_by": "system", "reason": "auto"}
    )

    state = await orchestrator.get_state(entity_id)
    assert "metadata" in state
    assert state["metadata"]["transitioned_by"] == "system"


@pytest.mark.asyncio
async def test_transition_state_validation_failure(orchestrator, entity_id):
    """Test state transition with validation failure."""
    await orchestrator.persist_state(entity_id, {"status": "pending"})

    # Mock validation to fail
    def invalid_transition(from_status, to_status):
        return False, "Invalid transition"

    orchestrator.validate_transition = invalid_transition

    success = await orchestrator.transition_state(
        entity_id,
        from_status="pending",
        to_status="active"
    )

    assert success is False

    # State should remain unchanged
    state = await orchestrator.get_state(entity_id)
    assert state["status"] == "pending"


@pytest.mark.asyncio
async def test_transition_state_skip_validation(orchestrator, entity_id):
    """Test state transition without validation."""
    await orchestrator.persist_state(entity_id, {"status": "pending"})

    # This would normally fail validation
    def invalid_transition(from_status, to_status):
        return False, "Should not be called"

    orchestrator.validate_transition = invalid_transition

    success = await orchestrator.transition_state(
        entity_id,
        from_status="pending",
        to_status="active",
        validate=False
    )

    assert success is True


@pytest.mark.asyncio
async def test_transition_state_not_found(orchestrator, entity_id):
    """Test state transition when entity doesn't exist."""
    success = await orchestrator.transition_state(
        entity_id,
        from_status="pending",
        to_status="active"
    )

    assert success is False


def test_validate_transition_default(orchestrator):
    """Test default transition validation (allows all)."""
    is_valid, error = orchestrator.validate_transition("any", "status")

    assert is_valid is True
    assert error is None


# ===============================
# Cache Management Tests
# ===============================


def test_invalidate_cache_single_entity(orchestrator, entity_id):
    """Test cache invalidation for single entity."""
    # Populate cache
    orchestrator._state_cache[entity_id] = {"status": "active"}

    orchestrator.invalidate_cache(entity_id)

    assert entity_id not in orchestrator._state_cache


def test_invalidate_cache_all(orchestrator):
    """Test cache invalidation for all entities."""
    # Populate cache
    id1, id2 = uuid4(), uuid4()
    orchestrator._state_cache[id1] = {"status": "active"}
    orchestrator._state_cache[id2] = {"status": "pending"}

    orchestrator.invalidate_cache()

    assert len(orchestrator._state_cache) == 0


def test_invalidate_cache_nonexistent(orchestrator, entity_id):
    """Test cache invalidation for non-existent entity."""
    # Should not raise error
    orchestrator.invalidate_cache(entity_id)

    assert entity_id not in orchestrator._state_cache


def test_get_cache_stats(orchestrator):
    """Test cache statistics retrieval."""
    id1, id2 = uuid4(), uuid4()
    orchestrator._state_cache[id1] = {"status": "active"}
    orchestrator._state_cache[id2] = {"status": "pending"}

    stats = orchestrator.get_cache_stats()

    assert stats["enabled"] is True
    assert stats["size"] == 2
    assert len(stats["entities"]) == 2
    assert str(id1) in stats["entities"]
    assert str(id2) in stats["entities"]


def test_get_cache_stats_disabled(mock_db):
    """Test cache statistics when caching is disabled."""
    orchestrator = TestStateAwareOrchestrator(
        db=mock_db,
        state_cache_enabled=False
    )

    stats = orchestrator.get_cache_stats()

    assert stats["enabled"] is False
    assert stats["size"] == 0


# ===============================
# Abstract Method Tests
# ===============================


def test_abstract_methods_must_be_implemented(mock_db):
    """Test that abstract methods must be implemented."""

    class IncompleteOrchestrator(BaseOrchestrator, StateAwareOrchestrator):
        async def execute(self, context):
            return {}

        def validate(self, context):
            return True, None

    orchestrator = IncompleteOrchestrator(db=mock_db)
    entity_id = uuid4()

    # Should raise NotImplementedError
    with pytest.raises(NotImplementedError):
        asyncio.run(orchestrator._persist_to_db(entity_id, {}))

    with pytest.raises(NotImplementedError):
        asyncio.run(orchestrator._fetch_from_db(entity_id))


# ===============================
# Integration Tests
# ===============================


@pytest.mark.asyncio
async def test_full_state_lifecycle(orchestrator, entity_id):
    """Test complete state lifecycle."""
    # Create initial state
    initial_state = {"status": "pending", "step": 1}
    await orchestrator.persist_state(entity_id, initial_state)

    # Transition to active
    await orchestrator.transition_state(
        entity_id,
        from_status="pending",
        to_status="active",
        metadata={"started_at": "2025-11-15"}
    )

    # Verify state
    state = await orchestrator.get_state(entity_id)
    assert state["status"] == "active"
    assert state["previous_status"] == "pending"
    assert state["metadata"]["started_at"] == "2025-11-15"

    # Update state
    state["step"] = 5
    await orchestrator.persist_state(entity_id, state)

    # Transition to completed
    await orchestrator.transition_state(
        entity_id,
        from_status="active",
        to_status="completed"
    )

    # Final verification
    final_state = await orchestrator.get_state(entity_id)
    assert final_state["status"] == "completed"
    assert final_state["step"] == 5


@pytest.mark.asyncio
async def test_cache_performance(orchestrator):
    """Test cache improves retrieval performance."""
    entity_id = uuid4()
    state_data = {"status": "active", "large_data": "x" * 1000}

    # First persist (writes to both db and cache)
    await orchestrator.persist_state(entity_id, state_data)

    # Clear database to test cache hit
    orchestrator._db_storage.clear()

    # Should still retrieve from cache
    cached_state = await orchestrator.get_state(entity_id, from_cache=True)

    assert cached_state == state_data


@pytest.mark.asyncio
async def test_concurrent_state_updates(orchestrator):
    """Test concurrent state updates."""
    entity_id = uuid4()

    # Setup initial state
    await orchestrator.persist_state(entity_id, {"status": "pending", "counter": 0})

    # Simulate concurrent updates
    tasks = []
    for i in range(5):
        async def update(iteration):
            state = await orchestrator.get_state(entity_id)
            state["counter"] = iteration
            await orchestrator.persist_state(entity_id, state)

        tasks.append(update(i))

    await asyncio.gather(*tasks)

    # Verify final state
    final_state = await orchestrator.get_state(entity_id)
    assert "counter" in final_state
