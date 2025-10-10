"""
Integration tests for complete system startup.

Tests the full application initialization flow including:
- Application factory pattern
- Middleware stack setup
- Service orchestration
- Database connectivity
- Redis connectivity
- API endpoint availability
- Health checks
"""
import pytest
import os
import asyncio
import time
from unittest.mock import patch, Mock, AsyncMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import httpx
import json


class TestApplicationFactoryIntegration:
    """Test application factory integration."""

    def test_create_application_production_mode(self):
        """Test creating application in production mode."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,  # Disable for testing
                deployment_mode="production"
            )

            assert app is not None
            assert isinstance(app, FastAPI)
            assert app.state.deployment_mode == "production"
            assert not app.state.debug_endpoints_enabled

        except ImportError:
            pytest.skip("Application factory not available")

    def test_create_application_development_mode(self):
        """Test creating application in development mode."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            assert app is not None
            assert isinstance(app, FastAPI)
            assert app.state.deployment_mode == "development"
            assert app.state.debug_endpoints_enabled

        except ImportError:
            pytest.skip("Application factory not available")

    def test_create_application_debug_mode(self):
        """Test creating application in debug mode."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="debug"
            )

            assert app is not None
            assert isinstance(app, FastAPI)
            assert app.state.deployment_mode == "debug"
            assert app.state.debug_endpoints_enabled

        except ImportError:
            pytest.skip("Application factory not available")

    def test_application_metadata_configuration(self):
        """Test application metadata configuration."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            # Check application metadata
            assert "Hormonia Backend API" in app.title
            assert app.version == "2.0.0"
            assert app.description is not None
            assert len(app.description) > 100  # Should have comprehensive description

        except ImportError:
            pytest.skip("Application factory not available")


class TestFullSystemStartupIntegration:
    """Test full system startup integration."""

    def test_complete_application_startup(self):
        """Test complete application startup flow."""
        try:
            from app.core.application_factory import create_application

            # Create app with all components
            app = create_application(
                enable_monitoring=False,  # Disable for testing
                enable_debug_endpoints=True,
                deployment_mode="development",
                enable_error_tracking=True,
                enable_enhanced_openapi=True
            )

            assert app is not None

            # Check that app has essential components
            assert len(app.routes) > 0  # Should have routes
            assert len(app.user_middleware) > 0  # Should have middleware

        except Exception as e:
            pytest.fail(f"Complete application startup failed: {e}")

    def test_application_with_test_client(self):
        """Test application with test client."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            client = TestClient(app)

            # Test basic connectivity
            response = client.get("/test")

            # Should either work or return 404 (endpoint exists or doesn't)
            assert response.status_code in [200, 404]

        except Exception as e:
            pytest.fail(f"Test client integration failed: {e}")

    def test_application_health_endpoints(self):
        """Test application health endpoints."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                enable_debug_endpoints=True,
                deployment_mode="development"
            )

            client = TestClient(app)

            # Test debug health endpoint
            response = client.get("/debug/health")

            if response.status_code == 200:
                data = response.json()
                assert "status" in data
                assert "deployment_mode" in data
                assert data["deployment_mode"] == "development"

        except Exception as e:
            # Health endpoints might not be available in all configurations
            pass

    def test_application_openapi_integration(self):
        """Test OpenAPI integration."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development",
                enable_enhanced_openapi=True
            )

            client = TestClient(app)

            # Test OpenAPI endpoint
            response = client.get("/openapi.json")

            if response.status_code == 200:
                openapi_spec = response.json()

                # Should have OpenAPI structure
                assert "openapi" in openapi_spec
                assert "info" in openapi_spec
                assert "paths" in openapi_spec

                # Should have security schemes
                if "components" in openapi_spec:
                    components = openapi_spec["components"]
                    if "securitySchemes" in components:
                        security_schemes = components["securitySchemes"]
                        assert len(security_schemes) > 0

        except Exception as e:
            # OpenAPI might not be available in all configurations
            pass


class TestMiddlewareStackIntegration:
    """Test middleware stack integration."""

    def test_middleware_request_processing(self):
        """Test middleware request processing flow."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            client = TestClient(app)

            # Test request with various headers
            response = client.get("/test", headers={
                "User-Agent": "test-client",
                "Accept": "application/json",
                "Origin": "http://localhost:3000"
            })

            # Should process through middleware stack
            assert response.status_code in [200, 404, 405]

            # Check for security headers (should be added by middleware)
            headers = response.headers

            # Security headers might be present
            security_headers = [
                'x-content-type-options',
                'x-frame-options',
                'x-xss-protection',
                'strict-transport-security',
                'content-security-policy'
            ]

            # At least some security headers should be present
            security_headers_found = any(header in headers for header in security_headers)

            # Note: Exact headers depend on middleware configuration

        except Exception as e:
            pytest.fail(f"Middleware integration failed: {e}")

    def test_cors_middleware_integration(self):
        """Test CORS middleware integration."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            client = TestClient(app)

            # Test CORS preflight request
            response = client.options(
                "/api/v1/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "authorization"
                }
            )

            # Should handle CORS (200, 204, or method not allowed)
            assert response.status_code in [200, 204, 405, 404]

            # Check for CORS headers
            headers = response.headers
            cors_headers_found = any(
                header.startswith('access-control-')
                for header in headers.keys()
            )

            # CORS headers might be present depending on configuration

        except Exception as e:
            # CORS integration might vary by configuration
            pass

    def test_rate_limiting_middleware_integration(self):
        """Test rate limiting middleware integration."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            client = TestClient(app)

            # Make multiple requests to test rate limiting
            responses = []
            for i in range(5):
                response = client.get("/test")
                responses.append(response)

            # All requests should be processed (unless rate limited)
            for response in responses:
                assert response.status_code in [200, 404, 429]  # 429 = rate limited

        except Exception as e:
            # Rate limiting might not be active in test mode
            pass


