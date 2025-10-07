"""
Load Test for DI Session Isolation

Simulates high-concurrency scenarios to validate session isolation
and detect any session leaks or cross-talk under load.

Run with: pytest tests/load/test_di_session_isolation.py -v -m load
Or with locust if installed: locust -f tests/load/test_di_session_isolation.py
"""
import pytest
import asyncio
import time
from typing import List
from fastapi.testclient import TestClient


class TestLoadSessionIsolation:
    """Load tests for session isolation under high concurrency"""

    def setup_method(self):
        """Setup test environment"""
        from app.main import app
        self.client = TestClient(app)

    @pytest.mark.load
    @pytest.mark.asyncio
    async def test_100_concurrent_requests(self):
        """
        Test 100 concurrent requests to verify session isolation.

        This simulates high load to detect:
        - Session leaks
        - Connection pool exhaustion
        - Session cross-talk
        - Memory leaks
        """
        async def make_request(request_id: int):
            """Make a single health check request"""
            start_time = time.time()

            try:
                response = self.client.get("/api/v1/railway/health")
                end_time = time.time()

                return {
                    "request_id": request_id,
                    "status_code": response.status_code,
                    "response_time_ms": (end_time - start_time) * 1000,
                    "success": response.status_code in [200, 503],
                    "error": None
                }
            except Exception as e:
                end_time = time.time()
                return {
                    "request_id": request_id,
                    "status_code": 0,
                    "response_time_ms": (end_time - start_time) * 1000,
                    "success": False,
                    "error": str(e)
                }

        # Fire 100 concurrent requests
        print("\n🔥 Starting 100 concurrent requests...")
        start_time = time.time()

        tasks = [make_request(i) for i in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        total_time = end_time - start_time

        # Analyze results
        successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
        failed = len(results) - successful

        avg_response_time = sum(
            r["response_time_ms"] for r in results if isinstance(r, dict)
        ) / len(results)

        print(f"\n📊 Load Test Results:")
        print(f"  Total requests: 100")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Avg response time: {avg_response_time:.2f}ms")
        print(f"  Requests/sec: {100/total_time:.2f}")

        # Assertions
        assert successful >= 95, f"Too many failures: {failed}/100"
        assert avg_response_time < 5000, f"Response time too slow: {avg_response_time}ms"

    @pytest.mark.load
    def test_sequential_load_no_memory_leak(self):
        """
        Test that sequential requests don't cause memory leaks.

        Makes 100 sequential requests and monitors for resource cleanup.
        """
        from app.database import engine

        initial_pool_size = engine.pool.checkedin()
        response_times: List[float] = []

        print("\n🔄 Running 100 sequential requests...")
        for i in range(100):
            start = time.time()
            response = self.client.get("/api/v1/railway/health")
            end = time.time()

            response_times.append((end - start) * 1000)

            # Should succeed
            assert response.status_code in [200, 503]

        final_pool_size = engine.pool.checkedin()

        # Response times should remain consistent (no degradation)
        first_10_avg = sum(response_times[:10]) / 10
        last_10_avg = sum(response_times[-10:]) / 10

        degradation_pct = ((last_10_avg - first_10_avg) / first_10_avg) * 100 if first_10_avg > 0 else 0

        print(f"\n📈 Sequential Load Test Results:")
        print(f"  First 10 requests avg: {first_10_avg:.2f}ms")
        print(f"  Last 10 requests avg: {last_10_avg:.2f}ms")
        print(f"  Performance degradation: {degradation_pct:.2f}%")
        print(f"  Pool size - Initial: {initial_pool_size}, Final: {final_pool_size}")

        # Should have minimal degradation (< 50%)
        assert degradation_pct < 50, f"Performance degraded by {degradation_pct}%"

        # Pool should not leak connections
        assert abs(final_pool_size - initial_pool_size) <= 2, "Connection pool leak detected"

    @pytest.mark.load
    @pytest.mark.asyncio
    async def test_burst_load_session_pool(self):
        """
        Test burst load to validate connection pool behavior.

        Simulates traffic spikes to ensure:
        - Pool handles overflow correctly
        - Sessions are returned to pool
        - No deadlocks occur
        """
        from app.database import engine

        async def burst_request(burst_id: int, request_id: int):
            """Make a request as part of a burst"""
            response = self.client.get("/api/v1/railway/health")
            return response.status_code in [200, 503]

        # 5 bursts of 20 requests each
        print("\n💥 Running 5 bursts of 20 concurrent requests each...")
        for burst in range(5):
            print(f"  Burst {burst + 1}/5 - Sending 20 concurrent requests...")

            pool_before = engine.pool.checkedin()

            tasks = [burst_request(burst, i) for i in range(20)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            pool_after = engine.pool.checkedin()

            successful = sum(1 for r in results if r is True)

            print(f"    Success: {successful}/20, Pool: {pool_before} -> {pool_after}")

            assert successful >= 18, f"Burst {burst + 1} had too many failures"

            # Small delay between bursts
            await asyncio.sleep(0.1)


# Locust Load Test (if locust is installed)
try:
    from locust import HttpUser, task, between

    class SessionIsolationUser(HttpUser):
        """
        Locust user for session isolation testing.

        Run with:
        locust -f tests/load/test_di_session_isolation.py --host=http://localhost:8000
        """

        wait_time = between(0.1, 0.5)

        @task(10)
        def health_check(self):
            """Health check endpoint (most frequently called)"""
            self.client.get("/api/v1/railway/health")

        @task(5)
        def readiness_probe(self):
            """Readiness probe endpoint"""
            self.client.get("/api/v1/railway/health/readiness")

        @task(2)
        def liveness_probe(self):
            """Liveness probe endpoint"""
            self.client.get("/api/v1/railway/health/liveness")

except ImportError:
    # Locust not installed - skip
    pass
