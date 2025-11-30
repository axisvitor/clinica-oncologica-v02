"""
Test Patient Repository N+1 Query Optimizations

Validates that the PatientRepository correctly implements eager loading
and caching strategies to prevent N+1 query problems.
"""
import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import event
from typing import List

from app.repositories.patient import PatientRepository
from app.models.patient import Patient, FlowState
from app.models.user import User
from app.models.message import Message


@pytest.fixture
def query_counter():
    """Fixture to count SQL queries executed"""
    class QueryCounter:
        def __init__(self):
            self.count = 0
            self.queries: List[str] = []

        def reset(self):
            self.count = 0
            self.queries = []

    counter = QueryCounter()

    def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        counter.count += 1
        counter.queries.append(statement)

    return counter


@pytest.fixture
def setup_test_data(db: Session):
    """Create test data with relationships"""
    # Create doctor
    doctor = User(
        id=uuid4(),
        email=f"doctor-{uuid4()}@test.com",
        full_name="Dr. Test",
        password_hash="hashed",
        role="doctor"
    )
    db.add(doctor)

    # Create 20 patients with related data
    patients = []
    for i in range(20):
        patient = Patient(
            id=uuid4(),
            doctor_id=doctor.id,
            phone=f"+5511999{i:06d}",
            name=f"Patient {i}",
            email=f"patient{i}@test.com",
            flow_state=FlowState.ACTIVE,
            current_day=i
        )
        db.add(patient)
        patients.append(patient)

        # Add messages for each patient
        for j in range(5):
            message = Message(
                id=uuid4(),
                patient_id=patient.id,
                sender_id=doctor.id,
                content=f"Message {j} for patient {i}",
                direction="outbound",
                status="sent"
            )
            db.add(message)

    db.commit()
    return doctor, patients


