"""
Tests for QuizFlowIntegration - Quiz service integration testing.

This module tests the integration between flow system and quiz service,
including quiz flow creation, monitoring, and result processing.
"""

import pytest
from typing import Dict, Any
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from app.services.flow.integrations.quiz_integration import QuizFlowIntegration
from app.services.flow.types import FlowType


class TestQuizFlowIntegrationCreation:
    """Test suite for quiz flow creation."""

    @pytest.fixture
    def integration(self) -> QuizFlowIntegration:
        """Create integration instance."""
        return QuizFlowIntegration()

    @pytest.fixture
    def patient_id(self) -> UUID:
        """Create test patient ID."""
        return uuid4()

    def test_create_quiz_flow_success(
        self, integration: QuizFlowIntegration, patient_id: UUID
    ):
        """Test successful quiz flow creation."""
        # Act
        result = integration.create_quiz_flow(
            patient_id=patient_id,
            quiz_type="monthly",
            quiz_data={"category": "symptoms"},
        )

        # Assert
        assert result is not None
        assert "quiz_id" in result
        assert "flow_instance_id" in result
        assert result["patient_id"] == patient_id
        assert result["quiz_type"] == "monthly"
        assert result["status"] == "pending"

    def test_create_quiz_flow_maps_to_flow_type(
        self, integration: QuizFlowIntegration, patient_id: UUID
    ):
        """Test quiz type maps to correct flow type."""
        # Act
        result = integration.create_quiz_flow(
            patient_id=patient_id, quiz_type="monthly"
        )

        # Assert
        assert result["flow_type"] == FlowType.MONTHLY_QUIZ.value

    def test_create_quiz_flow_stores_mappings(
        self, integration: QuizFlowIntegration, patient_id: UUID
    ):
        """Test quiz flow creation stores ID mappings."""
        # Act
        result = integration.create_quiz_flow(
            patient_id=patient_id, quiz_type="monthly"
        )

        quiz_id = result["quiz_id"]
        flow_id = result["flow_instance_id"]

        # Assert
        assert flow_id in integration._flow_to_quiz
        assert quiz_id in integration._quiz_to_flow
        assert integration._flow_to_quiz[flow_id] == quiz_id
        assert integration._quiz_to_flow[quiz_id] == flow_id

    def test_create_quiz_flow_sets_expiration(
        self, integration: QuizFlowIntegration, patient_id: UUID
    ):
        """Test quiz flow has expiration time set."""
        # Act
        result = integration.create_quiz_flow(
            patient_id=patient_id, quiz_type="monthly"
        )

        # Assert
        assert "expires_at" in result
        assert result["expires_at"] > result["created_at"]

    def test_create_quiz_flow_different_types(
        self, integration: QuizFlowIntegration, patient_id: UUID
    ):
        """Test creating quiz flows of different types."""
        quiz_types = ["monthly", "symptom", "onboarding"]

        for quiz_type in quiz_types:
            # Act
            result = integration.create_quiz_flow(
                patient_id=patient_id, quiz_type=quiz_type
            )

            # Assert
            assert result["quiz_type"] == quiz_type
            assert result["status"] == "pending"


