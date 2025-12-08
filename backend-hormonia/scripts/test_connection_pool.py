#!/usr/bin/env python3
"""
Connection pool load testing script.
Part of MEDIUM-007: Connection Pool Tuning

This script uses Locust to perform load testing with different connection pool sizes.
It simulates realistic patient management workloads.

Usage:
    # Test with default settings (pool_size=5, max_overflow=10)
    python scripts/test_connection_pool.py --pool-size 5 --max-overflow 10

    # Test with optimized settings
    python scripts/test_connection_pool.py --pool-size 20 --max-overflow 40

    # Run full load test suite
    python scripts/test_connection_pool.py --full-suite
"""

import argparse
import asyncio
import json
import time
from datetime import datetime
from typing import Dict, List
from locust import HttpUser, task, between, events
from locust.env import Environment
from locust.stats import stats_printer, stats_history
import subprocess
import sys
import statistics


class PatientManagementUser(HttpUser):
    """Simulates realistic patient management workload."""

    wait_time = between(1, 3)

    def on_start(self):
        """Login before starting tasks."""
        # Login to get authentication token
        response = self.client.post("/api/v2/auth/login", json={
            "email": "admin@clinic.com",
            "password": "test_password"
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    @task(10)
    def list_patients(self):
        """Most common operation - list patients with pagination."""
        self.client.get("/api/v2/patients?page=1&limit=20")

    @task(5)
    def get_patient_details(self):
        """Fetch single patient details."""
        # Assume patient ID 1 exists for testing
        self.client.get("/api/v2/patients/1")

    @task(3)
    def create_patient(self):
        """Create new patient (write operation)."""
        self.client.post("/api/v2/patients", json={
            "name": "Load Test Patient",
            "email": f"loadtest_{time.time()}@example.com",
            "phone": "+5511999999999",
            "birth_date": "1990-01-01"
        })

    @task(2)
    def update_patient(self):
        """Update patient information."""
        self.client.put("/api/v2/patients/1", json={
            "name": "Updated Patient"
        })

    @task(8)
    def start_quiz_session(self):
        """Start quiz session (joins multiple tables)."""
        self.client.post("/api/v2/quiz/sessions", json={
            "patient_id": 1,
            "quiz_id": 1
        })

    @task(5)
    def submit_quiz_response(self):
        """Submit quiz response (write with JSON)."""
        self.client.post("/api/v2/quiz/sessions/1/responses", json={
            "question_id": 1,
            "response_value": {"answer": "test"}
        })

    @task(4)
    def list_messages(self):
        """List patient messages (conversation history)."""
        self.client.get("/api/v2/messages/conversations/1")

    @task(2)
    def get_dashboard_data(self):
        """Fetch dashboard analytics (complex queries)."""
        self.client.get("/api/v2/dashboard/stats")


class QuizIntensiveUser(HttpUser):
    """Simulates quiz-heavy workload with JSONB operations."""

    wait_time = between(0.5, 2)

    def on_start(self):
        """Login before starting tasks."""
        response = self.client.post("/api/v2/auth/login", json={
            "email": "admin@clinic.com",
            "password": "test_password"
        })
        if response.status_code == 200:
            self.token = response.json()["access_token"]
            self.client.headers.update({"Authorization": f"Bearer {self.token}"})

    @task(15)
    def submit_quiz_responses_rapid(self):
        """Rapid quiz response submission."""
        for i in range(5):
            self.client.post("/api/v2/quiz/sessions/1/responses", json={
                "question_id": i + 1,
                "response_value": {"answer": f"response_{i}", "metadata": {"time": time.time()}}
            })

    @task(10)
    def query_by_metadata(self):
        """Query patients by JSONB metadata (tests GIN index)."""
        self.client.get("/api/v2/patients?metadata_filter=" + json.dumps({
            "consent": {"lgpd": True}
        }))


def run_load_test(
    pool_size: int,
    max_overflow: int,
    users: int = 100,
    spawn_rate: int = 10,
    duration: int = 60
) -> Dict:
    """
    Run a single load test with specific pool settings.

    Args:
        pool_size: Base connection pool size
        max_overflow: Maximum overflow connections
        users: Number of concurrent users
        spawn_rate: Users spawned per second
        duration: Test duration in seconds

    Returns:
        Dictionary with test results
    """

    print(f"\n{'='*80}")
    print(f"🧪 LOAD TEST: pool_size={pool_size}, max_overflow={max_overflow}")
    print(f"{'='*80}")
    print(f"Users: {users}, Spawn rate: {spawn_rate}/s, Duration: {duration}s")

    # Update environment variables for the backend
    import os
    os.environ['DATABASE_POOL_SIZE'] = str(pool_size)
    os.environ['DATABASE_MAX_OVERFLOW'] = str(max_overflow)

    # Note: In real scenario, restart backend with new pool settings
    print("\n⚠️  Remember to restart backend with new pool settings:")
    print(f"   export DATABASE_POOL_SIZE={pool_size}")
    print(f"   export DATABASE_MAX_OVERFLOW={max_overflow}")
    print("   Press Enter to continue after restart...")
    input()

    # Run locust programmatically
    env = Environment(user_classes=[PatientManagementUser, QuizIntensiveUser])
    env.create_local_runner()

    # Start test
    env.runner.start(users, spawn_rate=spawn_rate)

    # Run for specified duration
    gevent_timeout = gevent.Timeout(duration)
    gevent_timeout.start()

    try:
        env.runner.greenlet.join(timeout=duration)
    except gevent.Timeout:
        pass
    finally:
        gevent_timeout.cancel()
        env.runner.quit()

    # Collect stats
    stats = env.runner.stats

    results = {
        'pool_size': pool_size,
        'max_overflow': max_overflow,
        'total_pool': pool_size + max_overflow,
        'total_requests': stats.total.num_requests,
        'failures': stats.total.num_failures,
        'failure_rate': stats.total.fail_ratio,
        'avg_response_time': stats.total.avg_response_time,
        'median_response_time': stats.total.median_response_time,
        'p95_response_time': stats.total.get_response_time_percentile(0.95),
        'p99_response_time': stats.total.get_response_time_percentile(0.99),
        'requests_per_second': stats.total.total_rps,
        'timestamp': datetime.now().isoformat()
    }

    # Print results
    print(f"\n📊 Results:")
    print(f"   Total requests: {results['total_requests']}")
    print(f"   Failures: {results['failures']} ({results['failure_rate']*100:.2f}%)")
    print(f"   Avg response time: {results['avg_response_time']:.2f}ms")
    print(f"   Median response time: {results['median_response_time']:.2f}ms")
    print(f"   P95 response time: {results['p95_response_time']:.2f}ms")
    print(f"   P99 response time: {results['p99_response_time']:.2f}ms")
    print(f"   Requests/sec: {results['requests_per_second']:.2f}")

    return results


def run_full_suite() -> None:
    """Run full test suite with multiple pool configurations."""

    test_configs = [
        {'pool_size': 5, 'max_overflow': 10},   # Current default
        {'pool_size': 10, 'max_overflow': 20},  # 2x
        {'pool_size': 20, 'max_overflow': 40},  # 4x (recommended)
        {'pool_size': 30, 'max_overflow': 60},  # 6x
        {'pool_size': 40, 'max_overflow': 80},  # 8x (high load)
    ]

    results = []

    for config in test_configs:
        result = run_load_test(
            pool_size=config['pool_size'],
            max_overflow=config['max_overflow'],
            users=100,
            spawn_rate=10,
            duration=60
        )
        results.append(result)

        # Wait between tests
        print("\n⏸️  Waiting 30s before next test...")
        time.sleep(30)

    # Generate comparison report
    print(f"\n{'='*80}")
    print("📈 CONNECTION POOL COMPARISON REPORT")
    print(f"{'='*80}\n")

    print(f"{'Config':<20} {'Requests':<12} {'Failures':<12} {'P95 (ms)':<12} {'P99 (ms)':<12} {'RPS':<12}")
    print("-" * 80)

    for r in results:
        config = f"{r['pool_size']}/{r['max_overflow']}"
        print(f"{config:<20} {r['total_requests']:<12} {r['failures']:<12} "
              f"{r['p95_response_time']:<12.2f} {r['p99_response_time']:<12.2f} "
              f"{r['requests_per_second']:<12.2f}")

    # Find optimal configuration
    # Prefer lowest P95 with acceptable failure rate
    valid_configs = [r for r in results if r['failure_rate'] < 0.01]  # <1% failures

    if valid_configs:
        optimal = min(valid_configs, key=lambda x: x['p95_response_time'])
        print(f"\n✅ RECOMMENDED CONFIGURATION:")
        print(f"   pool_size = {optimal['pool_size']}")
        print(f"   max_overflow = {optimal['max_overflow']}")
        print(f"   (P95: {optimal['p95_response_time']:.2f}ms, Failure rate: {optimal['failure_rate']*100:.2f}%)")
    else:
        print(f"\n⚠️  All configurations had >1% failure rate. Consider scaling database.")

    # Save results to file
    with open('backend-hormonia/scripts/pool_test_results.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n💾 Results saved to: backend-hormonia/scripts/pool_test_results.json")


def main():
    """Main entry point."""

    parser = argparse.ArgumentParser(description='Connection pool load testing')
    parser.add_argument('--pool-size', type=int, default=5, help='Connection pool size')
    parser.add_argument('--max-overflow', type=int, default=10, help='Max overflow connections')
    parser.add_argument('--users', type=int, default=100, help='Number of concurrent users')
    parser.add_argument('--spawn-rate', type=int, default=10, help='Users spawned per second')
    parser.add_argument('--duration', type=int, default=60, help='Test duration in seconds')
    parser.add_argument('--full-suite', action='store_true', help='Run full test suite')

    args = parser.parse_args()

    if args.full_suite:
        run_full_suite()
    else:
        run_load_test(
            pool_size=args.pool_size,
            max_overflow=args.max_overflow,
            users=args.users,
            spawn_rate=args.spawn_rate,
            duration=args.duration
        )


if __name__ == "__main__":
    # Check if locust is installed
    try:
        import locust
        import gevent
    except ImportError:
        print("❌ Missing dependencies. Install with:")
        print("   pip install locust gevent")
        sys.exit(1)

    main()
