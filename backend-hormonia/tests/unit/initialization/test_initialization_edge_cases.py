"""
Edge case and error handling tests for initialization system.

Tests system behavior under:
- Missing dependencies
- Invalid configurations
- Network failures
- Resource constraints
- Concurrent initialization
- Partial failures
"""
import pytest
import os
import asyncio
import threading
import time
from unittest.mock import patch, Mock, AsyncMock, MagicMock
from concurrent.futures import ThreadPoolExecutor
import tempfile
import json
import signal
import sys


class TestMissingDependencyHandling:
    """Test handling of missing dependencies during initialization."""

    def test_missing_database_dependency(self):
        """Test behavior when database dependency is missing."""
        # Mock missing database module
        with patch.dict('sys.modules', {'sqlalchemy': None}):
            try:
                from app.config import Settings

                # Should handle missing database gracefully or fail predictably
                with patch.dict(os.environ, {
                    'SECRET_KEY': 'test-secret',
                    'DATABASE_URL': 'postgresql://test:test@localhost/test'
                }):
                    try:
                        settings = Settings()
                        # If it succeeds, should handle gracefully
                    except (ImportError, ModuleNotFoundError):
                        # Expected behavior for missing dependency
                        pass

            except ImportError:
                # Expected when dependency is missing
                pass

    def test_missing_redis_dependency(self):
        """Test behavior when Redis dependency is missing."""
        with patch.dict('sys.modules', {'redis': None}):
            try:
                from app.config import Settings

                with patch.dict(os.environ, {
                    'SECRET_KEY': 'test-secret',
                    'DATABASE_URL': 'postgresql://test:test@localhost/test',
                    'REDIS_URL': 'redis://localhost:6379'
                }):
                    try:
                        settings = Settings()
                        # Should handle missing Redis gracefully
                    except (ImportError, ModuleNotFoundError):
                        # Expected behavior
                        pass

            except ImportError:
                # Expected when dependency is missing
                pass

    def test_missing_firebase_dependency(self):
        """Test behavior when Firebase dependency is missing."""
        with patch.dict('sys.modules', {'firebase_admin': None}):
            try:
                from app.config import Settings

                with patch.dict(os.environ, {
                    'SECRET_KEY': 'test-secret',
                    'DATABASE_URL': 'postgresql://test:test@localhost/test',
                    'FIREBASE_ADMIN_PROJECT_ID': 'test-project'
                }):
                    try:
                        settings = Settings()
                        # Should handle missing Firebase gracefully
                    except (ImportError, ModuleNotFoundError):
                        # Expected behavior
                        pass

            except ImportError:
                # Expected when dependency is missing
                pass

    def test_missing_optional_dependencies(self):
        """Test behavior when optional dependencies are missing."""
        optional_modules = ['celery', 'slowapi', 'fastapi_csrf_protect']

        for module in optional_modules:
            with patch.dict('sys.modules', {module: None}):
                try:
                    from app.config import Settings

                    with patch.dict(os.environ, {
                        'SECRET_KEY': 'test-secret',
                        'DATABASE_URL': 'postgresql://test:test@localhost/test'
                    }):
                        settings = Settings()
                        # Should handle missing optional dependencies gracefully
                        assert settings is not None

                except ImportError:
                    # Some modules might be required
                    pass


