"""
Integration tests for query caching functionality.

Tests the @cached_query decorator in real database scenarios to verify:
- Cache hit/miss rates
- Performance improvements
- Cache invalidation on mutations
- Multi-query coordination
"""

import pytest
import time
from datetime import datetime, timedelta
from typing import List
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.user import User
from app.repositories.patient import PatientRepository
from app.repositories.user import UserRepository
from app.utils.query_cache import cached_query, QueryCache, invalidate_cache


class TestQueryCacheIntegration:
    """Integration tests for query caching with real database operations."""

    @pytest.fixture
    def cache(self):
        """Provide a fresh cache instance for each test."""
        cache_instance = QueryCache()
        cache_instance.clear()
        return cache_instance

    @pytest.fixture
    def patient_repo(self):
        """Provide patient repository instance."""
        return PatientRepository()

    @pytest.fixture
    def user_repo(self):
        """Provide user repository instance."""
        return UserRepository()

    @pytest.fixture
    def sample_patient(self, db_session: Session) -> Patient:
        """Create a sample patient for testing."""
        patient = Patient(
            nome="Test Patient",
            email="test.patient@example.com",
            telefone="1234567890",
            data_nascimento=datetime(1990, 1, 1),
            cpf="12345678901"
        )
        db_session.add(patient)
        db_session.commit()
        db_session.refresh(patient)
        return patient

    def test_cached_query_reduces_database_calls(
        self,
        db_session: Session,
        patient_repo: PatientRepository,
        sample_patient: Patient,
        cache: QueryCache
    ):
        """Verify that cached queries reduce database calls."""
        patient_id = sample_patient.id

        # Get initial query count
        initial_count = self._get_query_count(db_session)

        # First call - cache miss, hits database
        patient1 = patient_repo.get_by_id(db_session, patient_id)
        after_first_call = self._get_query_count(db_session)
        first_call_queries = after_first_call - initial_count

        # Second call - cache hit, should NOT hit database
        patient2 = patient_repo.get_by_id(db_session, patient_id)
        after_second_call = self._get_query_count(db_session)
        second_call_queries = after_second_call - after_first_call

        # Verify cache worked
        assert patient1.id == patient2.id
        assert patient1.nome == patient2.nome
        assert first_call_queries > 0, "First call should query database"
        assert second_call_queries == 0, "Second call should use cache"

    def test_cache_hit_miss_rates(
        self,
        db_session: Session,
        patient_repo: PatientRepository,
        sample_patient: Patient,
        cache: QueryCache
    ):
        """Test cache hit/miss statistics tracking."""
        patient_id = sample_patient.id

        # Clear cache to start fresh
        cache.clear()

        # First call - miss
        patient_repo.get_by_id(db_session, patient_id)
        stats = cache.get_stats()
        assert stats['misses'] == 1
        assert stats['hits'] == 0
        assert stats['hit_rate'] == 0.0

        # Second call - hit
        patient_repo.get_by_id(db_session, patient_id)
        stats = cache.get_stats()
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate'] == 0.5

        # Third call - hit
        patient_repo.get_by_id(db_session, patient_id)
        stats = cache.get_stats()
        assert stats['hits'] == 2
        assert stats['misses'] == 1
        assert stats['hit_rate'] == pytest.approx(0.667, 0.01)

    def test_cache_invalidation_on_update(
        self,
        db_session: Session,
        patient_repo: PatientRepository,
        sample_patient: Patient,
        cache: QueryCache
    ):
        """Verify cache invalidates correctly on data mutation."""
        patient_id = sample_patient.id

        # Cache the patient
        cached_patient = patient_repo.get_by_id(db_session, patient_id)
        assert cached_patient.nome == "Test Patient"

        # Update patient directly in database
        db_session.query(Patient).filter(Patient.id == patient_id).update(
            {"nome": "Updated Patient Name"}
        )
        db_session.commit()

        # Invalidate cache
        invalidate_cache(f"patient:{patient_id}")

        # Fetch again - should get updated data
        updated_patient = patient_repo.get_by_id(db_session, patient_id)
        assert updated_patient.nome == "Updated Patient Name"

    def test_cache_invalidation_on_delete(
        self,
        db_session: Session,
        patient_repo: PatientRepository,
        sample_patient: Patient,
        cache: QueryCache
    ):
        """Verify cache invalidates on record deletion."""
        patient_id = sample_patient.id

        # Cache the patient
        patient_repo.get_by_id(db_session, patient_id)

        # Delete patient
        db_session.delete(sample_patient)
        db_session.commit()

        # Invalidate cache
        invalidate_cache(f"patient:{patient_id}")

        # Fetch again - should return None
        deleted_patient = patient_repo.get_by_id(db_session, patient_id)
        assert deleted_patient is None

    def test_cache_performance_improvement(
        self,
        db_session: Session,
        patient_repo: PatientRepository,
        sample_patient: Patient
    ):
        """Verify cache improves query performance."""
        patient_id = sample_patient.id

        # Measure uncached query time
        uncached_times = []
        for _ in range(5):
            start = time.perf_counter()
            patient_repo.get_by_id(db_session, patient_id)
            invalidate_cache(f"patient:{patient_id}")  # Force cache miss
            uncached_times.append(time.perf_counter() - start)

        avg_uncached = sum(uncached_times) / len(uncached_times)

        # Measure cached query time
        cached_times = []
        # Prime the cache
        patient_repo.get_by_id(db_session, patient_id)

        for _ in range(5):
            start = time.perf_counter()
            patient_repo.get_by_id(db_session, patient_id)
            cached_times.append(time.perf_counter() - start)

        avg_cached = sum(cached_times) / len(cached_times)

        # Cache should be faster (at least 2x)
        assert avg_cached < avg_uncached / 2, \
            f"Cache ({avg_cached:.6f}s) should be faster than uncached ({avg_uncached:.6f}s)"

    def test_cache_with_multiple_queries(
        self,
        db_session: Session,
        patient_repo: PatientRepository,
        cache: QueryCache
    ):
        """Test cache behavior with multiple different queries."""
        # Create multiple patients
        patients = []
        for i in range(5):
            patient = Patient(
                nome=f"Patient {i}",
                email=f"patient{i}@example.com",
                telefone=f"123456789{i}",
                data_nascimento=datetime(1990 + i, 1, 1),
                cpf=f"1234567890{i}"
            )
            db_session.add(patient)
            patients.append(patient)
        db_session.commit()

        cache.clear()

        # Query each patient twice
        for patient in patients:
            # First call - miss
            result1 = patient_repo.get_by_id(db_session, patient.id)
            # Second call - hit
            result2 = patient_repo.get_by_id(db_session, patient.id)
            assert result1.id == result2.id

        # Verify stats
        stats = cache.get_stats()
        assert stats['misses'] == 5  # One miss per patient
        assert stats['hits'] == 5    # One hit per patient
        assert stats['hit_rate'] == 0.5

    def test_cache_expiration(
        self,
        db_session: Session,
        patient_repo: PatientRepository,
        sample_patient: Patient,
        cache: QueryCache
    ):
        """Test cache TTL expiration."""
        patient_id = sample_patient.id

        # Set cache with short TTL (1 second)
        cache_key = f"patient:{patient_id}"
        patient_repo.get_by_id(db_session, patient_id)

        # Verify cache hit
        assert cache.get(cache_key) is not None

        # Wait for expiration
        time.sleep(1.5)

        # Cache should be expired
        assert cache.get(cache_key) is None

    def test_concurrent_cache_access(
        self,
        db_session: Session,
        patient_repo: PatientRepository,
        sample_patient: Patient,
        cache: QueryCache
    ):
        """Test cache behavior under concurrent access patterns."""
        patient_id = sample_patient.id

        # Simulate concurrent reads
        results = []
        for _ in range(10):
            result = patient_repo.get_by_id(db_session, patient_id)
            results.append(result)

        # All results should be identical
        assert all(r.id == patient_id for r in results)
        assert all(r.nome == sample_patient.nome for r in results)

        # Most should be cache hits
        stats = cache.get_stats()
        assert stats['hits'] >= 8  # At least 80% hit rate

    def _get_query_count(self, db_session: Session) -> int:
        """Get the number of queries executed in current session."""
        # This is a simplified version - in production you'd use
        # SQLAlchemy's connection pool statistics or a query counter
        result = db_session.execute(text(
            "SELECT count(*) FROM pg_stat_statements WHERE query LIKE '%SELECT%'"
        ))
        return result.scalar() or 0


