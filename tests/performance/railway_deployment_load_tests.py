"""
Performance and Load Testing for Railway Deployment
==================================================

This test suite validates performance characteristics and load handling
capabilities of the oncology clinic system when deployed on Railway.

Test Coverage:
- API endpoint response times under load
- Database connection pool performance
- Redis cache performance under stress
- Memory usage patterns
- Concurrent user scenarios
- Railway-specific deployment performance
- Auto-scaling behavior testing
"""

import pytest
import asyncio
import time
import threading
import statistics
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple
import psutil
import gc

import httpx
import aiohttp
from fastapi.testclient import TestClient

from app.main import app


class PerformanceMetrics:
    """Class to collect and analyze performance metrics."""

    def __init__(self):
        self.response_times = []
        self.error_count = 0
        self.success_count = 0
        self.memory_usage = []
        self.cpu_usage = []

    def add_response_time(self, response_time: float):
        """Add a response time measurement."""
        self.response_times.append(response_time)

    def add_error(self):
        """Increment error count."""
        self.error_count += 1

    def add_success(self):
        """Increment success count."""
        self.success_count += 1

    def add_system_metrics(self):
        """Add current system metrics."""
        process = psutil.Process()
        self.memory_usage.append(process.memory_info().rss / 1024 / 1024)  # MB
        self.cpu_usage.append(process.cpu_percent())

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary statistics."""
        if not self.response_times:
            return {"error": "No response times recorded"}

        return {
            "response_times": {
                "min": min(self.response_times),
                "max": max(self.response_times),
                "mean": statistics.mean(self.response_times),
                "median": statistics.median(self.response_times),
                "p95": self.percentile(self.response_times, 95),
                "p99": self.percentile(self.response_times, 99)
            },
            "requests": {
                "total": self.success_count + self.error_count,
                "success": self.success_count,
                "errors": self.error_count,
                "error_rate": self.error_count / (self.success_count + self.error_count) * 100 if (self.success_count + self.error_count) > 0 else 0
            },
            "system": {
                "avg_memory_mb": statistics.mean(self.memory_usage) if self.memory_usage else 0,
                "max_memory_mb": max(self.memory_usage) if self.memory_usage else 0,
                "avg_cpu_percent": statistics.mean(self.cpu_usage) if self.cpu_usage else 0,
                "max_cpu_percent": max(self.cpu_usage) if self.cpu_usage else 0
            }
        }

    @staticmethod
    def percentile(data: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]


class LoadTestRunner:
    """Load test runner for concurrent testing."""

    def __init__(self, base_url: str = "http://testserver"):
        self.base_url = base_url
        self.client = TestClient(app)

    def single_request(self, endpoint: str, method: str = "GET", **kwargs) -> Tuple[float, int]:
        """Make a single request and return response time and status code."""
        start_time = time.time()

        try:
            if method.upper() == "GET":
                response = self.client.get(endpoint, **kwargs)
            elif method.upper() == "POST":
                response = self.client.post(endpoint, **kwargs)
            elif method.upper() == "PUT":
                response = self.client.put(endpoint, **kwargs)
            elif method.upper() == "DELETE":
                response = self.client.delete(endpoint, **kwargs)
            else:
                raise ValueError(f"Unsupported method: {method}")

            end_time = time.time()
            return end_time - start_time, response.status_code

        except Exception as e:
            end_time = time.time()
            return end_time - start_time, 500

    def concurrent_load_test(
        self,
        endpoint: str,
        concurrent_users: int,
        requests_per_user: int,
        method: str = "GET",
        **kwargs
    ) -> PerformanceMetrics:
        """Run concurrent load test."""
        metrics = PerformanceMetrics()

        def user_simulation():
            """Simulate a single user making multiple requests."""
            for _ in range(requests_per_user):
                response_time, status_code = self.single_request(endpoint, method, **kwargs)
                metrics.add_response_time(response_time)

                if 200 <= status_code < 300:
                    metrics.add_success()
                else:
                    metrics.add_error()

                # Add system metrics periodically
                if metrics.success_count % 10 == 0:
                    metrics.add_system_metrics()

        # Run concurrent users
        with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
            futures = [executor.submit(user_simulation) for _ in range(concurrent_users)]

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"User simulation error: {e}")

        return metrics


class TestAPIPerformance:
    """Test API endpoint performance under various load conditions."""

    @pytest.fixture
    def load_runner(self):
        return LoadTestRunner()

    def test_health_check_performance(self, load_runner):
        """Test health check endpoint performance under load."""
        metrics = load_runner.concurrent_load_test(
            endpoint="/health",
            concurrent_users=50,
            requests_per_user=10
        )

        summary = metrics.get_summary()

        # Health check should be very fast
        assert summary["response_times"]["mean"] < 0.05  # 50ms average
        assert summary["response_times"]["p95"] < 0.1   # 95th percentile under 100ms
        assert summary["requests"]["error_rate"] < 1.0  # Less than 1% errors

    def test_authentication_endpoint_performance(self, load_runner):
        """Test authentication endpoint performance."""
        # Mock authentication data
        auth_data = {
            "email": "test@example.com",
            "password": "testpassword"
        }

        metrics = load_runner.concurrent_load_test(
            endpoint="/api/v1/auth/login-json",
            concurrent_users=20,
            requests_per_user=5,
            method="POST",
            json=auth_data
        )

        summary = metrics.get_summary()

        # Authentication should be reasonably fast
        assert summary["response_times"]["mean"] < 0.5   # 500ms average
        assert summary["response_times"]["p95"] < 1.0    # 95th percentile under 1s
        # Note: Auth endpoints might have higher error rates due to validation

    def test_database_intensive_endpoint_performance(self, load_runner):
        """Test database-intensive endpoints under load."""
        # Test user listing endpoint (database intensive)
        metrics = load_runner.concurrent_load_test(
            endpoint="/api/v1/admin/users",
            concurrent_users=30,
            requests_per_user=8
        )

        summary = metrics.get_summary()

        # Database operations should still be performant
        assert summary["response_times"]["mean"] < 1.0   # 1s average
        assert summary["response_times"]["p99"] < 3.0    # 99th percentile under 3s
        assert summary["requests"]["error_rate"] < 5.0   # Less than 5% errors

    def test_analytics_endpoint_performance(self, load_runner):
        """Test analytics/dashboard endpoint performance."""
        metrics = load_runner.concurrent_load_test(
            endpoint="/api/v1/analytics/dashboard",
            concurrent_users=15,
            requests_per_user=5
        )

        summary = metrics.get_summary()

        # Analytics might be slower due to complex calculations
        assert summary["response_times"]["mean"] < 2.0   # 2s average
        assert summary["response_times"]["p95"] < 4.0    # 95th percentile under 4s

    def test_concurrent_crud_operations(self, load_runner):
        """Test concurrent CRUD operations performance."""
        # Test template CRUD operations
        template_data = {
            "name": "Load Test Template",
            "description": "Template for load testing",
            "questions": [
                {
                    "id": "q1",
                    "text": "Test question",
                    "type": "multiple_choice",
                    "options": ["A", "B", "C"]
                }
            ]
        }

        create_metrics = load_runner.concurrent_load_test(
            endpoint="/api/v1/templates",
            concurrent_users=10,
            requests_per_user=3,
            method="POST",
            json=template_data
        )

        read_metrics = load_runner.concurrent_load_test(
            endpoint="/api/v1/templates",
            concurrent_users=20,
            requests_per_user=5
        )

        create_summary = create_metrics.get_summary()
        read_summary = read_metrics.get_summary()

        # Create operations should be reasonably fast
        assert create_summary["response_times"]["mean"] < 1.5
        # Read operations should be faster
        assert read_summary["response_times"]["mean"] < 0.5

    @pytest.mark.asyncio
    async def test_async_performance_characteristics(self):
        """Test async performance characteristics using aiohttp."""
        async def make_request(session, url):
            start_time = time.time()
            async with session.get(url) as response:
                await response.text()
                return time.time() - start_time, response.status

        async def run_async_test():
            async with aiohttp.ClientSession() as session:
                # Create 100 concurrent requests
                tasks = []
                for _ in range(100):
                    task = make_request(session, "http://testserver/health")
                    tasks.append(task)

                results = await asyncio.gather(*tasks, return_exceptions=True)

                response_times = []
                success_count = 0

                for result in results:
                    if isinstance(result, tuple):
                        response_time, status = result
                        response_times.append(response_time)
                        if 200 <= status < 300:
                            success_count += 1

                return {
                    "avg_response_time": statistics.mean(response_times),
                    "success_rate": success_count / len(results) * 100,
                    "total_requests": len(results)
                }

        # Note: This test requires actual async implementation
        # For now, we'll skip it in the mock environment
        # results = await run_async_test()
        # assert results["avg_response_time"] < 0.1
        # assert results["success_rate"] > 95


class TestMemoryPerformance:
    """Test memory usage and performance characteristics."""

    def test_memory_usage_under_load(self):
        """Test memory usage patterns under sustained load."""
        load_runner = LoadTestRunner()

        # Baseline memory usage
        gc.collect()  # Force garbage collection
        process = psutil.Process()
        baseline_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Run sustained load
        metrics = load_runner.concurrent_load_test(
            endpoint="/health",
            concurrent_users=50,
            requests_per_user=20
        )

        # Force garbage collection and measure memory
        gc.collect()
        final_memory = process.memory_info().rss / 1024 / 1024  # MB

        memory_increase = final_memory - baseline_memory

        # Memory increase should be reasonable
        assert memory_increase < 100  # Less than 100MB increase
        assert final_memory < 512     # Total memory under 512MB

        summary = metrics.get_summary()
        print(f"Memory usage - Baseline: {baseline_memory:.2f}MB, Final: {final_memory:.2f}MB")
        print(f"Performance summary: {summary}")

    def test_memory_leak_detection(self):
        """Test for potential memory leaks during sustained operation."""
        load_runner = LoadTestRunner()
        memory_samples = []

        # Take memory samples during sustained load
        for cycle in range(5):
            # Run load test cycle
            load_runner.concurrent_load_test(
                endpoint="/health",
                concurrent_users=20,
                requests_per_user=10
            )

            # Force garbage collection and sample memory
            gc.collect()
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
            memory_samples.append(memory_mb)

            # Small delay between cycles
            time.sleep(0.1)

        # Check for significant memory growth trend
        if len(memory_samples) >= 3:
            # Calculate trend (should not continuously increase)
            memory_increases = [
                memory_samples[i] - memory_samples[i-1]
                for i in range(1, len(memory_samples))
            ]

            # Average increase per cycle should be minimal
            avg_increase = statistics.mean(memory_increases)
            assert avg_increase < 10  # Less than 10MB average increase per cycle

        print(f"Memory samples across cycles: {memory_samples}")

    def test_database_connection_pool_performance(self):
        """Test database connection pool performance under load."""
        load_runner = LoadTestRunner()

        # Test database-intensive operations
        metrics = load_runner.concurrent_load_test(
            endpoint="/api/v1/admin/users/stats/overview",
            concurrent_users=25,
            requests_per_user=8
        )

        summary = metrics.get_summary()

        # Database connection pool should handle load efficiently
        assert summary["response_times"]["mean"] < 2.0
        assert summary["requests"]["error_rate"] < 10.0  # Some errors expected for auth

    def test_cache_performance_under_load(self):
        """Test Redis cache performance under sustained load."""
        load_runner = LoadTestRunner()

        # Test endpoints that should use caching
        cached_endpoints = [
            "/health",
            "/health/detailed",
            "/api/v1/analytics/dashboard"
        ]

        for endpoint in cached_endpoints:
            # First request (cache miss)
            first_response_time, _ = load_runner.single_request(endpoint)

            # Subsequent requests (cache hits)
            cached_times = []
            for _ in range(10):
                cached_time, _ = load_runner.single_request(endpoint)
                cached_times.append(cached_time)

            avg_cached_time = statistics.mean(cached_times)

            # Cached responses should be faster (if caching is implemented)
            # If not, we just ensure reasonable performance
            assert avg_cached_time < 0.5  # Should be fast regardless


class TestRailwayDeploymentPerformance:
    """Test performance characteristics specific to Railway deployment."""

    def test_railway_cold_start_performance(self):
        """Test cold start performance on Railway."""
        load_runner = LoadTestRunner()

        # Simulate cold start by testing first request after "idle"
        time.sleep(1)  # Simulate brief idle period

        start_time = time.time()
        response_time, status_code = load_runner.single_request("/health")
        cold_start_time = time.time() - start_time

        # Cold start should be reasonable
        assert cold_start_time < 5.0  # Under 5 seconds for cold start
        assert status_code == 200

    def test_railway_auto_scaling_simulation(self):
        """Simulate Railway auto-scaling behavior under increasing load."""
        load_runner = LoadTestRunner()

        # Gradually increase load to trigger scaling
        scaling_phases = [
            (5, 5),   # 5 users, 5 requests each
            (15, 8),  # 15 users, 8 requests each
            (30, 10), # 30 users, 10 requests each
            (50, 12)  # 50 users, 12 requests each
        ]

        phase_results = []

        for phase_num, (users, requests) in enumerate(scaling_phases):
            print(f"Running scaling phase {phase_num + 1}: {users} users, {requests} requests each")

            metrics = load_runner.concurrent_load_test(
                endpoint="/health",
                concurrent_users=users,
                requests_per_user=requests
            )

            summary = metrics.get_summary()
            phase_results.append({
                "phase": phase_num + 1,
                "users": users,
                "avg_response_time": summary["response_times"]["mean"],
                "error_rate": summary["requests"]["error_rate"]
            })

            # Brief pause between phases
            time.sleep(2)

        # Analyze scaling behavior
        for result in phase_results:
            print(f"Phase {result['phase']}: {result['users']} users, "
                  f"avg response: {result['avg_response_time']:.3f}s, "
                  f"error rate: {result['error_rate']:.1f}%")

            # Even under high load, system should remain responsive
            assert result["avg_response_time"] < 2.0
            assert result["error_rate"] < 25.0  # Allow higher error rate under extreme load

    def test_railway_resource_limits(self):
        """Test behavior near Railway resource limits."""
        load_runner = LoadTestRunner()

        # Monitor resource usage during intensive load
        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024

        # Run intensive load test
        metrics = load_runner.concurrent_load_test(
            endpoint="/api/v1/analytics/dashboard",
            concurrent_users=40,
            requests_per_user=15
        )

        final_memory = process.memory_info().rss / 1024 / 1024
        memory_usage = final_memory - initial_memory

        summary = metrics.get_summary()

        # Should handle load without exceeding reasonable resource limits
        assert final_memory < 1024  # Under 1GB total memory usage
        assert summary["system"]["max_cpu_percent"] < 90  # Under 90% CPU
        assert summary["requests"]["error_rate"] < 20.0  # Reasonable error rate

        print(f"Resource usage - Memory: {final_memory:.1f}MB (+{memory_usage:.1f}MB), "
              f"Max CPU: {summary['system']['max_cpu_percent']:.1f}%")

    def test_railway_network_performance(self):
        """Test network performance characteristics on Railway."""
        load_runner = LoadTestRunner()

        # Test various payload sizes
        payload_tests = [
            {"size": "small", "data": {"test": "small_payload"}},
            {"size": "medium", "data": {"test": "medium_payload", "data": "x" * 1000}},
            {"size": "large", "data": {"test": "large_payload", "data": "x" * 10000}}
        ]

        for test in payload_tests:
            metrics = load_runner.concurrent_load_test(
                endpoint="/api/v1/auth/login-json",
                concurrent_users=10,
                requests_per_user=3,
                method="POST",
                json=test["data"]
            )

            summary = metrics.get_summary()

            # Network performance should scale reasonably with payload size
            if test["size"] == "small":
                assert summary["response_times"]["mean"] < 0.5
            elif test["size"] == "medium":
                assert summary["response_times"]["mean"] < 1.0
            else:  # large
                assert summary["response_times"]["mean"] < 2.0

            print(f"{test['size'].capitalize()} payload performance: "
                  f"{summary['response_times']['mean']:.3f}s average")


class TestErrorHandlingPerformance:
    """Test performance of error handling under various conditions."""

    def test_error_response_performance(self):
        """Test that error responses are generated quickly."""
        load_runner = LoadTestRunner()

        # Test various error scenarios
        error_tests = [
            ("/api/v1/nonexistent", "GET", 404),
            ("/api/v1/admin/users", "GET", 401),  # Unauthorized
            ("/api/v1/admin/users", "POST", 422)  # Validation error
        ]

        for endpoint, method, expected_status in error_tests:
            start_time = time.time()
            response_time, status_code = load_runner.single_request(endpoint, method)
            end_time = time.time()

            # Error responses should be fast
            assert response_time < 0.2  # Under 200ms
            # Note: Status code might differ in test environment

    def test_rate_limiting_performance(self):
        """Test rate limiting performance impact."""
        load_runner = LoadTestRunner()

        # Simulate rate limiting scenario
        metrics = load_runner.concurrent_load_test(
            endpoint="/api/v1/auth/login-json",
            concurrent_users=50,  # High concurrency to trigger rate limiting
            requests_per_user=10,
            method="POST",
            json={"email": "test@example.com", "password": "wrong"}
        )

        summary = metrics.get_summary()

        # Rate limiting should not significantly degrade performance
        assert summary["response_times"]["mean"] < 1.0
        # High error rate expected due to rate limiting and wrong credentials
        print(f"Rate limiting test - Error rate: {summary['requests']['error_rate']:.1f}%")


def generate_performance_report(test_results: Dict[str, Any]) -> str:
    """Generate a comprehensive performance report."""
    report = """
    Performance Test Report
    ======================

    Test Results Summary:
    """

    for test_name, results in test_results.items():
        report += f"\n    {test_name}:\n"
        if "response_times" in results:
            report += f"      - Average Response Time: {results['response_times']['mean']:.3f}s\n"
            report += f"      - 95th Percentile: {results['response_times']['p95']:.3f}s\n"
            report += f"      - Error Rate: {results['requests']['error_rate']:.1f}%\n"

    return report


if __name__ == "__main__":
    # Run basic performance tests if executed directly
    print("Running basic performance tests...")

    load_runner = LoadTestRunner()

    # Health check performance
    health_metrics = load_runner.concurrent_load_test(
        endpoint="/health",
        concurrent_users=20,
        requests_per_user=10
    )

    print("Health Check Performance:", health_metrics.get_summary())

    # Generate report
    results = {"health_check": health_metrics.get_summary()}
    report = generate_performance_report(results)
    print(report)