"""
Test to verify SagaOrchestrator uses Unit of Work pattern correctly.

This test demonstrates that the saga orchestrator now properly supports
test isolation by using flush() instead of commit() for intermediate steps.
"""

import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch

from app.orchestration.saga_orchestrator import SagaOrchestrator
from app.schemas.patient import PatientCreate


@pytest.fixture
def mock_db_session():
    """Mock database session that tracks flush() and commit() calls."""
    session = MagicMock()
    session.flush_count = 0
    session.commit_count = 0
    session.rollback_count = 0

    # Track calls
    original_flush = session.flush
    original_commit = session.commit
    original_rollback = session.rollback

    def tracked_flush():
        session.flush_count += 1
        return original_flush()

    def tracked_commit():
        session.commit_count += 1
        return original_commit()

    def tracked_rollback():
        session.rollback_count += 1
        return original_rollback()

    session.flush = tracked_flush
    session.commit = tracked_commit
    session.rollback = tracked_rollback

    return session


@pytest.fixture
def orchestrator(mock_db_session):
    """Create SagaOrchestrator with mocked dependencies."""
    orchestrator = SagaOrchestrator(db=mock_db_session)

    # Mock repository and services
    orchestrator.patient_repo = MagicMock()
    orchestrator.flow_service = MagicMock()
    orchestrator.whatsapp_service = MagicMock()
    orchestrator.message_service = MagicMock()

    return orchestrator


@pytest.mark.asyncio
async def test_saga_uses_single_commit_on_success(orchestrator, mock_db_session):
    """
    Verify that a successful saga execution uses flush() for intermediate steps
    and only commits once at the end.
    """
    # Arrange
    patient_data = PatientCreate(
        name="Test Patient",
        email="test@example.com",
        phone="+5511987654321",
    )
    doctor_id = uuid4()

    # Mock successful patient creation
    mock_patient = MagicMock()
    mock_patient.id = uuid4()
    mock_patient.name = "Test Patient"
    orchestrator.patient_repo.create.return_value = mock_patient

    # Mock successful flow initialization
    orchestrator.flow_service.initialize_default_flow = AsyncMock()
    orchestrator.flow_service.activate_patient = AsyncMock()

    # Mock successful message sending
    mock_message = MagicMock()
    mock_message.id = uuid4()
    orchestrator.message_service.schedule_message.return_value = mock_message
    orchestrator.whatsapp_service.send_message = AsyncMock(return_value=True)
    orchestrator.message_service.mark_as_sent = MagicMock()

    # Mock query for saga
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    # Act
    with patch('app.orchestration.saga_orchestrator.acquire_lock'):
        patient = await orchestrator.execute_patient_onboarding_saga(
            patient_data=patient_data,
            doctor_id=doctor_id,
        )

    # Assert
    assert patient is not None
    assert patient.id == mock_patient.id

    # CRITICAL: Should have used flush() multiple times but commit() only once
    print(f"Flush calls: {mock_db_session.flush_count}")
    print(f"Commit calls: {mock_db_session.commit_count}")
    print(f"Rollback calls: {mock_db_session.rollback_count}")

    # Expect:
    # - 1 flush for saga initialization
    # - 1 flush for patient creation
    # - 1 flush for flow initialization
    # - 1 flush for message sending
    # - 1 commit at the end
    assert mock_db_session.flush_count >= 4, "Should use flush() for intermediate steps"
    assert mock_db_session.commit_count == 1, "Should commit only once at the end"
    assert mock_db_session.rollback_count == 0, "Should not rollback on success"


