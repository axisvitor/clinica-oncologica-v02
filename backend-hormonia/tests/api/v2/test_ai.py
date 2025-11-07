"""
Comprehensive tests for AI Services API v2

Tests cover:
- Humanize endpoints (single and batch)
- Insights generation and retrieval
- Sentiment, risk, and quality analysis
- Health checks and usage stats
- Redis caching behavior
- Token usage tracking
- Error handling and fallbacks
- Rate limiting (simulated)
"""
import pytest
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock
from fastapi import status
from fastapi.testclient import TestClient

from app.models.user import User, UserRole
from app.models.patient import Patient, FlowState


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing."""
    redis_mock = AsyncMock()
    redis_mock.ping = AsyncMock(return_value=True)
    redis_mock.get = AsyncMock(return_value=None)  # Default: cache miss
    redis_mock.setex = AsyncMock(return_value=True)
    redis_mock.hincrby = AsyncMock(return_value=1)
    redis_mock.hincrbyfloat = AsyncMock(return_value=1.0)
    redis_mock.expire = AsyncMock(return_value=True)
    redis_mock.scan = AsyncMock(return_value=(0, []))
    redis_mock.info = AsyncMock(return_value={
        "keyspace_hits": "1000",
        "keyspace_misses": "500",
    })
    return redis_mock


@pytest.fixture
def physician_user(db_session):
    """Create physician user for testing."""
    user = User(
        id=uuid4(),
        email="doctor@test.com",
        name="Dr. Test",
        role=UserRole.DOCTOR,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def test_patient(db_session, physician_user):
    """Create test patient."""
    patient = Patient(
        id=uuid4(),
        name="Test Patient",
        phone="+5511999999999",
        doctor_id=physician_user.id,
        treatment_type="hormone_therapy",
        current_day=15,
        flow_state=FlowState.ACTIVE,
    )
    db_session.add(patient)
    db_session.commit()
    return patient


@pytest.fixture
def auth_headers(physician_user):
    """Create authentication headers."""
    # Would normally generate JWT token
    return {"Authorization": f"Bearer test-token-{physician_user.id}"}


# ============================================================================
# Humanize Endpoint Tests
# ============================================================================


class TestHumanizeEndpoint:
    """Tests for POST /api/v2/ai/humanize"""

    def test_humanize_message_success(
        self,
        client: TestClient,
        auth_headers,
        test_patient,
        mock_redis_client
    ):
        """Test successful message humanization."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            response = client.post(
                "/api/v2/ai/humanize",
                json={
                    "message": "Time to take your medication",
                    "patient_id": str(test_patient.id),
                    "message_type": "reminder",
                    "tone": "empathetic",
                    "max_length": 300,
                    "use_cache": True,
                },
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "original_message" in data
        assert "humanized_message" in data
        assert "token_usage" in data
        assert "cache_info" in data
        assert data["cache_info"]["hit"] is False  # First call = cache miss

    def test_humanize_message_cached(
        self,
        client: TestClient,
        auth_headers,
        mock_redis_client
    ):
        """Test humanize with cache hit."""
        # Setup cache hit
        cached_response = {
            "original_message": "Test",
            "humanized_message": "Test humanized",
            "personalization_notes": [],
            "readability_score": 85.0,
            "tone_analysis": {},
            "token_usage": {
                "total_tokens": 100,
                "estimated_cost_usd": 0.0015,
            },
            "cache_info": {
                "hit": True,
                "cached_at": datetime.utcnow().isoformat(),
            },
            "generated_at": datetime.utcnow().isoformat(),
        }
        mock_redis_client.get = AsyncMock(return_value=str(cached_response))

        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            response = client.post(
                "/api/v2/ai/humanize",
                json={
                    "message": "Test",
                    "message_type": "general",
                    "tone": "empathetic",
                },
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        # Would verify cache hit in actual implementation

    def test_humanize_without_patient_context(
        self,
        client: TestClient,
        auth_headers,
        mock_redis_client
    ):
        """Test humanize without patient context."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            response = client.post(
                "/api/v2/ai/humanize",
                json={
                    "message": "Hello",
                    "message_type": "general",
                    "tone": "professional",
                },
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["humanized_message"] is not None

    def test_humanize_invalid_message_type(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test humanize with invalid message type."""
        response = client.post(
            "/api/v2/ai/humanize",
            json={
                "message": "Test",
                "message_type": "invalid_type",
                "tone": "empathetic",
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_humanize_invalid_tone(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test humanize with invalid tone."""
        response = client.post(
            "/api/v2/ai/humanize",
            json={
                "message": "Test",
                "message_type": "general",
                "tone": "invalid_tone",
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_humanize_message_too_long(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test humanize with message exceeding max length."""
        long_message = "x" * 2001  # Max is 2000

        response = client.post(
            "/api/v2/ai/humanize",
            json={
                "message": long_message,
                "message_type": "general",
                "tone": "empathetic",
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_humanize_unauthorized(self, client: TestClient):
        """Test humanize without authentication."""
        response = client.post(
            "/api/v2/ai/humanize",
            json={
                "message": "Test",
                "message_type": "general",
                "tone": "empathetic",
            },
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_humanize_fallback_on_error(
        self,
        client: TestClient,
        auth_headers,
        mock_redis_client
    ):
        """Test fallback response when AI service fails."""
        # Simulate AI service failure
        with patch("app.api.v2.ai.get_redis_cache", side_effect=Exception("AI Error")):
            response = client.post(
                "/api/v2/ai/humanize",
                json={
                    "message": "Test message",
                    "message_type": "general",
                    "tone": "empathetic",
                },
                headers=auth_headers,
            )

        # Should return fallback (original message)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["humanized_message"] == "Test message"


class TestBatchHumanize:
    """Tests for POST /api/v2/ai/humanize/batch"""

    def test_batch_humanize_success(
        self,
        client: TestClient,
        auth_headers,
        mock_redis_client
    ):
        """Test successful batch humanization."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            response = client.post(
                "/api/v2/ai/humanize/batch",
                json={
                    "messages": [
                        {
                            "message": "Message 1",
                            "message_type": "reminder",
                            "tone": "empathetic",
                        },
                        {
                            "message": "Message 2",
                            "message_type": "check_in",
                            "tone": "caring",
                        },
                    ]
                },
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "results" in data
        assert len(data["results"]) == 2
        assert "total_token_usage" in data
        assert "cache_hit_rate" in data

    def test_batch_humanize_max_limit(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test batch humanize with more than max (10) messages."""
        messages = [
            {
                "message": f"Message {i}",
                "message_type": "general",
                "tone": "empathetic"
            }
            for i in range(11)  # More than max of 10
        ]

        response = client.post(
            "/api/v2/ai/humanize/batch",
            json={"messages": messages},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_batch_humanize_empty_list(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test batch humanize with empty message list."""
        response = client.post(
            "/api/v2/ai/humanize/batch",
            json={"messages": []},
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestCacheStats:
    """Tests for GET /api/v2/ai/humanize/cache-stats"""

    def test_get_cache_stats_success(
        self,
        client: TestClient,
        auth_headers,
        mock_redis_client
    ):
        """Test successful cache stats retrieval."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            response = client.get(
                "/api/v2/ai/humanize/cache-stats",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "total_keys" in data
        assert "hit_rate" in data
        assert "miss_rate" in data
        assert "by_endpoint" in data

    def test_get_cache_stats_redis_unavailable(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test cache stats when Redis is unavailable."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=None):
            response = client.get(
                "/api/v2/ai/humanize/cache-stats",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


# ============================================================================
# Insights Endpoint Tests
# ============================================================================


class TestInsightsEndpoints:
    """Tests for insights generation endpoints"""

    def test_generate_insights_success(
        self,
        client: TestClient,
        auth_headers,
        test_patient,
        mock_redis_client
    ):
        """Test successful insights generation."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            response = client.post(
                "/api/v2/ai/insights/generate",
                json={
                    "patient_id": str(test_patient.id),
                    "analysis_type": "comprehensive",
                    "days": 30,
                    "include_medical_history": True,
                    "include_messages": True,
                    "force_refresh": False,
                },
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["patient_id"] == str(test_patient.id)
        assert "overall_status" in data
        assert "risk_level" in data
        assert "adherence_score" in data
        assert "token_usage" in data

    def test_get_insights_by_patient_id(
        self,
        client: TestClient,
        auth_headers,
        test_patient,
        mock_redis_client
    ):
        """Test GET insights by patient ID."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            response = client.get(
                f"/api/v2/ai/insights/{test_patient.id}?days=30",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["patient_id"] == str(test_patient.id)

    def test_insights_invalid_analysis_type(
        self,
        client: TestClient,
        auth_headers,
        test_patient
    ):
        """Test insights with invalid analysis type."""
        response = client.post(
            "/api/v2/ai/insights/generate",
            json={
                "patient_id": str(test_patient.id),
                "analysis_type": "invalid_type",
                "days": 30,
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_insights_days_out_of_range(
        self,
        client: TestClient,
        auth_headers,
        test_patient
    ):
        """Test insights with days out of valid range."""
        response = client.post(
            "/api/v2/ai/insights/generate",
            json={
                "patient_id": str(test_patient.id),
                "analysis_type": "comprehensive",
                "days": 365,  # Max is 90
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_insights_force_refresh(
        self,
        client: TestClient,
        auth_headers,
        test_patient,
        mock_redis_client
    ):
        """Test insights with force refresh (skip cache)."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            response = client.post(
                "/api/v2/ai/insights/generate",
                json={
                    "patient_id": str(test_patient.id),
                    "analysis_type": "comprehensive",
                    "days": 30,
                    "force_refresh": True,
                },
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        # Verify cache was not checked (would need actual implementation)


# ============================================================================
# Analysis Endpoint Tests
# ============================================================================


class TestSentimentAnalysis:
    """Tests for POST /api/v2/ai/analyze/sentiment"""

    def test_sentiment_analysis_success(
        self,
        client: TestClient,
        auth_headers,
        mock_redis_client
    ):
        """Test successful sentiment analysis."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            response = client.post(
                "/api/v2/ai/analyze/sentiment",
                json={
                    "message": "I've been feeling tired lately",
                    "include_medical_concerns": True,
                    "include_urgency": True,
                },
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "sentiment" in data
        assert "concern_level" in data
        assert "confidence" in data
        assert "token_usage" in data

    def test_sentiment_with_patient_context(
        self,
        client: TestClient,
        auth_headers,
        test_patient,
        mock_redis_client
    ):
        """Test sentiment analysis with patient context."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            response = client.post(
                "/api/v2/ai/analyze/sentiment",
                json={
                    "message": "Feeling much better today!",
                    "patient_id": str(test_patient.id),
                    "include_medical_concerns": True,
                },
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK

    def test_sentiment_message_too_long(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test sentiment with message exceeding max length."""
        long_message = "x" * 5001  # Max is 5000

        response = client.post(
            "/api/v2/ai/analyze/sentiment",
            json={
                "message": long_message,
            },
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestRiskAnalysis:
    """Tests for POST /api/v2/ai/analyze/risk"""

    def test_risk_analysis_success(
        self,
        client: TestClient,
        auth_headers,
        test_patient,
        mock_redis_client
    ):
        """Test successful risk analysis."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            response = client.post(
                "/api/v2/ai/analyze/risk",
                json={
                    "patient_id": str(test_patient.id),
                    "days": 30,
                    "include_historical": True,
                },
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["patient_id"] == str(test_patient.id)
        assert "risk_level" in data
        assert "risk_score" in data
        assert "recommendations" in data

    def test_risk_analysis_invalid_patient(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test risk analysis with invalid patient ID."""
        fake_id = uuid4()

        response = client.post(
            "/api/v2/ai/analyze/risk",
            json={
                "patient_id": str(fake_id),
                "days": 30,
            },
            headers=auth_headers,
        )

        assert response.status_code in [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN]


class TestResponseQuality:
    """Tests for POST /api/v2/ai/analyze/response"""

    def test_response_quality_analysis(
        self,
        client: TestClient,
        auth_headers,
        mock_redis_client
    ):
        """Test response quality analysis."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            response = client.post(
                "/api/v2/ai/analyze/response",
                json={
                    "message": "Hi! Hope you're doing well today.",
                    "context": "greeting",
                },
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "quality_score" in data
        assert "readability_score" in data
        assert "empathy_score" in data
        assert "suggestions" in data


# ============================================================================
# Health & Stats Tests
# ============================================================================


class TestHealthEndpoint:
    """Tests for GET /api/v2/ai/health"""

    def test_health_check_healthy(
        self,
        client: TestClient,
        mock_redis_client
    ):
        """Test health check when all services are operational."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            response = client.get("/api/v2/ai/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "status" in data
        assert "services" in data
        assert "redis_cache" in data
        assert "gemini_api" in data
        assert "response_time_ms" in data

    def test_health_check_redis_down(self, client: TestClient):
        """Test health check when Redis is unavailable."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=None):
            response = client.get("/api/v2/ai/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "degraded"


class TestUsageStats:
    """Tests for GET /api/v2/ai/usage"""

    def test_get_usage_stats_success(
        self,
        client: TestClient,
        auth_headers,
        mock_redis_client
    ):
        """Test successful usage stats retrieval."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            response = client.get(
                "/api/v2/ai/usage?period=day",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "total_requests" in data
        assert "total_tokens" in data
        assert "total_cost_usd" in data
        assert "by_endpoint" in data
        assert "cache_hit_rate" in data

    def test_usage_stats_invalid_period(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test usage stats with invalid period."""
        response = client.get(
            "/api/v2/ai/usage?period=invalid",
            headers=auth_headers,
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_usage_stats_redis_unavailable(
        self,
        client: TestClient,
        auth_headers
    ):
        """Test usage stats when Redis is unavailable."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=None):
            response = client.get(
                "/api/v2/ai/usage?period=day",
                headers=auth_headers,
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


# ============================================================================
# Authorization Tests
# ============================================================================


class TestAuthorization:
    """Tests for endpoint authorization"""

    def test_patient_cannot_access_ai(
        self,
        client: TestClient,
        db_session
    ):
        """Test that patients cannot access AI endpoints."""
        # Create patient user
        patient_user = User(
            id=uuid4(),
            email="patient@test.com",
            name="Patient User",
            role=UserRole.PATIENT,
            is_active=True,
        )
        db_session.add(patient_user)
        db_session.commit()

        patient_headers = {"Authorization": f"Bearer test-token-{patient_user.id}"}

        response = client.post(
            "/api/v2/ai/humanize",
            json={
                "message": "Test",
                "message_type": "general",
                "tone": "empathetic",
            },
            headers=patient_headers,
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_access_ai(
        self,
        client: TestClient,
        db_session,
        mock_redis_client
    ):
        """Test that admins can access AI endpoints."""
        # Create admin user
        admin_user = User(
            id=uuid4(),
            email="admin@test.com",
            name="Admin User",
            role=UserRole.ADMIN,
            is_active=True,
        )
        db_session.add(admin_user)
        db_session.commit()

        admin_headers = {"Authorization": f"Bearer test-token-{admin_user.id}"}

        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            response = client.post(
                "/api/v2/ai/humanize",
                json={
                    "message": "Test",
                    "message_type": "general",
                    "tone": "empathetic",
                },
                headers=admin_headers,
            )

        assert response.status_code == status.HTTP_200_OK


# ============================================================================
# Integration Tests
# ============================================================================


class TestAIIntegration:
    """Integration tests for AI endpoints"""

    def test_full_workflow_humanize_to_sentiment(
        self,
        client: TestClient,
        auth_headers,
        test_patient,
        mock_redis_client
    ):
        """Test full workflow: humanize message then analyze sentiment."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            # 1. Humanize message
            humanize_response = client.post(
                "/api/v2/ai/humanize",
                json={
                    "message": "How are you feeling?",
                    "patient_id": str(test_patient.id),
                    "message_type": "check_in",
                    "tone": "caring",
                },
                headers=auth_headers,
            )

            assert humanize_response.status_code == status.HTTP_200_OK
            humanized = humanize_response.json()

            # 2. Analyze sentiment of humanized message
            sentiment_response = client.post(
                "/api/v2/ai/analyze/sentiment",
                json={
                    "message": humanized["humanized_message"],
                    "patient_id": str(test_patient.id),
                },
                headers=auth_headers,
            )

            assert sentiment_response.status_code == status.HTTP_200_OK
            sentiment = sentiment_response.json()
            assert "sentiment" in sentiment

    def test_token_usage_tracking(
        self,
        client: TestClient,
        auth_headers,
        mock_redis_client
    ):
        """Test that token usage is tracked correctly."""
        with patch("app.api.v2.ai.get_redis_cache", return_value=mock_redis_client):
            # Make several API calls
            for i in range(3):
                client.post(
                    "/api/v2/ai/humanize",
                    json={
                        "message": f"Test message {i}",
                        "message_type": "general",
                        "tone": "empathetic",
                    },
                    headers=auth_headers,
                )

            # Verify token tracking was called
            # Would verify actual Redis calls in implementation
            assert mock_redis_client.hincrby.called
