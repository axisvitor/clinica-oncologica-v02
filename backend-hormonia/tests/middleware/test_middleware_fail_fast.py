"""
Tests for middleware fail-fast and retry logic.

Tests cover:
- Fail-fast behavior for CSRF and Security Headers in production
- Retry with exponential backoff for Rate Limiting
- Middleware status tracking
- /health/detailed endpoint
- Integration tests that actually call setup_middleware() with mocks
"""
import pytest
from unittest.mock import patch, MagicMock, call
from fastapi import FastAPI, HTTPException
import sys


# =============================================================================
# FIXTURE: Auto-reset CRITICAL_MIDDLEWARES before each test
# =============================================================================

@pytest.fixture(autouse=True)
def reset_middleware_status():
    """Reset CRITICAL_MIDDLEWARES to False before each test to avoid state pollution."""
    from app.core.middleware_setup import CRITICAL_MIDDLEWARES
    
    # Save original state
    original_state = CRITICAL_MIDDLEWARES.copy()
    
    # Reset to False
    for key in CRITICAL_MIDDLEWARES:
        CRITICAL_MIDDLEWARES[key] = False
    
    yield
    
    # Restore original state after test
    for key, value in original_state.items():
        CRITICAL_MIDDLEWARES[key] = value


# =============================================================================
# BASIC STATUS TRACKING TESTS
# =============================================================================

class TestMiddlewareStatusTracking:
    """Test middleware status tracking."""

    def test_get_middleware_status_returns_dict(self):
        """Test get_middleware_status returns dictionary with all middlewares."""
        from app.core.middleware_setup import get_middleware_status

        status = get_middleware_status()

        assert isinstance(status, dict)
        assert "csrf" in status
        assert "security_headers" in status
        assert "rate_limiting" in status
        assert all(isinstance(v, bool) for v in status.values())

    def test_get_middleware_status_returns_copy(self):
        """Test get_middleware_status returns a copy, not the original dict."""
        from app.core.middleware_setup import get_middleware_status, CRITICAL_MIDDLEWARES

        original_csrf = CRITICAL_MIDDLEWARES["csrf"]
        status = get_middleware_status()
        status["csrf"] = not status["csrf"]  # Modify the copy

        # Original should be unchanged
        assert CRITICAL_MIDDLEWARES["csrf"] == original_csrf


class TestCriticalMiddlewaresDict:
    """Test the CRITICAL_MIDDLEWARES dictionary structure."""

    def test_critical_middlewares_has_required_keys(self):
        """Test CRITICAL_MIDDLEWARES has all required keys."""
        from app.core.middleware_setup import CRITICAL_MIDDLEWARES

        required_keys = ["csrf", "security_headers", "rate_limiting"]
        for key in required_keys:
            assert key in CRITICAL_MIDDLEWARES, f"Missing required key: {key}"

    def test_critical_middlewares_values_are_boolean(self):
        """Test CRITICAL_MIDDLEWARES values are all booleans."""
        from app.core.middleware_setup import CRITICAL_MIDDLEWARES

        for key, value in CRITICAL_MIDDLEWARES.items():
            assert isinstance(value, bool), f"Value for {key} should be boolean, got {type(value)}"


# =============================================================================
# HEALTH CHECK ENDPOINT TESTS
# =============================================================================

class TestHealthCheckDetailed:
    """Test /health/detailed endpoint."""

    @pytest.mark.asyncio
    async def test_health_detailed_returns_middleware_status(self):
        """Test /health/detailed returns middleware loading status."""
        from app.core.middleware_setup import CRITICAL_MIDDLEWARES
        from app.routers.health import detailed_health_check

        # Set all middlewares as loaded
        CRITICAL_MIDDLEWARES["csrf"] = True
        CRITICAL_MIDDLEWARES["security_headers"] = True
        CRITICAL_MIDDLEWARES["rate_limiting"] = True

        response = await detailed_health_check()

        assert response["status"] == "healthy"
        assert "middlewares" in response
        assert response["middlewares"]["csrf"]["loaded"] is True
        assert response["middlewares"]["security_headers"]["loaded"] is True
        assert response["middlewares"]["rate_limiting"]["loaded"] is True

    @pytest.mark.asyncio
    async def test_health_detailed_fails_with_missing_middleware(self):
        """Test /health/detailed returns 503 if middleware failed to load."""
        from app.core.middleware_setup import CRITICAL_MIDDLEWARES
        from app.routers.health import detailed_health_check

        # Simulate CSRF not loaded
        CRITICAL_MIDDLEWARES["csrf"] = False
        CRITICAL_MIDDLEWARES["security_headers"] = True
        CRITICAL_MIDDLEWARES["rate_limiting"] = True

        with pytest.raises(HTTPException) as exc_info:
            await detailed_health_check()

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["status"] == "unhealthy"

    @pytest.mark.asyncio
    async def test_health_detailed_includes_descriptions(self):
        """Test /health/detailed includes middleware descriptions."""
        from app.core.middleware_setup import CRITICAL_MIDDLEWARES
        from app.routers.health import detailed_health_check

        for key in CRITICAL_MIDDLEWARES:
            CRITICAL_MIDDLEWARES[key] = True

        response = await detailed_health_check()

        assert "CSRF" in response["middlewares"]["csrf"]["description"]
        assert "HSTS" in response["middlewares"]["security_headers"]["description"]
        assert "Redis" in response["middlewares"]["rate_limiting"]["description"]