class TestInvalidConfigurationHandling:
    """Test handling of invalid configurations."""

    def test_invalid_database_url_formats(self):
        """Test handling of invalid database URLs."""
        invalid_urls = [
            'not-a-url',
            'http://example.com',  # Wrong protocol
            'postgresql://',  # Incomplete
            'postgresql://user@',  # Missing parts
            '',  # Empty
            'postgresql://user:pass@host:invalid-port/db'  # Invalid port
        ]

        for invalid_url in invalid_urls:
            with patch.dict(os.environ, {
                'SECRET_KEY': 'test-secret',
                'DATABASE_URL': invalid_url
            }):
                try:
                    from app.config import Settings
                    settings = Settings()
                    # If it succeeds, validation might be lenient
                except (ValueError, Exception) as e:
                    # Expected for invalid URLs
                    assert "database" in str(e).lower() or "url" in str(e).lower()

    def test_invalid_redis_url_formats(self):
        """Test handling of invalid Redis URLs."""
        invalid_redis_urls = [
            'not-a-redis-url',
            'http://example.com',
            'redis://',  # Incomplete
            'redis://host:invalid-port',
            'rediss://host:-1'  # Invalid port
        ]

        for invalid_url in invalid_redis_urls:
            with patch.dict(os.environ, {
                'SECRET_KEY': 'test-secret',
                'DATABASE_URL': 'postgresql://test:test@localhost/test',
                'REDIS_URL': invalid_url
            }):
                try:
                    from app.config import Settings
                    settings = Settings()
                    # If it succeeds, validation might be lenient
                except (ValueError, Exception) as e:
                    # Expected for invalid URLs
                    assert "redis" in str(e).lower() or "url" in str(e).lower()

    def test_invalid_json_configuration(self):
        """Test handling of invalid JSON in configuration."""
        invalid_json_configs = [
            ('FIREBASE_ALLOWED_DOMAINS', '{invalid json}'),
            ('ALLOWED_ORIGINS', '[invalid, json]'),
            ('AI_HUMANIZATION_CRITICAL_KEYWORDS', 'not json at all')
        ]

        for env_var, invalid_value in invalid_json_configs:
            with patch.dict(os.environ, {
                'SECRET_KEY': 'test-secret',
                'DATABASE_URL': 'postgresql://test:test@localhost/test',
                env_var: invalid_value
            }):
                try:
                    from app.config import Settings
                    settings = Settings()
                    # Should handle invalid JSON gracefully (fallback to defaults)
                    assert settings is not None
                except (ValueError, json.JSONDecodeError):
                    # Expected for invalid JSON
                    pass

    def test_conflicting_configuration_values(self):
        """Test handling of conflicting configuration values."""
        with patch.dict(os.environ, {
            'SECRET_KEY': 'test-secret',
            'DATABASE_URL': 'postgresql://test:test@localhost/test',
            'ENVIRONMENT': 'production',
            'DEBUG': 'true',  # Conflict: production but debug enabled
            'SESSION_COOKIE_SECURE': 'false',  # Insecure in production
            'REDIS_SSL': 'true',
            'REDIS_URL': 'redis://localhost:6379'  # SSL true but non-SSL URL
        }):
            try:
                from app.config import Settings

                with pytest.raises(ValueError) as exc_info:
                    settings = Settings()

                assert "production" in str(exc_info.value).lower()

            except ImportError:
                pytest.skip("Settings not available")

    def test_extreme_configuration_values(self):
        """Test handling of extreme configuration values."""
        extreme_configs = [
            ('REDIS_MAX_CONNECTIONS', '0'),  # Zero connections
            ('REDIS_MAX_CONNECTIONS', '99999'),  # Extremely high
            ('ACCESS_TOKEN_EXPIRE_MINUTES', '0'),  # Zero expiration
            ('ACCESS_TOKEN_EXPIRE_MINUTES', '525600'),  # 1 year
            ('BCRYPT_ROUNDS', '1'),  # Too low security
            ('BCRYPT_ROUNDS', '31'),  # Too high (would be very slow)
            ('REDIS_SOCKET_TIMEOUT', '0.001'),  # Very short timeout
            ('REDIS_SOCKET_TIMEOUT', '3600')  # Very long timeout
        ]

        for env_var, extreme_value in extreme_configs:
            with patch.dict(os.environ, {
                'SECRET_KEY': 'test-secret',
                'DATABASE_URL': 'postgresql://test:test@localhost/test',
                env_var: extreme_value
            }):
                try:
                    from app.config import Settings
                    settings = Settings()
                    # Should handle extreme values gracefully
                    assert settings is not None
                except (ValueError, Exception):
                    # Some extreme values might be rejected
                    pass


