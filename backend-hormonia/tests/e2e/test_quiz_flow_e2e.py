"""
E2E-002: Quiz Mensal Flow Complete
Tests: send link → complete → generate report
"""
import pytest
from datetime import datetime
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.quiz import Quiz, QuizResponse, QuizTemplate
from app.models.flow import Flow


@pytest.mark.asyncio
class TestQuizFlowE2E:
    """E2E tests for monthly quiz complete flow"""

    async def test_complete_quiz_flow(
        self,
        async_client: AsyncClient,
        db_session: Session,
        patient_user: Patient,
        quiz_template: QuizTemplate,
        active_flow: Flow,
        auth_headers_admin: dict,
        mock_evolution_api
    ):
        """
        Test complete quiz flow:
        1. Send quiz link via WhatsApp
        2. Patient completes quiz
        3. Generate report
        4. Update flow state
        """
        # Step 1: Send quiz link
        response = await async_client.post(
            "/api/v2/quiz/send-link",
            json={
                "patient_id": patient_user.id,
                "template_id": quiz_template.id,
                "send_via": "whatsapp"
            },
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        quiz_data = response.json()
        quiz_id = quiz_data["quiz_id"]
        quiz_link = quiz_data["link"]

        # Verify quiz created
        quiz = db_session.query(Quiz).filter_by(id=quiz_id).first()
        assert quiz is not None
        assert quiz.status == "pending"

        # Step 2: Patient accesses quiz (public endpoint)
        # Extract token from link
        quiz_token = quiz_link.split("/")[-1]

        response = await async_client.get(
            f"/api/v2/quiz/public/{quiz_token}"
        )

        assert response.status_code == 200
        quiz_public = response.json()
        assert quiz_public["template"]["title"] == quiz_template.title

        # Step 3: Submit quiz responses
        responses = {
            "q1": "4",
            "q2": "Fadiga"
        }

        response = await async_client.post(
            f"/api/v2/quiz/public/{quiz_token}/submit",
            json={"responses": responses}
        )

        assert response.status_code == 200

        # Verify quiz completed
        db_session.refresh(quiz)
        assert quiz.status == "completed"
        assert quiz.completed_at is not None

        # Step 4: Generate report
        response = await async_client.post(
            f"/api/v2/quiz/{quiz_id}/generate-report",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        report = response.json()
        assert report["quiz_id"] == quiz_id
        assert "analysis" in report

        # Step 5: Verify flow updated
        db_session.refresh(active_flow)
        assert active_flow.current_step == "quiz_completed"

    async def test_quiz_reminder_flow(
        self,
        async_client: AsyncClient,
        db_session: Session,
        patient_user: Patient,
        quiz_template: QuizTemplate,
        auth_headers_admin: dict,
        mock_evolution_api
    ):
        """
        Test quiz reminder flow:
        1. Send quiz
        2. No response after 3 days
        3. Send reminder
        """
        # Create quiz
        response = await async_client.post(
            "/api/v2/quiz/assign",
            json={
                "patient_id": patient_user.id,
                "template_id": quiz_template.id
            },
            headers=auth_headers_admin
        )

        quiz_id = response.json()["id"]

        # Simulate time passing (would be Celery task)
        response = await async_client.post(
            f"/api/v2/quiz/{quiz_id}/send-reminder",
            headers=auth_headers_admin
        )

        assert response.status_code == 200

        # Verify reminder sent
        quiz = db_session.query(Quiz).filter_by(id=quiz_id).first()
        assert quiz.metadata_.get("reminder_sent") is True

    async def test_quiz_expiration(
        self,
        async_client: AsyncClient,
        db_session: Session,
        patient_user: Patient,
        quiz_template: QuizTemplate,
        auth_headers_admin: dict
    ):
        """Test quiz expires after deadline"""
        # Create quiz with short deadline
        response = await async_client.post(
            "/api/v2/quiz/assign",
            json={
                "patient_id": patient_user.id,
                "template_id": quiz_template.id,
                "deadline_days": 1
            },
            headers=auth_headers_admin
        )

        quiz_id = response.json()["id"]

        # Try to access expired quiz (simulated)
        quiz = db_session.query(Quiz).filter_by(id=quiz_id).first()
        quiz.status = "expired"
        db_session.commit()

        response = await async_client.get(
            f"/api/v2/quiz/public/{quiz.token}"
        )

        assert response.status_code == 410  # Gone

    async def test_quiz_partial_save(
        self,
        async_client: AsyncClient,
        db_session: Session,
        patient_user: Patient,
        quiz_template: QuizTemplate,
        auth_headers_admin: dict
    ):
        """Test quiz can be saved partially and resumed"""
        # Create quiz
        response = await async_client.post(
            "/api/v2/quiz/assign",
            json={
                "patient_id": patient_user.id,
                "template_id": quiz_template.id
            },
            headers=auth_headers_admin
        )

        quiz_token = response.json()["token"]

        # Save partial responses
        partial_responses = {
            "q1": "3"
            # q2 not answered yet
        }

        response = await async_client.post(
            f"/api/v2/quiz/public/{quiz_token}/save",
            json={"responses": partial_responses}
        )

        assert response.status_code == 200

        # Retrieve quiz state
        response = await async_client.get(
            f"/api/v2/quiz/public/{quiz_token}"
        )

        assert response.status_code == 200
        quiz_state = response.json()
        assert quiz_state["saved_responses"]["q1"] == "3"
        assert quiz_state["status"] == "in_progress"

        # Complete quiz
        full_responses = {
            "q1": "3",
            "q2": "Nenhum"
        }

        response = await async_client.post(
            f"/api/v2/quiz/public/{quiz_token}/submit",
            json={"responses": full_responses}
        )

        assert response.status_code == 200