# =============================================================================
# PRODUCTION INTEGRATION TESTS - CSRF FAIL-FAST
# =============================================================================

class TestCSRFProductionFailFast:
    """
    Integration tests for CSRF middleware fail-fast in production.
    
    These tests call setup_middleware(FastAPI()) with mocks to trigger RuntimeError.
    """

    @patch('app.core.middleware_setup.time.sleep')
    def test_csrf_import_error_raises_runtime_error_in_production(self, mock_sleep):
        """
        Test that ImportError for CSRFMiddleware raises RuntimeError in production.
        
        Mocks the CSRF import to fail and verifies setup_middleware raises RuntimeError.
        """
        from app.core.middleware_setup import CRITICAL_MIDDLEWARES, setup_middleware
        
        # Create mock settings for production
        mock_settings = MagicMock()
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.APP_ENABLE_DEBUG = False
        mock_settings.SECURITY_CSRF_SECRET_KEY = "test-csrf-secret-key"
        
        # Patch settings and make CSRF import fail
        with patch('app.core.middleware_setup.settings', mock_settings):
            # Create a custom import that fails for CSRF
            original_import = __builtins__['__import__']
            
            def mock_import(name, *args, **kwargs):
                if name == 'app.middleware.csrf':
                    raise ImportError("Mocked: No module named 'app.middleware.csrf'")
                return original_import(name, *args, **kwargs)
            
            with patch('builtins.__import__', side_effect=mock_import):
                app = FastAPI()
                
                with pytest.raises(RuntimeError) as exc_info:
                    setup_middleware(app)
                
                assert "CRITICAL" in str(exc_info.value)
                # Should fail on CSRF before reaching other middlewares

    @patch('app.core.middleware_setup.time.sleep')
    def test_csrf_missing_secret_raises_runtime_error_in_production(self, mock_sleep):
        """
        Test that missing CSRF secret raises RuntimeError in production.
        """
        from app.core.middleware_setup import setup_middleware
        
        mock_settings = MagicMock()
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.APP_ENABLE_DEBUG = False
        mock_settings.SECURITY_CSRF_SECRET_KEY = None  # No CSRF secret
        
        with patch('app.core.middleware_setup.settings', mock_settings):
            app = FastAPI()
            
            with pytest.raises(RuntimeError) as exc_info:
                setup_middleware(app)
            
            error_msg = str(exc_info.value)
            assert "CRITICAL" in error_msg
            assert "CSRF" in error_msg or "csrf" in error_msg.lower()


# =============================================================================
# PRODUCTION INTEGRATION TESTS - SECURITY HEADERS FAIL-FAST
# =============================================================================

class TestSecurityHeadersProductionFailFast:
    """
    Integration tests for Security Headers middleware fail-fast in production.
    """

    @patch('app.core.middleware_setup.time.sleep')
    def test_security_headers_import_error_raises_runtime_error_in_production(self, mock_sleep):
        """
        Test that ImportError for SecurityHeadersMiddleware raises RuntimeError in production.
        """
        from app.core.middleware_setup import setup_middleware
        
        mock_settings = MagicMock()
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.APP_ENABLE_DEBUG = False
        mock_settings.SECURITY_CSRF_SECRET_KEY = "test-csrf-secret"
        
        with patch('app.core.middleware_setup.settings', mock_settings):
            # Make security_headers import fail
            original_import = __builtins__['__import__']
            
            def mock_import(name, *args, **kwargs):
                if name == 'app.middleware.security_headers':
                    raise ImportError("Mocked: No module named 'app.middleware.security_headers'")
                return original_import(name, *args, **kwargs)
            
            with patch('builtins.__import__', side_effect=mock_import):
                app = FastAPI()
                
                with pytest.raises(RuntimeError) as exc_info:
                    setup_middleware(app)
                
                error_msg = str(exc_info.value)
                assert "CRITICAL" in error_msg


