"""
LGPD-compliant search operations for patients.

This module provides search functionality for patient records
using LGPD-compliant hash-based lookups for encrypted fields.
"""

from __future__ import annotations

import logging
from typing import List

from sqlalchemy import or_

from app.models.patient import Patient

from .encryption_helpers import build_search_criteria

logger = logging.getLogger(__name__)


class PatientSearchMixin:
    """
    Search operations for patients with LGPD compliance.

    Provides search functionality using LGPD-compliant methods:
    - Name: ILIKE pattern matching (plaintext)
    - Email: SHA-256 hash exact matching (encrypted)
    - Phone: SHA-256 hash exact matching (encrypted)

    Methods:
        search_active: Search active patients by name, email, or phone.
    """

    def search_active(
        self, search_term: str, skip: int = 0, limit: int = 100
    ) -> List[Patient]:
        """
        Search active patients by name, email hash, or phone hash.

        LGPD Compliance (migration 028+):
        - Name: uses ILIKE for partial match (plaintext OK)
        - Email: uses SHA-256 hash for exact match (encrypted storage)
        - Phone: uses SHA-256 hash for exact match (encrypted storage)
        """
        search_criteria = build_search_criteria(search_term)

        query = self.db.query(Patient).filter(Patient.deleted_at.is_(None))

        if search_criteria:
            query = query.filter(or_(*search_criteria))

        return query.offset(skip).limit(limit).all()
