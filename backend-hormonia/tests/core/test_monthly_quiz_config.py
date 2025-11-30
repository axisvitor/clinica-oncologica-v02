"""
Tests for Monthly Quiz Configuration validation.

Tests cover:
- URL validation (HttpUrl)
- Trailing slash normalization
- Invalid URL rejection
- Scheme validation (HTTP/HTTPS only)
- Empty/None URL rejection

CRITICAL: These tests validate configuration used for patient quiz links.
Invalid URLs could prevent patients from accessing their health assessments.
"""

import pytest
from unittest.mock import patch
from pydantic import ValidationError


class TestMonthlyQuizBaseURLValidation:
    """Test suite for QUIZ_BASE_URL validation."""

    def test_valid_https_url_accepted(self):
        """Valid HTTPS URL should be accepted."""
        from app.core.monthly_quiz_config import MonthlyQuizConfig

        with patch.dict(
            "os.environ",
            {
                "QUIZ_BASE_URL": "https://quiz.example.com",
                "QUIZ_TOKEN_SECRET": "test-secret-key-for-testing",
            },
        ):
            config = MonthlyQuizConfig()
            assert config.QUIZ_BASE_URL == "https://quiz.example.com"

    def test_valid_http_url_accepted(self):
        """Valid HTTP URL should be accepted (for local development)."""
        from app.core.monthly_quiz_config import MonthlyQuizConfig

        with patch.dict(
            "os.environ",
            {
                "QUIZ_BASE_URL": "http://localhost:3000",
                "QUIZ_TOKEN_SECRET": "test-secret-key-for-testing",
            },
        ):
            config = MonthlyQuizConfig()
            assert config.QUIZ_BASE_URL == "http://localhost:3000"

    def test_trailing_slash_removed(self):
        """URLs with trailing slash should have it removed."""
        from app.core.monthly_quiz_config import MonthlyQuizConfig

        with patch.dict(
            "os.environ",
            {
                "QUIZ_BASE_URL": "https://quiz.example.com/",
                "QUIZ_TOKEN_SECRET": "test-secret-key-for-testing",
            },
        ):
            config = MonthlyQuizConfig()
            assert config.QUIZ_BASE_URL == "https://quiz.example.com"
            assert not config.QUIZ_BASE_URL.endswith("/")

    def test_multiple_trailing_slashes_handled(self):
        """URL with path should preserve path but remove trailing slash."""
        from app.core.monthly_quiz_config import MonthlyQuizConfig

        with patch.dict(
            "os.environ",
            {
                "QUIZ_BASE_URL": "https://quiz.example.com/api/v1/",
                "QUIZ_TOKEN_SECRET": "test-secret-key-for-testing",
            },
        ):
            config = MonthlyQuizConfig()
            assert config.QUIZ_BASE_URL == "https://quiz.example.com/api/v1"

    def test_invalid_url_rejected(self):
        """Invalid URLs should raise ValidationError."""
        from app.core.monthly_quiz_config import MonthlyQuizConfig

        with patch.dict(
            "os.environ",
            {
                "QUIZ_BASE_URL": "not-a-valid-url",
                "QUIZ_TOKEN_SECRET": "test-secret-key-for-testing",
            },
        ):
            with pytest.raises(ValidationError) as exc_info:
                MonthlyQuizConfig()

            # Check that the error mentions URL validation
            error_str = str(exc_info.value)
            assert "QUIZ_BASE_URL" in error_str or "url" in error_str.lower()

    def test_empty_url_rejected(self):
        """Empty URL should raise ValidationError."""
        from app.core.monthly_quiz_config import MonthlyQuizConfig

        with patch.dict(
            "os.environ",
            {
                "QUIZ_BASE_URL": "",
                "QUIZ_TOKEN_SECRET": "test-secret-key-for-testing",
            },
        ):
            with pytest.raises(ValidationError) as exc_info:
                MonthlyQuizConfig()

            error_str = str(exc_info.value)
            assert "QUIZ_BASE_URL" in error_str or "empty" in error_str.lower()

    def test_whitespace_only_url_rejected(self):
        """Whitespace-only URL should raise ValidationError."""
        from app.core.monthly_quiz_config import MonthlyQuizConfig

        with patch.dict(
            "os.environ",
            {
                "QUIZ_BASE_URL": "   ",
                "QUIZ_TOKEN_SECRET": "test-secret-key-for-testing",
            },
        ):
            with pytest.raises(ValidationError) as exc_info:
                MonthlyQuizConfig()

            error_str = str(exc_info.value)
            assert "QUIZ_BASE_URL" in error_str

    def test_ftp_scheme_rejected(self):
        """FTP URLs should be rejected (only HTTP/HTTPS allowed)."""
        from app.core.monthly_quiz_config import MonthlyQuizConfig

        with patch.dict(
            "os.environ",
            {
                "QUIZ_BASE_URL": "ftp://files.example.com",
                "QUIZ_TOKEN_SECRET": "test-secret-key-for-testing",
            },
        ):
            with pytest.raises(ValidationError) as exc_info:
                MonthlyQuizConfig()

            error_str = str(exc_info.value)
            assert "QUIZ_BASE_URL" in error_str or "scheme" in error_str.lower()

    def test_url_with_port_accepted(self):
        """URL with custom port should be accepted."""
        from app.core.monthly_quiz_config import MonthlyQuizConfig

        with patch.dict(
            "os.environ",
            {
                "QUIZ_BASE_URL": "https://quiz.example.com:8443",
                "QUIZ_TOKEN_SECRET": "test-secret-key-for-testing",
            },
        ):
            config = MonthlyQuizConfig()
            assert config.QUIZ_BASE_URL == "https://quiz.example.com:8443"

    def test_url_whitespace_trimmed(self):
        """URL with leading/trailing whitespace should be trimmed."""
        from app.core.monthly_quiz_config import MonthlyQuizConfig

        with patch.dict(
            "os.environ",
            {
                "QUIZ_BASE_URL": "  https://quiz.example.com  ",
                "QUIZ_TOKEN_SECRET": "test-secret-key-for-testing",
            },
        ):
            config = MonthlyQuizConfig()
            assert config.QUIZ_BASE_URL == "https://quiz.example.com"

    def test_default_url_valid(self):
        """Default URL should be valid when not overridden."""
        from app.core.monthly_quiz_config import MonthlyQuizConfig

        with patch.dict(
            "os.environ",
            {
                "QUIZ_TOKEN_SECRET": "test-secret-key-for-testing",
            },
            clear=False,
        ):
            # Remove the env var if it exists
            import os
            env_backup = os.environ.pop("QUIZ_BASE_URL", None)
            try:
                config = MonthlyQuizConfig()
                assert config.QUIZ_BASE_URL == "https://quiz-interface-production.up.railway.app"
            finally:
                if env_backup:
                    os.environ["QUIZ_BASE_URL"] = env_backup