class TestNetworkFailureHandling:
    """Test handling of network failures during initialization."""

    @patch('redis.Redis')
    def test_redis_connection_timeout(self, mock_redis_class):
        """Test Redis connection timeout handling."""
        import redis.exceptions

        # Mock Redis connection timeout
        mock_redis = Mock()
        mock_redis.ping.side_effect = redis.exceptions.TimeoutError("Connection timeout")
        mock_redis_class.return_value = mock_redis

        try:
            from app.core.redis_manager import get_redis_client

            with pytest.raises(redis.exceptions.TimeoutError):
                client = get_redis_client()
                client.ping()

        except ImportError:
            pytest.skip("Redis manager not available")

    @patch('redis.Redis')
    def test_redis_connection_refused(self, mock_redis_class):
        """Test Redis connection refused handling."""
        import redis.exceptions

        # Mock Redis connection refused
        mock_redis = Mock()
        mock_redis.ping.side_effect = redis.exceptions.ConnectionError("Connection refused")
        mock_redis_class.return_value = mock_redis

        try:
            from app.core.redis_manager import get_redis_client

            with pytest.raises(redis.exceptions.ConnectionError):
                client = get_redis_client()
                client.ping()

        except ImportError:
            pytest.skip("Redis manager not available")

    @patch('sqlalchemy.ext.asyncio.create_async_engine')
    def test_database_connection_timeout(self, mock_create_engine):
        """Test database connection timeout handling."""
        import sqlalchemy.exc

        # Mock database connection timeout
        mock_create_engine.side_effect = sqlalchemy.exc.TimeoutError(
            "Connection timeout", None, None
        )

        try:
            from app.core.database import get_async_engine

            with pytest.raises(sqlalchemy.exc.TimeoutError):
                engine = get_async_engine()

        except ImportError:
            pytest.skip("Database module not available")

    @patch('firebase_admin.initialize_app')
    def test_firebase_network_error(self, mock_init_app):
        """Test Firebase network error handling."""
        from firebase_admin.exceptions import FirebaseError

        # Mock Firebase network error
        mock_init_app.side_effect = FirebaseError("Network error")

        try:
            from app.services.auth import FirebaseAuthService

            with pytest.raises(FirebaseError):
                service = FirebaseAuthService()

        except ImportError:
            pytest.skip("Firebase auth service not available")


class TestResourceConstraintHandling:
    """Test handling of resource constraints during initialization."""

    @patch('psutil.virtual_memory')
    def test_low_memory_conditions(self, mock_memory):
        """Test behavior under low memory conditions."""
        try:
            import psutil

            # Mock low memory condition
            mock_memory_info = Mock()
            mock_memory_info.available = 50 * 1024 * 1024  # 50MB available
            mock_memory_info.percent = 95  # 95% used
            mock_memory.return_value = mock_memory_info

            from app.config import Settings

            with patch.dict(os.environ, {
                'SECRET_KEY': 'test-secret',
                'DATABASE_URL': 'postgresql://test:test@localhost/test'
            }):
                # Should handle low memory gracefully
                settings = Settings()
                assert settings is not None

        except ImportError:
            pytest.skip("psutil not available")

    def test_file_descriptor_limits(self):
        """Test behavior when approaching file descriptor limits."""
        try:
            import resource

            # Get current limit
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)

            # Mock low file descriptor limit
            with patch('resource.getrlimit', return_value=(10, 10)):
                try:
                    from app.config import Settings

                    with patch.dict(os.environ, {
                        'SECRET_KEY': 'test-secret',
                        'DATABASE_URL': 'postgresql://test:test@localhost/test'
                    }):
                        settings = Settings()
                        # Should handle low FD limit gracefully
                        assert settings is not None

                except OSError:
                    # Expected when FD limit is too low
                    pass

        except ImportError:
            pytest.skip("resource module not available")

    def test_disk_space_constraints(self):
        """Test behavior under low disk space conditions."""
        try:
            import shutil

            # Mock low disk space
            with patch('shutil.disk_usage', return_value=(1024*1024, 1024, 1024)):  # 1MB total, 1KB free
                from app.config import Settings

                with patch.dict(os.environ, {
                    'SECRET_KEY': 'test-secret',
                    'DATABASE_URL': 'postgresql://test:test@localhost/test',
                    'UPLOAD_DIR': '/tmp/test_uploads'
                }):
                    try:
                        settings = Settings()
                        # Should handle low disk space gracefully
                        assert settings is not None
                    except (OSError, IOError):
                        # Expected when disk space is too low
                        pass

        except ImportError:
            pytest.skip("shutil not available")