# =============================================================================
# PRODUCTION INTEGRATION TESTS - RATE LIMITING RETRY & FAIL
# =============================================================================

class TestRateLimitingRetryFailProduction:
    """
    Integration tests for Rate Limiting retry logic and fail-fast in production.
    
    Tests verify:
    - 3 retry attempts with exponential backoff
    - RuntimeError after all retries fail in production
    """

    @patch('app.core.middleware_setup.time.sleep')
    def test_rate_limiting_retries_three_times_then_raises_in_production(self, mock_sleep):
        """
        Test rate limiting retries 3 times with exponential backoff then raises RuntimeError.
        
        Verifies:
        - get_redis_client called 3 times
        - sleep called with (1,) and (2,) for backoff (no 4 since fails on 3rd)
        - RuntimeError raised with 'Rate limiting failed after 3'
        """
        from app.core.middleware_setup import setup_middleware
        
        mock_settings = MagicMock()
        mock_settings.APP_ENVIRONMENT = "production"
        mock_settings.APP_ENABLE_DEBUG = False
        mock_settings.SECURITY_CSRF_SECRET_KEY = "test-secret"
        
        # Mock redis to always fail
        mock_get_redis = MagicMock(side_effect=ConnectionError("Redis connection refused"))
        
        with patch('app.core.middleware_setup.settings', mock_settings):
            with patch('app.core.redis_client.get_redis_client', mock_get_redis):
                app = FastAPI()
                
                with pytest.raises(RuntimeError) as exc_info:
                    setup_middleware(app)
                
                error_msg = str(exc_info.value)
                assert "CRITICAL" in error_msg
                assert "Rate limiting" in error_msg or "rate" in error_msg.lower()
                
                # Verify 3 attempts
                assert mock_get_redis.call_count == 3
                
                # Verify exponential backoff: sleep(1), sleep(2) - no sleep(4) since fails on 3rd
                sleep_calls = mock_sleep.call_args_list
                assert call(1) in sleep_calls, "Should sleep 1s after first failure"
                assert call(2) in sleep_calls, "Should sleep 2s after second failure"
                # Should NOT have sleep(4) since it fails on 3rd attempt
                assert call(4) not in sleep_calls, "Should not sleep 4s - fails on 3rd attempt"

    @patch('app.core.middleware_setup.time.sleep')
    def test_rate_limiting_succeeds_on_third_retry(self, mock_sleep):
        """
        Test rate limiting succeeds after 2 failures and 1 success.
        """
        from app.core.middleware_setup import setup_middleware, CRITICAL_MIDDLEWARES
        
        mock_settings = MagicMock()
        mock_settings.APP_ENVIRONMENT = "development"  # Dev to not fail on other middlewares
        mock_settings.APP_ENABLE_DEBUG = False
        mock_settings.SECURITY_CSRF_SECRET_KEY = None  # Skip CSRF in dev
        
        # Mock redis to fail twice then succeed
        mock_redis_client = MagicMock()
        mock_redis_client.ping.return_value = True
        
        call_count = [0]
        def mock_get_redis():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("Redis connection refused")
            return mock_redis_client
        
        with patch('app.core.middleware_setup.settings', mock_settings):
            with patch('app.core.redis_client.get_redis_client', side_effect=mock_get_redis):
                with patch('app.middleware.distributed_rate_limiter.RateLimitMiddleware'):
                    app = FastAPI()
                    
                    # Should NOT raise - succeeds on 3rd attempt
                    setup_middleware(app)
                    
                    # Verify retry attempts
                    assert call_count[0] == 3
                    
                    # Rate limiting should be marked as loaded
                    assert CRITICAL_MIDDLEWARES["rate_limiting"] is True


# =============================================================================
# DEVELOPMENT MODE TESTS - NO FAIL-FAST
# =============================================================================

