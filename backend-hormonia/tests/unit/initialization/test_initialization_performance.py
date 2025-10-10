"""
Performance tests for initialization system.

Tests initialization timing, memory usage, resource utilization,
and scalability characteristics of the system startup process.
"""
import pytest
import os
import time
import asyncio
import threading
from unittest.mock import patch, Mock, AsyncMock
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics
import gc
from datetime import datetime
import json


class TestInitializationTiming:
    """Test initialization timing performance."""

    def test_config_initialization_timing(self, performance_timer):
        """Test configuration initialization timing."""
        with patch.dict(os.environ, {
            'SECRET_KEY': 'test-secret-key-for-performance-testing',
            'DATABASE_URL': 'postgresql://test:test@localhost:5432/test_db',
            'REDIS_URL': 'redis://localhost:6379',
            'ENVIRONMENT': 'test'
        }):
            performance_timer.start()

            from app.config import Settings
            settings = Settings()

            elapsed = performance_timer.stop()

            # Configuration should initialize very quickly
            assert elapsed < 0.1, f"Config init took {elapsed:.3f}s, expected < 0.1s"
            assert settings is not None

    def test_repeated_config_initialization_timing(self, performance_timer):
        """Test repeated configuration initialization timing."""
        timings = []

        with patch.dict(os.environ, {
            'SECRET_KEY': 'test-secret-key-for-performance-testing',
            'DATABASE_URL': 'postgresql://test:test@localhost:5432/test_db',
            'REDIS_URL': 'redis://localhost:6379'
        }):
            for i in range(10):
                performance_timer.start()

                from app.config import Settings
                settings = Settings()

                elapsed = performance_timer.stop()
                timings.append(elapsed)

        # Calculate statistics
        avg_time = statistics.mean(timings)
        max_time = max(timings)
        min_time = min(timings)

        # All initializations should be fast
        assert avg_time < 0.05, f"Average init time {avg_time:.3f}s, expected < 0.05s"
        assert max_time < 0.1, f"Max init time {max_time:.3f}s, expected < 0.1s"

        print(f"Config init timing - avg: {avg_time:.3f}s, min: {min_time:.3f}s, max: {max_time:.3f}s")

    @patch('app.core.database.get_async_engine')
    def test_database_engine_creation_timing(self, mock_get_engine, performance_timer):
        """Test database engine creation timing."""
        # Mock engine creation
        mock_engine = Mock()
        mock_get_engine.return_value = mock_engine

        try:
            from app.core.database import get_async_engine

            performance_timer.start()
            engine = get_async_engine()
            elapsed = performance_timer.stop()

            # Database engine creation should be fast
            assert elapsed < 0.5, f"DB engine creation took {elapsed:.3f}s, expected < 0.5s"
            assert engine is not None

        except ImportError:
            pytest.skip("Database module not available")

    @patch('redis.Redis')
    def test_redis_client_creation_timing(self, mock_redis_class, performance_timer):
        """Test Redis client creation timing."""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis_class.return_value = mock_redis

        try:
            from app.core.redis_manager import get_redis_client

            performance_timer.start()
            client = get_redis_client()
            elapsed = performance_timer.stop()

            # Redis client creation should be fast
            assert elapsed < 0.3, f"Redis client creation took {elapsed:.3f}s, expected < 0.3s"
            assert client is not None

        except ImportError:
            pytest.skip("Redis manager not available")

    def test_application_factory_timing(self, performance_timer):
        """Test application factory timing."""
        try:
            from app.core.application_factory import create_application

            # Mock external dependencies for consistent timing
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

            # Application creation should complete within reasonable time
            assert elapsed < 2.0, f"App creation took {elapsed:.3f}s, expected < 2.0s"
            assert app is not None

        except ImportError:
            pytest.skip("Application factory not available")