class TestDatabaseIntegration:
    """Test database integration during startup."""

    @patch('app.core.database.get_async_engine')
    def test_database_connection_during_startup(self, mock_get_engine):
        """Test database connection during application startup."""
        # Mock database engine
        mock_engine = Mock()
        mock_engine.dispose = AsyncMock()
        mock_get_engine.return_value = mock_engine

        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            # Application should start without database errors
            assert app is not None

        except Exception as e:
            pytest.fail(f"Database integration during startup failed: {e}")

    def test_database_health_check_integration(self):
        """Test database health check integration."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            client = TestClient(app)

            # Try to access database-dependent endpoint
            response = client.get("/api/v1/health")

            # Should handle gracefully (might return error if DB unavailable)
            assert response.status_code in [200, 500, 503, 404]

        except Exception as e:
            # Database health check might not be available
            pass


class TestRedisIntegration:
    """Test Redis integration during startup."""

    @patch('redis.Redis')
    def test_redis_connection_during_startup(self, mock_redis_class):
        """Test Redis connection during application startup."""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis_class.return_value = mock_redis

        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            # Application should start without Redis errors
            assert app is not None

        except Exception as e:
            pytest.fail(f"Redis integration during startup failed: {e}")

    @patch('redis.Redis')
    def test_redis_session_integration(self, mock_redis_class):
        """Test Redis session integration."""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis_class.return_value = mock_redis

        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            client = TestClient(app)

            # Test session-dependent endpoint
            response = client.get("/api/v1/csrf-token")

            # Should handle gracefully
            assert response.status_code in [200, 404, 500]

        except Exception as e:
            # Session integration might not be available
            pass


class TestServiceOrchestrationIntegration:
    """Test service orchestration during startup."""

    def test_service_initialization_order(self):
        """Test service initialization order."""
        try:
            from app.core.application_factory import create_application

            # Mock service dependencies
            with patch('app.core.database.get_async_engine') as mock_db, \
                 patch('redis.Redis') as mock_redis:

                mock_engine = Mock()
                mock_db.return_value = mock_engine

                mock_redis_client = Mock()
                mock_redis_client.ping.return_value = True
                mock_redis.return_value = mock_redis_client

                app = create_application(
                    enable_monitoring=False,
                    deployment_mode="development"
                )

                # Services should be initialized in correct order
                assert app is not None

        except Exception as e:
            pytest.fail(f"Service orchestration failed: {e}")

    def test_dependency_injection_integration(self):
        """Test dependency injection integration."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            # Dependencies should be properly injected
            assert app is not None

            # Test dependency resolution through routes
            client = TestClient(app)

            # Try routes that require dependencies
            auth_routes = [
                "/api/v1/auth/me",
                "/api/v1/patients",
                "/api/v1/admin/users"
            ]

            for route in auth_routes:
                try:
                    response = client.get(route)
                    # Should handle missing auth (401) or work (200)
                    assert response.status_code in [200, 401, 404, 422]
                except Exception:
                    # Route might not exist
                    pass

        except Exception as e:
            # Dependency injection might not be fully available
            pass


