"""
Patient repository with soft delete support and N+1 query optimizations.

This package provides a comprehensive patient repository with
LGPD compliance, performance optimizations, and advanced querying
capabilities.

LGPD Compliance (migration 028+):
- Email and phone are encrypted in the database
- Searches use SHA-256 hashes for exact matches
- Name searches still use ILIKE (plaintext OK for names)

Architecture:
- base.py: Core CRUD operations
- search.py: LGPD-compliant search
- pagination.py: Cursor pagination with caching
- eager_loading.py: Query optimization strategies
- encryption_helpers.py: Hash lookup utilities
- audit.py: Hard delete with audit trail

Performance Features:
- N+1 query prevention via eager loading
- Redis caching for counts (60s TTL)
- Cursor-based pagination
- Batch relationship loading
"""

from __future__ import annotations

from .audit import PatientAuditMixin
from .base import PatientRepositoryBase
from .eager_loading import PatientEagerLoadingMixin
from .encryption_helpers import build_search_criteria
from .pagination import PatientPaginationMixin
from .search import PatientSearchMixin


class PatientRepository(
    PatientRepositoryBase,
    PatientSearchMixin,
    PatientPaginationMixin,
    PatientEagerLoadingMixin,
    PatientAuditMixin,
):
    """
    Patient repository with soft delete filtering and advanced query capabilities.

    This is the main repository class that combines all mixins to provide
    comprehensive patient data management with LGPD compliance and
    performance optimizations.

    Performance Optimizations:
        - N+1 query prevention via joinedload/selectinload
        - Redis caching for total counts (60s TTL)
        - Batch loading for relationships
        - Optimized eager loading strategies

    LGPD Compliance:
        - Hash-based encrypted field lookups
        - Audit trail for hard deletes
        - Right to be forgotten support
        - Encrypted email and phone storage

    Features:
        - Soft delete support
        - Cursor-based pagination
        - Advanced filtering and search
        - Optimized eager loading
        - Redis caching integration
        - LGPD-compliant audit logging

    See Also:
        - docs/database/PERFORMANCE_INDEXES.md for SQL index recommendations
    """

    pass


# Public API exports
__all__ = [
    "PatientRepository",
    "PatientRepositoryBase",
    "PatientSearchMixin",
    "PatientPaginationMixin",
    "PatientEagerLoadingMixin",
    "PatientAuditMixin",
    "build_search_criteria",
]