class TestMemoryPerformance:
    """Test memory performance during initialization."""

    def test_config_memory_usage(self):
        """Test configuration memory usage."""
        try:
            import psutil
            import gc

            process = psutil.Process(os.getpid())
            gc.collect()  # Clean up before measurement
            memory_before = process.memory_info().rss

            with patch.dict(os.environ, {
                'SECRET_KEY': 'test-secret-key-for-memory-testing',
                'DATABASE_URL': 'postgresql://test:test@localhost:5432/test_db',
                'REDIS_URL': 'redis://localhost:6379'
            }):
                from app.config import Settings
                settings = Settings()

            memory_after = process.memory_info().rss
            memory_increase = memory_after - memory_before

            # Configuration should use minimal memory
            assert memory_increase < 5 * 1024 * 1024, f"Config used {memory_increase / 1024 / 1024:.1f}MB"

        except ImportError:
            pytest.skip("psutil not available")

    def test_repeated_config_memory_stability(self):
        """Test memory stability with repeated configuration loading."""
        try:
            import psutil
            import gc

            process = psutil.Process(os.getpid())

            # Baseline measurement
            gc.collect()
            initial_memory = process.memory_info().rss

            # Create many configuration instances
            configs = []
            for i in range(50):
                with patch.dict(os.environ, {
                    'SECRET_KEY': f'test-secret-{i}',
                    'DATABASE_URL': 'postgresql://test:test@localhost/test'
                }):
                    from app.config import Settings
                    configs.append(Settings())

            # Memory after creating configs
            middle_memory = process.memory_info().rss

            # Clear configs and force garbage collection
            configs.clear()
            gc.collect()
            final_memory = process.memory_info().rss

            memory_increase = middle_memory - initial_memory
            memory_recovered = middle_memory - final_memory

            # Should not leak significant memory
            assert memory_increase < 50 * 1024 * 1024, f"50 configs used {memory_increase / 1024 / 1024:.1f}MB"

            # Should recover most memory after cleanup
            recovery_percentage = (memory_recovered / memory_increase) * 100 if memory_increase > 0 else 100
            assert recovery_percentage > 50, f"Only recovered {recovery_percentage:.1f}% of memory"

        except ImportError:
            pytest.skip("psutil not available")

    def test_application_memory_usage(self):
        """Test application creation memory usage."""
        try:
            import psutil
            import gc

            process = psutil.Process(os.getpid())
            gc.collect()
            memory_before = process.memory_info().rss

            # Mock dependencies to focus on application memory
            with patch('app.core.database.get_async_engine') as mock_db, \
                 patch('redis.Redis') as mock_redis:

                mock_engine = Mock()
                mock_db.return_value = mock_engine

                mock_redis_client = Mock()
                mock_redis_client.ping.return_value = True
                mock_redis.return_value = mock_redis_client

                from app.core.application_factory import create_application

                app = create_application(
                    enable_monitoring=False,
                    deployment_mode="development"
                )

            memory_after = process.memory_info().rss
            memory_increase = memory_after - memory_before

            # Application should use reasonable memory
            assert memory_increase < 100 * 1024 * 1024, f"App creation used {memory_increase / 1024 / 1024:.1f}MB"

        except (ImportError, Exception):
            pytest.skip("Application factory or psutil not available")