class TestQuizFlowIntegrationRetrieval:
    """Test suite for quiz flow retrieval."""

    @pytest.fixture
    def integration(self) -> QuizFlowIntegration:
        """Create integration instance."""
        return QuizFlowIntegration()

    @pytest.fixture
    def patient_id(self) -> UUID:
        """Create test patient ID."""
        return uuid4()

    @pytest.fixture
    def created_quiz_flow(
        self, integration: QuizFlowIntegration, patient_id: UUID
    ) -> Dict[str, Any]:
        """Create a quiz flow for testing."""
        return integration.create_quiz_flow(
            patient_id=patient_id,
            quiz_type="monthly",
            quiz_data={"test": "data"},
        )

    def test_get_quiz_flow_by_id_found(
        self,
        integration: QuizFlowIntegration,
        created_quiz_flow: Dict[str, Any],
    ):
        """Test getting quiz flow by ID."""
        # Act
        result = integration.get_quiz_flow(created_quiz_flow["quiz_id"])

        # Assert
        assert result is not None
        assert result["quiz_id"] == created_quiz_flow["quiz_id"]

    def test_get_quiz_flow_by_id_not_found(self, integration: QuizFlowIntegration):
        """Test getting non-existent quiz flow returns None."""
        # Act
        result = integration.get_quiz_flow(uuid4())

        # Assert
        assert result is None

    def test_get_flow_by_quiz_id(
        self,
        integration: QuizFlowIntegration,
        created_quiz_flow: Dict[str, Any],
    ):
        """Test getting flow ID from quiz ID."""
        # Act
        flow_id = integration.get_flow_by_quiz_id(created_quiz_flow["quiz_id"])

        # Assert
        assert flow_id == created_quiz_flow["flow_instance_id"]

    def test_get_quiz_by_flow_id(
        self,
        integration: QuizFlowIntegration,
        created_quiz_flow: Dict[str, Any],
    ):
        """Test getting quiz ID from flow ID."""
        # Act
        quiz_id = integration.get_quiz_by_flow_id(created_quiz_flow["flow_instance_id"])

        # Assert
        assert quiz_id == created_quiz_flow["quiz_id"]


class TestQuizFlowIntegrationStatus:
    """Test suite for quiz flow status management."""

    @pytest.fixture
    def integration(self) -> QuizFlowIntegration:
        """Create integration instance."""
        return QuizFlowIntegration()

    @pytest.fixture
    def patient_id(self) -> UUID:
        """Create test patient ID."""
        return uuid4()

    @pytest.fixture
    def created_quiz_flow(
        self, integration: QuizFlowIntegration, patient_id: UUID
    ) -> Dict[str, Any]:
        """Create a quiz flow for testing."""
        return integration.create_quiz_flow(patient_id=patient_id, quiz_type="monthly")

    def test_start_quiz_flow(
        self,
        integration: QuizFlowIntegration,
        created_quiz_flow: Dict[str, Any],
    ):
        """Test starting a quiz flow."""
        # Act
        result = integration.start_quiz_flow(created_quiz_flow["quiz_id"])

        # Assert
        assert result is not None
        assert result["status"] == "in_progress"

    def test_complete_quiz_flow(
        self,
        integration: QuizFlowIntegration,
        created_quiz_flow: Dict[str, Any],
    ):
        """Test completing a quiz flow."""
        # Arrange
        integration.start_quiz_flow(created_quiz_flow["quiz_id"])

        # Act
        result = integration.complete_quiz_flow(
            created_quiz_flow["quiz_id"],
            results={"score": 85, "answers": []},
        )

        # Assert
        assert result is not None
        assert result["status"] == "completed"
        assert "results" in result

    def test_cancel_quiz_flow(
        self,
        integration: QuizFlowIntegration,
        created_quiz_flow: Dict[str, Any],
    ):
        """Test canceling a quiz flow."""
        # Act
        result = integration.cancel_quiz_flow(created_quiz_flow["quiz_id"])

        # Assert
        assert result is not None
        assert result["status"] == "cancelled"