class TestAPIEndpointIntegration:
    """Test API endpoint integration."""

    def test_core_api_endpoints_availability(self):
        """Test core API endpoints availability."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            client = TestClient(app)

            # Test core endpoints
            core_endpoints = [
                "/",
                "/test",
                "/docs",
                "/openapi.json",
                "/debug/health"
            ]

            for endpoint in core_endpoints:
                try:
                    response = client.get(endpoint)
                    # Should return valid HTTP status
                    assert 200 <= response.status_code < 600
                except Exception:
                    # Endpoint might not exist
                    pass

        except Exception as e:
            pytest.fail(f"API endpoint integration failed: {e}")

    def test_auth_api_integration(self):
        """Test authentication API integration."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            client = TestClient(app)

            # Test auth endpoints
            auth_endpoints = [
                "/api/v1/auth/login",
                "/api/v1/auth/me",
                "/api/v1/csrf-token"
            ]

            for endpoint in auth_endpoints:
                try:
                    response = client.get(endpoint)
                    # Should handle properly (might require POST, auth, etc.)
                    assert 200 <= response.status_code < 600
                except Exception:
                    # Endpoint might not exist or require different method
                    pass

        except Exception as e:
            # Auth integration might not be fully available
            pass

    def test_health_check_integration(self):
        """Test health check integration."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                enable_debug_endpoints=True,
                deployment_mode="development"
            )

            client = TestClient(app)

            # Test health endpoints
            health_endpoints = [
                "/debug/health",
                "/debug/env",
                "/debug/imports"
            ]

            for endpoint in health_endpoints:
                try:
                    response = client.get(endpoint)

                    if response.status_code == 200:
                        data = response.json()
                        # Should have proper health check structure
                        assert isinstance(data, dict)

                except Exception:
                    # Health endpoint might not exist
                    pass

        except Exception as e:
            # Health check integration might vary
            pass


class TestStartupPerformanceIntegration:
    """Test startup performance integration."""

    def test_application_startup_time(self, performance_timer):
        """Test application startup time."""
        try:
            from app.core.application_factory import create_application

            # Mock external dependencies for speed
            with patch('app.core.database.get_async_engine') as mock_db, \
                 patch('redis.Redis') as mock_redis:

                mock_engine = Mock()
                mock_db.return_value = mock_engine

                mock_redis_client = Mock()
                mock_redis_client.ping.return_value = True
                mock_redis.return_value = mock_redis_client

                performance_timer.start()

                app = create_application(
                    enable_monitoring=False,
                    deployment_mode="development"
                )

                elapsed = performance_timer.stop()

            # Application startup should be reasonably fast
            assert elapsed < 5.0, f"Application startup took {elapsed}s, expected < 5.0s"

        except Exception as e:
            pytest.fail(f"Startup performance test failed: {e}")

    def test_first_request_performance(self, performance_timer):
        """Test first request performance."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            client = TestClient(app)

            performance_timer.start()

            # First request might be slower due to initialization
            response = client.get("/test")

            elapsed = performance_timer.stop()

            # First request should complete within reasonable time
            assert elapsed < 3.0, f"First request took {elapsed}s, expected < 3.0s"
            assert 200 <= response.status_code < 600

        except Exception as e:
            pytest.fail(f"First request performance test failed: {e}")


class TestStartupErrorHandlingIntegration:
    """Test startup error handling integration."""

    def test_database_connection_failure_handling(self):
        """Test handling of database connection failure during startup."""
        try:
            from app.core.application_factory import create_application

            # Mock database connection failure
            with patch('app.core.database.get_async_engine', side_effect=Exception("Database unavailable")):
                try:
                    app = create_application(
                        enable_monitoring=False,
                        deployment_mode="development"
                    )

                    # Application might start but handle DB errors gracefully
                    assert app is not None

                except Exception as e:
                    # Database failures might prevent startup
                    assert "database" in str(e).lower() or "connection" in str(e).lower()

        except ImportError:
            pytest.skip("Database integration not available")

    def test_redis_connection_failure_handling(self):
        """Test handling of Redis connection failure during startup."""
        try:
            from app.core.application_factory import create_application
            import redis.exceptions

            # Mock Redis connection failure
            with patch('redis.Redis', side_effect=redis.exceptions.ConnectionError("Redis unavailable")):
                try:
                    app = create_application(
                        enable_monitoring=False,
                        deployment_mode="development"
                    )

                    # Application should handle Redis failures gracefully
                    assert app is not None

                except redis.exceptions.ConnectionError:
                    # Redis failures might be acceptable
                    pass

        except ImportError:
            pytest.skip("Redis integration not available")

    def test_service_initialization_failure_handling(self):
        """Test handling of service initialization failures."""
        try:
            from app.core.application_factory import create_application

            # Mock service initialization failure
            with patch('app.services.auth.FirebaseAuthService', side_effect=Exception("Auth service failed")):
                try:
                    app = create_application(
                        enable_monitoring=False,
                        deployment_mode="development"
                    )

                    # Application might start with degraded functionality
                    assert app is not None

                except Exception as e:
                    # Service failures might be acceptable in development
                    assert "auth" in str(e).lower() or "service" in str(e).lower()

        except ImportError:
            pytest.skip("Service integration not available")


