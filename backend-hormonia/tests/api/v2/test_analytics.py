"""
Tests for Analytics API v2
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from datetime import datetime, timedelta


from app.utils.timezone import now_sao_paulo, now_sao_paulo_naive
class TestAnalyticsV2:
    """Test suite for analytics v2 endpoints"""
    
    def test_get_analytics_overview(self, client: TestClient, db: Session, auth_headers: dict):
        """Test analytics overview endpoint"""
        response = client.get("/api/v2/analytics/overview", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "total_patients" in data
        assert "total_quizzes" in data
        assert "completed_quizzes" in data
        assert "completion_rate" in data
        assert "active_patients_30d" in data
        assert "period" in data
        
        # Verify data types
        assert isinstance(data["total_patients"], int)
        assert isinstance(data["total_quizzes"], int)
        assert isinstance(data["completed_quizzes"], int)
        assert isinstance(data["completion_rate"], (int, float))
        assert isinstance(data["active_patients_30d"], int)
        
        # Verify completion rate is a percentage
        assert 0 <= data["completion_rate"] <= 100
    
    def test_get_analytics_overview_with_date_filter(self, client: TestClient, db: Session, auth_headers: dict):
        """Test analytics overview with date filtering"""
        start_date = (now_sao_paulo_naive() - timedelta(days=30)).isoformat()
        end_date = now_sao_paulo_naive().isoformat()
        
        response = client.get(
            f"/api/v2/analytics/overview?start_date={start_date}&end_date={end_date}",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "period" in data
        assert data["period"]["start_date"] is not None
        assert data["period"]["end_date"] is not None
    
    def test_get_quiz_status_distribution(self, client: TestClient, db: Session, auth_headers: dict):
        """Test quiz status distribution endpoint"""
        response = client.get("/api/v2/analytics/quiz-status", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "distribution" in data
        assert "total" in data
        assert "filters" in data
        
        # Verify distribution contains expected statuses
        assert isinstance(data["distribution"], dict)
        assert "started" in data["distribution"]
        assert "completed" in data["distribution"]
        assert "cancelled" in data["distribution"]
        
        # Verify counts are non-negative
        for status, count in data["distribution"].items():
            assert count >= 0
    
    def test_get_quiz_status_distribution_with_filters(self, client: TestClient, db: Session, auth_headers: dict):
        """Test quiz status distribution with month/year filters"""
        response = client.get(
            "/api/v2/analytics/quiz-status?month=1&year=2025",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["filters"]["month"] == 1
        assert data["filters"]["year"] == 2025
    
    def test_get_completion_trend(self, client: TestClient, db: Session, auth_headers: dict):
        """Test completion trend endpoint"""
        response = client.get("/api/v2/analytics/completion-trend", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "trend" in data
        assert "period" in data
        
        # Verify trend is a list
        assert isinstance(data["trend"], list)
        
        # Verify each trend point has required fields
        for point in data["trend"]:
            assert "year" in point
            assert "month" in point
            assert "total" in point
            assert "completed" in point
            assert "completion_rate" in point
            
            # Verify month is valid
            assert 1 <= point["month"] <= 12
            
            # Verify completion rate is a percentage
            assert 0 <= point["completion_rate"] <= 100
    
    def test_get_completion_trend_with_custom_months(self, client: TestClient, db: Session, auth_headers: dict):
        """Test completion trend with custom month range"""
        response = client.get(
            "/api/v2/analytics/completion-trend?months=12",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["period"]["months"] == 12
    
    def test_get_patient_engagement(self, client: TestClient, db: Session, auth_headers: dict):
        """Test patient engagement endpoint"""
        response = client.get("/api/v2/analytics/patient-engagement", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify required fields
        assert "engagement_levels" in data
        assert "average_quizzes_per_patient" in data
        assert "total_active_patients" in data
        
        # Verify engagement levels structure
        levels = data["engagement_levels"]
        assert "no_quizzes" in levels
        assert "low_engagement" in levels
        assert "high_engagement" in levels
        
        # Verify all counts are non-negative
        assert levels["no_quizzes"] >= 0
        assert levels["low_engagement"] >= 0
        assert levels["high_engagement"] >= 0
        
        # Verify average is non-negative
        assert data["average_quizzes_per_patient"] >= 0
        assert data["total_active_patients"] >= 0
    
    def test_analytics_endpoints_require_auth(self, client: TestClient, db: Session):
        """Test that analytics endpoints require authentication"""
        endpoints = [
            "/api/v2/analytics/overview",
            "/api/v2/analytics/quiz-status",
            "/api/v2/analytics/completion-trend",
            "/api/v2/analytics/patient-engagement",
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code in [401, 403], f"Endpoint {endpoint} should require auth"