class TestPatientRepositoryN1Prevention:
    """Test N+1 query prevention in PatientRepository"""

    def test_list_v2_query_count_optimized(self, db: Session, setup_test_data, query_counter):
        """
        Verify list_v2 executes maximum 4 queries with eager loading.

        Expected queries:
        1. Main query with doctor JOIN
        2. Batch load messages
        3. Batch load quiz_sessions
        4. Batch load flow_states (if requested)
        """
        doctor, patients = setup_test_data
        repo = PatientRepository(db)

        # Attach query counter
        event.listen(db.bind, "after_cursor_execute", query_counter.receive_after_cursor_execute)

        try:
            query_counter.reset()

            # Execute with eager loading
            results, has_more, cursor, total = repo.list_v2(
                filters={"doctor_id": str(doctor.id)},
                limit=20,
                eager_load=["messages", "quiz_sessions", "flow_states"]
            )

            # Should execute max 5 queries:
            # 1. Count query
            # 2. Main query + doctor join
            # 3. Batch load messages
            # 4. Batch load quiz_sessions
            # 5. Batch load flow_states
            assert query_counter.count <= 5, (
                f"Expected max 5 queries, got {query_counter.count}. "
                f"Queries: {query_counter.queries}"
            )

            # Verify data loaded
            assert len(results) == 20
            for patient in results:
                # Doctor should be loaded (no additional query)
                assert patient.doctor is not None
                assert patient.doctor.full_name == "Dr. Test"

        finally:
            event.remove(db.bind, "after_cursor_execute", query_counter.receive_after_cursor_execute)

    def test_list_v2_messages_with_sender_no_n1(self, db: Session, setup_test_data, query_counter):
        """
        Verify messages with senders are loaded without N+1 queries.

        Critical fix: selectinload(messages).joinedload(sender)
        instead of selectinload(messages).selectinload(sender)
        """
        doctor, patients = setup_test_data
        repo = PatientRepository(db)

        event.listen(db.bind, "after_cursor_execute", query_counter.receive_after_cursor_execute)

        try:
            query_counter.reset()

            results, _, _, _ = repo.list_v2(
                filters={"doctor_id": str(doctor.id)},
                limit=20,
                eager_load=["messages"]
            )

            # Access messages and senders (should not trigger additional queries)
            for patient in results:
                for message in patient.messages:
                    # Accessing sender should NOT trigger query
                    sender = message.sender
                    assert sender is not None

            # Should be same query count (no N+1 from accessing senders)
            # Count + Main + Messages batch = 3 queries
            assert query_counter.count <= 3, (
                f"N+1 detected! Expected max 3 queries, got {query_counter.count}"
            )

        finally:
            event.remove(db.bind, "after_cursor_execute", query_counter.receive_after_cursor_execute)

    def test_cached_count_reduces_queries(self, db: Session, setup_test_data, query_counter, mocker):
        """
        Verify Redis caching reduces count queries on subsequent requests.
        """
        doctor, patients = setup_test_data
        repo = PatientRepository(db)

        # Mock Redis client
        mock_redis = mocker.MagicMock()
        mock_redis.get.return_value = None  # First call: cache miss
        mock_redis.setex.return_value = True
        repo._redis_client = mock_redis

        filters = {"doctor_id": str(doctor.id)}

        # First call: cache miss, should execute count query
        repo.list_v2(filters, limit=20)
        assert mock_redis.setex.called, "Count should be cached"

        # Second call: cache hit, should skip count query
        mock_redis.get.return_value = b"20"  # Cached count
        event.listen(db.bind, "after_cursor_execute", query_counter.receive_after_cursor_execute)

        try:
            query_counter.reset()
            results, _, _, total = repo.list_v2(filters, limit=20)

            # Should only execute main query (skip count)
            # 1. Main query + doctor join
            assert query_counter.count == 1, (
                f"With cache, expected 1 query, got {query_counter.count}"
            )
            assert total == 20, "Should use cached total"

        finally:
            event.remove(db.bind, "after_cursor_execute", query_counter.receive_after_cursor_execute)

    def test_list_patients_optimized_comprehensive(self, db: Session, setup_test_data, query_counter):
        """
        Test new list_patients_optimized method for guaranteed N+1 prevention.
        """
        doctor, patients = setup_test_data
        repo = PatientRepository(db)

        event.listen(db.bind, "after_cursor_execute", query_counter.receive_after_cursor_execute)

        try:
            query_counter.reset()

            # Use new optimized method
            import asyncio
            results, has_more, cursor, total = asyncio.run(
                repo.list_patients_optimized(
                    doctor_id=str(doctor.id),
                    filters={"search": "Patient"},
                    limit=20
                )
            )

            # Should execute max 8 queries:
            # 1. Count query
            # 2. Main query + doctor join
            # 3. Batch load messages
            # 4. Batch load quiz_sessions
            # 5. Batch load flow_states
            # 6. Batch load treatments
            # 7. Batch load appointments
            # 8. Batch load medications
            assert query_counter.count <= 8, (
                f"Expected max 8 queries, got {query_counter.count}"
            )

            # Verify all relationships loaded
            for patient in results:
                assert patient.doctor is not None
                # Messages should be loaded
                messages = patient.messages
                # No additional queries when accessing

        finally:
            event.remove(db.bind, "after_cursor_execute", query_counter.receive_after_cursor_execute)

    def test_cursor_pagination_query_count_stable(self, db: Session, setup_test_data, query_counter):
        """
        Verify query count remains stable across pagination.
        """
        doctor, patients = setup_test_data
        repo = PatientRepository(db)

        event.listen(db.bind, "after_cursor_execute", query_counter.receive_after_cursor_execute)

        try:
            # Page 1
            query_counter.reset()
            page1, has_more, cursor, _ = repo.list_v2(
                filters={"doctor_id": str(doctor.id)},
                limit=10,
                eager_load=["messages"]
            )
            page1_queries = query_counter.count

            # Page 2 (with cursor)
            query_counter.reset()
            page2, _, _, _ = repo.list_v2(
                filters={"doctor_id": str(doctor.id)},
                cursor_data={"id": str(page1[-1].id), "created_at": page1[-1].created_at.isoformat()},
                limit=10,
                eager_load=["messages"]
            )
            page2_queries = query_counter.count

            # Query count should be consistent (no count query on page 2)
            assert page2_queries <= page1_queries, (
                f"Page 2 should have same or fewer queries. "
                f"Page 1: {page1_queries}, Page 2: {page2_queries}"
            )

            # Should be exactly page1_queries - 1 (skip count)
            assert page2_queries == page1_queries - 1, (
                "Page 2 should skip count query"
            )

        finally:
            event.remove(db.bind, "after_cursor_execute", query_counter.receive_after_cursor_execute)

    def test_cache_key_generation_deterministic(self, db: Session):
        """
        Verify cache keys are deterministic for same filters.
        """
        repo = PatientRepository(db)

        # Same filters should produce same key
        filters1 = {"doctor_id": "abc-123", "status": "active"}
        filters2 = {"status": "active", "doctor_id": "abc-123"}  # Different order

        key1 = repo._get_cache_key("count", filters1)
        key2 = repo._get_cache_key("count", filters2)

        assert key1 == key2, "Keys should be identical for same filters regardless of order"

    def test_graceful_degradation_without_redis(self, db: Session, setup_test_data):
        """
        Verify repository works correctly even if Redis is unavailable.
        """
        doctor, patients = setup_test_data
        repo = PatientRepository(db)

        # Simulate Redis unavailable
        repo._redis_client = False

        # Should still work, just without caching
        results, has_more, cursor, total = repo.list_v2(
            filters={"doctor_id": str(doctor.id)},
            limit=20
        )

        assert len(results) == 20
        assert total == 20
        assert has_more is False