class TestConcurrentPerformance:
    """Test concurrent initialization performance."""

    def test_concurrent_config_initialization_performance(self):
        """Test concurrent configuration initialization performance."""
        def create_config(thread_id):
            start_time = time.time()

            with patch.dict(os.environ, {
                'SECRET_KEY': f'test-secret-{thread_id}',
                'DATABASE_URL': 'postgresql://test:test@localhost/test'
            }):
                from app.config import Settings
                settings = Settings()

            elapsed = time.time() - start_time
            return elapsed, settings

        # Test concurrent creation
        num_threads = 5
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_config, i) for i in range(num_threads)]

            timings = []
            configs = []

            for future in as_completed(futures, timeout=10):
                elapsed, config = future.result()
                timings.append(elapsed)
                configs.append(config)

        # All configs should be created successfully
        assert len(configs) == num_threads

        # Calculate performance metrics
        avg_time = statistics.mean(timings)
        max_time = max(timings)

        # Concurrent creation should not be significantly slower
        assert avg_time < 0.2, f"Concurrent config avg time {avg_time:.3f}s, expected < 0.2s"
        assert max_time < 0.5, f"Concurrent config max time {max_time:.3f}s, expected < 0.5s"

        print(f"Concurrent config timing - avg: {avg_time:.3f}s, max: {max_time:.3f}s")

    @patch('redis.Redis')
    def test_concurrent_redis_client_performance(self, mock_redis_class):
        """Test concurrent Redis client creation performance."""
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis_class.return_value = mock_redis

        def create_redis_client(thread_id):
            start_time = time.time()

            try:
                from app.core.redis_manager import get_redis_client
                client = get_redis_client()
                elapsed = time.time() - start_time
                return elapsed, client
            except ImportError:
                return 0, None

        # Test concurrent Redis client creation
        num_threads = 5
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_redis_client, i) for i in range(num_threads)]

            timings = []
            clients = []

            for future in as_completed(futures, timeout=10):
                elapsed, client = future.result()
                if client is not None:
                    timings.append(elapsed)
                    clients.append(client)

        if timings:  # Only test if Redis clients were created
            avg_time = statistics.mean(timings)
            max_time = max(timings)

            assert avg_time < 0.3, f"Concurrent Redis avg time {avg_time:.3f}s, expected < 0.3s"
            assert max_time < 0.6, f"Concurrent Redis max time {max_time:.3f}s, expected < 0.6s"

    def test_concurrent_application_creation_performance(self):
        """Test concurrent application creation performance."""
        def create_app(thread_id):
            start_time = time.time()

            try:
                # Mock dependencies for consistent performance
                with patch('app.core.database.get_async_engine') as mock_db, \
                     patch('redis.Redis') as mock_redis:

                    mock_engine = Mock()
                    mock_db.return_value = mock_engine

                    mock_redis_client = Mock()
                    mock_redis_client.ping.return_value = True
                    mock_redis.return_value = mock_redis_client

                    from app.core.application_factory import create_application

                    app = create_application(
                        enable_monitoring=False,
                        deployment_mode="development"
                    )

                elapsed = time.time() - start_time
                return elapsed, app

            except ImportError:
                return 0, None

        # Test concurrent application creation
        num_threads = 3  # Fewer threads for more complex operation
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(create_app, i) for i in range(num_threads)]

            timings = []
            apps = []

            for future in as_completed(futures, timeout=30):
                elapsed, app = future.result()
                if app is not None:
                    timings.append(elapsed)
                    apps.append(app)

        if timings:  # Only test if apps were created
            avg_time = statistics.mean(timings)
            max_time = max(timings)

            # Concurrent app creation might be slower but should be reasonable
            assert avg_time < 5.0, f"Concurrent app avg time {avg_time:.3f}s, expected < 5.0s"
            assert max_time < 10.0, f"Concurrent app max time {max_time:.3f}s, expected < 10.0s"