class TestQuizFlowIntegrationResponses:
    """Test suite for quiz response handling."""

    @pytest.fixture
    def integration(self) -> QuizFlowIntegration:
        """Create integration instance."""
        return QuizFlowIntegration()

    @pytest.fixture
    def patient_id(self) -> UUID:
        """Create test patient ID."""
        return uuid4()

    @pytest.fixture
    def active_quiz_flow(
        self, integration: QuizFlowIntegration, patient_id: UUID
    ) -> Dict[str, Any]:
        """Create and start a quiz flow."""
        quiz_flow = integration.create_quiz_flow(
            patient_id=patient_id, quiz_type="monthly"
        )
        return integration.start_quiz_flow(quiz_flow["quiz_id"])

    def test_record_quiz_response(
        self,
        integration: QuizFlowIntegration,
        active_quiz_flow: Dict[str, Any],
    ):
        """Test recording a quiz response."""
        # Arrange
        response_data = {
            "question_id": "q1",
            "answer": "Yes",
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Act
        result = integration.record_response(active_quiz_flow["quiz_id"], response_data)

        # Assert
        assert result is True

    def test_get_quiz_responses(
        self,
        integration: QuizFlowIntegration,
        active_quiz_flow: Dict[str, Any],
    ):
        """Test getting all responses for a quiz."""
        # Arrange
        response1 = {"question_id": "q1", "answer": "Yes"}
        response2 = {"question_id": "q2", "answer": "No"}

        integration.record_response(active_quiz_flow["quiz_id"], response1)
        integration.record_response(active_quiz_flow["quiz_id"], response2)

        # Act
        responses = integration.get_responses(active_quiz_flow["quiz_id"])

        # Assert
        assert len(responses) == 2
        assert responses[0]["question_id"] == "q1"
        assert responses[1]["question_id"] == "q2"


class TestQuizFlowIntegrationReminders:
    """Test suite for quiz reminder management."""

    @pytest.fixture
    def integration(self) -> QuizFlowIntegration:
        """Create integration instance."""
        return QuizFlowIntegration()

    @pytest.fixture
    def patient_id(self) -> UUID:
        """Create test patient ID."""
        return uuid4()

    @pytest.fixture
    def created_quiz_flow(
        self, integration: QuizFlowIntegration, patient_id: UUID
    ) -> Dict[str, Any]:
        """Create a quiz flow for testing."""
        return integration.create_quiz_flow(patient_id=patient_id, quiz_type="monthly")

    def test_schedule_reminder(
        self,
        integration: QuizFlowIntegration,
        created_quiz_flow: Dict[str, Any],
    ):
        """Test scheduling a quiz reminder."""
        # Arrange
        remind_at = datetime.utcnow() + timedelta(hours=24)

        # Act
        result = integration.schedule_reminder(
            created_quiz_flow["quiz_id"],
            remind_at=remind_at,
            message="Please complete your monthly quiz",
        )

        # Assert
        assert result is not None
        assert "reminder_id" in result

    def test_cancel_reminder(
        self,
        integration: QuizFlowIntegration,
        created_quiz_flow: Dict[str, Any],
    ):
        """Test canceling a scheduled reminder."""
        # Arrange
        remind_at = datetime.utcnow() + timedelta(hours=24)
        reminder = integration.schedule_reminder(
            created_quiz_flow["quiz_id"], remind_at=remind_at
        )

        # Act
        result = integration.cancel_reminder(reminder["reminder_id"])

        # Assert
        assert result is True

    def test_get_pending_reminders(
        self,
        integration: QuizFlowIntegration,
        created_quiz_flow: Dict[str, Any],
    ):
        """Test getting pending reminders."""
        # Arrange
        remind_at = datetime.utcnow() + timedelta(hours=24)
        integration.schedule_reminder(created_quiz_flow["quiz_id"], remind_at=remind_at)

        # Act
        reminders = integration.get_pending_reminders()

        # Assert
        assert len(reminders) >= 1


class TestQuizFlowIntegrationExpiration:
    """Test suite for quiz flow expiration handling."""

    @pytest.fixture
    def integration(self) -> QuizFlowIntegration:
        """Create integration instance."""
        return QuizFlowIntegration()

    @pytest.fixture
    def patient_id(self) -> UUID:
        """Create test patient ID."""
        return uuid4()

    def test_check_expired_flows(
        self, integration: QuizFlowIntegration, patient_id: UUID
    ):
        """Test checking for expired quiz flows."""
        # Arrange - create a quiz flow
        quiz_flow = integration.create_quiz_flow(
            patient_id=patient_id, quiz_type="monthly"
        )

        # Manually set expiration in the past
        quiz_flow["expires_at"] = datetime.utcnow() - timedelta(hours=1)
        integration._quiz_flows[quiz_flow["quiz_id"]] = quiz_flow

        # Act
        expired = integration.get_expired_flows()

        # Assert
        assert len(expired) >= 1
        assert quiz_flow["quiz_id"] in [q["quiz_id"] for q in expired]

    def test_cleanup_expired_flows(
        self, integration: QuizFlowIntegration, patient_id: UUID
    ):
        """Test cleanup of expired quiz flows."""
        # Arrange - create expired quiz flow
        quiz_flow = integration.create_quiz_flow(
            patient_id=patient_id, quiz_type="monthly"
        )
        quiz_flow["expires_at"] = datetime.utcnow() - timedelta(hours=1)
        integration._quiz_flows[quiz_flow["quiz_id"]] = quiz_flow

        # Act
        cleaned_count = integration.cleanup_expired_flows()

        # Assert
        assert cleaned_count >= 1
        assert quiz_flow["quiz_id"] not in integration._quiz_flows


class TestQuizFlowIntegrationStatistics:
    """Test suite for quiz flow statistics."""

    @pytest.fixture
    def integration(self) -> QuizFlowIntegration:
        """Create integration instance."""
        return QuizFlowIntegration()

    @pytest.fixture
    def patient_id(self) -> UUID:
        """Create test patient ID."""
        return uuid4()

    def test_get_statistics_empty(self, integration: QuizFlowIntegration):
        """Test getting statistics with no quiz flows."""
        # Act
        stats = integration.get_statistics()

        # Assert
        assert stats is not None
        assert stats["total_quiz_flows"] == 0

    def test_get_statistics_with_flows(
        self, integration: QuizFlowIntegration, patient_id: UUID
    ):
        """Test getting statistics with quiz flows."""
        # Arrange - create multiple quiz flows
        for i in range(3):
            quiz_flow = integration.create_quiz_flow(
                patient_id=patient_id, quiz_type="monthly"
            )
            if i == 0:
                integration.complete_quiz_flow(quiz_flow["quiz_id"], results={})

        # Act
        stats = integration.get_statistics()

        # Assert
        assert stats["total_quiz_flows"] == 3
        assert stats["completed_flows"] >= 1
        assert stats["pending_flows"] >= 2

    def test_get_patient_quiz_history(
        self, integration: QuizFlowIntegration, patient_id: UUID
    ):
        """Test getting quiz history for a patient."""
        # Arrange - create quiz flows
        for _ in range(2):
            integration.create_quiz_flow(patient_id=patient_id, quiz_type="monthly")

        # Act
        history = integration.get_patient_quiz_history(patient_id)

        # Assert
        assert len(history) == 2
        assert all(q["patient_id"] == patient_id for q in history)


class TestQuizFlowIntegrationErrorHandling:
    """Test suite for error handling."""

    @pytest.fixture
    def integration(self) -> QuizFlowIntegration:
        """Create integration instance."""
        return QuizFlowIntegration()

    def test_start_nonexistent_quiz_flow(self, integration: QuizFlowIntegration):
        """Test starting non-existent quiz flow raises error."""
        # Act & Assert
        with pytest.raises(ValueError, match="Quiz flow not found"):
            integration.start_quiz_flow(uuid4())

    def test_complete_nonexistent_quiz_flow(self, integration: QuizFlowIntegration):
        """Test completing non-existent quiz flow raises error."""
        # Act & Assert
        with pytest.raises(ValueError, match="Quiz flow not found"):
            integration.complete_quiz_flow(uuid4(), results={})

    def test_record_response_for_nonexistent_quiz(
        self, integration: QuizFlowIntegration
    ):
        """Test recording response for non-existent quiz raises error."""
        # Act & Assert
        with pytest.raises(ValueError, match="Quiz flow not found"):
            integration.record_response(uuid4(), {"answer": "test"})

    def test_integration_disabled_raises_error(self, integration: QuizFlowIntegration):
        """Test operations when integration is disabled."""
        # Arrange
        integration.config.enable_quiz_integration = False

        # Act & Assert
        with pytest.raises(RuntimeError, match="Quiz integration is disabled"):
            integration.create_quiz_flow(patient_id=uuid4(), quiz_type="monthly")
