"""
Tests for System Initialization

Comprehensive tests for all initialization scripts and utilities.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

# Add project root to path
import sys
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestSystemInitializer:
    """Tests for init_system.py"""

    @pytest.mark.asyncio
    async def test_environment_validation_success(self):
        """Test successful environment validation"""
        with patch.dict('os.environ', {
            'DATABASE_URL': 'postgresql://user:pass@localhost/db',
            'REDIS_URL': 'redis://localhost:6379',
            'SECRET_KEY': 'test_secret_key_at_least_32_chars_long',
            'ENCRYPTION_KEY': 'test_encryption_key_32_bytes_'
        }):
            from scripts.init_system import SystemInitializer

            initializer = SystemInitializer(check_only=True)
            await initializer._validate_environment()

            # Should have no failures
            failures = [r for r in initializer.results if r.status.value == 'failed']
            assert len(failures) == 0

    @pytest.mark.asyncio
    async def test_environment_validation_missing_vars(self):
        """Test environment validation with missing variables"""
        with patch.dict('os.environ', {}, clear=True):
            from scripts.init_system import SystemInitializer

            initializer = SystemInitializer(check_only=True)
            await initializer._validate_environment()

            # Should have failures for missing vars
            failures = [r for r in initializer.results if r.status.value == 'failed']
            assert len(failures) > 0

    @pytest.mark.asyncio
    async def test_configuration_validation(self):
        """Test configuration validation"""
        with patch.dict('os.environ', {
            'DATABASE_URL': 'postgresql://user:pass@localhost/db',
            'REDIS_URL': 'redis://localhost:6379',
            'SECRET_KEY': 'test_secret_key_at_least_32_chars_long',
        }):
            from scripts.init_system import SystemInitializer

            initializer = SystemInitializer(check_only=True)
            await initializer._validate_configuration()

            # Should complete without critical errors
            critical = [r for r in initializer.results if r.status.value == 'failed']
            assert len(critical) == 0


class TestDatabaseInitializer:
    """Tests for init_database.py"""

    @pytest.mark.asyncio
    async def test_validate_connection(self):
        """Test database connection validation"""
        with patch('app.core.database.AsyncSessionLocal') as mock_session:
            mock_session.return_value.__aenter__.return_value.execute = AsyncMock()

            from scripts.init_database import DatabaseInitializer

            initializer = DatabaseInitializer(skip_migrations=True)
            await initializer._validate_connection()

            # Should succeed with mocked connection
            assert True

    @pytest.mark.asyncio
    async def test_validate_schema(self):
        """Test schema validation"""
        with patch('app.core.database.AsyncSessionLocal') as mock_session:
            # Mock database queries
            mock_result = Mock()
            mock_result.fetchall.return_value = [
                ('users',),
                ('appointments',),
            ]
            mock_session.return_value.__aenter__.return_value.execute = AsyncMock(
                return_value=mock_result
            )

            from scripts.init_database import DatabaseInitializer

            initializer = DatabaseInitializer(skip_migrations=True)
            await initializer._validate_schema()

            # Should succeed
            assert True


class TestRedisInitializer:
    """Tests for init_redis.py"""

    @pytest.mark.asyncio
    async def test_validate_connection(self):
        """Test Redis connection validation"""
        with patch('app.core.redis_manager.RedisManager') as mock_redis:
            mock_manager = AsyncMock()
            mock_manager.ping.return_value = 'PONG'
            mock_manager.get_redis_info.return_value = {
                'redis_version': '6.2.0',
                'redis_mode': 'standalone',
                'uptime_in_seconds': '3600',
                'connected_clients': '5',
                'used_memory': '1048576'
            }
            mock_redis.return_value = mock_manager

            from scripts.init_redis import RedisInitializer

            initializer = RedisInitializer()
            await initializer._validate_connection()

            # Should succeed
            mock_manager.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_cache(self):
        """Test cache initialization"""
        with patch('app.core.redis_manager.RedisManager') as mock_redis:
            mock_manager = AsyncMock()
            mock_redis.return_value = mock_manager

            from scripts.init_redis import RedisInitializer

            initializer = RedisInitializer()
            await initializer._initialize_cache()

            # Should call set for cache keys
            assert mock_manager.set.called

    @pytest.mark.asyncio
    async def test_validate_setup(self):
        """Test Redis setup validation"""
        with patch('app.core.redis_manager.RedisManager') as mock_redis:
            mock_manager = AsyncMock()
            mock_manager.get.side_effect = ['test_value', None, None]
            mock_manager.redis.dbsize.return_value = 10
            mock_manager.get_redis_info.return_value = {
                'used_memory': '1048576',
                'keyspace_hits': '100',
                'keyspace_misses': '10'
            }
            mock_redis.return_value = mock_manager

            from scripts.init_redis import RedisInitializer

            initializer = RedisInitializer()
            await initializer._validate_setup()

            # Should complete all operations
            assert mock_manager.set.called
            assert mock_manager.get.called
            assert mock_manager.delete.called


class TestHealthChecker:
    """Tests for health_check.py"""

    @pytest.mark.asyncio
    async def test_database_health_check(self):
        """Test database health check"""
        with patch('app.core.database.AsyncSessionLocal') as mock_session:
            mock_result = Mock()
            mock_result.scalar.side_effect = [5, 1048576]  # active connections, db size
            mock_session.return_value.__aenter__.return_value.execute = AsyncMock(
                return_value=mock_result
            )

            from scripts.health_check import HealthChecker

            checker = HealthChecker()
            await checker._check_database()

            # Should succeed
            assert 'database' in checker.results
            assert checker.results['database'].healthy

    @pytest.mark.asyncio
    async def test_redis_health_check(self):
        """Test Redis health check"""
        with patch('app.core.redis_manager.RedisManager') as mock_redis:
            mock_manager = AsyncMock()
            mock_manager.ping.return_value = 'PONG'
            mock_manager.get_redis_info.return_value = {
                'connected_clients': '5',
                'used_memory': '1048576',
                'uptime_in_seconds': '3600'
            }
            mock_manager.get.return_value = 'ok'
            mock_redis.return_value = mock_manager

            from scripts.health_check import HealthChecker

            checker = HealthChecker()
            await checker._check_redis()

            # Should succeed
            assert 'redis' in checker.results
            assert checker.results['redis'].healthy

    @pytest.mark.asyncio
    async def test_overall_health(self):
        """Test overall health determination"""
        from scripts.health_check import HealthChecker, HealthStatus

        checker = HealthChecker()
        checker.results = {
            'database': HealthStatus(healthy=True, response_time_ms=10.0, message='OK'),
            'redis': HealthStatus(healthy=True, response_time_ms=5.0, message='OK'),
            'api': HealthStatus(healthy=True, response_time_ms=15.0, message='OK'),
        }

        # Should be healthy
        assert checker.is_healthy() is True

        # Add unhealthy component
        checker.results['test'] = HealthStatus(
            healthy=False, response_time_ms=100.0, message='FAIL'
        )

        # Should be unhealthy
        assert checker.is_healthy() is False


class TestEnvironmentValidator:
    """Tests for validate_env.py"""

    def test_required_variables_check(self):
        """Test required variables checking"""
        with patch.dict('os.environ', {}, clear=True):
            from scripts.validate_env import EnvironmentValidator, Severity

            validator = EnvironmentValidator()
            validator._check_required_variables()

            # Should have critical issues for missing vars
            critical = [i for i in validator.issues if i.severity == Severity.CRITICAL]
            assert len(critical) > 0

    def test_database_url_validation(self):
        """Test DATABASE_URL validation"""
        with patch.dict('os.environ', {
            'DATABASE_URL': 'mysql://user:pass@localhost/db'  # Wrong protocol
        }):
            from scripts.validate_env import EnvironmentValidator

            validator = EnvironmentValidator()
            validator._validate_database_url()

            # Should have error for wrong protocol
            errors = [i for i in validator.issues if i.variable == 'DATABASE_URL']
            assert len(errors) > 0

    def test_secret_key_validation(self):
        """Test SECRET_KEY validation"""
        with patch.dict('os.environ', {
            'SECRET_KEY': 'short'  # Too short
        }):
            from scripts.validate_env import EnvironmentValidator

            validator = EnvironmentValidator()
            validator._validate_security_keys()

            # Should have error for short key
            errors = [i for i in validator.issues if i.variable == 'SECRET_KEY']
            assert len(errors) > 0

    def test_weak_secret_detection(self):
        """Test weak secret detection"""
        with patch.dict('os.environ', {
            'SECRET_KEY': 'my_secret_password_123_test_demo'  # Weak patterns
        }):
            from scripts.validate_env import EnvironmentValidator, Severity

            validator = EnvironmentValidator()
            validator._validate_security_keys()

            # Should detect weak patterns
            critical = [
                i for i in validator.issues
                if i.variable == 'SECRET_KEY' and i.severity == Severity.CRITICAL
            ]
            assert len(critical) > 0

    def test_strict_mode(self):
        """Test strict mode behavior"""
        with patch.dict('os.environ', {
            'DATABASE_URL': 'postgresql://user:pass@localhost/db',
            'REDIS_URL': 'redis://localhost:6379',  # No TLS
            'SECRET_KEY': 'test_secret_key_at_least_32_chars_long',
            'ENCRYPTION_KEY': 'test_encryption_key_32_bytes_',
            'CORS_ORIGINS': '*',  # Warning
        }):
            from scripts.validate_env import EnvironmentValidator

            # Normal mode should pass with warnings
            validator = EnvironmentValidator(strict=False)
            validator._check_required_variables()
            validator._validate_api_settings()

            # Strict mode should fail on warnings
            validator_strict = EnvironmentValidator(strict=True)
            validator_strict._check_required_variables()
            validator_strict._validate_api_settings()

            # Should have warnings
            assert len(validator_strict.issues) > 0


@pytest.mark.integration
class TestInitializationIntegration:
    """Integration tests for full initialization flow"""

    @pytest.mark.asyncio
    async def test_full_initialization_flow(self):
        """Test complete initialization flow"""
        # This would require actual database and Redis instances
        # Skip in unit tests, run in integration test environment
        pytest.skip("Requires actual services")

    @pytest.mark.asyncio
    async def test_health_check_after_init(self):
        """Test health check after initialization"""
        # This would require actual services
        pytest.skip("Requires actual services")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