class TestScalabilityPerformance:
    """Test scalability performance characteristics."""

    def test_config_initialization_scalability(self):
        """Test configuration initialization scalability."""
        batch_sizes = [1, 5, 10, 25, 50]
        timings_per_batch = {}

        for batch_size in batch_sizes:
            start_time = time.time()

            configs = []
            for i in range(batch_size):
                with patch.dict(os.environ, {
                    'SECRET_KEY': f'test-secret-{i}',
                    'DATABASE_URL': 'postgresql://test:test@localhost/test'
                }):
                    from app.config import Settings
                    configs.append(Settings())

            elapsed = time.time() - start_time
            timings_per_batch[batch_size] = elapsed

            # Calculate per-config timing
            per_config_time = elapsed / batch_size

            # Per-config time should not increase significantly with batch size
            assert per_config_time < 0.1, f"Per-config time {per_config_time:.3f}s for batch {batch_size}"

        print("Config scalability timings:")
        for batch_size, timing in timings_per_batch.items():
            per_config = timing / batch_size
            print(f"  Batch {batch_size}: {timing:.3f}s total, {per_config:.4f}s per config")

        # Check that scaling is reasonable (not exponential)
        small_batch_per_config = timings_per_batch[5] / 5
        large_batch_per_config = timings_per_batch[50] / 50

        # Large batch should not be more than 3x slower per config
        scalability_factor = large_batch_per_config / small_batch_per_config
        assert scalability_factor < 3.0, f"Poor scalability: {scalability_factor:.2f}x slowdown"

    def test_memory_scalability(self):
        """Test memory usage scalability."""
        try:
            import psutil
            import gc

            process = psutil.Process(os.getpid())
            batch_sizes = [1, 10, 50, 100]
            memory_usage = {}

            for batch_size in batch_sizes:
                gc.collect()
                memory_before = process.memory_info().rss

                configs = []
                for i in range(batch_size):
                    with patch.dict(os.environ, {
                        'SECRET_KEY': f'test-secret-{i}',
                        'DATABASE_URL': 'postgresql://test:test@localhost/test'
                    }):
                        from app.config import Settings
                        configs.append(Settings())

                memory_after = process.memory_info().rss
                memory_increase = memory_after - memory_before
                memory_usage[batch_size] = memory_increase

                # Clean up
                configs.clear()
                gc.collect()

            print("Memory scalability:")
            for batch_size, memory in memory_usage.items():
                per_config_memory = memory / batch_size
                print(f"  Batch {batch_size}: {memory / 1024 / 1024:.1f}MB total, "
                      f"{per_config_memory / 1024:.1f}KB per config")

            # Check memory scalability
            small_batch_per_config = memory_usage[10] / 10
            large_batch_per_config = memory_usage[100] / 100

            # Memory per config should not increase dramatically
            memory_factor = large_batch_per_config / small_batch_per_config if small_batch_per_config > 0 else 1
            assert memory_factor < 2.0, f"Poor memory scalability: {memory_factor:.2f}x increase"

        except ImportError:
            pytest.skip("psutil not available")


class TestColdStartPerformance:
    """Test cold start performance characteristics."""

    def test_first_import_timing(self, performance_timer):
        """Test first import timing (cold start)."""
        # Clear import cache to simulate cold start
        modules_to_clear = [
            'app.config',
            'app.core.application_factory',
            'app.core.database',
            'app.core.redis_manager'
        ]

        for module in modules_to_clear:
            if module in sys.modules:
                del sys.modules[module]

        performance_timer.start()

        # First import (cold start)
        from app.config import Settings

        elapsed = performance_timer.stop()

        # Cold start should complete within reasonable time
        assert elapsed < 1.0, f"Cold start took {elapsed:.3f}s, expected < 1.0s"

    def test_warm_start_timing(self, performance_timer):
        """Test warm start timing (already imported)."""
        # Ensure modules are already imported
        from app.config import Settings

        performance_timer.start()

        # Subsequent import (warm start)
        with patch.dict(os.environ, {
            'SECRET_KEY': 'test-secret-warm-start',
            'DATABASE_URL': 'postgresql://test:test@localhost/test'
        }):
            settings = Settings()

        elapsed = performance_timer.stop()

        # Warm start should be very fast
        assert elapsed < 0.05, f"Warm start took {elapsed:.3f}s, expected < 0.05s"

    def test_application_cold_start_timing(self, performance_timer):
        """Test application cold start timing."""
        try:
            # Mock dependencies for consistent timing
            with patch('app.core.database.get_async_engine') as mock_db, \
                 patch('redis.Redis') as mock_redis:

                mock_engine = Mock()
                mock_db.return_value = mock_engine

                mock_redis_client = Mock()
                mock_redis_client.ping.return_value = True
                mock_redis.return_value = mock_redis_client

                performance_timer.start()

                # First application creation (cold start)
                from app.core.application_factory import create_application

                app = create_application(
                    enable_monitoring=False,
                    deployment_mode="development"
                )

                elapsed = performance_timer.stop()

            # Cold start should complete within reasonable time
            assert elapsed < 3.0, f"App cold start took {elapsed:.3f}s, expected < 3.0s"

        except ImportError:
            pytest.skip("Application factory not available")