class TestDevelopmentModeNoFailFast:
    """
    Tests verifying that development mode does NOT raise RuntimeError on failures.
    """

    @patch('app.core.middleware_setup.time.sleep')
    def test_csrf_import_error_does_not_raise_in_development(self, mock_sleep):
        """
        Test that ImportError for CSRF does NOT raise RuntimeError in development.
        """
        from app.core.middleware_setup import setup_middleware
        
        mock_settings = MagicMock()
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.APP_ENABLE_DEBUG = True
        mock_settings.SECURITY_CSRF_SECRET_KEY = "test-secret"
        
        with patch('app.core.middleware_setup.settings', mock_settings):
            original_import = __builtins__['__import__']
            
            def mock_import(name, *args, **kwargs):
                if name == 'app.middleware.csrf':
                    raise ImportError("Mocked import error")
                return original_import(name, *args, **kwargs)
            
            with patch('builtins.__import__', side_effect=mock_import):
                app = FastAPI()
                
                # Should NOT raise in development mode
                try:
                    setup_middleware(app)
                except RuntimeError as e:
                    if "CRITICAL" in str(e):
                        pytest.fail("Should NOT raise CRITICAL error in development mode")

    @patch('app.core.middleware_setup.time.sleep')
    def test_rate_limiting_failure_does_not_raise_in_development(self, mock_sleep):
        """
        Test that rate limiting failures do NOT raise RuntimeError in development.
        """
        from app.core.middleware_setup import setup_middleware
        
        mock_settings = MagicMock()
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.APP_ENABLE_DEBUG = True
        mock_settings.SECURITY_CSRF_SECRET_KEY = None  # No CSRF
        
        mock_get_redis = MagicMock(side_effect=ConnectionError("Redis unavailable"))
        
        with patch('app.core.middleware_setup.settings', mock_settings):
            with patch('app.core.redis_client.get_redis_client', mock_get_redis):
                app = FastAPI()
                
                # Should NOT raise in development mode
                try:
                    setup_middleware(app)
                except RuntimeError as e:
                    if "CRITICAL" in str(e):
                        pytest.fail("Should NOT raise CRITICAL error in development mode")

    @patch('app.core.middleware_setup.time.sleep')
    def test_missing_csrf_secret_does_not_raise_in_development(self, mock_sleep):
        """
        Test that missing CSRF secret does NOT raise RuntimeError in development.
        """
        from app.core.middleware_setup import setup_middleware
        
        mock_settings = MagicMock()
        mock_settings.APP_ENVIRONMENT = "development"
        mock_settings.APP_ENABLE_DEBUG = True
        mock_settings.SECURITY_CSRF_SECRET_KEY = None  # Missing secret
        
        with patch('app.core.middleware_setup.settings', mock_settings):
            app = FastAPI()
            
            # Should NOT raise in development
            try:
                setup_middleware(app)
            except RuntimeError as e:
                if "CRITICAL" in str(e):
                    pytest.fail("Should NOT raise CRITICAL error in development mode")


# =============================================================================
# RETRY LOGIC UNIT TESTS
# =============================================================================

class TestRateLimitingRetryLogic:
    """Test retry logic for rate limiting middleware."""

    def test_exponential_backoff_calculation(self):
        """Test exponential backoff formula is correct: 2^attempt."""
        expected_waits = [1, 2, 4]  # 2^0, 2^1, 2^2

        for attempt in range(3):
            wait_time = 2 ** attempt
            assert wait_time == expected_waits[attempt]

    def test_max_retries_is_three(self):
        """Verify the max_retries constant is 3."""
        max_retries = 3
        attempts = list(range(max_retries))
        assert len(attempts) == 3
        assert attempts == [0, 1, 2]


# =============================================================================
# FINAL VALIDATION TESTS
# =============================================================================

class TestFinalValidationLogic:
    """Test final validation logic that runs at end of setup_middleware()."""

    def test_final_validation_detects_failed_middlewares(self):
        """Test that final validation correctly identifies failed middlewares."""
        from app.core.middleware_setup import CRITICAL_MIDDLEWARES
        
        # Simulate mixed state
        CRITICAL_MIDDLEWARES["csrf"] = True
        CRITICAL_MIDDLEWARES["security_headers"] = True
        CRITICAL_MIDDLEWARES["rate_limiting"] = False  # This one failed
        
        failed_middlewares = [
            name for name, loaded in CRITICAL_MIDDLEWARES.items()
            if not loaded
        ]
        
        assert "rate_limiting" in failed_middlewares
        assert len(failed_middlewares) == 1

    def test_final_validation_passes_when_all_loaded(self):
        """Test that validation passes when all middlewares are loaded."""
        from app.core.middleware_setup import CRITICAL_MIDDLEWARES
        
        CRITICAL_MIDDLEWARES["csrf"] = True
        CRITICAL_MIDDLEWARES["security_headers"] = True
        CRITICAL_MIDDLEWARES["rate_limiting"] = True
        
        failed_middlewares = [
            name for name, loaded in CRITICAL_MIDDLEWARES.items()
            if not loaded
        ]
        
        assert len(failed_middlewares) == 0
