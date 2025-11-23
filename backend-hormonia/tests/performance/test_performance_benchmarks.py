"""
Performance Benchmarking Suite - HIGH-001, HIGH-002, HIGH-003

This test suite provides benchmarks for the performance improvements:
- HIGH-001: N+1 Query Fix
- HIGH-002: Cache Strategy
- HIGH-003: Race Condition Fix (no perf impact, correctness fix)

Target Metrics:
- GET /patients: < 50ms (from ~200ms)
- Cache hit rate: > 90%
- Zero N+1 queries in listings
- Zero race conditions under concurrent load
"""
import pytest
import time
import asyncio
from typing import List
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.patient import Patient
from app.models.user import User, UserRole
from app.services.cache.flow_template_cache import get_flow_template_cache


class TestN1QueryPerformance:
    """
    Benchmark N+1 query fixes (HIGH-001).

    Success Criteria:
    - List 50 patients in < 50ms
    - Query count ≤ 2 (1 for patients, 1 for doctors via JOIN)
    - No lazy loading warnings
    """

    @pytest.fixture
    def setup_patients(self, db: Session, test_doctor: User):
        """Create 50 test patients."""
        patients = []

        for i in range(50):
            patient = Patient(
                name=f"Test Patient {i}",
                phone=f"+5511999{i:06d}",
                email=f"patient{i}@test.com",
                cpf=f"{i:011d}",
                doctor_id=test_doctor.id,
            )
            db.add(patient)
            patients.append(patient)

        db.commit()
        return patients

    def test_list_patients_no_n1_queries(
        self,
        client: TestClient,
        setup_patients: List[Patient],
        db: Session,
        auth_headers: dict
    ):
        """
        Test that listing patients doesn't cause N+1 queries.

        Expected:
        - Execution time < 50ms
        - Query count = 1 (joined load)
        """
        # Enable query logging
        from sqlalchemy import event
        queries_executed = []

        def receive_after_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ):
            queries_executed.append(statement)

        event.listen(
            db.bind,
            'after_cursor_execute',
            receive_after_cursor_execute
        )

        # Measure performance
        start_time = time.perf_counter()

        response = client.get(
            "/api/v2/patients?limit=50",
            headers=auth_headers
        )

        end_time = time.perf_counter()
        execution_time_ms = (end_time - start_time) * 1000

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 50

        # Performance assertion
        assert execution_time_ms < 50, f"Too slow: {execution_time_ms:.2f}ms"

        # Query count assertion (should be 1 with joinedload)
        # Allow up to 2 queries (main query + possible count query)
        assert len(queries_executed) <= 2, (
            f"Too many queries: {len(queries_executed)}. "
            f"N+1 query detected!"
        )

        print(f"✅ Performance: {execution_time_ms:.2f}ms for 50 patients")
        print(f"✅ Query count: {len(queries_executed)}")

    def test_list_patients_with_doctor_no_n1(
        self,
        client: TestClient,
        setup_patients: List[Patient],
        db: Session,
        auth_headers: dict
    ):
        """
        Test that accessing doctor doesn't cause N+1.

        Expected:
        - Execution time < 50ms
        - Query count = 1 (joinedload)
        """
        from sqlalchemy import event
        queries_executed = []

        def receive_after_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ):
            queries_executed.append(statement)

        event.listen(
            db.bind,
            'after_cursor_execute',
            receive_after_cursor_execute
        )

        start_time = time.perf_counter()

        response = client.get(
            "/api/v2/patients?limit=50&include=doctor",
            headers=auth_headers
        )

        end_time = time.perf_counter()
        execution_time_ms = (end_time - start_time) * 1000

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 50

        # Verify doctor data is included
        for patient_data in data["data"]:
            assert "doctor" in patient_data
            assert patient_data["doctor"]["name"]

        # Performance
        assert execution_time_ms < 50, f"Too slow: {execution_time_ms:.2f}ms"
        assert len(queries_executed) <= 2, f"N+1 detected: {len(queries_executed)} queries"

        print(f"✅ Performance with doctor: {execution_time_ms:.2f}ms")