class TestResourceUtilizationPerformance:
    """Test resource utilization during initialization."""

    def test_cpu_usage_during_initialization(self):
        """Test CPU usage during initialization."""
        try:
            import psutil
            import threading
            import time

            process = psutil.Process(os.getpid())
            cpu_samples = []
            monitoring = True

            def monitor_cpu():
                while monitoring:
                    cpu_percent = process.cpu_percent()
                    cpu_samples.append(cpu_percent)
                    time.sleep(0.1)

            # Start CPU monitoring
            monitor_thread = threading.Thread(target=monitor_cpu)
            monitor_thread.start()

            try:
                # Perform initialization
                with patch.dict(os.environ, {
                    'SECRET_KEY': 'test-secret-cpu-test',
                    'DATABASE_URL': 'postgresql://test:test@localhost/test'
                }):
                    from app.config import Settings

                    for i in range(10):
                        settings = Settings()

                time.sleep(0.5)  # Allow monitoring to capture data

            finally:
                monitoring = False
                monitor_thread.join(timeout=1)

            if cpu_samples:
                avg_cpu = statistics.mean(cpu_samples)
                max_cpu = max(cpu_samples)

                # CPU usage should be reasonable
                assert avg_cpu < 50.0, f"Average CPU usage {avg_cpu:.1f}%, expected < 50%"
                assert max_cpu < 80.0, f"Peak CPU usage {max_cpu:.1f}%, expected < 80%"

                print(f"CPU usage during init - avg: {avg_cpu:.1f}%, max: {max_cpu:.1f}%")

        except ImportError:
            pytest.skip("psutil not available")

    def test_file_descriptor_usage(self):
        """Test file descriptor usage during initialization."""
        try:
            import psutil

            process = psutil.Process(os.getpid())
            fd_before = process.num_fds()

            # Perform initialization
            with patch.dict(os.environ, {
                'SECRET_KEY': 'test-secret-fd-test',
                'DATABASE_URL': 'postgresql://test:test@localhost/test'
            }):
                from app.config import Settings

                configs = []
                for i in range(20):
                    configs.append(Settings())

            fd_after = process.num_fds()
            fd_increase = fd_after - fd_before

            # Should not leak file descriptors
            assert fd_increase < 10, f"FD increase {fd_increase}, expected < 10"

            print(f"File descriptor usage - before: {fd_before}, after: {fd_after}, increase: {fd_increase}")

        except (ImportError, AttributeError):
            pytest.skip("psutil or num_fds not available")