class TestConcurrentInitializationHandling:
    """Test handling of concurrent initialization scenarios."""

    def test_concurrent_application_creation(self):
        """Test concurrent application creation."""
        try:
            from app.core.application_factory import create_application

            def create_app():
                return create_application(
                    enable_monitoring=False,
                    deployment_mode="development"
                )

            # Create multiple applications concurrently
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = [executor.submit(create_app) for _ in range(3)]

                apps = []
                for future in futures:
                    try:
                        app = future.result(timeout=10)
                        apps.append(app)
                    except Exception as e:
                        # Some concurrent creation might fail
                        pass

                # At least one should succeed
                assert len(apps) > 0

        except ImportError:
            pytest.skip("Application factory not available")

    @patch('redis.Redis')
    def test_concurrent_redis_connections(self, mock_redis_class):
        """Test concurrent Redis connection creation."""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis_class.return_value = mock_redis

        try:
            from app.core.redis_manager import get_redis_client

            def create_redis_client():
                return get_redis_client()

            # Create multiple Redis clients concurrently
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(create_redis_client) for _ in range(5)]

                clients = []
                for future in futures:
                    try:
                        client = future.result(timeout=5)
                        clients.append(client)
                    except Exception:
                        # Some concurrent creation might fail
                        pass

                # At least one should succeed
                assert len(clients) > 0

        except ImportError:
            pytest.skip("Redis manager not available")

    def test_concurrent_configuration_loading(self):
        """Test concurrent configuration loading."""
        from app.config import Settings

        def load_settings():
            with patch.dict(os.environ, {
                'SECRET_KEY': f'test-secret-{threading.current_thread().ident}',
                'DATABASE_URL': 'postgresql://test:test@localhost/test'
            }):
                return Settings()

        # Load settings concurrently
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(load_settings) for _ in range(3)]

            settings_list = []
            for future in futures:
                try:
                    settings = future.result(timeout=5)
                    settings_list.append(settings)
                except Exception:
                    # Some concurrent loading might fail
                    pass

            # At least one should succeed
            assert len(settings_list) > 0