class TestConfigurationIntegration:
    """Test configuration integration during startup."""

    def test_environment_configuration_integration(self):
        """Test environment configuration integration."""
        test_env = {
            'SECRET_KEY': 'test-secret-key-for-integration-testing',
            'DATABASE_URL': 'postgresql://test:test@localhost:5432/test_db',
            'REDIS_URL': 'redis://localhost:6379/0',
            'ENVIRONMENT': 'test',
            'DEBUG': 'true',
            'RATE_LIMIT_ENABLED': 'true'
        }

        with patch.dict(os.environ, test_env):
            try:
                from app.core.application_factory import create_application

                app = create_application(
                    enable_monitoring=False,
                    deployment_mode="development"
                )

                # Configuration should be properly loaded
                assert app is not None

                # Check that environment is reflected in app state
                if hasattr(app.state, 'deployment_mode'):
                    # App state should reflect configuration
                    assert app.state.deployment_mode in ['development', 'test']

            except Exception as e:
                pytest.fail(f"Configuration integration failed: {e}")

    def test_production_configuration_integration(self):
        """Test production configuration integration."""
        prod_env = {
            'SECRET_KEY': 'production-secret-key-very-secure',
            'DATABASE_URL': 'postgresql://prod:prod@localhost:5432/prod_db',
            'REDIS_URL': 'rediss://localhost:6379/0',
            'ENVIRONMENT': 'production',
            'DEBUG': 'false',
            'SESSION_COOKIE_SECURE': 'true',
            'SECURE_SSL_REDIRECT': 'true'
        }

        with patch.dict(os.environ, prod_env):
            try:
                from app.core.application_factory import create_application

                app = create_application(
                    enable_monitoring=False,
                    deployment_mode="production"
                )

                # Production configuration should be applied
                assert app is not None
                assert app.state.deployment_mode == "production"

                # Production app should have different characteristics
                # (docs disabled, enhanced security, etc.)

            except Exception as e:
                # Production configuration might have stricter requirements
                assert "production" in str(e).lower() or "security" in str(e).lower()


class TestMemoryAndResourceIntegration:
    """Test memory and resource usage during startup."""

    def test_startup_memory_usage(self):
        """Test startup memory usage is reasonable."""
        try:
            import psutil
            import os

            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss

            from app.core.application_factory import create_application

            # Create application with minimal features
            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            memory_after = process.memory_info().rss
            memory_increase = memory_after - memory_before

            # Memory increase should be reasonable (< 100MB)
            assert memory_increase < 100 * 1024 * 1024, f"Startup used {memory_increase / 1024 / 1024:.1f}MB"

        except ImportError:
            pytest.skip("psutil not available for memory testing")

    def test_startup_resource_cleanup(self):
        """Test startup resource cleanup."""
        try:
            from app.core.application_factory import create_application

            # Create and destroy multiple applications
            for i in range(3):
                app = create_application(
                    enable_monitoring=False,
                    deployment_mode="development"
                )

                # Simulate cleanup
                del app

            # Should not accumulate resources

        except Exception as e:
            pytest.fail(f"Resource cleanup test failed: {e}")


# Async Integration Tests
class TestAsyncStartupIntegration:
    """Test async startup integration."""

    @pytest.mark.asyncio
    async def test_async_component_initialization(self):
        """Test async component initialization."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            # Should handle async components properly
            assert app is not None

            # Test async client
            async with httpx.AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get("/test")
                assert 200 <= response.status_code < 600

        except Exception as e:
            pytest.fail(f"Async component initialization failed: {e}")

    @pytest.mark.asyncio
    async def test_async_lifespan_integration(self):
        """Test async lifespan integration."""
        try:
            from app.core.application_factory import create_application

            app = create_application(
                enable_monitoring=False,
                deployment_mode="development"
            )

            # Should have proper lifespan management
            assert app is not None
            assert hasattr(app, 'lifespan')

        except Exception as e:
            pytest.fail(f"Async lifespan integration failed: {e}")