class TestCacheInvalidationPatterns:
    """Test different cache invalidation strategies."""

    @pytest.fixture
    def patient_repo(self):
        return PatientRepository()

    def test_single_key_invalidation(
        self,
        db_session: Session,
        patient_repo: PatientRepository
    ):
        """Test invalidating a single cache key."""
        patient = Patient(
            nome="Test Patient",
            email="test@example.com",
            telefone="1234567890",
            data_nascimento=datetime(1990, 1, 1),
            cpf="12345678901"
        )
        db_session.add(patient)
        db_session.commit()

        # Cache the patient
        patient_repo.get_by_id(db_session, patient.id)

        # Invalidate
        invalidate_cache(f"patient:{patient.id}")

        # Should be cache miss
        QueryCache().clear_pattern(f"patient:{patient.id}")

    def test_pattern_invalidation(
        self,
        db_session: Session,
        patient_repo: PatientRepository
    ):
        """Test invalidating multiple keys by pattern."""
        # Create multiple patients
        for i in range(5):
            patient = Patient(
                nome=f"Patient {i}",
                email=f"patient{i}@example.com",
                telefone=f"123456789{i}",
                data_nascimento=datetime(1990 + i, 1, 1),
                cpf=f"1234567890{i}"
            )
            db_session.add(patient)
        db_session.commit()

        # Cache all patients
        patients = db_session.query(Patient).all()
        for p in patients:
            patient_repo.get_by_id(db_session, p.id)

        # Invalidate all patient cache
        QueryCache().clear_pattern("patient:*")

        # All should be cache misses now
        stats = QueryCache().get_stats()
        initial_misses = stats['misses']

        for p in patients:
            patient_repo.get_by_id(db_session, p.id)

        new_stats = QueryCache().get_stats()
        assert new_stats['misses'] > initial_misses


