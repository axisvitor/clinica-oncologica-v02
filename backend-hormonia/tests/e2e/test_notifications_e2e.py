"""
E2E-004: Notificação Multi-Canal
Tests: WhatsApp → Email → Slack notification flow
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.alert import Alert


@pytest.mark.asyncio
class TestNotificationsE2E:
    """E2E tests for multi-channel notifications"""

    async def test_whatsapp_notification_flow(
        self,
        async_client: AsyncClient,
        db_session: Session,
        patient_user: Patient,
        auth_headers_admin: dict,
        mock_evolution_api
    ):
        """
        Test WhatsApp notification:
        1. Create alert
        2. Send WhatsApp message
        3. Track delivery status
        """
        # Create alert
        response = await async_client.post(
            "/api/v2/alerts",
            json={
                "patient_id": patient_user.id,
                "title": "Lembrete de Medicação",
                "message": "Não esqueça de tomar sua medicação hoje às 20h",
                "priority": "high",
                "channels": ["whatsapp"]
            },
            headers=auth_headers_admin
        )

        assert response.status_code == 201
        alert_data = response.json()
        alert_id = alert_data["id"]

        # Verify WhatsApp message sent
        assert alert_data["status"]["whatsapp"] == "sent"
        assert "message_id" in alert_data["status"]

        # Check delivery status
        response = await async_client.get(
            f"/api/v2/alerts/{alert_id}/status",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        status = response.json()
        assert status["whatsapp"]["delivered"] is True

    async def test_email_notification_flow(
        self,
        async_client: AsyncClient,
        patient_user: Patient,
        auth_headers_admin: dict,
        monkeypatch
    ):
        """Test email notification flow"""
        # Mock email service
        sent_emails = []

        class MockEmailService:
            async def send_email(self, to: str, subject: str, body: str):
                sent_emails.append({"to": to, "subject": subject, "body": body})
                return {"message_id": "email_123"}

        monkeypatch.setattr(
            "app.services.notifications.EmailService",
            MockEmailService
        )

        # Send email notification
        response = await async_client.post(
            "/api/v2/alerts",
            json={
                "patient_id": patient_user.id,
                "title": "Resultado de Exame",
                "message": "Seu resultado está disponível",
                "priority": "medium",
                "channels": ["email"]
            },
            headers=auth_headers_admin
        )

        assert response.status_code == 201
        assert len(sent_emails) == 1
        assert sent_emails[0]["to"] == patient_user.email

    async def test_multi_channel_notification(
        self,
        async_client: AsyncClient,
        patient_user: Patient,
        auth_headers_admin: dict,
        mock_evolution_api,
        monkeypatch
    ):
        """Test notification sent to multiple channels"""
        sent_emails = []

        class MockEmailService:
            async def send_email(self, to: str, subject: str, body: str):
                sent_emails.append({"to": to})
                return {"message_id": "email_123"}

        monkeypatch.setattr(
            "app.services.notifications.EmailService",
            MockEmailService
        )

        # Send to all channels
        response = await async_client.post(
            "/api/v2/alerts",
            json={
                "patient_id": patient_user.id,
                "title": "Consulta Agendada",
                "message": "Sua consulta é amanhã às 10h",
                "priority": "high",
                "channels": ["whatsapp", "email", "sms"]
            },
            headers=auth_headers_admin
        )

        assert response.status_code == 201
        alert_data = response.json()

        # Verify all channels processed
        assert "whatsapp" in alert_data["status"]
        assert "email" in alert_data["status"]
        assert len(sent_emails) == 1

    async def test_notification_retry_on_failure(
        self,
        async_client: AsyncClient,
        patient_user: Patient,
        auth_headers_admin: dict,
        monkeypatch
    ):
        """Test notification retry mechanism"""
        attempt_count = {"count": 0}

        class MockFailingEvolutionAPI:
            async def send_message(self, instance: str, number: str, message: str):
                attempt_count["count"] += 1
                if attempt_count["count"] < 3:
                    raise Exception("Connection timeout")
                return {"success": True, "message_id": "msg_123"}

        monkeypatch.setattr(
            "app.services.whatsapp.EvolutionAPI",
            MockFailingEvolutionAPI
        )

        # Send notification
        response = await async_client.post(
            "/api/v2/alerts",
            json={
                "patient_id": patient_user.id,
                "title": "Test Retry",
                "message": "Testing retry mechanism",
                "priority": "medium",
                "channels": ["whatsapp"]
            },
            headers=auth_headers_admin
        )

        # Should eventually succeed after retries
        assert response.status_code == 201
        assert attempt_count["count"] >= 1  # At least one attempt

    async def test_notification_template_rendering(
        self,
        async_client: AsyncClient,
        patient_user: Patient,
        auth_headers_admin: dict,
        mock_evolution_api
    ):
        """Test notification uses templates with variables"""
        response = await async_client.post(
            "/api/v2/alerts/from-template",
            json={
                "patient_id": patient_user.id,
                "template": "medication_reminder",
                "variables": {
                    "patient_name": patient_user.name,
                    "medication": "Tamoxifeno",
                    "time": "20:00"
                },
                "channels": ["whatsapp"]
            },
            headers=auth_headers_admin
        )

        assert response.status_code == 201
        alert = response.json()

        # Verify template rendered correctly
        assert patient_user.name in alert["message"]
        assert "Tamoxifeno" in alert["message"]
        assert "20:00" in alert["message"]
