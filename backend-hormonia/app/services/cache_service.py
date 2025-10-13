"""
Cache Invalidation Service - Tag-based and Pattern-based Invalidation

Sprint 1 (P1-1): Comprehensive cache management with warming strategies.

Features:
- Tag-based invalidation (invalidate all "patient:123" queries)
- Pattern-based invalidation (invalidate "patient:*")
- Bulk invalidation methods
- Cache warming strategies for common queries
- Cache statistics and monitoring
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID

from app.utils.query_cache import QueryCache, get_query_cache

logger = logging.getLogger(__name__)


class CacheService:
    """
    Cache invalidation and management service.

    Provides high-level API for cache operations beyond basic get/set.
    """

    def __init__(self, cache: Optional[QueryCache] = None):
        """
        Initialize cache service.

        Args:
            cache: Optional QueryCache instance (uses global if None)
        """
        self.cache = cache or get_query_cache()

    # ==========================
    # INVALIDATION METHODS
    # ==========================

    def invalidate_patient(self, patient_id: UUID) -> int:
        """
        Invalidate all cached queries for a patient.

        Call this after:
        - Patient update
        - Patient deletion
        - Flow state changes

        Args:
            patient_id: Patient UUID

        Returns:
            Number of cache entries invalidated
        """
        tag = f"patient:{patient_id}"
        count = self.cache.invalidate_by_tag(tag)
        logger.info(f"Invalidated {count} cache entries for patient {patient_id}")
        return count

    def invalidate_quiz(self, quiz_id: UUID) -> int:
        """
        Invalidate all cached queries for a quiz.

        Args:
            quiz_id: Quiz UUID

        Returns:
            Number of cache entries invalidated
        """
        tag = f"quiz:{quiz_id}"
        count = self.cache.invalidate_by_tag(tag)
        logger.info(f"Invalidated {count} cache entries for quiz {quiz_id}")
        return count

    def invalidate_report(self, report_id: UUID) -> int:
        """
        Invalidate all cached queries for a report.

        Args:
            report_id: Report UUID

        Returns:
            Number of cache entries invalidated
        """
        tag = f"report:{report_id}"
        count = self.cache.invalidate_by_tag(tag)
        logger.info(f"Invalidated {count} cache entries for report {report_id}")
        return count

    def invalidate_doctor(self, doctor_id: UUID) -> int:
        """
        Invalidate all cached queries for a doctor.

        Use case: Doctor profile update, patient assignment changes.

        Args:
            doctor_id: Doctor UUID

        Returns:
            Number of cache entries invalidated
        """
        tag = f"doctor:{doctor_id}"
        count = self.cache.invalidate_by_tag(tag)
        logger.info(f"Invalidated {count} cache entries for doctor {doctor_id}")
        return count

    def invalidate_all_patients(self) -> int:
        """
        Invalidate ALL patient-related caches.

        WARNING: Expensive operation. Use sparingly.

        Returns:
            Number of cache entries invalidated
        """
        pattern = "query_cache:patient:*"
        count = self.cache.invalidate_by_pattern(pattern)
        logger.warning(f"Invalidated ALL patient caches: {count} entries")
        return count

    def invalidate_all_quizzes(self) -> int:
        """
        Invalidate ALL quiz-related caches.

        Returns:
            Number of cache entries invalidated
        """
        pattern = "query_cache:quiz:*"
        count = self.cache.invalidate_by_pattern(pattern)
        logger.warning(f"Invalidated ALL quiz caches: {count} entries")
        return count

    def invalidate_multiple_tags(self, tags: List[str]) -> Dict[str, int]:
        """
        Bulk invalidation by multiple tags.

        Args:
            tags: List of tags to invalidate

        Returns:
            Dictionary mapping tag -> count invalidated
        """
        results = {}

        for tag in tags:
            count = self.cache.invalidate_by_tag(tag)
            results[tag] = count

        total = sum(results.values())
        logger.info(f"Bulk invalidation: {total} entries across {len(tags)} tags")

        return results

    def invalidate_by_tag(self, tag: str) -> int:
        """
        Invalidate cache entries associated with a specific tag.

        Args:
            tag: Cache tag identifier

        Returns:
            Number of entries invalidated
        """
        count = self.cache.invalidate_by_tag(tag)
        logger.debug(f"Cache invalidated by tag {tag}: {count} entries")
        return count

    # ==========================
    # CACHE WARMING METHODS
    # ==========================

    def warm_patient_cache(
        self,
        db,
        patient_id: UUID,
        include_relations: bool = True
    ) -> Dict[str, bool]:
        """
        Pre-warm cache for a patient's common queries.

        Reduces cold-start latency for frequently accessed patient data.

        Args:
            db: Database session
            patient_id: Patient UUID
            include_relations: Warm related data (doctor, reports, etc.)

        Returns:
            Dictionary of warmed queries and their success status
        """
        from app.repositories.patient import PatientRepository
        from app.repositories.report import MedicalReportRepository
        from app.repositories.quiz import QuizRepository

        results = {}

        try:
            # Warm patient basic info
            patient_repo = PatientRepository(db)
            patient = patient_repo.get_by_id(patient_id)

            if patient:
                cache_key = self.cache.generate_cache_key(
                    'patient',
                    arg_1=str(patient_id)
                )
                self.cache.set(
                    cache_key,
                    patient,
                    ttl=600,
                    tags=[f"patient:{patient_id}"]
                )
                results['patient_info'] = True

                if include_relations:
                    # Warm patient reports
                    report_repo = MedicalReportRepository(db)
                    reports = report_repo.get_by_patient(patient_id, limit=10)

                    cache_key = self.cache.generate_cache_key(
                        'patient_reports',
                        arg_1=str(patient_id)
                    )
                    self.cache.set(
                        cache_key,
                        reports,
                        ttl=300,
                        tags=[f"patient:{patient_id}"]
                    )
                    results['patient_reports'] = True

                    # Warm patient quiz responses
                    quiz_repo = QuizRepository(db)
                    sessions = quiz_repo.get_by_patient(patient_id, limit=10)

                    cache_key = self.cache.generate_cache_key(
                        'patient_quizzes',
                        arg_1=str(patient_id)
                    )
                    self.cache.set(
                        cache_key,
                        sessions,
                        ttl=300,
                        tags=[f"patient:{patient_id}"]
                    )
                    results['patient_quizzes'] = True
            else:
                results['patient_info'] = False

        except Exception as e:
            logger.error(f"Cache warming error for patient {patient_id}: {e}")
            results['error'] = str(e)

        logger.info(f"Cache warming completed for patient {patient_id}: {results}")
        return results

    def warm_doctor_dashboard(self, db, doctor_id: UUID) -> Dict[str, bool]:
        """
        Pre-warm cache for doctor dashboard queries.

        Reduces dashboard load time by caching common aggregations.

        Args:
            db: Database session
            doctor_id: Doctor UUID

        Returns:
            Dictionary of warmed queries
        """
        from app.repositories.patient import PatientRepository

        results = {}

        try:
            patient_repo = PatientRepository(db)

            # Warm patient list (most common query)
            patients = patient_repo.get_by_doctor(doctor_id, limit=50)

            cache_key = self.cache.generate_cache_key(
                'doctor_patients',
                arg_1=str(doctor_id)
            )
            self.cache.set(
                cache_key,
                patients,
                ttl=300,
                tags=[f"doctor:{doctor_id}"]
            )
            results['doctor_patients'] = True

        except Exception as e:
            logger.error(f"Dashboard cache warming error for doctor {doctor_id}: {e}")
            results['error'] = str(e)

        logger.info(f"Dashboard cache warming completed for doctor {doctor_id}")
        return results

    # ==========================
    # MONITORING & STATISTICS
    # ==========================

    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics.

        Returns:
            Dictionary with performance metrics
        """
        stats = self.cache.get_stats()

        # Add timestamp
        stats['timestamp'] = datetime.utcnow().isoformat()

        # Add health indicators
        hit_rate = stats.get('hit_rate_percent', 0)
        stats['health'] = {
            'status': 'healthy' if hit_rate >= 60 else 'degraded' if hit_rate >= 40 else 'unhealthy',
            'hit_rate_target': 60,
            'current_hit_rate': hit_rate
        }

        return stats

    def reset_statistics(self):
        """Reset cache performance statistics."""
        self.cache.reset_stats()
        logger.info("Cache statistics reset")

    def get_tag_info(self, tag: str) -> Dict[str, Any]:
        """
        Get information about a cache tag.

        Args:
            tag: Tag to inspect

        Returns:
            Dictionary with tag information
        """
        try:
            tag_key = f"query_cache_tags:{tag}"

            # Get keys associated with tag
            keys = self.cache.redis.smembers(tag_key)

            # Get TTL for tag set
            ttl = self.cache.redis.ttl(tag_key)

            return {
                'tag': tag,
                'key_count': len(keys),
                'ttl_seconds': ttl if ttl > 0 else None,
                'keys': list(keys) if keys else []
            }

        except Exception as e:
            logger.error(f"Error getting tag info for '{tag}': {e}")
            return {'error': str(e)}


# Global service instance
_cache_service = None


def get_cache_service() -> CacheService:
    """
    Get global cache service instance.

    Returns:
        CacheService singleton
    """
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service