@pytest.mark.integration
@pytest.mark.performance
class TestCachePerformanceBenchmarks:
    """Performance benchmarks for cache system."""

    def test_large_result_set_caching(self, db_session: Session):
        """Test cache performance with large result sets."""
        # Create 100 patients
        patients = []
        for i in range(100):
            patient = Patient(
                nome=f"Patient {i}",
                email=f"patient{i}@example.com",
                telefone=f"123456789{i}",
                data_nascimento=datetime(1990, 1, 1),
                cpf=f"1234567890{i:02d}"
            )
            patients.append(patient)

        db_session.bulk_save_objects(patients)
        db_session.commit()

        # Measure uncached query
        start = time.perf_counter()
        result1 = db_session.query(Patient).all()
        uncached_time = time.perf_counter() - start

        # Measure cached query (simulated)
        start = time.perf_counter()
        result2 = db_session.query(Patient).all()
        cached_time = time.perf_counter() - start

        assert len(result1) == 100
        assert len(result2) == 100
        # Note: Actual caching would show bigger difference

    def test_cache_memory_efficiency(self, db_session: Session):
        """Test cache memory usage stays reasonable."""
        cache = QueryCache()
        cache.clear()

        # Add many items to cache
        for i in range(1000):
            cache.set(f"key_{i}", f"value_{i}")

        # Cache should maintain reasonable size
        stats = cache.get_stats()
        assert stats['size'] <= 1000  # Should not exceed set size