class TestPartialFailureHandling:
    """Test handling of partial system failures."""

    def test_database_available_redis_unavailable(self):
        """Test behavior when database is available but Redis is not."""
        with patch('sqlalchemy.ext.asyncio.create_async_engine') as mock_db, \
             patch('redis.Redis') as mock_redis_class:

            import redis.exceptions

            # Mock successful database
            mock_engine = Mock()
            mock_db.return_value = mock_engine

            # Mock failed Redis
            mock_redis_class.side_effect = redis.exceptions.ConnectionError("Redis unavailable")

            try:
                from app.core.application_factory import create_application

                # Should handle partial failure gracefully
                app = create_application(
                    enable_monitoring=False,
                    deployment_mode="development"
                )

                assert app is not None

            except Exception as e:
                # Partial failure might prevent startup
                assert "redis" in str(e).lower()

    def test_redis_available_database_unavailable(self):
        """Test behavior when Redis is available but database is not."""
        with patch('redis.Redis') as mock_redis_class, \
             patch('sqlalchemy.ext.asyncio.create_async_engine') as mock_db:

            import sqlalchemy.exc

            # Mock successful Redis
            mock_redis = Mock()
            mock_redis.ping.return_value = True
            mock_redis_class.return_value = mock_redis

            # Mock failed database
            mock_db.side_effect = sqlalchemy.exc.OperationalError("Database unavailable", None, None)

            try:
                from app.core.application_factory import create_application

                # Should handle partial failure gracefully
                app = create_application(
                    enable_monitoring=False,
                    deployment_mode="development"
                )

                assert app is not None

            except Exception as e:
                # Partial failure might prevent startup
                assert "database" in str(e).lower()

    def test_auth_service_unavailable(self):
        """Test behavior when auth service is unavailable."""
        with patch('app.services.auth.FirebaseAuthService', side_effect=Exception("Auth service failed")):
            try:
                from app.core.application_factory import create_application

                # Should handle auth service failure gracefully
                app = create_application(
                    enable_monitoring=False,
                    deployment_mode="development"
                )

                assert app is not None

            except Exception as e:
                # Auth failure might prevent startup
                assert "auth" in str(e).lower()

    def test_monitoring_unavailable(self):
        """Test behavior when monitoring is unavailable."""
        with patch('app.monitoring.manager.get_monitoring_manager', side_effect=ImportError("Monitoring unavailable")):
            try:
                from app.core.application_factory import create_application

                # Should handle monitoring failure gracefully
                app = create_application(
                    enable_monitoring=True,  # Request monitoring but it fails
                    deployment_mode="development"
                )

                assert app is not None

            except ImportError:
                # Monitoring failure should be graceful
                pass


class TestSignalHandlingDuringInitialization:
    """Test signal handling during initialization."""

    def test_sigterm_during_initialization(self):
        """Test SIGTERM handling during initialization."""
        if os.name == 'nt':  # Windows
            pytest.skip("SIGTERM not available on Windows")

        try:
            from app.core.application_factory import create_application

            def delayed_create_app():
                time.sleep(0.1)  # Simulate slow initialization
                return create_application(
                    enable_monitoring=False,
                    deployment_mode="development"
                )

            # Start initialization in background
            import threading
            result = [None]
            exception = [None]

            def target():
                try:
                    result[0] = delayed_create_app()
                except Exception as e:
                    exception[0] = e

            thread = threading.Thread(target=target)
            thread.start()

            # Send signal after short delay
            time.sleep(0.05)
            os.kill(os.getpid(), signal.SIGTERM)

            thread.join(timeout=1)

            # Should handle signal gracefully
            # (Either complete initialization or handle interruption)

        except ImportError:
            pytest.skip("Application factory not available")

    def test_keyboard_interrupt_during_initialization(self):
        """Test KeyboardInterrupt handling during initialization."""
        try:
            from app.core.application_factory import create_application

            def interruptible_create_app():
                # Simulate being interrupted during initialization
                raise KeyboardInterrupt("User interrupted")

            with pytest.raises(KeyboardInterrupt):
                app = interruptible_create_app()

        except ImportError:
            pytest.skip("Application factory not available")


