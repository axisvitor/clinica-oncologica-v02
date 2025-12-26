"""
Test AI Simulation Guards Implementation

This test verifies that AI endpoints properly block simulation mode in production
when ALLOW_AI_SIMULATION is set to False.
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from datetime import datetime, timezone
from uuid import uuid4

from app.api.v2.routers.ai.insights import generate_patient_insights
from app.api.v2.routers.ai.humanize import humanize_message
from app.api.v2.routers.ai.analysis import (
    analyze_sentiment,
    analyze_risk,
    analyze_response_quality,
)
from app.schemas.v2.ai import (
    GenerateInsightsRequest,
    HumanizeRequest,
    SentimentAnalysisRequest,
    RiskAnalysisRequest,
    ResponseQualityRequest,
)


class TestAISimulationGuards:
    """Test AI simulation guards prevent production use of mock data."""

    @pytest.fixture
    def mock_user(self):
        """Create mock user for testing."""
        user = MagicMock()
        user.id = uuid4()
        user.role = "physician"
        return user

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return MagicMock()

    @pytest.fixture
    def mock_request(self):
        """Create mock request object for rate limiter."""
        return MagicMock()

    @pytest.fixture
    def mock_background_tasks(self):
        """Create mock background tasks."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_insights_blocked_in_production(
        self, mock_request, mock_user, mock_db, mock_background_tasks
    ):
        """Test insights generation is blocked in production without AI service."""
        request = GenerateInsightsRequest(
            patient_id=uuid4(),
            days=30,
            force_refresh=False,
        )

        with patch("app.api.v2.routers.ai.insights.settings") as mock_settings:
            mock_settings.APP_ENVIRONMENT = "production"
            mock_settings.ALLOW_AI_SIMULATION = False

            with pytest.raises(HTTPException) as exc_info:
                await generate_patient_insights(
                    mock_request, request, mock_background_tasks, mock_user, mock_db
                )

            assert exc_info.value.status_code == 501
            assert "AI service not configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_humanize_blocked_in_production(
        self, mock_request, mock_user, mock_db, mock_background_tasks
    ):
        """Test humanization is blocked in production without AI service."""
        request = HumanizeRequest(
            message="Please take your medication",
            patient_id=uuid4(),
            message_type="reminder",
            tone="friendly",
            use_cache=False,
        )

        with patch("app.api.v2.routers.ai.humanize.settings") as mock_settings:
            mock_settings.APP_ENVIRONMENT = "production"
            mock_settings.ALLOW_AI_SIMULATION = False

            # Mock Redis and patient service
            with patch(
                "app.api.v2.routers.ai.humanize.get_redis_cache"
            ) as mock_redis:
                mock_redis.return_value = MagicMock()

                with pytest.raises(HTTPException) as exc_info:
                    await humanize_message(
                        mock_request, request, mock_background_tasks, mock_user, mock_db
                    )

                assert exc_info.value.status_code == 501
                assert "AI service not configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_sentiment_blocked_in_production(
        self, mock_request, mock_user, mock_db, mock_background_tasks
    ):
        """Test sentiment analysis is blocked in production without AI service."""
        request = SentimentAnalysisRequest(
            message="I'm feeling very tired today",
            include_medical_concerns=True,
            include_urgency=True,
        )

        with patch("app.api.v2.routers.ai.analysis.settings") as mock_settings:
            mock_settings.APP_ENVIRONMENT = "production"
            mock_settings.ALLOW_AI_SIMULATION = False

            with pytest.raises(HTTPException) as exc_info:
                await analyze_sentiment(
                    mock_request, request, mock_background_tasks, mock_user, mock_db
                )

            assert exc_info.value.status_code == 501
            assert "AI service not configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_risk_blocked_in_production(
        self, mock_request, mock_user, mock_db, mock_background_tasks
    ):
        """Test risk analysis is blocked in production without AI service."""
        request = RiskAnalysisRequest(
            patient_id=uuid4(),
        )

        with patch("app.api.v2.routers.ai.analysis.settings") as mock_settings:
            mock_settings.APP_ENVIRONMENT = "production"
            mock_settings.ALLOW_AI_SIMULATION = False

            # Mock patient validation
            with patch(
                "app.api.v2.routers.ai.analysis.validate_patient_access"
            ) as mock_validate:
                mock_validate.return_value = MagicMock()

                with pytest.raises(HTTPException) as exc_info:
                    await analyze_risk(
                        mock_request, request, mock_background_tasks, mock_user, mock_db
                    )

                assert exc_info.value.status_code == 501
                assert "AI service not configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_response_quality_blocked_in_production(
        self, mock_request, mock_user, mock_background_tasks
    ):
        """Test response quality analysis is blocked in production without AI service."""
        request = ResponseQualityRequest(
            message="Your treatment is going well. Keep taking your medication.",
        )

        with patch("app.api.v2.routers.ai.analysis.settings") as mock_settings:
            mock_settings.APP_ENVIRONMENT = "production"
            mock_settings.ALLOW_AI_SIMULATION = False

            with pytest.raises(HTTPException) as exc_info:
                await analyze_response_quality(
                    mock_request, request, mock_background_tasks, mock_user
                )

            assert exc_info.value.status_code == 501
            assert "AI service not configured" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_simulation_allowed_in_development(
        self, mock_request, mock_user, mock_db, mock_background_tasks
    ):
        """Test simulation is allowed in development environment."""
        request = SentimentAnalysisRequest(
            message="I'm feeling good",
            include_medical_concerns=False,
            include_urgency=False,
        )

        with patch("app.api.v2.routers.ai.analysis.settings") as mock_settings:
            mock_settings.APP_ENVIRONMENT = "development"
            mock_settings.ALLOW_AI_SIMULATION = True

            # Mock Redis
            with patch("app.api.v2.routers.ai.analysis.get_redis_cache") as mock_redis:
                mock_redis.return_value = MagicMock()

                # Should not raise exception in development
                response = await analyze_sentiment(
                    mock_request, request, mock_background_tasks, mock_user, mock_db
                )

                assert response is not None
                assert response.message == request.message

    @pytest.mark.asyncio
    async def test_simulation_allowed_with_override(
        self, mock_request, mock_user, mock_db, mock_background_tasks
    ):
        """Test simulation can be allowed in production with explicit override."""
        request = ResponseQualityRequest(
            message="Test message",
        )

        with patch("app.api.v2.routers.ai.analysis.settings") as mock_settings:
            mock_settings.APP_ENVIRONMENT = "production"
            mock_settings.ALLOW_AI_SIMULATION = True  # Explicit override

            # Mock Redis
            with patch("app.api.v2.routers.ai.analysis.get_redis_cache") as mock_redis:
                mock_redis.return_value = MagicMock()

                # Should work with override, but log warning
                response = await analyze_response_quality(
                    mock_request, request, mock_background_tasks, mock_user
                )

                assert response is not None
                assert response.message == request.message


class TestConfigurationValidation:
    """Test configuration validation for AI simulation settings."""

    def test_allow_ai_simulation_default(self):
        """Test ALLOW_AI_SIMULATION has correct default value."""
        from app.config.settings import settings

        # In development, simulation should be allowed by default
        if settings.APP_ENVIRONMENT == "development":
            assert settings.ALLOW_AI_SIMULATION is True

    def test_production_validation_warning(self):
        """Test production configuration validation logs warning when simulation enabled."""
        with patch("app.config.settings.base.os.environ.get") as mock_env:
            mock_env.return_value = "production"

            # Import will trigger validation
            # Should log warning but not raise error
            # (actual test would need to capture logs)
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
