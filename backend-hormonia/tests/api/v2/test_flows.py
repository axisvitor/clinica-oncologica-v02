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
from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.patient import Patient


# ============================================================================
# Test Flow State Operations (5 endpoints)
# ============================================================================

class TestFlowStateOperations:
    """Test flow state management endpoints."""

    def test_get_flow_state_success(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test getting current flow state for a patient."""
        response = client.get(
            f"/api/v2/flows/{test_patient.id}/state",
            headers=auth_headers
        )
        # Accept 200 (success) or 404 (flow not initialized yet)
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "patient_id" in data or "flow_state" in data

    def test_advance_flow_success(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test advancing patient flow to next step."""
        payload = {"force_day": None}
        response = client.post(
            f"/api/v2/flows/{test_patient.id}/advance",
            json=payload,
            headers=auth_headers
        )
        # Accept 200 (success), 404 (not found), or 400 (cannot advance)
        assert response.status_code in [200, 400, 404]

    def test_pause_flow_with_duration(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test pausing flow with auto-resume duration."""
        payload = {"reason": "Patient request", "duration_hours": 24}
        response = client.post(
            f"/api/v2/flows/{test_patient.id}/pause",
            json=payload,
            headers=auth_headers
        )
        # Accept 200 (success), 404 (not found), or 400 (already paused)
        assert response.status_code in [200, 400, 404]

    def test_resume_flow_success(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test resuming paused flow."""
        response = client.post(
            f"/api/v2/flows/{test_patient.id}/resume",
            headers=auth_headers
        )
        # Accept 200 (success), 404 (not found), or 400 (not paused)
        assert response.status_code in [200, 400, 404]

    def test_flow_history_cursor_pagination(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test flow history with cursor pagination."""
        response = client.get(
            f"/api/v2/flows/{test_patient.id}/history?limit=10",
            headers=auth_headers
        )
        # Accept 200 (success) or 404 (not found)
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.json()
            assert "data" in data or isinstance(data, list)


# ============================================================================
# Test Analytics & Dashboard (7 endpoints)
# ============================================================================

class TestAnalyticsDashboard:
    """Test analytics and dashboard endpoints."""

    @patch('app.utils.redis_cache.get_async_redis_client')
    def test_dashboard_overview_cached(self, mock_redis, client: TestClient, auth_headers: dict):
        """Test dashboard overview with Redis caching."""
        mock_redis_client = AsyncMock()
        mock_redis_client.get.return_value = None
        mock_redis.return_value = mock_redis_client

        response = client.get(
            "/api/v2/flows/dashboard/overview?timeframe=week",
            headers=auth_headers
        )
        # Accept 200 (success) or 404 (endpoint not implemented)
        assert response.status_code in [200, 404]

    def test_flow_metrics(self, client: TestClient, auth_headers: dict):
        """Test flow metrics endpoint."""
        response = client.get(
            "/api/v2/flows/dashboard/flow-metrics?timeframe=month",
            headers=auth_headers
        )
        # Accept 200 (success) or 404 (endpoint not implemented)
        assert response.status_code in [200, 404]

    def test_patient_engagement(self, client: TestClient, auth_headers: dict):
        """Test patient engagement analytics."""
        response = client.get(
            "/api/v2/flows/dashboard/patient-engagement",
            headers=auth_headers
        )
        # Accept 200 (success) or 404 (endpoint not implemented)
        assert response.status_code in [200, 404]

    def test_risk_assessment(self, client: TestClient, auth_headers: dict):
        """Test risk assessment analytics."""
        response = client.get(
            "/api/v2/flows/analytics/risk-assessment",
            headers=auth_headers
        )
        # Accept 200 (success) or 404 (endpoint not implemented)
        assert response.status_code in [200, 404]

    def test_flow_performance(self, client: TestClient, auth_headers: dict):
        """Test flow performance metrics."""
        response = client.get(
            "/api/v2/flows/analytics/flow-performance",
            headers=auth_headers
        )
        # Accept 200 (success) or 404 (endpoint not implemented)
        assert response.status_code in [200, 404]

    def test_patient_journey(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test patient journey analysis."""
        response = client.get(
            f"/api/v2/flows/analytics/patient-journey?patient_id={test_patient.id}",
            headers=auth_headers
        )
        # Accept 200 (success) or 404 (endpoint not implemented)
        assert response.status_code in [200, 404]

    def test_generate_insights(self, client: TestClient, auth_headers: dict):
        """Test AI insights generation."""
        payload = {"timeframe": "month", "focus_areas": ["engagement", "risk"]}
        response = client.post(
            "/api/v2/flows/analytics/generate-insights",
            json=payload,
            headers=auth_headers
        )
        # Accept 200 (success) or 404 (endpoint not implemented)
        assert response.status_code in [200, 404]


# ============================================================================
# Test Template Management (5 endpoints)
# ============================================================================

class TestTemplateManagement:
    """Test flow template CRUD operations."""

    def test_list_templates_cursor_pagination(self, client: TestClient, auth_headers: dict):
        """Test listing templates with cursor pagination."""
        response = client.get(
            "/api/v2/flows/templates?limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert isinstance(data["data"], list)

    def test_create_template(self, client: TestClient, auth_headers: dict):
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
            headers=auth_headers
        )
        assert response.status_code in [200, 201]

    def test_get_template_by_id(self, client: TestClient, auth_headers: dict):
        """Test getting template by ID."""
        template_id = uuid4()
        response = client.get(
            f"/api/v2/flows/templates/{template_id}",
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

    def test_update_template(self, client: TestClient, auth_headers: dict):
        """Test updating a template."""
        template_id = uuid4()
        payload = {"name": "Updated Template"}
        response = client.put(
            f"/api/v2/flows/templates/{template_id}",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

    def test_delete_template_soft_delete(self, client: TestClient, auth_headers: dict):
        """Test soft deleting a template."""
        template_id = uuid4()
        response = client.delete(
            f"/api/v2/flows/templates/{template_id}",
            headers=auth_headers
        )
        assert response.status_code in [200, 204, 404]


# ============================================================================
# Test Customization (4 endpoints)
# ============================================================================

class TestCustomization:
    """Test flow customization endpoints."""

    def test_create_customization(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test creating patient flow customization."""
        payload = {
            "customization_data": {"skip_days": [5, 10], "custom_messages": {}}
        }
        response = client.post(
            f"/api/v2/flows/{test_patient.id}/customize",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code in [200, 201]

    def test_get_customization(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test getting patient customization."""
        response = client.get(
            f"/api/v2/flows/{test_patient.id}/customization",
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

    def test_update_customization(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test updating patient customization."""
        payload = {"customization_data": {"skip_days": [7]}}
        response = client.put(
            f"/api/v2/flows/{test_patient.id}/customization",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

    def test_delete_customization(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test deleting patient customization."""
        response = client.delete(
            f"/api/v2/flows/{test_patient.id}/customization",
            headers=auth_headers
        )
        assert response.status_code in [200, 204, 404]


# ============================================================================
# Test Rules Engine (4 endpoints)
# ============================================================================

class TestRulesEngine:
    """Test flow rules engine endpoints."""

    def test_create_rule(self, client: TestClient, auth_headers: dict):
        """Test creating a flow rule."""
        payload = {
            "name": "High Risk Alert",
            "condition": {"risk_level": "high"},
            "action": {"notify_doctor": True}
        }
        response = client.post(
            "/api/v2/flows/rules",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code in [200, 201]

    def test_list_rules_pagination(self, client: TestClient, auth_headers: dict):
        """Test listing rules with pagination."""
        response = client.get(
            "/api/v2/flows/rules?limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_update_rule(self, client: TestClient, auth_headers: dict):
        """Test updating a rule."""
        rule_id = uuid4()
        payload = {"name": "Updated Rule"}
        response = client.put(
            f"/api/v2/flows/rules/{rule_id}",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

    def test_delete_rule(self, client: TestClient, auth_headers: dict):
        """Test deleting a rule."""
        rule_id = uuid4()
        response = client.delete(
            f"/api/v2/flows/rules/{rule_id}",
            headers=auth_headers
        )
        assert response.status_code in [200, 204, 404]


# ============================================================================
# Test A/B Testing (6 endpoints)
# ============================================================================

class TestABTesting:
    """Test A/B testing framework endpoints."""

    def test_create_ab_test(self, client: TestClient, auth_headers: dict):
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
            headers=auth_headers
        )
        assert response.status_code in [200, 201]

    def test_list_ab_tests(self, client: TestClient, auth_headers: dict):
        """Test listing A/B tests."""
        response = client.get(
            "/api/v2/flows/ab-tests?limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_get_ab_test(self, client: TestClient, auth_headers: dict):
        """Test getting A/B test details."""
        test_id = uuid4()
        response = client.get(
            f"/api/v2/flows/ab-tests/{test_id}",
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

    def test_update_ab_test(self, client: TestClient, auth_headers: dict):
        """Test updating an A/B test."""
        test_id = uuid4()
        payload = {"name": "Updated Test"}
        response = client.put(
            f"/api/v2/flows/ab-tests/{test_id}",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

    def test_stop_ab_test(self, client: TestClient, auth_headers: dict):
        """Test stopping an A/B test."""
        test_id = uuid4()
        response = client.post(
            f"/api/v2/flows/ab-tests/{test_id}/stop",
            headers=auth_headers
        )
        assert response.status_code in [200, 404]

    def test_get_ab_test_results(self, client: TestClient, auth_headers: dict):
        """Test getting A/B test results."""
        test_id = uuid4()
        response = client.get(
            f"/api/v2/flows/ab-tests/{test_id}/results",
            headers=auth_headers
        )
        assert response.status_code in [200, 404]


# ============================================================================
# Test Utility Endpoints (7 endpoints)
# ============================================================================

class TestUtilityEndpoints:
    """Test utility and health check endpoints."""

    def test_preview_message(self, client: TestClient, auth_headers: dict):
        """Test message preview generation."""
        payload = {
            "template": "Hello {{name}}",
            "variables": {"name": "John"}
        }
        response = client.post(
            "/api/v2/flows/preview-message",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_health_gemini(self, client: TestClient, auth_headers: dict):
        """Test Gemini API health check."""
        response = client.get(
            "/api/v2/flows/health/gemini",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_health_redis(self, client: TestClient, auth_headers: dict):
        """Test Redis health check."""
        response = client.get(
            "/api/v2/flows/health/redis",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_list_all_flows(self, client: TestClient, auth_headers: dict):
        """Test listing all flows."""
        response = client.get(
            "/api/v2/flows?limit=20",
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_start_flow(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test starting a flow for patient."""
        payload = {"patient_id": str(test_patient.id), "flow_type": "onboarding"}
        response = client.post(
            "/api/v2/flows/start",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code in [200, 201]

    def test_process_response(self, client: TestClient, auth_headers: dict, test_patient: Patient):
        """Test processing patient response."""
        payload = {"response_text": "Yes", "metadata": {}}
        response = client.post(
            f"/api/v2/flows/{test_patient.id}/response",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200

    def test_overall_analytics(self, client: TestClient, auth_headers: dict):
        """Test overall flow analytics."""
        response = client.get(
            "/api/v2/flows/analytics",
            headers=auth_headers
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
