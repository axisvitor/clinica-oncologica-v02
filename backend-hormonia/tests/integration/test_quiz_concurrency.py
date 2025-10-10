"""
Comprehensive tests for quiz session concurrency control.

This module tests the critical P8 fix: preventing concurrent quiz session creation
for the same patient, template, and time period.

Test Coverage:
1. Race condition prevention during concurrent session creation
2. Database-level constraint validation
3. Service-level locking behavior
4. Error handling and recovery
5. Performance under concurrent load
6. Month boundary edge cases
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from typing import List
from unittest.mock import patch, AsyncMock
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.quiz import QuizTemplate, QuizSession
from app.services.quiz import QuizSessionService
from app.schemas.quiz import QuizSessionCreate
from app.exceptions import ConflictError, NotFoundError


class TestQuizConcurrencyPrevention:
    """Test concurrent quiz session creation prevention."""

    @pytest.fixture
    def quiz_template(self, db_session):
        """Create a test quiz template."""
        template = QuizTemplate(
            name="Concurrency Test Template",
            version="1.0",
            questions=[
                {
                    "id": "q1",
                    "text": "Test question",
                    "type": "scale",
                    "validation_rules": [{"type": "range", "min": 1, "max": 10}],
                    "required": True
                }
            ],
            is_active=True
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        return template

    @pytest.fixture
    def session_service(self, db_session):
        """Create QuizSessionService with database session."""
        return QuizSessionService(db_session)

    @pytest.mark.asyncio
    async def test_concurrent_session_creation_prevented(self, session_service, quiz_template):
        """
        Test that concurrent session creation for same patient is prevented.

        This is the core P8 test: multiple concurrent requests to create a session
        for the same patient should result in only ONE session being created.
        """
        patient_id = uuid4()

        # Create 10 concurrent session creation requests
        async def create_session():
            try:
                session_data = QuizSessionCreate(
                    patient_id=patient_id,
                    quiz_template_id=quiz_template.id
                )
                with patch('app.services.websocket_events.websocket_events', None):
                    return await session_service.start_quiz_session(session_data)
            except (ConflictError, IntegrityError) as e:
                # Expected for race condition losers
                return e

        # Execute all requests concurrently
        tasks = [create_session() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful creations
        successful_sessions = [r for r in results if isinstance(r, type(r)) and not isinstance(r, Exception)]
        failed_attempts = [r for r in results if isinstance(r, Exception)]

        # CRITICAL ASSERTION: Only ONE session should be created
        assert len(successful_sessions) == 1, f"Expected 1 session, got {len(successful_sessions)}"

        # All other attempts should fail with ConflictError or IntegrityError
        assert len(failed_attempts) == 9, f"Expected 9 failures, got {len(failed_attempts)}"

        # Verify only one session exists in database
        db_sessions = session_service.db.query(QuizSession).filter(
            QuizSession.patient_id == patient_id
        ).all()
        assert len(db_sessions) == 1, f"Database should have exactly 1 session, found {len(db_sessions)}"

    @pytest.mark.asyncio
    async def test_concurrent_different_patients_allowed(self, session_service, quiz_template):
        """
        Test that concurrent session creation for different patients is allowed.

        Different patients should be able to create sessions concurrently without conflict.
        """
        # Create 5 different patients
        patient_ids = [uuid4() for _ in range(5)]

        async def create_session_for_patient(patient_id):
            session_data = QuizSessionCreate(
                patient_id=patient_id,
                quiz_template_id=quiz_template.id
            )
            with patch('app.services.websocket_events.websocket_events', None):
                return await session_service.start_quiz_session(session_data)

        # Create sessions concurrently for all patients
        tasks = [create_session_for_patient(pid) for pid in patient_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed
        successful_sessions = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_sessions) == 5, f"Expected 5 successful sessions, got {len(successful_sessions)}"

        # Verify all sessions in database
        for patient_id in patient_ids:
            db_sessions = session_service.db.query(QuizSession).filter(
                QuizSession.patient_id == patient_id
            ).all()
            assert len(db_sessions) == 1

    @pytest.mark.asyncio
    async def test_concurrent_different_templates_allowed(self, session_service, db_session):
        """
        Test that same patient can create sessions for different templates concurrently.
        """
        patient_id = uuid4()

        # Create two different templates
        template1 = QuizTemplate(
            name="Template 1",
            version="1.0",
            questions=[{"id": "q1", "text": "Q1", "type": "scale"}],
            is_active=True
        )
        template2 = QuizTemplate(
            name="Template 2",
            version="1.0",
            questions=[{"id": "q1", "text": "Q1", "type": "scale"}],
            is_active=True
        )
        db_session.add_all([template1, template2])
        db_session.commit()
        db_session.refresh(template1)
        db_session.refresh(template2)

        async def create_session_for_template(template_id):
            session_data = QuizSessionCreate(
                patient_id=patient_id,
                quiz_template_id=template_id
            )
            with patch('app.services.websocket_events.websocket_events', None):
                return await session_service.start_quiz_session(session_data)

        # Create sessions concurrently for different templates
        tasks = [
            create_session_for_template(template1.id),
            create_session_for_template(template2.id)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Both should succeed
        successful_sessions = [r for r in results if not isinstance(r, Exception)]
        assert len(successful_sessions) == 2

        # Verify both sessions exist
        db_sessions = session_service.db.query(QuizSession).filter(
            QuizSession.patient_id == patient_id
        ).all()
        assert len(db_sessions) == 2

    @pytest.mark.asyncio
    async def test_completed_session_allows_new_session_same_month(self, session_service, quiz_template):
        """
        Test that completing a session allows creating a new one in the same month.

        The unique constraint only applies to active sessions, so completed sessions
        should not prevent new session creation.
        """
        patient_id = uuid4()

        # Create and complete first session
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=quiz_template.id
        )
        with patch('app.services.websocket_events.websocket_events', None):
            session1 = await session_service.start_quiz_session(session_data)
            await session_service.complete_session(session1.id)

        # Create second session (should succeed because first is completed)
        with patch('app.services.websocket_events.websocket_events', None):
            session2 = await session_service.start_quiz_session(session_data)

        assert session1.id != session2.id

        # Verify both sessions exist
        db_sessions = session_service.db.query(QuizSession).filter(
            QuizSession.patient_id == patient_id
        ).all()
        assert len(db_sessions) == 2

        # Verify first is completed, second is active
        completed_sessions = [s for s in db_sessions if s.status == 'completed']
        active_sessions = [s for s in db_sessions if s.status == 'started']
        assert len(completed_sessions) == 1
        assert len(active_sessions) == 1

    @pytest.mark.asyncio
    async def test_cancelled_session_allows_new_session(self, session_service, quiz_template):
        """
        Test that cancelling a session allows creating a new one.

        Cancelled sessions should behave like completed sessions - they don't block
        new session creation.
        """
        patient_id = uuid4()

        # Create session and mark as cancelled
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=quiz_template.id
        )
        with patch('app.services.websocket_events.websocket_events', None):
            session1 = await session_service.start_quiz_session(session_data)

        # Manually cancel the session
        session1_obj = session_service.db.query(QuizSession).filter(
            QuizSession.id == session1.id
        ).first()
        session1_obj.status = 'cancelled'
        session_service.db.commit()

        # Create new session (should succeed)
        with patch('app.services.websocket_events.websocket_events', None):
            session2 = await session_service.start_quiz_session(session_data)

        assert session1.id != session2.id
        assert session2.status == 'started'

    @pytest.mark.asyncio
    async def test_month_boundary_uniqueness(self, session_service, quiz_template, db_session):
        """
        Test that sessions in different months don't conflict.

        The unique constraint is per-month, so sessions created in different months
        for the same patient and template should be allowed.
        """
        patient_id = uuid4()

        # Create session in "current" month (simulated)
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=quiz_template.id
        )
        with patch('app.services.websocket_events.websocket_events', None):
            session1 = await session_service.start_quiz_session(session_data)

        # Manually update the started_at to previous month
        session1_obj = db_session.query(QuizSession).filter(
            QuizSession.id == session1.id
        ).first()
        session1_obj.started_at = datetime.utcnow() - timedelta(days=35)  # Previous month
        db_session.commit()

        # Create new session in "current" month (should succeed)
        with patch('app.services.websocket_events.websocket_events', None):
            session2 = await session_service.start_quiz_session(session_data)

        assert session1.id != session2.id

        # Verify both sessions exist
        db_sessions = db_session.query(QuizSession).filter(
            QuizSession.patient_id == patient_id
        ).all()
        assert len(db_sessions) == 2

    @pytest.mark.asyncio
    async def test_database_constraint_enforcement(self, quiz_template, db_session):
        """
        Test that database-level constraint prevents duplicates even when bypassing service layer.

        This tests the database constraint directly, ensuring it works even if
        someone bypasses the service layer.
        """
        patient_id = uuid4()
        current_time = datetime.utcnow()

        # Create first session directly in database
        session1 = QuizSession(
            patient_id=patient_id,
            quiz_template_id=quiz_template.id,
            current_question=0,
            status='started',
            started_at=current_time
        )
        db_session.add(session1)
        db_session.commit()

        # Try to create duplicate session directly in database
        session2 = QuizSession(
            patient_id=patient_id,
            quiz_template_id=quiz_template.id,
            current_question=0,
            status='started',
            started_at=current_time  # Same month
        )
        db_session.add(session2)

        # Should fail with IntegrityError
        with pytest.raises(IntegrityError):
            db_session.commit()

        db_session.rollback()

    @pytest.mark.asyncio
    async def test_high_concurrency_stress_test(self, session_service, quiz_template):
        """
        Stress test with high number of concurrent requests.

        Simulates realistic production load with many concurrent users.
        """
        patient_id = uuid4()

        async def create_session():
            try:
                session_data = QuizSessionCreate(
                    patient_id=patient_id,
                    quiz_template_id=quiz_template.id
                )
                with patch('app.services.websocket_events.websocket_events', None):
                    return await session_service.start_quiz_session(session_data)
            except (ConflictError, IntegrityError) as e:
                return e

        # Create 50 concurrent requests
        tasks = [create_session() for _ in range(50)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Only ONE should succeed
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == 1

        # Verify database state
        db_sessions = session_service.db.query(QuizSession).filter(
            QuizSession.patient_id == patient_id
        ).all()
        assert len(db_sessions) == 1

    @pytest.mark.asyncio
    async def test_concurrent_session_with_response_submission(self, session_service, quiz_template):
        """
        Test concurrency handling when sessions are being created and responses submitted.

        Real-world scenario: multiple requests happening simultaneously.
        """
        patient_id = uuid4()

        # First create a valid session
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=quiz_template.id
        )
        with patch('app.services.websocket_events.websocket_events', None):
            valid_session = await session_service.start_quiz_session(session_data)

        # Try to create duplicate session while the first exists
        async def try_create_duplicate():
            try:
                with patch('app.services.websocket_events.websocket_events', None):
                    return await session_service.start_quiz_session(session_data)
            except (ConflictError, IntegrityError) as e:
                return e

        # Execute multiple duplicate attempts
        tasks = [try_create_duplicate() for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should fail
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(failures) == 5

        # Original session should still exist and be valid
        current_session = session_service.get_session(valid_session.id)
        assert current_session.status == 'started'

    def test_service_layer_error_handling(self, session_service, quiz_template):
        """
        Test that service layer properly handles and reports concurrency errors.
        """
        patient_id = uuid4()

        # Create first session
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=quiz_template.id
        )
        with patch('app.services.websocket_events.websocket_events', None):
            asyncio.run(session_service.start_quiz_session(session_data))

        # Try to create duplicate - should raise ConflictError with clear message
        with pytest.raises(ConflictError) as exc_info:
            with patch('app.services.websocket_events.websocket_events', None):
                asyncio.run(session_service.start_quiz_session(session_data))

        # Error message should be clear
        assert "active quiz session" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_recovery_from_failed_session_creation(self, session_service, quiz_template, db_session):
        """
        Test that failed session creation doesn't leave database in inconsistent state.
        """
        patient_id = uuid4()

        # Create session that will fail midway
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=quiz_template.id
        )

        # Mock to cause failure after partial creation
        original_flush = db_session.flush
        call_count = 0

        def failing_flush():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise IntegrityError("Simulated error", None, None)
            return original_flush()

        db_session.flush = failing_flush

        # Attempt creation (should fail)
        with pytest.raises((ConflictError, IntegrityError)):
            with patch('app.services.websocket_events.websocket_events', None):
                await session_service.start_quiz_session(session_data)

        # Restore normal flush
        db_session.flush = original_flush

        # Database should have no orphaned sessions
        db_sessions = db_session.query(QuizSession).filter(
            QuizSession.patient_id == patient_id
        ).all()
        assert len(db_sessions) == 0

        # New creation should work
        with patch('app.services.websocket_events.websocket_events', None):
            session = await session_service.start_quiz_session(session_data)
        assert session is not None


class TestQuizConcurrencyPerformance:
    """Test performance characteristics of concurrency control."""

    @pytest.fixture
    def quiz_template(self, db_session):
        """Create test template."""
        template = QuizTemplate(
            name="Performance Test Template",
            version="1.0",
            questions=[{"id": "q1", "text": "Q1", "type": "scale"}],
            is_active=True
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        return template

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_creation_performance(self, session_service, quiz_template):
        """
        Test that concurrency control doesn't significantly degrade performance.

        Performance target: Handle 100 concurrent requests in under 5 seconds.
        """
        import time

        # Create 100 different patients
        patient_ids = [uuid4() for _ in range(100)]

        async def create_session_for_patient(patient_id):
            session_data = QuizSessionCreate(
                patient_id=patient_id,
                quiz_template_id=quiz_template.id
            )
            with patch('app.services.websocket_events.websocket_events', None):
                return await session_service.start_quiz_session(session_data)

        # Measure execution time
        start_time = time.time()

        tasks = [create_session_for_patient(pid) for pid in patient_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        execution_time = time.time() - start_time

        # All should succeed
        successful = [r for r in results if not isinstance(r, Exception)]
        assert len(successful) == 100

        # Performance assertion
        assert execution_time < 5.0, f"Took {execution_time}s, expected < 5s"

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_lock_contention_minimal(self, session_service, quiz_template):
        """
        Test that database locking doesn't cause excessive contention.

        Concurrent requests for different patients should not block each other.
        """
        import time

        patient_ids = [uuid4() for _ in range(20)]

        async def timed_session_creation(patient_id):
            start = time.time()
            session_data = QuizSessionCreate(
                patient_id=patient_id,
                quiz_template_id=quiz_template.id
            )
            with patch('app.services.websocket_events.websocket_events', None):
                result = await session_service.start_quiz_session(session_data)
            duration = time.time() - start
            return duration

        tasks = [timed_session_creation(pid) for pid in patient_ids]
        durations = await asyncio.gather(*tasks)

        # No individual request should take more than 1 second
        # (indicates minimal lock contention)
        max_duration = max(durations)
        assert max_duration < 1.0, f"Max duration {max_duration}s indicates lock contention"


# Fixtures for performance testing
@pytest.fixture
def performance_timer():
    """Simple performance timer fixture."""
    class Timer:
        def __init__(self):
            self.start_time = None

        def start(self):
            import time
            self.start_time = time.time()

        def stop(self):
            import time
            if self.start_time is None:
                return 0
            elapsed = time.time() - self.start_time
            self.start_time = None
            return elapsed

    return Timer()
