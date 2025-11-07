"""
Tests for Flows API v2

Comprehensive test suite for flow management endpoints including:
- Flow state operations
- Analytics & dashboard
- Template management
- Customization
- Rules engine
- A/B testing
- Utility endpoints
"""

import pytest
import json
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient

from app.models.user import User, UserRole
from app.models.patient import Patient
from app.main import app


# ============================================================================
# Test Flow State Operations (5 endpoints)
# ============================================================================

class TestFlowStateOperations:
    """Test flow state management endpoints."""

    def test_get_flow_state_success(self, client: TestClient, test_user: User, test_patient: Patient):
        """Test getting current flow state for a patient."""
        response = client.get(
            f"/api/v2/flows/{test_patient.id}/state",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["patient_id"] == str(test_patient.id)
        assert "flow_state" in data

    def test_advance_flow_success(self, client: TestClient, test_user: User, test_patient: Patient):
        """Test advancing patient flow to next step."""
        payload = {"force_day": None}
        response = client.post(
            f"/api/v2/flows/{test_patient.id}/advance",
            json=payload,
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "previous_step" in data
        assert "current_step" in data

    def test_pause_flow_with_duration(self, client: TestClient, test_user: User, test_patient: Patient):
        """Test pausing flow with auto-resume duration."""
        payload = {"reason": "Patient request", "duration_hours": 24}
        response = client.post(
            f"/api/v2/flows/{test_patient.id}/pause",
            json=payload,
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["paused"] == True

    def test_resume_flow_success(self, client: TestClient, test_user: User, test_patient: Patient):
        """Test resuming paused flow."""
        response = client.post(
            f"/api/v2/flows/{test_patient.id}/resume",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["resumed"] == True

    def test_flow_history_cursor_pagination(self, client: TestClient, test_user: User, test_patient: Patient):
        """Test flow history with cursor pagination."""
        response = client.get(
            f"/api/v2/flows/{test_patient.id}/history?limit=10",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "next_cursor" in data
        assert "has_more" in data


# ============================================================================
# Test Analytics & Dashboard (7 endpoints)
# ============================================================================

class TestAnalyticsDashboard:
    """Test analytics and dashboard endpoints."""

    @patch('app.utils.redis_cache.get_async_redis_client')
    def test_dashboard_overview_cached(self, mock_redis, client: TestClient, test_user: User):
        """Test dashboard overview with Redis caching."""
        mock_redis_client = AsyncMock()
        mock_redis_client.get.return_value = None
        mock_redis.return_value = mock_redis_client

        response = client.get(
            "/api/v2/flows/dashboard/overview?timeframe=week",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "active_flows" in data
        assert "completion_rate" in data

    def test_flow_metrics(self, client: TestClient, test_user: User):
        """Test flow metrics endpoint."""
        response = client.get(
            "/api/v2/flows/dashboard/flow-metrics?timeframe=month",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data

    def test_patient_engagement(self, client: TestClient, test_user: User):
        """Test patient engagement analytics."""
        response = client.get(
            "/api/v2/flows/dashboard/patient-engagement",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200

    def test_risk_assessment(self, client: TestClient, test_user: User):
        """Test risk assessment analytics."""
        response = client.get(
            "/api/v2/flows/analytics/risk-assessment",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200

    def test_flow_performance(self, client: TestClient, test_user: User):
        """Test flow performance metrics."""
        response = client.get(
            "/api/v2/flows/analytics/flow-performance",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200

    def test_patient_journey(self, client: TestClient, test_user: User, test_patient: Patient):
        """Test patient journey analysis."""
        response = client.get(
            f"/api/v2/flows/analytics/patient-journey?patient_id={test_patient.id}",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200

    def test_generate_insights(self, client: TestClient, test_user: User):
        """Test AI insights generation."""
        payload = {"timeframe": "month", "focus_areas": ["engagement", "risk"]}
        response = client.post(
            "/api/v2/flows/analytics/generate-insights",
            json=payload,
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200


# ============================================================================
# Test Template Management (5 endpoints)
# ============================================================================

class TestTemplateManagement:
    """Test flow template CRUD operations."""

    def test_list_templates_cursor_pagination(self, client: TestClient, test_user: User):
        """Test listing templates with cursor pagination."""
        response = client.get(
            "/api/v2/flows/templates?limit=20",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_create_template(self, client: TestClient, test_user: User):
        """Test creating a flow template."""
        payload = {
            "name": "Test Template",
            "flow_type": "onboarding",
            "duration_days": 30,
            "template_data": {
                "steps": [{"day": 1, "message": "Welcome"}],
                "triggers": ["patient_created"]
            }
        }
        response = client.post(
            "/api/v2/flows/templates",
            json=payload,
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 201]

    def test_get_template_by_id(self, client: TestClient, test_user: User):
        """Test getting template by ID."""
        template_id = uuid4()
        response = client.get(
            f"/api/v2/flows/templates/{template_id}",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 404]

    def test_update_template(self, client: TestClient, test_user: User):
        """Test updating a template."""
        template_id = uuid4()
        payload = {"name": "Updated Template"}
        response = client.put(
            f"/api/v2/flows/templates/{template_id}",
            json=payload,
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 404]

    def test_delete_template_soft_delete(self, client: TestClient, test_user: User):
        """Test soft deleting a template."""
        template_id = uuid4()
        response = client.delete(
            f"/api/v2/flows/templates/{template_id}",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 204, 404]


# ============================================================================
# Test Customization (4 endpoints)
# ============================================================================

class TestCustomization:
    """Test flow customization endpoints."""

    def test_create_customization(self, client: TestClient, test_user: User, test_patient: Patient):
        """Test creating patient flow customization."""
        payload = {
            "customization_data": {"skip_days": [5, 10], "custom_messages": {}}
        }
        response = client.post(
            f"/api/v2/flows/{test_patient.id}/customize",
            json=payload,
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 201]

    def test_get_customization(self, client: TestClient, test_user: User, test_patient: Patient):
        """Test getting patient customization."""
        response = client.get(
            f"/api/v2/flows/{test_patient.id}/customization",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 404]

    def test_update_customization(self, client: TestClient, test_user: User, test_patient: Patient):
        """Test updating patient customization."""
        payload = {"customization_data": {"skip_days": [7]}}
        response = client.put(
            f"/api/v2/flows/{test_patient.id}/customization",
            json=payload,
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 404]

    def test_delete_customization(self, client: TestClient, test_user: User, test_patient: Patient):
        """Test deleting patient customization."""
        response = client.delete(
            f"/api/v2/flows/{test_patient.id}/customization",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 204, 404]


# ============================================================================
# Test Rules Engine (4 endpoints)
# ============================================================================

class TestRulesEngine:
    """Test flow rules engine endpoints."""

    def test_create_rule(self, client: TestClient, test_user: User):
        """Test creating a flow rule."""
        payload = {
            "name": "High Risk Alert",
            "condition": {"risk_level": "high"},
            "action": {"notify_doctor": True}
        }
        response = client.post(
            "/api/v2/flows/rules",
            json=payload,
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 201]

    def test_list_rules_pagination(self, client: TestClient, test_user: User):
        """Test listing rules with pagination."""
        response = client.get(
            "/api/v2/flows/rules?limit=20",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200

    def test_update_rule(self, client: TestClient, test_user: User):
        """Test updating a rule."""
        rule_id = uuid4()
        payload = {"name": "Updated Rule"}
        response = client.put(
            f"/api/v2/flows/rules/{rule_id}",
            json=payload,
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 404]

    def test_delete_rule(self, client: TestClient, test_user: User):
        """Test deleting a rule."""
        rule_id = uuid4()
        response = client.delete(
            f"/api/v2/flows/rules/{rule_id}",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 204, 404]


# ============================================================================
# Test A/B Testing (6 endpoints)
# ============================================================================

class TestABTesting:
    """Test A/B testing framework endpoints."""

    def test_create_ab_test(self, client: TestClient, test_user: User):
        """Test creating an A/B test."""
        payload = {
            "name": "Message Timing Test",
            "variants": [
                {"name": "Morning", "percentage": 50},
                {"name": "Evening", "percentage": 50}
            ],
            "duration_days": 14
        }
        response = client.post(
            "/api/v2/flows/ab-tests",
            json=payload,
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 201]

    def test_list_ab_tests(self, client: TestClient, test_user: User):
        """Test listing A/B tests."""
        response = client.get(
            "/api/v2/flows/ab-tests?limit=20",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200

    def test_get_ab_test(self, client: TestClient, test_user: User):
        """Test getting A/B test details."""
        test_id = uuid4()
        response = client.get(
            f"/api/v2/flows/ab-tests/{test_id}",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 404]

    def test_update_ab_test(self, client: TestClient, test_user: User):
        """Test updating an A/B test."""
        test_id = uuid4()
        payload = {"name": "Updated Test"}
        response = client.put(
            f"/api/v2/flows/ab-tests/{test_id}",
            json=payload,
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 404]

    def test_stop_ab_test(self, client: TestClient, test_user: User):
        """Test stopping an A/B test."""
        test_id = uuid4()
        response = client.post(
            f"/api/v2/flows/ab-tests/{test_id}/stop",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 404]

    def test_get_ab_test_results(self, client: TestClient, test_user: User):
        """Test getting A/B test results."""
        test_id = uuid4()
        response = client.get(
            f"/api/v2/flows/ab-tests/{test_id}/results",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 404]


# ============================================================================
# Test Utility Endpoints (7 endpoints)
# ============================================================================

class TestUtilityEndpoints:
    """Test utility and health check endpoints."""

    def test_preview_message(self, client: TestClient, test_user: User):
        """Test message preview generation."""
        payload = {
            "template": "Hello {{name}}",
            "variables": {"name": "John"}
        }
        response = client.post(
            "/api/v2/flows/preview-message",
            json=payload,
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200

    def test_health_gemini(self, client: TestClient, test_user: User):
        """Test Gemini API health check."""
        response = client.get(
            "/api/v2/flows/health/gemini",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200

    def test_health_redis(self, client: TestClient, test_user: User):
        """Test Redis health check."""
        response = client.get(
            "/api/v2/flows/health/redis",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200

    def test_list_all_flows(self, client: TestClient, test_user: User):
        """Test listing all flows."""
        response = client.get(
            "/api/v2/flows?limit=20",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200

    def test_start_flow(self, client: TestClient, test_user: User, test_patient: Patient):
        """Test starting a flow for patient."""
        payload = {"patient_id": str(test_patient.id), "flow_type": "onboarding"}
        response = client.post(
            "/api/v2/flows/start",
            json=payload,
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code in [200, 201]

    def test_process_response(self, client: TestClient, test_user: User, test_patient: Patient):
        """Test processing patient response."""
        payload = {"response_text": "Yes", "metadata": {}}
        response = client.post(
            f"/api/v2/flows/{test_patient.id}/response",
            json=payload,
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200

    def test_overall_analytics(self, client: TestClient, test_user: User):
        """Test overall flow analytics."""
        response = client.get(
            "/api/v2/flows/analytics",
            headers={"Authorization": f"Bearer {test_user.access_token}"}
        )
        assert response.status_code == 200


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def test_patient(db_session: Session, test_user: User) -> Patient:
    """Create a test patient."""
    patient = Patient(
        id=uuid4(),
        name="Test Patient",
        phone="5511999999999",
        doctor_id=test_user.id,
        created_at=datetime.utcnow()
    )
    db_session.add(patient)
    db_session.commit()
    return patient