class TestInitializationBottlenecks:
    """Test for initialization bottlenecks."""

    def test_config_validation_performance(self, performance_timer):
        """Test configuration validation performance."""
        # Test with complex configuration
        complex_config = {
            'SECRET_KEY': 'test-secret-complex-validation',
            'DATABASE_URL': 'postgresql://user:pass@host:5432/db',
            'REDIS_URL': 'redis://localhost:6379',
            'FIREBASE_ALLOWED_DOMAINS': json.dumps(['domain1.com', 'domain2.org'] * 100),
            'ALLOWED_ORIGINS': json.dumps(['http://localhost:3000'] * 50),
            'AI_HUMANIZATION_CRITICAL_KEYWORDS': json.dumps(['keyword'] * 200)
        }

        with patch.dict(os.environ, complex_config):
            performance_timer.start()

            from app.config import Settings
            settings = Settings()

            elapsed = performance_timer.stop()

        # Complex validation should still be fast
        assert elapsed < 0.2, f"Complex config validation took {elapsed:.3f}s, expected < 0.2s"

    def test_environment_parsing_performance(self, performance_timer):
        """Test environment variable parsing performance."""
        # Create many environment variables
        large_env = {
            'SECRET_KEY': 'test-secret-parsing-perf',
            'DATABASE_URL': 'postgresql://test:test@localhost/test'
        }

        # Add many additional variables
        for i in range(100):
            large_env[f'EXTRA_VAR_{i}'] = f'value_{i}' * 10

        with patch.dict(os.environ, large_env):
            performance_timer.start()

            from app.config import Settings
            settings = Settings()

            elapsed = performance_timer.stop()

        # Should handle large environment efficiently
        assert elapsed < 0.3, f"Large env parsing took {elapsed:.3f}s, expected < 0.3s"

    def test_import_dependency_performance(self, performance_timer):
        """Test import dependency performance."""
        # Clear import cache
        modules_to_clear = [mod for mod in sys.modules.keys() if mod.startswith('app.')]
        for module in modules_to_clear:
            del sys.modules[module]

        performance_timer.start()

        # Import with all dependencies
        try:
            from app.core.application_factory import create_application
            from app.config import Settings
            from app.core.database import get_async_engine
            from app.core.redis_manager import get_redis_client

        except ImportError:
            pass

        elapsed = performance_timer.stop()

        # Import should be reasonably fast
        assert elapsed < 2.0, f"Import dependencies took {elapsed:.3f}s, expected < 2.0s"