class TestMonthlyQuizLinkGeneration:
    """Test that link generation works correctly with validated URLs."""

    def test_link_generation_no_double_slash(self):
        """Generated links should not have double slashes."""
        from app.core.monthly_quiz_config import MonthlyQuizConfig

        with patch.dict(
            "os.environ",
            {
                "QUIZ_BASE_URL": "https://quiz.example.com/",
                "QUIZ_TOKEN_SECRET": "test-secret-key-for-testing",
            },
        ):
            config = MonthlyQuizConfig()
            token = "abc123"
            link = f"{config.QUIZ_BASE_URL}?token={token}"

            assert "//?token" not in link
            assert link == "https://quiz.example.com?token=abc123"

    def test_link_generation_with_path(self):
        """Link generation with path-based URLs should work correctly."""
        from app.core.monthly_quiz_config import MonthlyQuizConfig

        with patch.dict(
            "os.environ",
            {
                "QUIZ_BASE_URL": "https://quiz.example.com/quiz/monthly/",
                "QUIZ_TOKEN_SECRET": "test-secret-key-for-testing",
            },
        ):
            config = MonthlyQuizConfig()
            token = "xyz789"
            link = f"{config.QUIZ_BASE_URL}?token={token}"

            assert link == "https://quiz.example.com/quiz/monthly?token=xyz789"


class TestMonthlyQuizConfigIntegration:
    """Integration tests for the complete configuration."""

    def test_config_loads_all_required_fields(self):
        """Configuration should load all required fields."""
        from app.core.monthly_quiz_config import MonthlyQuizConfig

        with patch.dict(
            "os.environ",
            {
                "QUIZ_BASE_URL": "https://quiz.example.com",
                "QUIZ_TOKEN_SECRET": "test-secret-key-for-testing",
            },
        ):
            config = MonthlyQuizConfig()

            # Verify essential fields are present
            assert hasattr(config, "QUIZ_BASE_URL")
            assert hasattr(config, "QUIZ_TOKEN_SECRET")
            assert hasattr(config, "MONTHLY_QUIZ_TOKEN_EXPIRY_HOURS")
            assert hasattr(config, "ENABLE_LINK_BASED_MONTHLY_QUIZ")

    def test_get_monthly_quiz_config_function(self):
        """get_monthly_quiz_config() should return valid config."""
        from app.core.monthly_quiz_config import get_monthly_quiz_config

        config = get_monthly_quiz_config()

        assert config is not None
        assert isinstance(config.QUIZ_BASE_URL, str)
        assert config.QUIZ_BASE_URL.startswith(("http://", "https://"))

    def test_should_use_link_based_quiz_function(self):
        """should_use_link_based_quiz() should work with valid config."""
        from app.core.monthly_quiz_config import should_use_link_based_quiz
        import uuid

        patient_id = str(uuid.uuid4())
        result = should_use_link_based_quiz(patient_id)

        assert isinstance(result, bool)