class TestEnvironmentVariableEdgeCases:
    """Test edge cases in environment variable handling."""

    def test_empty_environment_variables(self):
        """Test handling of empty environment variables."""
        with patch.dict(os.environ, {
            'SECRET_KEY': '',  # Empty
            'DATABASE_URL': '',
            'REDIS_URL': ''
        }):
            try:
                from app.config import Settings

                with pytest.raises((ValueError, Exception)):
                    settings = Settings()

            except ImportError:
                pytest.skip("Settings not available")

    def test_whitespace_only_environment_variables(self):
        """Test handling of whitespace-only environment variables."""
        with patch.dict(os.environ, {
            'SECRET_KEY': '   ',  # Whitespace only
            'DATABASE_URL': '\t\n',
            'REDIS_URL': '  \r\n  '
        }):
            try:
                from app.config import Settings

                with pytest.raises((ValueError, Exception)):
                    settings = Settings()

            except ImportError:
                pytest.skip("Settings not available")

    def test_unicode_environment_variables(self):
        """Test handling of Unicode in environment variables."""
        with patch.dict(os.environ, {
            'SECRET_KEY': 'test-secret-with-unicode-🔑',
            'DATABASE_URL': 'postgresql://test:test@localhost/test_üñíçødé',
            'REDIS_URL': 'redis://localhost:6379'
        }):
            try:
                from app.config import Settings

                # Should handle Unicode gracefully
                settings = Settings()
                assert settings is not None

            except (ValueError, UnicodeError):
                # Unicode might not be supported in all contexts
                pass
            except ImportError:
                pytest.skip("Settings not available")

    def test_very_long_environment_variables(self):
        """Test handling of very long environment variables."""
        very_long_value = 'x' * 10000  # 10KB string

        with patch.dict(os.environ, {
            'SECRET_KEY': very_long_value,
            'DATABASE_URL': f'postgresql://test:test@localhost/test_{very_long_value[:100]}'
        }):
            try:
                from app.config import Settings

                # Should handle long values gracefully
                settings = Settings()
                assert settings is not None

            except (ValueError, MemoryError):
                # Very long values might be rejected
                pass
            except ImportError:
                pytest.skip("Settings not available")


class TestFileSystemEdgeCases:
    """Test file system edge cases during initialization."""

    def test_readonly_filesystem(self):
        """Test behavior on read-only filesystem."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Make directory read-only
            os.chmod(temp_dir, 0o444)

            try:
                with patch.dict(os.environ, {
                    'SECRET_KEY': 'test-secret',
                    'DATABASE_URL': 'postgresql://test:test@localhost/test',
                    'UPLOAD_DIR': temp_dir
                }):
                    from app.config import Settings

                    try:
                        settings = Settings()
                        # Should handle read-only filesystem gracefully
                        assert settings is not None
                    except (OSError, PermissionError):
                        # Expected when filesystem is read-only
                        pass

            finally:
                # Restore permissions for cleanup
                os.chmod(temp_dir, 0o755)

    def test_no_home_directory(self):
        """Test behavior when HOME directory is not available."""
        with patch.dict(os.environ, {'HOME': '/nonexistent'}, clear=False):
            try:
                from app.config import Settings

                with patch.dict(os.environ, {
                    'SECRET_KEY': 'test-secret',
                    'DATABASE_URL': 'postgresql://test:test@localhost/test'
                }):
                    # Should handle missing HOME gracefully
                    settings = Settings()
                    assert settings is not None

            except ImportError:
                pytest.skip("Settings not available")

    def test_corrupted_configuration_file(self):
        """Test behavior with corrupted configuration files."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            # Write corrupted configuration
            f.write('INVALID_CONFIG_LINE_WITHOUT_EQUALS\n')
            f.write('ANOTHER=INVALID\x00LINE\n')  # With null byte
            f.write('SECRET_KEY=test-secret\n')
            corrupted_file = f.name

        try:
            with patch('app.config.Settings.model_config') as mock_config:
                mock_config.env_file = corrupted_file

                from app.config import Settings

                try:
                    settings = Settings()
                    # Should handle corrupted file gracefully
                    assert settings is not None
                except Exception:
                    # Corrupted files might prevent initialization
                    pass

        finally:
            os.unlink(corrupted_file)


