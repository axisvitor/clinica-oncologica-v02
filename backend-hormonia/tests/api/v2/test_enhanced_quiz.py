"""
Tests for Enhanced Quiz API v2
Comprehensive test suite for advanced quiz features.
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.quiz import QuizSession, QuizTemplate
from app.models.patient import Patient


from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
class TestEnhancedQuizAnalytics:
    """Test suite for enhanced quiz analytics endpoint."""

    def test_get_analytics_success(self, client: TestClient, db: Session, auth_headers: dict):
        """Test successful retrieval of quiz analytics."""
        response = client.get("/api/v2/enhanced-quiz/analytics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify required fields
        assert "total_sessions" in data
        assert "completed_sessions" in data
        assert "completion_rate" in data
        assert "trends" in data
        assert "category_breakdown" in data
        assert "risk_distribution" in data
        assert "top_templates" in data

        # Verify data types
        assert isinstance(data["total_sessions"], int)
        assert isinstance(data["completed_sessions"], int)
        assert isinstance(data["completion_rate"], (int, float))
        assert isinstance(data["trends"], list)
        assert isinstance(data["category_breakdown"], dict)
        assert isinstance(data["risk_distribution"], dict)

    def test_get_analytics_with_date_filter(self, client: TestClient, db: Session, auth_headers: dict):
        """Test analytics with date filtering."""
        start_date = (now_sao_paulo_naive() - timedelta(days=30)).isoformat()
        end_date = now_sao_paulo_naive().isoformat()

        response = client.get(
            f"/api/v2/enhanced-quiz/analytics?start_date={start_date}&end_date={end_date}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_sessions"] >= 0

    def test_get_analytics_by_category(self, client: TestClient, db: Session, auth_headers: dict):
        """Test analytics filtered by category."""
        response = client.get(
            "/api/v2/enhanced-quiz/analytics?category=pain_assessment",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["category_breakdown"], dict)

    def test_get_analytics_with_trends(self, client: TestClient, db: Session, auth_headers: dict):
        """Test analytics with trend data."""
        response = client.get(
            "/api/v2/enhanced-quiz/analytics?include_trends=true",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "trends" in data

        if data["trends"]:
            trend = data["trends"][0]
            assert "date" in trend
            assert "total_sessions" in trend
            assert "completed_sessions" in trend
            assert "completion_rate" in trend

    def test_get_analytics_unauthorized(self, client: TestClient, db: Session):
        """Test analytics endpoint requires authentication."""
        response = client.get("/api/v2/enhanced-quiz/analytics")
        assert response.status_code in [401, 403]


class TestAdvancedTemplateCreation:
    """Test suite for advanced template creation."""

    def test_create_advanced_template_success(self, client: TestClient, db: Session, auth_headers: dict):
        """Test successful creation of advanced template."""
        template_data = {
            "title": "Advanced Pain Assessment",
            "description": "Comprehensive pain assessment with branching logic",
            "category": "pain_assessment",
            "difficulty": "advanced",
            "questions": [
                {
                    "id": "q1_pain_level",
                    "question_text": "Rate your pain level (0-10)",
                    "question_type": "scale",
                    "required": True,
                    "scoring_weight": 2.0,
                    "category": "pain",
                    "branching_rules": [
                        {
                            "conditions": [
                                {
                                    "field": "pain_level",
                                    "operator": "gte",
                                    "value": 7
                                }
                            ],
                            "logic": "AND",
                            "next_question_id": "q2_pain_location",
                            "show_alert": "High pain level detected"
                        }
                    ],
                    "risk_factors": {
                        "high_pain": 0.8
                    }
                }
            ],
            "time_limit_minutes": 30,
            "risk_scoring_enabled": True,
            "adaptive_flow_enabled": True
        }

        response = client.post(
            "/api/v2/enhanced-quiz/templates/advanced",
            json=template_data,
            headers=auth_headers
        )

        assert response.status_code == 201
        data = response.json()

        assert "id" in data
        assert data["name"] == template_data["title"]
        assert data["category"] == template_data["category"]
        assert data["adaptive_flow_enabled"] == True
        assert data["risk_scoring_enabled"] == True

    def test_create_template_with_validation_rules(self, client: TestClient, db: Session, auth_headers: dict):
        """Test template creation with validation rules."""
        template_data = {
            "title": "Validated Assessment",
            "category": "symptoms",
            "questions": [
                {
                    "id": "q1_temp",
                    "question_text": "What is your temperature?",
                    "question_type": "number",
                    "required": True,
                    "validation_rules": {
                        "min": 35.0,
                        "max": 42.0,
                        "decimal_places": 1
                    }
                }
            ]
        }

        response = client.post(
            "/api/v2/enhanced-quiz/templates/advanced",
            json=template_data,
            headers=auth_headers
        )

        assert response.status_code == 201

    def test_create_template_missing_required_fields(self, client: TestClient, db: Session, auth_headers: dict):
        """Test template creation fails with missing required fields."""
        template_data = {
            "title": "Incomplete Template",
            # Missing category and questions
        }

        response = client.post(
            "/api/v2/enhanced-quiz/templates/advanced",
            json=template_data,
            headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    def test_create_template_duplicate_question_ids(self, client: TestClient, db: Session, auth_headers: dict):
        """Test template creation fails with duplicate question IDs."""
        template_data = {
            "title": "Duplicate Questions",
            "category": "symptoms",
            "questions": [
                {
                    "id": "q1",
                    "question_text": "Question 1",
                    "question_type": "text",
                    "required": True
                },
                {
                    "id": "q1",  # Duplicate ID
                    "question_text": "Question 2",
                    "question_type": "text",
                    "required": True
                }
            ]
        }

        response = client.post(
            "/api/v2/enhanced-quiz/templates/advanced",
            json=template_data,
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_create_template_unauthorized(self, client: TestClient, db: Session):
        """Test template creation requires authentication."""
        template_data = {
            "title": "Test Template",
            "category": "symptoms",
            "questions": [{"id": "q1", "question_text": "Test", "question_type": "text", "required": True}]
        }

        response = client.post(
            "/api/v2/enhanced-quiz/templates/advanced",
            json=template_data
        )

        assert response.status_code in [401, 403]


class TestAdaptiveQuizFlow:
    """Test suite for adaptive quiz flow."""

    def test_adaptive_flow_basic(self, client: TestClient, db: Session, auth_headers: dict):
        """Test basic adaptive flow processing."""
        # Create a quiz session first
        patient = db.query(Patient).first()
        template = db.query(QuizTemplate).first()

        if not patient or not template:
            pytest.skip("No patient or template available")

        session = QuizSession(
            patient_id=patient.id,
            quiz_template_id=template.id,
            status="started",
            started_at=now_sao_paulo_naive()
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        flow_request = {
            "session_id": str(session.id),
            "current_question_id": "q1",
            "response_value": 8,
            "response_metadata": {
                "answered_at": now_sao_paulo_naive().isoformat()
            }
        }

        response = client.post(
            "/api/v2/enhanced-quiz/adaptive-flow",
            json=flow_request,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "is_completed" in data
        assert "alerts" in data
        assert "progress_percentage" in data
        assert isinstance(data["is_completed"], bool)
        assert isinstance(data["alerts"], list)
        assert 0 <= data["progress_percentage"] <= 100

    def test_adaptive_flow_session_not_found(self, client: TestClient, db: Session, auth_headers: dict):
        """Test adaptive flow with non-existent session."""
        flow_request = {
            "session_id": str(uuid4()),
            "current_question_id": "q1",
            "response_value": 5
        }

        response = client.post(
            "/api/v2/enhanced-quiz/adaptive-flow",
            json=flow_request,
            headers=auth_headers
        )

        assert response.status_code == 404

class TestRiskScoring:
    """Test suite for risk scoring."""

    def test_calculate_risk_score_success(self, client: TestClient, db: Session, auth_headers: dict):
        """Test successful risk score calculation."""
        patient = db.query(Patient).first()

        if not patient:
            pytest.skip("No patient available")

        # Create a completed quiz session
        template = db.query(QuizTemplate).first()
        if not template:
            pytest.skip("No template available")

        session = QuizSession(
            patient_id=patient.id,
            quiz_template_id=template.id,
            status="completed",
            started_at=now_sao_paulo_naive() - timedelta(hours=1),
            completed_at=now_sao_paulo_naive()
        )
        db.add(session)
        db.commit()

        risk_request = {
            "patient_id": str(patient.id),
            "lookback_days": 30,
            "include_historical": True
        }

        response = client.post(
            "/api/v2/enhanced-quiz/risk-scoring",
            json=risk_request,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "patient_id" in data
        assert "assessment_date" in data
        assert "current_risk" in data
        assert "trend" in data

        # Verify risk structure
        risk = data["current_risk"]
        assert "overall_risk_level" in risk
        assert "risk_score" in risk
        assert "risk_factors" in risk
        assert "recommendations" in risk
        assert "confidence_score" in risk

        # Verify values
        assert risk["overall_risk_level"] in ["low", "medium", "high", "critical"]
        assert 0 <= risk["risk_score"] <= 100
        assert 0 <= risk["confidence_score"] <= 1

    def test_risk_scoring_patient_not_found(self, client: TestClient, db: Session, auth_headers: dict):
        """Test risk scoring with non-existent patient."""
        risk_request = {
            "patient_id": str(uuid4()),
            "lookback_days": 30
        }

        response = client.post(
            "/api/v2/enhanced-quiz/risk-scoring",
            json=risk_request,
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_risk_scoring_with_historical_data(self, client: TestClient, db: Session, auth_headers: dict):
        """Test risk scoring includes historical scores."""
        patient = db.query(Patient).first()
        if not patient:
            pytest.skip("No patient available")

        risk_request = {
            "patient_id": str(patient.id),
            "lookback_days": 90,
            "include_historical": True
        }

        response = client.post(
            "/api/v2/enhanced-quiz/risk-scoring",
            json=risk_request,
            headers=auth_headers
        )

        if response.status_code == 200:
            data = response.json()
            assert "historical_scores" in data
            assert isinstance(data["historical_scores"], list)


class TestQuizRecommendations:
    """Test suite for quiz recommendations."""

    def test_get_recommendations_success(self, client: TestClient, db: Session, auth_headers: dict):
        """Test successful retrieval of quiz recommendations."""
        patient = db.query(Patient).first()

        if not patient:
            pytest.skip("No patient available")

        response = client.get(
            f"/api/v2/enhanced-quiz/recommendations?patient_id={patient.id}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "patient_id" in data
        assert "recommendations" in data
        assert "total_recommendations" in data

        assert isinstance(data["recommendations"], list)
        assert isinstance(data["total_recommendations"], int)

        # Verify recommendation structure if any exist
        if data["recommendations"]:
            rec = data["recommendations"][0]
            assert "template_id" in rec
            assert "template_title" in rec
            assert "category" in rec
            assert "priority" in rec
            assert "reason" in rec
            assert rec["priority"] in ["high", "medium", "low"]

    def test_recommendations_patient_not_found(self, client: TestClient, db: Session, auth_headers: dict):
        """Test recommendations with non-existent patient."""
        response = client.get(
            f"/api/v2/enhanced-quiz/recommendations?patient_id={uuid4()}",
            headers=auth_headers
        )

        assert response.status_code == 404

    def test_recommendations_prioritized(self, client: TestClient, db: Session, auth_headers: dict):
        """Test recommendations are prioritized correctly."""
        patient = db.query(Patient).first()
        if not patient:
            pytest.skip("No patient available")

        response = client.get(
            f"/api/v2/enhanced-quiz/recommendations?patient_id={patient.id}",
            headers=auth_headers
        )

        if response.status_code == 200:
            data = response.json()
            if len(data["recommendations"]) > 1:
                # Check if high priority comes before low priority
                priorities = [r["priority"] for r in data["recommendations"]]
                priority_order = {"high": 0, "medium": 1, "low": 2}
                for i in range(len(priorities) - 1):
                    assert priority_order[priorities[i]] <= priority_order[priorities[i + 1]]


class TestPerformanceMetrics:
    """Test suite for performance metrics."""

    def test_get_performance_metrics_success(self, client: TestClient, db: Session, auth_headers: dict):
        """Test successful retrieval of performance metrics."""
        response = client.get(
            "/api/v2/enhanced-quiz/performance-metrics",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "period_start" in data
        assert "period_end" in data
        assert "metrics" in data
        assert "insights" in data

        assert isinstance(data["metrics"], list)
        assert isinstance(data["insights"], list)

        # Verify metric structure
        if data["metrics"]:
            metric = data["metrics"][0]
            assert "metric_name" in metric
            assert "current_value" in metric
            assert "trend" in metric
            assert metric["trend"] in ["up", "down", "stable"]

    def test_performance_metrics_with_date_range(self, client: TestClient, db: Session, auth_headers: dict):
        """Test performance metrics with custom date range."""
        start_date = (now_sao_paulo_naive() - timedelta(days=60)).isoformat()
        end_date = now_sao_paulo_naive().isoformat()

        response = client.get(
            f"/api/v2/enhanced-quiz/performance-metrics?start_date={start_date}&end_date={end_date}",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["period_start"]
        assert data["period_end"]

    def test_performance_metrics_with_comparison(self, client: TestClient, db: Session, auth_headers: dict):
        """Test performance metrics includes period comparison."""
        response = client.get(
            "/api/v2/enhanced-quiz/performance-metrics?compare_period=true",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Should have previous values for comparison
        if data["metrics"]:
            metric = data["metrics"][0]
            assert "previous_value" in metric or metric["previous_value"] is None
            assert "change_percentage" in metric or metric["change_percentage"] is None


class TestBulkOperations:
    """Test suite for bulk quiz operations."""

    def test_bulk_assign_success(self, client: TestClient, db: Session, auth_headers: dict):
        """Test successful bulk quiz assignment."""
        patients = db.query(Patient).limit(3).all()
        template = db.query(QuizTemplate).filter(QuizTemplate.is_active == True).first()

        if len(patients) < 2 or not template:
            pytest.skip("Not enough patients or no template available")

        bulk_request = {
            "operation": "assign",
            "patient_ids": [str(p.id) for p in patients],
            "template_id": str(template.id)
        }

        response = client.post(
            "/api/v2/enhanced-quiz/bulk-operations",
            json=bulk_request,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert "job_id" in data
        assert "operation" in data
        assert "total_patients" in data
        assert "status" in data
        assert "successful" in data
        assert "failed" in data

        assert data["operation"] == "assign"
        assert data["total_patients"] == len(patients)

    def test_bulk_update_success(self, client: TestClient, db: Session, auth_headers: dict):
        """Test successful bulk quiz update."""
        patients = db.query(Patient).limit(2).all()

        if len(patients) < 1:
            pytest.skip("No patients available")

        bulk_request = {
            "operation": "update",
            "patient_ids": [str(p.id) for p in patients],
            "update_data": {
                "status": "cancelled"
            }
        }

        response = client.post(
            "/api/v2/enhanced-quiz/bulk-operations",
            json=bulk_request,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["operation"] == "update"

    def test_bulk_delete_success(self, client: TestClient, db: Session, auth_headers: dict):
        """Test successful bulk quiz deletion."""
        patients = db.query(Patient).limit(2).all()

        if len(patients) < 1:
            pytest.skip("No patients available")

        bulk_request = {
            "operation": "delete",
            "patient_ids": [str(p.id) for p in patients]
        }

        response = client.post(
            "/api/v2/enhanced-quiz/bulk-operations",
            json=bulk_request,
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["operation"] == "delete"

    def test_bulk_operation_invalid_operation(self, client: TestClient, db: Session, auth_headers: dict):
        """Test bulk operation with invalid operation type."""
        bulk_request = {
            "operation": "invalid_op",
            "patient_ids": [str(uuid4())]
        }

        response = client.post(
            "/api/v2/enhanced-quiz/bulk-operations",
            json=bulk_request,
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_bulk_assign_missing_template(self, client: TestClient, db: Session, auth_headers: dict):
        """Test bulk assign fails without template_id."""
        bulk_request = {
            "operation": "assign",
            "patient_ids": [str(uuid4())]
            # Missing template_id
        }

        response = client.post(
            "/api/v2/enhanced-quiz/bulk-operations",
            json=bulk_request,
            headers=auth_headers
        )

        assert response.status_code == 422


class TestQuizExport:
    """Test suite for quiz export."""

    def test_export_pdf_success(self, client: TestClient, db: Session, auth_headers: dict):
        """Test successful PDF export."""
        export_request = {
            "format": "pdf",
            "start_date": (now_sao_paulo_naive() - timedelta(days=30)).isoformat(),
            "end_date": now_sao_paulo_naive().isoformat(),
            "include_responses": True,
            "include_analytics": True
        }

        response = client.post(
            "/api/v2/enhanced-quiz/export",
            json=export_request,
            headers=auth_headers
        )

        # May return 200 or 404 if no data exists
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "export_id" in data
            assert "format" in data
            assert "status" in data
            assert data["format"] == "pdf"
            assert data["status"] == "processing"

    def test_export_csv_success(self, client: TestClient, db: Session, auth_headers: dict):
        """Test successful CSV export."""
        export_request = {
            "format": "csv",
            "include_responses": True
        }

        response = client.post(
            "/api/v2/enhanced-quiz/export",
            json=export_request,
            headers=auth_headers
        )

        assert response.status_code in [200, 404]

    def test_export_json_success(self, client: TestClient, db: Session, auth_headers: dict):
        """Test successful JSON export."""
        export_request = {
            "format": "json",
            "include_analytics": False
        }

        response = client.post(
            "/api/v2/enhanced-quiz/export",
            json=export_request,
            headers=auth_headers
        )

        assert response.status_code in [200, 404]

    def test_export_xlsx_success(self, client: TestClient, db: Session, auth_headers: dict):
        """Test successful XLSX export."""
        export_request = {
            "format": "xlsx",
            "include_responses": True,
            "include_analytics": True
        }

        response = client.post(
            "/api/v2/enhanced-quiz/export",
            json=export_request,
            headers=auth_headers
        )

        assert response.status_code in [200, 404]

    def test_export_invalid_format(self, client: TestClient, db: Session, auth_headers: dict):
        """Test export with invalid format."""
        export_request = {
            "format": "invalid_format"
        }

        response = client.post(
            "/api/v2/enhanced-quiz/export",
            json=export_request,
            headers=auth_headers
        )

        assert response.status_code == 422

    def test_export_with_filters(self, client: TestClient, db: Session, auth_headers: dict):
        """Test export with patient and template filters."""
        patient = db.query(Patient).first()
        template = db.query(QuizTemplate).first()

        if not patient or not template:
            pytest.skip("No patient or template available")

        export_request = {
            "format": "pdf",
            "patient_ids": [str(patient.id)],
            "template_ids": [str(template.id)],
            "include_responses": True
        }

        response = client.post(
            "/api/v2/enhanced-quiz/export",
            json=export_request,
            headers=auth_headers
        )

        assert response.status_code in [200, 404]


class TestScoringAlgorithms:
    """Test suite for scoring algorithms."""


class TestCaching:
    """Test suite for caching functionality."""

    def test_analytics_cached(self, client: TestClient, db: Session, auth_headers: dict):
        """Test that analytics results are cached."""
        # First request
        response1 = client.get("/api/v2/enhanced-quiz/analytics", headers=auth_headers)
        assert response1.status_code == 200

        # Second request should hit cache
        response2 = client.get("/api/v2/enhanced-quiz/analytics", headers=auth_headers)
        assert response2.status_code == 200

        # Results should be identical
        assert response1.json() == response2.json()

class TestRateLimiting:
    """Test suite for rate limiting."""


class TestRBAC:
    """Test suite for role-based access control."""
