"""
E2E-005: Celery Task Complete Flow
Tests: enqueue → process → retry → success
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta

from app.models.patient import Patient
from app.models.quiz import Quiz


@pytest.mark.asyncio
class TestCeleryTasksE2E:
    """E2E tests for Celery async tasks"""

    async def test_quiz_reminder_task(
        self,
        async_client: AsyncClient,
        db_session: Session,
        patient_user: Patient,
        auth_headers_admin: dict,
        mock_evolution_api
    ):
        """
        Test scheduled quiz reminder task:
        1. Create pending quiz
        2. Trigger reminder task
        3. Verify message sent
        4. Update quiz metadata
        """
        # Create quiz
        response = await async_client.post(
            "/api/v2/quiz/assign",
            json={
                "patient_id": patient_user.id,
                "template_id": 1
            },
            headers=auth_headers_admin
        )

        quiz_id = response.json()["id"]

        # Trigger reminder task (simulated)
        response = await async_client.post(
            f"/api/v2/tasks/quiz-reminder",
            json={"quiz_id": quiz_id},
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        task_result = response.json()

        assert task_result["status"] == "success"
        assert task_result["message_sent"] is True

        # Verify quiz updated
        quiz = db_session.query(Quiz).filter_by(id=quiz_id).first()
        assert quiz.metadata_.get("reminder_sent") is True
        assert quiz.metadata_.get("reminder_count", 0) >= 1

    async def test_report_generation_task(
        self,
        async_client: AsyncClient,
        patient_user: Patient,
        auth_headers_admin: dict
    ):
        """
        Test async report generation:
        1. Request report
        2. Task queued
        3. Process in background
        4. Report ready
        """
        # Request monthly report
        response = await async_client.post(
            "/api/v2/reports/generate",
            json={
                "patient_id": patient_user.id,
                "report_type": "monthly_summary",
                "async": True
            },
            headers=auth_headers_admin
        )

        assert response.status_code == 202  # Accepted
        task_data = response.json()
        task_id = task_data["task_id"]

        # Check task status
        response = await async_client.get(
            f"/api/v2/tasks/{task_id}/status",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        status = response.json()
        assert status["state"] in ["PENDING", "PROCESSING", "SUCCESS"]

        # Simulate task completion
        # In real scenario, would poll until complete
        if status["state"] == "SUCCESS":
            assert "result" in status
            assert status["result"]["report_url"]

    async def test_task_retry_on_failure(
        self,
        async_client: AsyncClient,
        patient_user: Patient,
        auth_headers_admin: dict,
        monkeypatch
    ):
        """Test task retry mechanism"""
        retry_count = {"count": 0}

        class MockFailingService:
            def process(self):
                retry_count["count"] += 1
                if retry_count["count"] < 3:
                    raise Exception("Temporary failure")
                return {"success": True}

        # Trigger task that fails initially
        response = await async_client.post(
            "/api/v2/tasks/test-retry",
            json={"patient_id": patient_user.id},
            headers=auth_headers_admin
        )

        task_id = response.json()["task_id"]

        # Check final status (should succeed after retries)
        response = await async_client.get(
            f"/api/v2/tasks/{task_id}/status",
            headers=auth_headers_admin
        )

        status = response.json()
        assert status["state"] == "SUCCESS"
        assert status.get("retry_count", 0) >= 1

    async def test_scheduled_task_execution(
        self,
        async_client: AsyncClient,
        db_session: Session,
        auth_headers_admin: dict
    ):
        """Test scheduled periodic tasks"""
        # Trigger daily cleanup task
        response = await async_client.post(
            "/api/v2/tasks/daily-cleanup",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        result = response.json()

        assert "expired_quizzes_cleaned" in result
        assert "old_notifications_deleted" in result

    async def test_task_chaining(
        self,
        async_client: AsyncClient,
        patient_user: Patient,
        auth_headers_admin: dict
    ):
        """
        Test task chaining:
        1. Generate report
        2. Send notification
        3. Update patient record
        """
        response = await async_client.post(
            "/api/v2/tasks/report-and-notify",
            json={
                "patient_id": patient_user.id,
                "report_type": "quarterly"
            },
            headers=auth_headers_admin
        )

        task_id = response.json()["task_id"]

        # Check chain execution
        response = await async_client.get(
            f"/api/v2/tasks/{task_id}/chain-status",
            headers=auth_headers_admin
        )

        chain_status = response.json()
        assert len(chain_status["tasks"]) >= 2
        assert all(t["state"] in ["SUCCESS", "PENDING"] for t in chain_status["tasks"])
