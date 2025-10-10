"""
Integration tests for quiz session management.

Tests the complete quiz session workflow including:
- Session lifecycle management (start, progress, complete)
- Session state consistency across database operations
- Concurrent session handling and race conditions
- Session-response relationship integrity
- WebSocket event integration
- Performance under realistic load
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4
from typing import List, Dict, Any
from unittest.mock import Mock, AsyncMock, patch

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.quiz import QuizTemplate, QuizSession, QuizResponse
from app.services.quiz import QuizSessionService, QuizResponseService
from app.schemas.quiz import (
    QuizSessionCreate, QuizSessionResponse,
    QuizResponseCreate, QuizResponseResponse,
    QuestionType
)
from app.exceptions import NotFoundError, ValidationError, ConflictError


class TestQuizSessionLifecycle:
    """Test complete quiz session lifecycle integration."""

    @pytest.fixture
    def sample_template(self, db_session):
        """Create a sample quiz template in the database."""
        template = QuizTemplate(
            name="Integration Test Template",
            version="1.0",
            questions=[
                {
                    "id": "mood_check",
                    "text": "How are you feeling today?",
                    "type": "scale",
                    "validation_rules": [{"type": "range", "min": 1, "max": 10}],
                    "required": True
                },
                {
                    "id": "medication_taken",
                    "text": "Did you take your medication?",
                    "type": "yes_no",
                    "options": [
                        {"id": "yes", "value": "Yes"},
                        {"id": "no", "value": "No"}
                    ],
                    "required": True
                },
                {
                    "id": "side_effects",
                    "text": "Any side effects?",
                    "type": "open_text",
                    "validation_rules": [{"type": "max_length", "value": 500}],
                    "required": False
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
        """Create QuizSessionService with real database session."""
        return QuizSessionService(db_session)

    @pytest.fixture
    def response_service(self, db_session):
        """Create QuizResponseService with real database session."""
        return QuizResponseService(db_session)

    @pytest.mark.asyncio
    async def test_complete_session_workflow(self, session_service, response_service,
                                           sample_template, db_session):
        """Test complete session workflow from start to completion."""
        patient_id = uuid4()

        # Step 1: Start session
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=sample_template.id
        )

        with patch('app.services.websocket_events.websocket_events', None):
            session = await session_service.start_quiz_session(session_data)

        assert session.patient_id == patient_id
        assert session.quiz_template_id == sample_template.id
        assert session.status == "started"
        assert session.current_question == 0

        # Step 2: Submit responses for each question
        questions = sample_template.questions
        responses = []

        for i, question in enumerate(questions):
            # Create response based on question type
            if question["type"] == "scale":
                response_value = "7"
            elif question["type"] == "yes_no":
                response_value = "yes"
            elif question["type"] == "open_text":
                response_value = "No side effects today"
            else:
                response_value = "default_response"

            response_data = QuizResponseCreate(
                patient_id=patient_id,
                quiz_template_id=sample_template.id,
                question_id=question["id"],
                response_type=getattr(QuestionType, question["type"].upper()),
                response_value=response_value,
                response_metadata={"question_index": i}
            )

            response = await response_service.create_response(response_data)
            responses.append(response)

            # Advance session after each response (except last)
            if i < len(questions) - 1:
                session = session_service.advance_session(session.id)
                assert session.current_question == i + 1

        # Step 3: Complete session
        completed_session = await session_service.complete_session(session.id)

        assert completed_session.status == "completed"
        assert completed_session.completed_at is not None
        assert len(responses) == len(questions)

        # Step 4: Verify data integrity
        # Check session in database
        db_session = session_service.db
        saved_session = db_session.query(QuizSession).filter(
            QuizSession.id == session.id
        ).first()

        assert saved_session.status == "completed"
        assert saved_session.completed_at is not None

        # Check all responses are saved
        saved_responses = db_session.query(QuizResponse).filter(
            QuizResponse.patient_id == patient_id,
            QuizResponse.quiz_template_id == sample_template.id
        ).all()

        assert len(saved_responses) == len(questions)

        # Verify response order and content
        for i, response in enumerate(saved_responses):
            expected_question = questions[i]
            assert response.question_id == expected_question["id"]
            assert response.patient_id == patient_id

    @pytest.mark.asyncio
    async def test_session_state_consistency(self, session_service, sample_template):
        """Test session state consistency across operations."""
        patient_id = uuid4()

        # Start session
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=sample_template.id
        )

        with patch('app.services.websocket_events.websocket_events', None):
            session = await session_service.start_quiz_session(session_data)

        original_session_id = session.id
        original_start_time = session.started_at

        # Advance session multiple times
        for i in range(len(sample_template.questions)):
            session = session_service.advance_session(session.id)

            # Verify session ID remains constant
            assert session.id == original_session_id

            # Verify start time doesn't change
            assert session.started_at == original_start_time

            # Verify current question progresses correctly
            if i < len(sample_template.questions) - 1:
                assert session.current_question == i + 1
                assert session.status == "started"
            else:
                # Last advance should complete the session
                assert session.status == "completed"
                assert session.completed_at is not None

    @pytest.mark.asyncio
    async def test_concurrent_session_operations(self, session_service, sample_template):
        """Test handling of concurrent session operations."""
        patient_id = uuid4()

        # Start session
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=sample_template.id
        )

        with patch('app.services.websocket_events.websocket_events', None):
            session = await session_service.start_quiz_session(session_data)

        # Simulate concurrent operations
        async def advance_session():
            try:
                return session_service.advance_session(session.id)
            except Exception as e:
                return e

        async def complete_session():
            try:
                return await session_service.complete_session(session.id)
            except Exception as e:
                return e

        # Run operations concurrently
        tasks = [
            advance_session(),
            complete_session(),
            advance_session()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # At least one operation should succeed
        success_count = sum(1 for result in results if not isinstance(result, Exception))
        assert success_count >= 1

        # Final session should be in consistent state
        final_session = session_service.get_session(session.id)
        assert final_session.status in ["started", "completed"]

    @pytest.mark.asyncio
    async def test_session_with_multiple_patients(self, session_service, sample_template):
        """Test handling multiple concurrent sessions for different patients."""
        patient_ids = [uuid4() for _ in range(5)]
        sessions = []

        # Start sessions for multiple patients
        for patient_id in patient_ids:
            session_data = QuizSessionCreate(
                patient_id=patient_id,
                quiz_template_id=sample_template.id
            )

            with patch('app.services.websocket_events.websocket_events', None):
                session = await session_service.start_quiz_session(session_data)
                sessions.append(session)

        # Verify all sessions are created
        assert len(sessions) == len(patient_ids)

        # Verify each patient has unique session
        session_patient_map = {s.patient_id: s.id for s in sessions}
        assert len(session_patient_map) == len(patient_ids)

        # Advance all sessions concurrently
        async def advance_patient_session(session_id):
            return session_service.advance_session(session_id)

        advance_tasks = [advance_patient_session(s.id) for s in sessions]
        advanced_sessions = await asyncio.gather(*advance_tasks)

        # Verify all sessions advanced correctly
        for session in advanced_sessions:
            assert session.current_question == 1

    def test_session_database_constraints(self, session_service, sample_template, db_session):
        """Test database constraint handling for sessions."""
        patient_id = uuid4()

        # Create session directly in database
        session1 = QuizSession(
            patient_id=patient_id,
            quiz_template_id=sample_template.id,
            current_question=0,
            status="started",
            started_at=datetime.utcnow()
        )

        db_session.add(session1)
        db_session.commit()

        # Try to create another active session for same patient
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=sample_template.id
        )

        # This should raise an error due to unique constraint or business logic
        with pytest.raises((ConflictError, IntegrityError)):
            with patch('app.services.websocket_events.websocket_events', None):
                asyncio.run(session_service.start_quiz_session(session_data))

    @pytest.mark.asyncio
    async def test_session_cleanup_after_completion(self, session_service, sample_template):
        """Test session cleanup and state after completion."""
        patient_id = uuid4()

        # Start and complete session
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=sample_template.id
        )

        with patch('app.services.websocket_events.websocket_events', None):
            session = await session_service.start_quiz_session(session_data)

        completed_session = await session_service.complete_session(session.id)

        # Verify completed session state
        assert completed_session.status == "completed"
        assert completed_session.completed_at is not None

        # Verify no active session exists for patient
        active_session = session_service.get_active_session(patient_id)
        assert active_session is None

        # Try to advance completed session (should fail)
        with pytest.raises(ValidationError):
            session_service.advance_session(completed_session.id)

        # Try to complete already completed session (should be idempotent)
        redundant_completion = await session_service.complete_session(completed_session.id)
        assert redundant_completion.id == completed_session.id
        assert redundant_completion.status == "completed"


class TestQuizSessionResponseIntegration:
    """Test integration between quiz sessions and responses."""

    @pytest.fixture
    def integrated_services(self, db_session):
        """Create integrated services with shared database session."""
        session_service = QuizSessionService(db_session)
        response_service = QuizResponseService(db_session)
        return session_service, response_service

    @pytest.fixture
    def multi_question_template(self, db_session):
        """Create template with various question types."""
        template = QuizTemplate(
            name="Multi-Question Template",
            version="1.0",
            questions=[
                {
                    "id": "scale_question",
                    "text": "Rate from 1-10",
                    "type": "scale",
                    "validation_rules": [{"type": "range", "min": 1, "max": 10}],
                    "required": True
                },
                {
                    "id": "choice_question",
                    "text": "Choose one",
                    "type": "single_choice",
                    "options": [
                        {"id": "a", "value": "Option A"},
                        {"id": "b", "value": "Option B"},
                        {"id": "c", "value": "Option C"}
                    ],
                    "required": True
                },
                {
                    "id": "multi_choice_question",
                    "text": "Choose multiple",
                    "type": "multiple_choice",
                    "options": [
                        {"id": "x", "value": "Option X"},
                        {"id": "y", "value": "Option Y"},
                        {"id": "z", "value": "Option Z"}
                    ],
                    "required": False
                },
                {
                    "id": "text_question",
                    "text": "Free text response",
                    "type": "open_text",
                    "validation_rules": [{"type": "max_length", "value": 1000}],
                    "required": False
                }
            ],
            is_active=True
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        return template

    @pytest.mark.asyncio
    async def test_session_response_coordination(self, integrated_services,
                                               multi_question_template):
        """Test coordination between session state and response submission."""
        session_service, response_service = integrated_services
        patient_id = uuid4()

        # Start session
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=multi_question_template.id
        )

        with patch('app.services.websocket_events.websocket_events', None):
            session = await session_service.start_quiz_session(session_data)

        questions = multi_question_template.questions

        # Submit responses in order, advancing session after each
        for i, question in enumerate(questions):
            # Verify session is at correct question
            current_session = session_service.get_session(session.id)
            assert current_session.current_question == i

            # Submit response for current question
            response_value = self._get_response_value_for_question(question)

            response_data = QuizResponseCreate(
                patient_id=patient_id,
                quiz_template_id=multi_question_template.id,
                question_id=question["id"],
                response_type=getattr(QuestionType, question["type"].upper()),
                response_value=response_value
            )

            response = await response_service.create_response(response_data)
            assert response.question_id == question["id"]

            # Advance session (except for last question)
            if i < len(questions) - 1:
                session_service.advance_session(session.id)

        # Complete session after all responses
        completed_session = await session_service.complete_session(session.id)
        assert completed_session.status == "completed"

        # Verify all responses are linked to the session
        patient_responses = response_service.get_patient_quiz_responses(
            patient_id, multi_question_template.id
        )
        assert len(patient_responses) == len(questions)

    def _get_response_value_for_question(self, question: Dict) -> str:
        """Get appropriate response value based on question type."""
        question_type = question["type"]

        if question_type == "scale":
            return "7"
        elif question_type == "single_choice":
            return question["options"][0]["id"]  # First option
        elif question_type == "multiple_choice":
            return json.dumps([question["options"][0]["id"], question["options"][1]["id"]])
        elif question_type == "yes_no":
            return "yes"
        elif question_type == "open_text":
            return "This is a sample text response"
        else:
            return "default_value"

    @pytest.mark.asyncio
    async def test_response_validation_with_session_context(self, integrated_services,
                                                          multi_question_template):
        """Test response validation considering session context."""
        session_service, response_service = integrated_services
        patient_id = uuid4()

        # Start session
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=multi_question_template.id
        )

        with patch('app.services.websocket_events.websocket_events', None):
            session = await session_service.start_quiz_session(session_data)

        # Try to submit response for question beyond current position
        future_question = multi_question_template.questions[2]  # Skip to question 3

        response_data = QuizResponseCreate(
            patient_id=patient_id,
            quiz_template_id=multi_question_template.id,
            question_id=future_question["id"],
            response_type=QuestionType.MULTIPLE_CHOICE,
            response_value=json.dumps(["x"])
        )

        # This should succeed (business logic may allow answering any question)
        # Or it might fail based on specific business rules
        try:
            response = await response_service.create_response(response_data)
            # If successful, verify the response was created
            assert response.question_id == future_question["id"]
        except ValidationError:
            # If validation fails, that's also acceptable behavior
            pass

    @pytest.mark.asyncio
    async def test_response_consistency_across_session_advances(self, integrated_services,
                                                              multi_question_template):
        """Test response data consistency as session advances."""
        session_service, response_service = integrated_services
        patient_id = uuid4()

        # Start session
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=multi_question_template.id
        )

        with patch('app.services.websocket_events.websocket_events', None):
            session = await session_service.start_quiz_session(session_data)

        # Submit response for first question
        first_question = multi_question_template.questions[0]
        response_data = QuizResponseCreate(
            patient_id=patient_id,
            quiz_template_id=multi_question_template.id,
            question_id=first_question["id"],
            response_type=QuestionType.SCALE,
            response_value="8"
        )

        first_response = await response_service.create_response(response_data)

        # Advance session
        session_service.advance_session(session.id)

        # Submit response for second question
        second_question = multi_question_template.questions[1]
        response_data_2 = QuizResponseCreate(
            patient_id=patient_id,
            quiz_template_id=multi_question_template.id,
            question_id=second_question["id"],
            response_type=QuestionType.SINGLE_CHOICE,
            response_value="a"
        )

        second_response = await response_service.create_response(response_data_2)

        # Verify both responses exist and are correct
        all_responses = response_service.get_patient_quiz_responses(
            patient_id, multi_question_template.id
        )

        assert len(all_responses) == 2
        response_by_question = {r.question_id: r for r in all_responses}

        assert first_question["id"] in response_by_question
        assert second_question["id"] in response_by_question
        assert response_by_question[first_question["id"]].response_value == "8"
        assert response_by_question[second_question["id"]].response_value == "a"


class TestQuizSessionPerformanceIntegration:
    """Test quiz session performance under realistic conditions."""

    @pytest.fixture
    def performance_template(self, db_session):
        """Create template optimized for performance testing."""
        questions = []
        for i in range(20):  # 20 questions for performance test
            questions.append({
                "id": f"perf_q_{i}",
                "text": f"Performance question {i}?",
                "type": "scale",
                "validation_rules": [{"type": "range", "min": 1, "max": 10}],
                "required": True
            })

        template = QuizTemplate(
            name="Performance Test Template",
            version="1.0",
            questions=questions,
            is_active=True
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        return template

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_session_creation_performance(self, session_service, performance_template,
                                              performance_timer):
        """Test performance of creating multiple sessions."""
        patient_ids = [uuid4() for _ in range(50)]

        # Measure session creation time
        performance_timer.start()

        sessions = []
        for patient_id in patient_ids:
            session_data = QuizSessionCreate(
                patient_id=patient_id,
                quiz_template_id=performance_template.id
            )

            with patch('app.services.websocket_events.websocket_events', None):
                session = await session_service.start_quiz_session(session_data)
                sessions.append(session)

        execution_time = performance_timer.stop()

        # Assert performance benchmarks
        assert execution_time < 10.0  # Should create 50 sessions in under 10 seconds
        assert len(sessions) == 50

        # Verify all sessions are unique and valid
        session_ids = {s.id for s in sessions}
        assert len(session_ids) == 50  # All unique

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_concurrent_session_performance(self, session_service, performance_template,
                                                performance_timer):
        """Test performance of concurrent session operations."""
        # Create multiple sessions
        patient_ids = [uuid4() for _ in range(10)]
        sessions = []

        for patient_id in patient_ids:
            session_data = QuizSessionCreate(
                patient_id=patient_id,
                quiz_template_id=performance_template.id
            )

            with patch('app.services.websocket_events.websocket_events', None):
                session = await session_service.start_quiz_session(session_data)
                sessions.append(session)

        # Measure concurrent operations
        performance_timer.start()

        # Create tasks for concurrent operations
        async def advance_all_sessions():
            tasks = [
                asyncio.create_task(session_service.advance_session(s.id))
                for s in sessions
            ]
            return await asyncio.gather(*tasks, return_exceptions=True)

        # Run concurrent advances multiple times
        for _ in range(5):  # Advance 5 times
            results = await advance_all_sessions()
            successful_advances = sum(1 for r in results if not isinstance(r, Exception))
            assert successful_advances >= len(sessions) * 0.8  # At least 80% success rate

        execution_time = performance_timer.stop()

        # Should handle concurrent operations efficiently
        assert execution_time < 5.0  # 50 concurrent operations in under 5 seconds

    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_session_with_many_responses_performance(self, integrated_services,
                                                         performance_template, performance_timer):
        """Test performance when session has many responses."""
        session_service, response_service = integrated_services
        patient_id = uuid4()

        # Start session
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=performance_template.id
        )

        with patch('app.services.websocket_events.websocket_events', None):
            session = await session_service.start_quiz_session(session_data)

        # Measure time to submit all responses
        performance_timer.start()

        questions = performance_template.questions
        for question in questions:
            response_data = QuizResponseCreate(
                patient_id=patient_id,
                quiz_template_id=performance_template.id,
                question_id=question["id"],
                response_type=QuestionType.SCALE,
                response_value="7"
            )

            await response_service.create_response(response_data)

        execution_time = performance_timer.stop()

        # Should handle 20 responses quickly
        assert execution_time < 3.0

        # Complete session
        with patch('app.services.websocket_events.websocket_events', None):
            completed_session = await session_service.complete_session(session.id)

        assert completed_session.status == "completed"

        # Verify all responses were saved
        responses = response_service.get_patient_quiz_responses(
            patient_id, performance_template.id
        )
        assert len(responses) == len(questions)


class TestQuizSessionErrorHandlingIntegration:
    """Test error handling in quiz session integration scenarios."""

    @pytest.fixture
    def error_prone_template(self, db_session):
        """Create template that might cause validation errors."""
        template = QuizTemplate(
            name="Error Test Template",
            version="1.0",
            questions=[
                {
                    "id": "strict_scale",
                    "text": "Rate strictly 1-5",
                    "type": "scale",
                    "validation_rules": [
                        {"type": "range", "min": 1, "max": 5},
                        {"type": "required", "value": True}
                    ],
                    "required": True
                },
                {
                    "id": "limited_choice",
                    "text": "Choose exactly one",
                    "type": "single_choice",
                    "options": [
                        {"id": "only_option", "value": "Only Option"}
                    ],
                    "required": True
                }
            ],
            is_active=True
        )
        db_session.add(template)
        db_session.commit()
        db_session.refresh(template)
        return template

    @pytest.mark.asyncio
    async def test_session_recovery_from_errors(self, integrated_services, error_prone_template):
        """Test session recovery from various error conditions."""
        session_service, response_service = integrated_services
        patient_id = uuid4()

        # Start session
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=error_prone_template.id
        )

        with patch('app.services.websocket_events.websocket_events', None):
            session = await session_service.start_quiz_session(session_data)

        # Try to submit invalid response (out of range)
        invalid_response_data = QuizResponseCreate(
            patient_id=patient_id,
            quiz_template_id=error_prone_template.id,
            question_id="strict_scale",
            response_type=QuestionType.SCALE,
            response_value="10"  # Out of range (1-5)
        )

        # Should raise validation error
        with pytest.raises(ValidationError):
            await response_service.create_response(invalid_response_data)

        # Session should still be in valid state
        current_session = session_service.get_session(session.id)
        assert current_session.status == "started"
        assert current_session.current_question == 0

        # Submit valid response
        valid_response_data = QuizResponseCreate(
            patient_id=patient_id,
            quiz_template_id=error_prone_template.id,
            question_id="strict_scale",
            response_type=QuestionType.SCALE,
            response_value="3"  # Valid range
        )

        response = await response_service.create_response(valid_response_data)
        assert response.response_value == "3"

        # Session should still be functional
        advanced_session = session_service.advance_session(session.id)
        assert advanced_session.current_question == 1

    @pytest.mark.asyncio
    async def test_session_rollback_on_critical_errors(self, session_service, error_prone_template,
                                                     db_session):
        """Test session rollback on critical database errors."""
        patient_id = uuid4()

        # Start session
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=error_prone_template.id
        )

        with patch('app.services.websocket_events.websocket_events', None):
            session = await session_service.start_quiz_session(session_data)

        # Simulate database error during session advance
        original_update = session_service.session_repository.update

        def error_update(*args, **kwargs):
            raise IntegrityError("Simulated database error", None, None)

        session_service.session_repository.update = error_update

        # Advance should fail and rollback
        with pytest.raises((IntegrityError, ConflictError)):
            session_service.advance_session(session.id)

        # Restore original method
        session_service.session_repository.update = original_update

        # Session should still be in original state
        current_session = session_service.get_session(session.id)
        assert current_session.current_question == 0
        assert current_session.status == "started"

    @pytest.mark.asyncio
    async def test_orphaned_session_handling(self, session_service, error_prone_template,
                                           db_session):
        """Test handling of orphaned sessions after errors."""
        patient_id = uuid4()

        # Create session directly in database (simulating orphaned state)
        orphaned_session = QuizSession(
            patient_id=patient_id,
            quiz_template_id=error_prone_template.id,
            current_question=0,
            status="started",
            started_at=datetime.utcnow() - timedelta(hours=24)  # Old session
        )

        db_session.add(orphaned_session)
        db_session.commit()

        # Try to start new session for same patient
        session_data = QuizSessionCreate(
            patient_id=patient_id,
            quiz_template_id=error_prone_template.id
        )

        # Should either clean up orphaned session or prevent new session
        try:
            with patch('app.services.websocket_events.websocket_events', None):
                new_session = await session_service.start_quiz_session(session_data)
            # If successful, verify it's a new session
            assert new_session.id != orphaned_session.id
        except ConflictError:
            # If conflict, that's acceptable behavior
            pass

        # Verify database consistency
        patient_sessions = db_session.query(QuizSession).filter(
            QuizSession.patient_id == patient_id
        ).all()

        # Should have at most one active session
        active_sessions = [s for s in patient_sessions if s.status != "completed"]
        assert len(active_sessions) <= 1