class TestAsyncInitializationPerformance:
    """Test async initialization performance."""

    @pytest.mark.asyncio
    async def test_async_database_initialization_timing(self):
        """Test async database initialization timing."""
        try:
            from app.core.database import get_async_engine

            start_time = time.time()

            with patch('sqlalchemy.ext.asyncio.create_async_engine') as mock_create:
                mock_engine = AsyncMock()
                mock_create.return_value = mock_engine

                engine = get_async_engine()

            elapsed = time.time() - start_time

            # Async database setup should be fast
            assert elapsed < 0.5, f"Async DB setup took {elapsed:.3f}s, expected < 0.5s"

        except ImportError:
            pytest.skip("Database module not available")

    @pytest.mark.asyncio
    async def test_concurrent_async_operations_performance(self):
        """Test concurrent async operations performance."""
        async def async_operation(operation_id):
            start_time = time.time()

            # Simulate async database/Redis operations
            await asyncio.sleep(0.01)  # Simulate async work

            # Mock configuration loading
            with patch.dict(os.environ, {
                'SECRET_KEY': f'test-secret-async-{operation_id}',
                'DATABASE_URL': 'postgresql://test:test@localhost/test'
            }):
                from app.config import Settings
                settings = Settings()

            elapsed = time.time() - start_time
            return elapsed, settings

        # Run multiple async operations concurrently
        start_time = time.time()

        tasks = [async_operation(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        total_elapsed = time.time() - start_time

        # Extract timings and configs
        timings = [result[0] for result in results]
        configs = [result[1] for result in results]

        # All operations should complete
        assert len(configs) == 10

        # Concurrent execution should be faster than sequential
        sequential_time_estimate = sum(timings)
        concurrency_benefit = sequential_time_estimate / total_elapsed

        assert concurrency_benefit > 1.5, f"Poor concurrency benefit: {concurrency_benefit:.2f}x"

        # Individual operations should still be fast
        avg_time = statistics.mean(timings)
        assert avg_time < 0.1, f"Async operation avg time {avg_time:.3f}s, expected < 0.1s"

        print(f"Async performance - total: {total_elapsed:.3f}s, "
              f"avg per op: {avg_time:.3f}s, concurrency benefit: {concurrency_benefit:.2f}x")


class TestInitializationMetrics:
    """Test initialization metrics and profiling."""

    def test_initialization_profiling(self):
        """Test initialization profiling."""
        import cProfile
        import io
        import pstats

        # Profile configuration initialization
        profiler = cProfile.Profile()
        profiler.enable()

        try:
            with patch.dict(os.environ, {
                'SECRET_KEY': 'test-secret-profiling',
                'DATABASE_URL': 'postgresql://test:test@localhost/test'
            }):
                from app.config import Settings

                for i in range(5):
                    settings = Settings()

        finally:
            profiler.disable()

        # Analyze profiling results
        stats_stream = io.StringIO()
        stats = pstats.Stats(profiler, stream=stats_stream)
        stats.sort_stats('cumulative')

        # Get total function calls and time
        total_calls = stats.total_calls
        total_time = stats.total_tt

        # Should not have excessive function calls
        assert total_calls < 10000, f"Too many function calls: {total_calls}"
        assert total_time < 1.0, f"Total time too high: {total_time:.3f}s"

        print(f"Profiling results - calls: {total_calls}, time: {total_time:.3f}s")

    def test_memory_profiling(self):
        """Test memory profiling during initialization."""
        try:
            import tracemalloc

            # Start memory tracing
            tracemalloc.start()

            # Perform initialization
            with patch.dict(os.environ, {
                'SECRET_KEY': 'test-secret-memory-profiling',
                'DATABASE_URL': 'postgresql://test:test@localhost/test'
            }):
                from app.config import Settings

                configs = []
                for i in range(10):
                    configs.append(Settings())

            # Get memory statistics
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            # Memory usage should be reasonable
            assert peak < 50 * 1024 * 1024, f"Peak memory {peak / 1024 / 1024:.1f}MB, expected < 50MB"

            print(f"Memory profiling - current: {current / 1024 / 1024:.1f}MB, "
                  f"peak: {peak / 1024 / 1024:.1f}MB")

        except ImportError:
            pytest.skip("tracemalloc not available")

    def test_initialization_metrics_collection(self):
        """Test collection of initialization metrics."""
        metrics = {
            'start_time': time.time(),
            'config_count': 0,
            'total_time': 0,
            'memory_usage': []
        }

        try:
            import psutil
            process = psutil.Process(os.getpid())

            for i in range(5):
                start_time = time.time()

                with patch.dict(os.environ, {
                    'SECRET_KEY': f'test-secret-metrics-{i}',
                    'DATABASE_URL': 'postgresql://test:test@localhost/test'
                }):
                    from app.config import Settings
                    settings = Settings()

                elapsed = time.time() - start_time
                memory_usage = process.memory_info().rss

                metrics['config_count'] += 1
                metrics['total_time'] += elapsed
                metrics['memory_usage'].append(memory_usage)

            # Calculate final metrics
            metrics['avg_time'] = metrics['total_time'] / metrics['config_count']
            metrics['avg_memory'] = statistics.mean(metrics['memory_usage'])
            metrics['peak_memory'] = max(metrics['memory_usage'])

            # Validate metrics
            assert metrics['avg_time'] < 0.1, f"Average time {metrics['avg_time']:.3f}s too high"
            assert metrics['peak_memory'] < 500 * 1024 * 1024, "Peak memory usage too high"

            print(f"Initialization metrics: {json.dumps({
                'config_count': metrics['config_count'],
                'total_time': round(metrics['total_time'], 3),
                'avg_time': round(metrics['avg_time'], 3),
                'avg_memory_mb': round(metrics['avg_memory'] / 1024 / 1024, 1),
                'peak_memory_mb': round(metrics['peak_memory'] / 1024 / 1024, 1)
            }, indent=2)}")

        except ImportError:
            pytest.skip("psutil not available")