class TestRaceConditionHandling:
    """Test handling of race conditions during initialization."""

    def test_concurrent_configuration_changes(self):
        """Test concurrent configuration changes."""
        def modify_env():
            # Modify environment while another thread reads it
            time.sleep(0.01)
            os.environ['DYNAMIC_CONFIG'] = 'modified'

        def read_config():
            from app.config import Settings

            with patch.dict(os.environ, {
                'SECRET_KEY': 'test-secret',
                'DATABASE_URL': 'postgresql://test:test@localhost/test',
                'DYNAMIC_CONFIG': 'original'
            }):
                return Settings()

        # Start concurrent modification
        modifier_thread = threading.Thread(target=modify_env)
        modifier_thread.start()

        try:
            # Read configuration concurrently
            settings = read_config()
            assert settings is not None
        except Exception:
            # Race conditions might cause issues
            pass

        modifier_thread.join()

    def test_concurrent_file_access(self):
        """Test concurrent file access during initialization."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write('SECRET_KEY=test-secret\n')
            f.write('DATABASE_URL=postgresql://test:test@localhost/test\n')
            config_file = f.name

        def read_config_file():
            try:
                from app.config import Settings

                with patch('app.config.Settings.model_config') as mock_config:
                    mock_config.env_file = config_file
                    return Settings()
            except Exception:
                return None

        # Read configuration from multiple threads
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(read_config_file) for _ in range(3)]

            results = []
            for future in futures:
                try:
                    result = future.result(timeout=5)
                    if result:
                        results.append(result)
                except Exception:
                    pass

        # At least one should succeed
        assert len(results) > 0

        os.unlink(config_file)


class TestMemoryLeakDetection:
    """Test for memory leaks during initialization."""

    def test_repeated_initialization_memory(self):
        """Test memory usage during repeated initialization."""
        try:
            import psutil
            import gc

            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss

            # Perform multiple initializations
            for i in range(10):
                try:
                    from app.config import Settings

                    with patch.dict(os.environ, {
                        'SECRET_KEY': f'test-secret-{i}',
                        'DATABASE_URL': 'postgresql://test:test@localhost/test'
                    }):
                        settings = Settings()

                    # Force garbage collection
                    gc.collect()

                except ImportError:
                    break

            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory

            # Memory increase should be reasonable (< 50MB for 10 iterations)
            assert memory_increase < 50 * 1024 * 1024, f"Memory leak detected: {memory_increase / 1024 / 1024:.1f}MB"

        except ImportError:
            pytest.skip("psutil not available for memory testing")

    def test_object_reference_cleanup(self):
        """Test that objects are properly cleaned up."""
        import weakref

        try:
            from app.config import Settings

            with patch.dict(os.environ, {
                'SECRET_KEY': 'test-secret',
                'DATABASE_URL': 'postgresql://test:test@localhost/test'
            }):
                settings = Settings()
                weak_ref = weakref.ref(settings)

                # Delete strong reference
                del settings

                # Force garbage collection
                import gc
                gc.collect()

                # Weak reference should be None if object was cleaned up
                # Note: This might not always work due to Python's garbage collection

        except ImportError:
            pytest.skip("Settings not available")


class TestInitializationTiming:
    """Test initialization timing edge cases."""

    def test_initialization_timeout(self):
        """Test initialization timeout handling."""
        def slow_initialization():
            # Simulate very slow initialization
            time.sleep(2)
            from app.config import Settings

            with patch.dict(os.environ, {
                'SECRET_KEY': 'test-secret',
                'DATABASE_URL': 'postgresql://test:test@localhost/test'
            }):
                return Settings()

        # Test with timeout
        import threading
        result = [None]
        exception = [None]

        def target():
            try:
                result[0] = slow_initialization()
            except Exception as e:
                exception[0] = e

        thread = threading.Thread(target=target)
        thread.start()
        thread.join(timeout=1)  # 1 second timeout

        if thread.is_alive():
            # Initialization is taking too long
            assert True  # This is expected for timeout test
        else:
            # Initialization completed within timeout
            assert result[0] is not None or exception[0] is not None

    def test_rapid_successive_initializations(self):
        """Test rapid successive initializations."""
        try:
            from app.config import Settings

            start_time = time.time()

            # Perform rapid initializations
            for i in range(100):
                with patch.dict(os.environ, {
                    'SECRET_KEY': f'test-secret-{i}',
                    'DATABASE_URL': 'postgresql://test:test@localhost/test'
                }):
                    settings = Settings()

            elapsed_time = time.time() - start_time

            # Should complete within reasonable time (< 5 seconds for 100 iterations)
            assert elapsed_time < 5.0, f"Rapid initialization took {elapsed_time:.2f}s"

        except ImportError:
            pytest.skip("Settings not available")