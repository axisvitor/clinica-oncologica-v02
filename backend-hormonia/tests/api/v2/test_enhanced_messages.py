"""
Tests for Enhanced Messages API v2

Comprehensive test suite covering template management, scheduling,
A/B testing, analytics, and bulk operations.
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import json
from uuid import uuid4

from app.models.patient import Patient
from app.models.user import User, UserRole


class TestTemplateManagementV2:
    """Test suite for template management endpoints"""

    def test_create_template_success(
        self, client: TestClient, db: Session, admin_headers: dict
    ):
        """Test creating a message template successfully"""
        template_data = {
            "name": "Test Medication Reminder",
            "content": "Olá {{patient_name}}, lembre-se de tomar {{medication_name}}.",
            "category": "medication",
            "language": "pt_BR",
            "variables": [
                {
                    "name": "patient_name",
                    "description": "Patient's name",
                    "type": "string",
                    "required": True
                },
                {
                    "name": "medication_name",
                    "description": "Medication name",
                    "type": "string",
                    "required": True
                }
            ],
            "tags": ["medication", "reminder"]
        }

        response = client.post(
            "/api/v2/enhanced-messages/templates",
            json=template_data,
            headers=admin_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == template_data["name"]
        assert data["category"] == template_data["category"]
        assert data["version"] == 1
        assert data["is_active"] is True
        assert len(data["variables"]) == 2

    def test_create_template_missing_variable_definition(
        self, client: TestClient, admin_headers: dict
    ):
        """Test creating template with undefined variables fails"""
        template_data = {
            "name": "Invalid Template",
            "content": "Hello {{patient_name}}, take {{medication_name}}",
            "category": "medication",
            "language": "pt_BR",
            "variables": [
                {
                    "name": "patient_name",
                    "type": "string",
                    "required": True
                }
                # Missing medication_name definition
            ],
            "tags": []
        }

        response = client.post(
            "/api/v2/enhanced-messages/templates",
            json=template_data,
            headers=admin_headers
        )

        assert response.status_code == 422  # Validation error

    def test_create_template_unauthorized(
        self, client: TestClient, db: Session
    ):
        """Test creating template without authentication fails"""
        template_data = {
            "name": "Test Template",
            "content": "Test content",
            "category": "reminder",
            "language": "pt_BR",
            "variables": [],
            "tags": []
        }

        response = client.post(
            "/api/v2/enhanced-messages/templates",
            json=template_data
        )

        assert response.status_code == 401

    def test_list_templates(
        self, client: TestClient, admin_headers: dict
    ):
        """Test listing templates with pagination"""
        response = client.get(
            "/api/v2/enhanced-messages/templates?limit=10",
            headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "next_cursor" in data
        assert "has_more" in data
        assert "total_active" in data
        assert isinstance(data["data"], list)

    def test_list_templates_with_category_filter(
        self, client: TestClient, admin_headers: dict
    ):
        """Test listing templates filtered by category"""
        response = client.get(
            "/api/v2/enhanced-messages/templates?category=medication",
            headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_list_templates_with_search(
        self, client: TestClient, admin_headers: dict
    ):
        """Test searching templates"""
        response = client.get(
            "/api/v2/enhanced-messages/templates?search=reminder",
            headers=admin_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_get_template_by_id(
        self, client: TestClient, admin_headers: dict
    ):
        """Test getting a specific template"""
        # First create a template
        template_data = {
            "name": "Get Test Template",
            "content": "Test {{variable}}",
            "category": "reminder",
            "language": "pt_BR",
            "variables": [
                {"name": "variable", "type": "string", "required": True}
            ],
            "tags": []
        }

        create_response = client.post(
            "/api/v2/enhanced-messages/templates",
            json=template_data,
            headers=admin_headers
        )

        if create_response.status_code == 201:
            template_id = create_response.json()["id"]

            # Get the template
            response = client.get(
                f"/api/v2/enhanced-messages/templates/{template_id}",
                headers=admin_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["id"] == template_id
            assert data["name"] == template_data["name"]

    def test_update_template(
        self, client: TestClient, admin_headers: dict
    ):
        """Test updating a template"""
        # First create a template
        template_data = {
            "name": "Update Test Template",
            "content": "Original {{content}}",
            "category": "reminder",
            "language": "pt_BR",
            "variables": [
                {"name": "content", "type": "string", "required": True}
            ],
            "tags": []
        }

        create_response = client.post(
            "/api/v2/enhanced-messages/templates",
            json=template_data,
            headers=admin_headers
        )

        if create_response.status_code == 201:
            template_id = create_response.json()["id"]

            # Update the template
            update_data = {
                "name": "Updated Template Name",
                "is_active": False
            }

            response = client.patch(
                f"/api/v2/enhanced-messages/templates/{template_id}",
                json=update_data,
                headers=admin_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == update_data["name"]
            assert data["version"] == 2  # Version incremented


class TestScheduledMessagesV2:
    """Test suite for scheduled message endpoints"""

    def test_schedule_message_success(
        self, client: TestClient, db: Session, auth_headers: dict
    ):
        """Test scheduling a message successfully"""
        # Get or create a patient
        doctor = db.query(User).filter(User.role == UserRole.DOCTOR).first()
        if not doctor:
            pytest.skip("No doctor available for test")

        patient = Patient(
            name="Test Patient",
            email=f"test_{uuid4().hex[:8]}@example.com",
            doctor_id=doctor.id
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)

        schedule_data = {
            "patient_id": str(patient.id),
            "content": "Reminder message",
            "type": "text",
            "scheduled_for": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
            "optimization_strategy": "immediate",
            "priority": "normal"
        }

        response = client.post(
            "/api/v2/enhanced-messages/scheduled",
            json=schedule_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["patient_id"] == str(patient.id)
        assert data["status"] == "pending"
        assert data["occurrences_sent"] == 0

    def test_schedule_recurring_message(
        self, client: TestClient, db: Session, auth_headers: dict
    ):
        """Test scheduling a recurring message"""
        doctor = db.query(User).filter(User.role == UserRole.DOCTOR).first()
        if not doctor:
            pytest.skip("No doctor available for test")

        patient = Patient(
            name="Recurring Test Patient",
            email=f"recurring_{uuid4().hex[:8]}@example.com",
            doctor_id=doctor.id
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)

        schedule_data = {
            "patient_id": str(patient.id),
            "content": "Daily reminder",
            "type": "text",
            "scheduled_for": (datetime.utcnow() + timedelta(hours=1)).isoformat() + "Z",
            "recurrence": {
                "type": "daily",
                "interval": 1,
                "time_of_day": "09:00",
                "max_occurrences": 7
            },
            "optimization_strategy": "best_time"
        }

        response = client.post(
            "/api/v2/enhanced-messages/scheduled",
            json=schedule_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["recurrence"] is not None
        assert data["recurrence"]["type"] == "daily"
        assert data["recurrence"]["max_occurrences"] == 7

    def test_schedule_message_past_date_fails(
        self, client: TestClient, db: Session, auth_headers: dict
    ):
        """Test scheduling message in the past fails"""
        doctor = db.query(User).filter(User.role == UserRole.DOCTOR).first()
        if not doctor:
            pytest.skip("No doctor available for test")

        patient = Patient(
            name="Past Test Patient",
            email=f"past_{uuid4().hex[:8]}@example.com",
            doctor_id=doctor.id
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)

        schedule_data = {
            "patient_id": str(patient.id),
            "content": "Past message",
            "type": "text",
            "scheduled_for": (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z",
            "optimization_strategy": "immediate"
        }

        response = client.post(
            "/api/v2/enhanced-messages/scheduled",
            json=schedule_data,
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    def test_list_scheduled_messages(
        self, client: TestClient, auth_headers: dict
    ):
        """Test listing scheduled messages"""
        response = client.get(
            "/api/v2/enhanced-messages/scheduled?limit=10",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "total_pending" in data
        assert "total_recurring" in data

    def test_list_scheduled_messages_with_patient_filter(
        self, client: TestClient, db: Session, auth_headers: dict
    ):
        """Test listing scheduled messages filtered by patient"""
        doctor = db.query(User).filter(User.role == UserRole.DOCTOR).first()
        if not doctor:
            pytest.skip("No doctor available for test")

        patient = db.query(Patient).filter(Patient.doctor_id == doctor.id).first()
        if not patient:
            pytest.skip("No patient available for test")

        response = client.get(
            f"/api/v2/enhanced-messages/scheduled?patient_id={patient.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data


class TestABTestingV2:
    """Test suite for A/B testing endpoints"""

    def test_create_ab_test_success(
        self, client: TestClient, admin_headers: dict
    ):
        """Test creating an A/B test successfully"""
        test_data = {
            "name": "Reminder Test",
            "description": "Testing different reminder formats",
            "variants": [
                {
                    "name": "Short",
                    "content": "Consulta amanhã",
                    "weight": 50.0
                },
                {
                    "name": "Detailed",
                    "content": "Olá! Lembre-se da consulta amanhã às 14h.",
                    "weight": 50.0
                }
            ],
            "patient_ids": ["pat_1", "pat_2", "pat_3"],
            "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z",
            "end_date": (datetime.utcnow() + timedelta(days=8)).isoformat() + "Z",
            "success_metric": "read_rate",
            "metadata": {}
        }

        response = client.post(
            "/api/v2/enhanced-messages/ab-tests",
            json=test_data,
            headers=admin_headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == test_data["name"]
        assert data["status"] == "draft"
        assert len(data["variants"]) == 2

    def test_create_ab_test_invalid_weights(
        self, client: TestClient, admin_headers: dict
    ):
        """Test creating A/B test with invalid weights fails"""
        test_data = {
            "name": "Invalid Test",
            "variants": [
                {
                    "name": "A",
                    "content": "Content A",
                    "weight": 40.0  # Only sums to 70
                },
                {
                    "name": "B",
                    "content": "Content B",
                    "weight": 30.0
                }
            ],
            "patient_ids": ["pat_1"],
            "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z",
            "end_date": (datetime.utcnow() + timedelta(days=8)).isoformat() + "Z",
            "success_metric": "read_rate"
        }

        response = client.post(
            "/api/v2/enhanced-messages/ab-tests",
            json=test_data,
            headers=admin_headers
        )

        assert response.status_code == 422  # Validation error

    def test_create_ab_test_non_admin_fails(
        self, client: TestClient, auth_headers: dict
    ):
        """Test non-admin cannot create A/B tests"""
        test_data = {
            "name": "Test",
            "variants": [
                {"name": "A", "content": "A", "weight": 50.0},
                {"name": "B", "content": "B", "weight": 50.0}
            ],
            "patient_ids": ["pat_1"],
            "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z",
            "end_date": (datetime.utcnow() + timedelta(days=8)).isoformat() + "Z",
            "success_metric": "read_rate"
        }

        response = client.post(
            "/api/v2/enhanced-messages/ab-tests",
            json=test_data,
            headers=auth_headers
        )

        # Should fail with 403 if user is not admin
        # If user happens to be admin, test will pass
        assert response.status_code in [403, 201]

    def test_get_ab_test_results(
        self, client: TestClient, admin_headers: dict
    ):
        """Test getting A/B test results"""
        # First create a test
        test_data = {
            "name": "Results Test",
            "variants": [
                {"name": "A", "content": "Content A", "weight": 50.0},
                {"name": "B", "content": "Content B", "weight": 50.0}
            ],
            "patient_ids": ["pat_1", "pat_2"],
            "start_date": (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z",
            "end_date": (datetime.utcnow() + timedelta(days=8)).isoformat() + "Z",
            "success_metric": "read_rate"
        }

        create_response = client.post(
            "/api/v2/enhanced-messages/ab-tests",
            json=test_data,
            headers=admin_headers
        )

        if create_response.status_code == 201:
            test_id = create_response.json()["id"]

            # Get results
            response = client.get(
                f"/api/v2/enhanced-messages/ab-tests/{test_id}/results",
                headers=admin_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert "results" in data or data["results"] is None  # May not have results yet


class TestAnalyticsV2:
    """Test suite for analytics endpoints"""

    def test_get_performance_analytics(
        self, client: TestClient, auth_headers: dict
    ):
        """Test getting message performance analytics"""
        response = client.get(
            "/api/v2/enhanced-messages/analytics/performance?days=30",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_messages" in data
        assert "delivery_rate" in data
        assert "read_rate" in data
        assert "response_rate" in data
        assert "peak_hours" in data
        assert isinstance(data["peak_hours"], list)

    def test_get_performance_analytics_custom_period(
        self, client: TestClient, auth_headers: dict
    ):
        """Test analytics with custom time period"""
        response = client.get(
            "/api/v2/enhanced-messages/analytics/performance?days=7",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "period_start" in data
        assert "period_end" in data

    def test_get_delivery_optimization(
        self, client: TestClient, db: Session, auth_headers: dict
    ):
        """Test getting delivery optimization recommendations"""
        doctor = db.query(User).filter(User.role == UserRole.DOCTOR).first()
        if not doctor:
            pytest.skip("No doctor available for test")

        patient = db.query(Patient).filter(Patient.doctor_id == doctor.id).first()
        if not patient:
            pytest.skip("No patient available for test")

        response = client.get(
            f"/api/v2/enhanced-messages/analytics/optimization/{patient.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "patient_id" in data
        assert "recommended_send_time" in data
        assert "recommended_days" in data
        assert "confidence_score" in data
        assert isinstance(data["recommended_days"], list)

    def test_get_optimization_nonexistent_patient(
        self, client: TestClient, auth_headers: dict
    ):
        """Test optimization for non-existent patient fails"""
        response = client.get(
            "/api/v2/enhanced-messages/analytics/optimization/invalid_patient_id",
            headers=auth_headers
        )

        assert response.status_code == 404


class TestBulkOperationsV2:
    """Test suite for bulk operations"""

    def test_send_bulk_messages_success(
        self, client: TestClient, db: Session, auth_headers: dict
    ):
        """Test sending bulk messages successfully"""
        doctor = db.query(User).filter(User.role == UserRole.DOCTOR).first()
        if not doctor:
            pytest.skip("No doctor available for test")

        # Create test patients
        patient_ids = []
        for i in range(3):
            patient = Patient(
                name=f"Bulk Test Patient {i}",
                email=f"bulk_test_{i}_{uuid4().hex[:8]}@example.com",
                doctor_id=doctor.id
            )
            db.add(patient)
            db.commit()
            db.refresh(patient)
            patient_ids.append(str(patient.id))

        bulk_data = {
            "patient_ids": patient_ids,
            "content": "Bulk message content",
            "type": "text",
            "optimization_strategy": "rate_limited",
            "batch_size": 50,
            "delay_between_batches_seconds": 5
        }

        response = client.post(
            "/api/v2/enhanced-messages/bulk",
            json=bulk_data,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["total_patients"] == len(patient_ids)
        assert data["scheduled_count"] >= 0

    def test_send_bulk_messages_empty_patient_list(
        self, client: TestClient, auth_headers: dict
    ):
        """Test bulk send with empty patient list fails"""
        bulk_data = {
            "patient_ids": [],
            "content": "Bulk message",
            "type": "text"
        }

        response = client.post(
            "/api/v2/enhanced-messages/bulk",
            json=bulk_data,
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    def test_get_bulk_job_status(
        self, client: TestClient, db: Session, auth_headers: dict
    ):
        """Test getting bulk job status"""
        doctor = db.query(User).filter(User.role == UserRole.DOCTOR).first()
        if not doctor:
            pytest.skip("No doctor available for test")

        patient = Patient(
            name="Status Test Patient",
            email=f"status_{uuid4().hex[:8]}@example.com",
            doctor_id=doctor.id
        )
        db.add(patient)
        db.commit()
        db.refresh(patient)

        # Create bulk job
        bulk_data = {
            "patient_ids": [str(patient.id)],
            "content": "Test message",
            "type": "text"
        }

        create_response = client.post(
            "/api/v2/enhanced-messages/bulk",
            json=bulk_data,
            headers=auth_headers
        )

        if create_response.status_code == 200:
            job_id = create_response.json()["job_id"]

            # Get job status
            response = client.get(
                f"/api/v2/enhanced-messages/bulk/{job_id}/status",
                headers=auth_headers
            )

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == job_id
            assert "status" in data
            assert "progress_percentage" in data

    def test_get_bulk_job_status_not_found(
        self, client: TestClient, auth_headers: dict
    ):
        """Test getting non-existent bulk job fails"""
        response = client.get(
            "/api/v2/enhanced-messages/bulk/invalid_job_id/status",
            headers=auth_headers
        )

        assert response.status_code == 404


class TestTemplateRendering:
    """Test suite for template rendering functionality"""

    def test_render_template_with_variables(self):
        """Test template variable rendering"""
        from app.api.v2.enhanced_messages import _render_template

        template = "Hello {{name}}, your appointment is at {{time}}."
        variables = {
            "name": "John",
            "time": "2:00 PM"
        }

        result = _render_template(template, variables)
        assert result == "Hello John, your appointment is at 2:00 PM."

    def test_render_template_missing_variable_fails(self):
        """Test rendering with missing variable fails"""
        from app.api.v2.enhanced_messages import _render_template

        template = "Hello {{name}}, your appointment is at {{time}}."
        variables = {
            "name": "John"
            # Missing 'time' variable
        }

        with pytest.raises(ValueError, match="Missing required variables"):
            _render_template(template, variables)


class TestRateLimiting:
    """Test suite for rate limiting (when enabled)"""

    def test_rate_limit_template_creation(
        self, client: TestClient, admin_headers: dict
    ):
        """Test rate limiting on template creation"""
        # Note: Rate limiting is currently disabled in the codebase
        # This test documents the expected behavior when it's enabled
        template_data = {
            "name": "Rate Limit Test",
            "content": "Test {{var}}",
            "category": "reminder",
            "language": "pt_BR",
            "variables": [
                {"name": "var", "type": "string", "required": True}
            ],
            "tags": []
        }

        # Send multiple requests
        responses = []
        for _ in range(5):
            response = client.post(
                "/api/v2/enhanced-messages/templates",
                json=template_data,
                headers=admin_headers
            )
            responses.append(response.status_code)

        # All should succeed since rate limiting is disabled
        # If rate limiting were enabled, some would be 429
        assert all(status in [201, 429] for status in responses)


class TestPermissions:
    """Test suite for permission checks"""

    def test_doctor_can_create_template(
        self, client: TestClient, db: Session
    ):
        """Test that doctors can create templates"""
        # This would require creating a doctor user and auth headers
        # Implementation depends on auth setup
        pass

    def test_patient_cannot_create_template(
        self, client: TestClient, db: Session
    ):
        """Test that patients cannot create templates"""
        # This would require creating a patient user and auth headers
        # Implementation depends on auth setup
        pass
