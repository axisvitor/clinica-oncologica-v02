"""
Patient repository with soft delete support and N+1 query optimizations.

LGPD Compliance (migration 028+):
- Email and phone are encrypted in the database
- Searches use SHA-256 hashes for exact matches
- Name searches still use ILIKE (plaintext OK for names)

Architecture:
- base.py: Core CRUD operations (~200 lines)
- search.py: LGPD-compliant search (~150 lines)
- pagination.py: Cursor pagination (~180 lines)
- eager_loading.py: Query optimization (~100 lines)
- encryption_helpers.py: Hash lookups (~80 lines)
- audit.py: Hard delete + audit (~100 lines)
"""

from .base import PatientRepositoryBase
from .search import PatientSearchMixin
from .pagination import PatientPaginationMixin
from .eager_loading import PatientEagerLoadingMixin
from .audit import PatientAuditMixin


class PatientRepository(
    PatientRepositoryBase,
    PatientSearchMixin,
    PatientPaginationMixin,
    PatientEagerLoadingMixin,
    PatientAuditMixin,
):
    """
    Patient repository with soft delete filtering and advanced query capabilities.

    PERFORMANCE OPTIMIZATIONS:
    - N+1 query prevention via joinedload/selectinload
    - Redis caching for total counts (60s TTL)
    - Batch loading for relationships
    - Optimized eager loading strategies

    LGPD COMPLIANCE:
    - Hash-based encrypted field lookups
    - Audit trail for hard deletes
    - Right to be forgotten support
    """

    pass


# Export for backward compatibility
__all__ = ["PatientRepository"]

# See docs/database/PERFORMANCE_INDEXES.md for SQL index recommendations