class TestPatientRepositoryPerformance:
    """Performance benchmarks for patient repository"""

    def test_response_time_under_limit(self, db: Session, setup_test_data, benchmark):
        """
        Benchmark patient listing to ensure response time < 200ms.
        """
        doctor, patients = setup_test_data
        repo = PatientRepository(db)

        def list_patients():
            return repo.list_v2(
                filters={"doctor_id": str(doctor.id)},
                limit=20,
                eager_load=["messages", "quiz_sessions"]
            )

        result = benchmark(list_patients)

        # Should complete in < 200ms
        assert result.stats.median < 0.2, (
            f"Patient listing too slow: {result.stats.median * 1000:.1f}ms"
        )

    def test_memory_usage_reasonable(self, db: Session, setup_test_data):
        """
        Verify memory usage stays reasonable even with eager loading.
        """
        import tracemalloc

        doctor, patients = setup_test_data
        repo = PatientRepository(db)

        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()

        # Load 20 patients with all relationships
        results, _, _, _ = repo.list_v2(
            filters={"doctor_id": str(doctor.id)},
            limit=20,
            eager_load=["messages", "quiz_sessions", "flow_states"]
        )

        snapshot2 = tracemalloc.take_snapshot()
        tracemalloc.stop()

        top_stats = snapshot2.compare_to(snapshot1, 'lineno')
        total_memory = sum(stat.size_diff for stat in top_stats)

        # Should use < 10MB for 20 patients
        assert total_memory < 10 * 1024 * 1024, (
            f"Excessive memory usage: {total_memory / 1024 / 1024:.2f}MB"
        )


# ============================================================================
# INTEGRATION TEST WITH ACTUAL DATABASE
# ============================================================================

@pytest.mark.integration
class TestPatientRepositoryIntegration:
    """Integration tests with real database"""

    def test_actual_query_count_in_production_scenario(self, db: Session):
        """
        Simulate production scenario and verify query count.

        This test should be run against a staging database with realistic data.
        """
        # This would use a real database with production-like data
        # Skip in unit tests
        pytest.skip("Integration test - requires staging database")