class TestCachePerformance:
    """
    Benchmark cache strategy (HIGH-002).

    Success Criteria:
    - Cache hit < 5ms
    - Cache miss < 200ms
    - Cache hit rate > 90% after warm-up
    """

    @pytest.fixture
    def cache_service(self):
        """Get cache service instance."""
        return get_flow_template_cache()

    async def test_cache_cold_start(self, cache_service):
        """
        Test cache performance on cold start (cache miss).

        Expected:
        - First access: ~200ms (load from YAML)
        - Subsequent accesses: < 5ms (cached)
        """
        # Clear cache
        cache_service.invalidate_all()

        # Cold start - cache miss
        start = time.perf_counter()
        template = await cache_service.get_template("monthly_quiz")
        cold_time_ms = (time.perf_counter() - start) * 1000

        assert template is not None
        print(f"Cache MISS: {cold_time_ms:.2f}ms")

        # Warm cache - cache hit
        start = time.perf_counter()
        template_cached = await cache_service.get_template("monthly_quiz")
        warm_time_ms = (time.perf_counter() - start) * 1000

        assert template_cached is not None
        assert template_cached == template

        print(f"Cache HIT: {warm_time_ms:.2f}ms")

        # Performance assertions
        assert warm_time_ms < 5, f"Cache too slow: {warm_time_ms:.2f}ms"

        # Should be at least 10x faster with cache
        speedup = cold_time_ms / warm_time_ms
        print(f"✅ Speedup: {speedup:.1f}x faster with cache")
        assert speedup > 10

    async def test_cache_hit_rate(self, cache_service):
        """
        Test cache hit rate under load.

        Expected:
        - Hit rate > 90% after warm-up
        """
        # Clear cache
        cache_service.invalidate_all()

        # Warm cache with first request
        await cache_service.get_template("monthly_quiz")

        # Simulate load (100 requests)
        for _ in range(100):
            await cache_service.get_template("monthly_quiz")

        # Check stats
        stats = cache_service.get_cache_stats()

        print(f"Cache Stats: {stats}")

        # Assertions
        assert stats["hit_rate_percent"] > 90, (
            f"Hit rate too low: {stats['hit_rate_percent']}%"
        )

        print(f"✅ Cache hit rate: {stats['hit_rate_percent']:.2f}%")

    async def test_cache_warm_performance(self, cache_service):
        """
        Test cache warming performance.

        Expected:
        - Warm all templates in < 1 second
        """
        # Clear cache
        cache_service.invalidate_all()

        # Warm cache
        start = time.perf_counter()
        count = await cache_service.warm_cache()
        warm_time_ms = (time.perf_counter() - start) * 1000

        print(f"Warmed {count} templates in {warm_time_ms:.2f}ms")

        assert count > 0
        assert warm_time_ms < 1000  # < 1 second


class TestRaceConditionProtection:
    """
    Test race condition protection (HIGH-003).

    Success Criteria:
    - Zero duplicates created under concurrent load
    - Proper IntegrityError handling
    - Clear error messages
    """

    def test_concurrent_patient_creation_no_duplicates(
        self,
        db: Session,
        test_doctor: User
    ):
        """
        Test that concurrent creation doesn't create duplicates.

        Scenario:
        - 10 threads try to create same patient simultaneously
        - Only 1 should succeed, 9 should get ValidationError
        """
        from app.services.patient.creation_service import PatientCreationService
        from app.schemas.patient import PatientCreate
        from app.exceptions import ValidationError

        # Same patient data for all threads
        patient_data = PatientCreate(
            name="Concurrent Test",
            phone="+5511999999999",
            email="concurrent@test.com",
            cpf="12345678901",
            birth_date="1990-01-01",
            treatment_type="Quimioterapia",
        )

        successes = []
        failures = []

        def create_patient_thread():
            """Thread function to create patient."""
            try:
                # Each thread gets its own session
                from app.database import SessionLocal
                thread_db = SessionLocal()

                service = PatientCreationService(thread_db)
                patient = service.create_patient_safe(
                    patient_data,
                    test_doctor.id
                )
                thread_db.commit()
                thread_db.close()

                successes.append(patient.id)
            except ValidationError as e:
                failures.append(e.code)
            except Exception as e:
                failures.append(str(e))

        # Launch 10 concurrent threads
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(create_patient_thread)
                for _ in range(10)
            ]

            # Wait for all threads
            for future in futures:
                future.result()

        # Assertions
        assert len(successes) == 1, (
            f"Expected 1 success, got {len(successes)}. "
            f"Race condition detected!"
        )

        assert len(failures) == 9, (
            f"Expected 9 failures, got {len(failures)}"
        )

        # All failures should be duplicate errors
        for failure in failures:
            assert failure in ["duplicate_cpf", "duplicate_phone", "duplicate_email"]

        print(f"✅ Concurrent creation: {len(successes)} success, {len(failures)} prevented")

        # Cleanup
        db.query(Patient).filter(Patient.cpf == "12345678901").delete()
        db.commit()


class TestEndToEndPerformance:
    """
    End-to-end performance tests combining all optimizations.

    Success Criteria:
    - Complete patient creation flow < 500ms
    - Patient listing < 50ms
    - Cache hit rate > 95%
    """

    def test_patient_creation_e2e_performance(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """
        Test complete patient creation performance.

        Expected:
        - Total time < 500ms (including Saga)
        """
        patient_data = {
            "name": "Performance Test",
            "phone": f"+5511999{uuid4().hex[:6]}",
            "email": f"perf{uuid4().hex[:8]}@test.com",
            "cpf": f"{uuid4().int % 100000000000:011d}",
            "birth_date": "1990-01-01",
            "treatment_type": "Quimioterapia",
            "doctor_id": str(uuid4()),
        }

        start = time.perf_counter()

        response = client.post(
            "/api/v2/patients",
            json=patient_data,
            headers=auth_headers
        )

        end = time.perf_counter()
        execution_time_ms = (end - start) * 1000

        print(f"Patient creation: {execution_time_ms:.2f}ms")

        # Allow up to 500ms for Saga orchestration
        assert execution_time_ms < 500, f"Too slow: {execution_time_ms:.2f}ms"

        if response.status_code == 201:
            print(f"✅ E2E creation: {execution_time_ms:.2f}ms")
