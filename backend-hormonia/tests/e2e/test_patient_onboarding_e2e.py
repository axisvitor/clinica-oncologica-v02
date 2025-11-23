"""
E2E-001: Patient Onboarding Complete Flow
Tests: register → verify → quiz → flow activation
"""
import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.flow import Flow, FlowState
from app.models.quiz import Quiz


@pytest.mark.asyncio
class TestPatientOnboardingE2E:
    """E2E tests for complete patient onboarding journey"""

    async def test_complete_onboarding_flow(
        self,
        async_client: AsyncClient,
        db_session: Session,
        auth_headers_admin: dict
    ):
        """
        Test complete patient onboarding flow:
        1. Admin creates patient
        2. Patient receives welcome message
        3. Patient is assigned to monthly quiz flow
        4. Flow state is tracked correctly
        """
        # Step 1: Create patient via API
        patient_data = {
            "name": "Maria Silva",
            "email": "maria.silva@test.com",
            "phone": "+5511999999999",
            "cpf": "123.456.789-00",
            "birth_date": "1985-05-15",
            "gender": "F",
            "metadata": {
                "treatment_type": "Hormonal",
                "diagnosis_date": "2024-01-15"
            }
        }

        response = await async_client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=auth_headers_admin
        )

        assert response.status_code == 201
        patient_response = response.json()
        assert patient_response["email"] == patient_data["email"]
        patient_id = patient_response["id"]

        # Step 2: Verify patient created in database
        patient = db_session.query(Patient).filter_by(id=patient_id).first()
        assert patient is not None
        assert patient.email == patient_data["email"]
        assert patient.is_active is True

        # Step 3: Check flow auto-creation
        # Simulating flow creation trigger
        response = await async_client.post(
            f"/api/v2/flows",
            json={
                "patient_id": patient_id,
                "flow_type": "monthly_quiz",
                "metadata": {
                    "onboarding": True
                }
            },
            headers=auth_headers_admin
        )

        assert response.status_code == 201
        flow_data = response.json()

        # Step 4: Verify flow state
        flow = db_session.query(Flow).filter_by(patient_id=patient_id).first()
        assert flow is not None
        assert flow.state == FlowState.ACTIVE
        assert flow.flow_type == "monthly_quiz"

        # Step 5: Assign first quiz
        response = await async_client.post(
            f"/api/v2/quiz/assign",
            json={
                "patient_id": patient_id,
                "template_id": 1,
                "send_notification": True
            },
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        quiz_data = response.json()

        # Step 6: Verify quiz assigned
        quiz = db_session.query(Quiz).filter_by(patient_id=patient_id).first()
        assert quiz is not None
        assert quiz.status == "pending"

        # Step 7: Verify flow updated
        db_session.refresh(flow)
        assert flow.current_step == "quiz_sent"

    async def test_onboarding_with_verification(
        self,
        async_client: AsyncClient,
        db_session: Session,
        auth_headers_admin: dict
    ):
        """
        Test onboarding with email verification:
        1. Create patient
        2. Send verification email
        3. Verify email
        4. Activate account
        """
        # Create patient
        response = await async_client.post(
            "/api/v2/patients",
            json={
                "name": "João Santos",
                "email": "joao.santos@test.com",
                "phone": "+5511988888888",
                "cpf": "987.654.321-00",
                "birth_date": "1990-10-20",
                "gender": "M"
            },
            headers=auth_headers_admin
        )

        assert response.status_code == 201
        patient_id = response.json()["id"]

        # Send verification (mocked)
        response = await async_client.post(
            f"/api/v2/patients/{patient_id}/send-verification",
            headers=auth_headers_admin
        )

        assert response.status_code == 200
        verification_data = response.json()
        assert "verification_token" in verification_data

        # Verify email
        token = verification_data["verification_token"]
        response = await async_client.post(
            f"/api/v2/patients/verify-email",
            json={"token": token}
        )

        assert response.status_code == 200

        # Check patient verified
        patient = db_session.query(Patient).filter_by(id=patient_id).first()
        assert patient.metadata_.get("email_verified") is True

    async def test_onboarding_failure_duplicate_email(
        self,
        async_client: AsyncClient,
        patient_user: Patient,
        auth_headers_admin: dict
    ):
        """Test onboarding fails with duplicate email"""
        response = await async_client.post(
            "/api/v2/patients",
            json={
                "name": "Duplicate Test",
                "email": patient_user.email,  # Same email
                "phone": "+5511977777777",
                "cpf": "111.222.333-44",
                "birth_date": "1980-01-01",
                "gender": "F"
            },
            headers=auth_headers_admin
        )

        assert response.status_code == 409
        error = response.json()
        assert "already exists" in error["detail"].lower()

    async def test_onboarding_with_invalid_data(
        self,
        async_client: AsyncClient,
        auth_headers_admin: dict
    ):
        """Test onboarding fails with invalid data"""
        # Invalid email
        response = await async_client.post(
            "/api/v2/patients",
            json={
                "name": "Invalid Email",
                "email": "invalid-email",
                "phone": "+5511966666666",
                "cpf": "444.555.666-77",
                "birth_date": "1975-06-30",
                "gender": "F"
            },
            headers=auth_headers_admin
        )

        assert response.status_code == 422

        # Missing required fields
        response = await async_client.post(
            "/api/v2/patients",
            json={
                "name": "Missing Fields",
                "email": "missing@test.com"
                # Missing phone, cpf, etc.
            },
            headers=auth_headers_admin
        )

        assert response.status_code == 422