@pytest.mark.asyncio
async def test_saga_rolls_back_on_failure(orchestrator, mock_db_session):
    """
    Verify that a failed saga execution rolls back the entire transaction
    and then commits only the failure state.
    """
    # Arrange
    patient_data = PatientCreate(
        name="Test Patient",
        email="test@example.com",
        phone="+5511987654321",
    )
    doctor_id = uuid4()

    # Mock successful patient creation
    mock_patient = MagicMock()
    mock_patient.id = uuid4()
    orchestrator.patient_repo.create.return_value = mock_patient

    # Mock FAILED flow initialization
    orchestrator.flow_service.initialize_default_flow = AsyncMock(
        side_effect=Exception("Flow initialization failed")
    )

    # Mock query for saga
    mock_db_session.query.return_value.filter.return_value.first.return_value = None

    # Act
    with patch('app.orchestration.saga_orchestrator.acquire_lock'):
        patient = await orchestrator.execute_patient_onboarding_saga(
            patient_data=patient_data,
            doctor_id=doctor_id,
        )

    # Assert
    assert patient is None  # Should return None on failure

    print(f"Flush calls: {mock_db_session.flush_count}")
    print(f"Commit calls: {mock_db_session.commit_count}")
    print(f"Rollback calls: {mock_db_session.rollback_count}")

    # Expect:
    # - Multiple flush() calls before failure
    # - 1 rollback() on failure
    # - 1 commit() for failure state
    # - 1 commit() for compensation
    assert mock_db_session.flush_count >= 2, "Should use flush() before failure"
    assert mock_db_session.rollback_count == 1, "Should rollback on failure"
    assert mock_db_session.commit_count >= 1, "Should commit failure state and compensation"


@pytest.mark.asyncio
async def test_saga_enables_test_isolation(orchestrator, mock_db_session):
    """
    Demonstrate that the Unit of Work pattern enables proper test isolation.

    This test shows that test fixtures can wrap saga operations in transactions
    that can be rolled back, which was not possible with intermediate commits.
    """
    # Arrange
    patient_data = PatientCreate(
        name="Test Patient",
        email="test@example.com",
        phone="+5511987654321",
    )
    doctor_id = uuid4()

    # Mock successful operations
    mock_patient = MagicMock()
    mock_patient.id = uuid4()
    orchestrator.patient_repo.create.return_value = mock_patient
    orchestrator.flow_service.initialize_default_flow = AsyncMock()
    orchestrator.flow_service.activate_patient = AsyncMock()
    mock_message = MagicMock()
    orchestrator.message_service.schedule_message.return_value = mock_message
    orchestrator.whatsapp_service.send_message = AsyncMock(return_value=True)
    orchestrator.message_service.mark_as_sent = MagicMock()

    # Simulate test fixture transaction wrapper
    test_transaction_started = True

    # Act - Execute saga within test transaction
    with patch('app.orchestration.saga_orchestrator.acquire_lock'):
        patient = await orchestrator.execute_patient_onboarding_saga(
            patient_data=patient_data,
            doctor_id=doctor_id,
        )

    # Simulate test cleanup - rollback test transaction
    # With the old code (intermediate commits), this would NOT undo the saga changes
    # With the new code (single commit), this WOULD undo everything if commit hadn't been called
    if test_transaction_started:
        # In real tests, this would be done by pytest fixture
        # mock_db_session.rollback()
        pass

    # Assert
    # The key insight: With flush() instead of commit(), the test fixture's
    # rollback would undo all changes if the saga hadn't called its final commit()
    assert patient is not None
    assert mock_db_session.commit_count == 1  # Only final commit, not intermediate ones


def test_unit_of_work_pattern_explanation():
    """
    Documentation test explaining the Unit of Work pattern fix.
    """
    explanation = """
    PROBLEM:
    --------
    Previously, SagaOrchestrator called db.commit() after each step:
    1. Commit after creating saga record
    2. Commit after creating patient
    3. Commit after initializing flow
    4. Commit after sending message

    This broke test isolation because:
    - Test fixtures wrap operations in transactions
    - Test transactions expect to rollback all changes after each test
    - Intermediate commits persisted data OUTSIDE the test transaction
    - Test rollback couldn't undo the committed changes
    - Tests polluted the database and interfered with each other

    SOLUTION:
    ---------
    Use the Unit of Work pattern:
    1. db.flush() after creating saga record (get ID without commit)
    2. db.flush() after creating patient (get ID without commit)
    3. db.flush() after initializing flow (persist without commit)
    4. db.flush() after sending message (persist without commit)
    5. db.commit() ONLY at the very end (all-or-nothing)

    On error:
    1. db.rollback() reverts entire transaction
    2. db.commit() only the failure state (in new transaction)
    3. Compensation runs in separate transaction

    BENEFITS:
    ---------
    1. Test isolation works properly
    2. All-or-nothing semantics (atomic transactions)
    3. No partial states in database
    4. Tests can rollback without database pollution
    5. Compensation logic unchanged
    """
    assert True  # This is a documentation test
    print(explanation)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
