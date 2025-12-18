"""
Encryption and hash lookup helpers for LGPD-compliant patient searches.

LGPD Compliance:
- Email and phone are encrypted in the database
- Searches use SHA-256 hashes for exact matches
"""

import logging
import re
from typing import List

from app.models.patient import Patient

logger = logging.getLogger(__name__)


def _looks_like_email(search_term: str) -> bool:
    """Check if search term looks like an email address."""
    return "@" in search_term and "." in search_term


def _looks_like_phone(search_term: str) -> bool:
    """Check if search term looks like a phone number."""
    # Remove common separators and check if mostly digits
    cleaned = re.sub(r"[\s\-\(\)\+]", "", search_term)
    return len(cleaned) >= 8 and cleaned.replace("+", "").isdigit()


def build_search_criteria(search_term: str) -> List:
    """
    Build search criteria for patient search using LGPD-compliant hash lookups.

    LGPD Compliance (migration 028+):
    - Email and phone are encrypted - use hash for exact match
    - Name is not encrypted - use ILIKE for partial match

    Args:
        search_term: The search term to look for

    Returns:
        List of SQLAlchemy filter criteria
    """
    criteria_parts = []
    search_val = f"%{search_term}%"

    # Name search - always use ILIKE (plaintext OK)
    criteria_parts.append(Patient.name.ilike(search_val))

    # Email search - use hash if looks like email
    if _looks_like_email(search_term):
        try:
            # Lazy import to avoid circular dependency
            from app.services.encryption import (
                get_unified_encryption_service,
                FieldType,
            )

            encryption_service = get_unified_encryption_service()
            email_hash = encryption_service.generate_hash(
                search_term.lower().strip(), FieldType.EMAIL
            )
            criteria_parts.append(Patient.email_hash == email_hash)
        except Exception as e:
            # Fallback: skip email search if encryption service unavailable
            logger.warning(f"Failed to hash email for search: {e}", exc_info=True)

    # Phone search - use hash if looks like phone
    if _looks_like_phone(search_term):
        try:
            # Lazy import to avoid circular dependency
            from app.services.encryption import (
                get_unified_encryption_service,
                FieldType,
            )

            encryption_service = get_unified_encryption_service()
            # Normalize phone for hash lookup
            normalized_phone = "".join(
                c for c in search_term if c.isdigit() or c == "+"
            )
            phone_hash = encryption_service.generate_hash(
                normalized_phone, FieldType.PHONE
            )
            criteria_parts.append(Patient.phone_hash == phone_hash)
        except Exception as e:
            # Fallback: skip phone search if encryption service unavailable
            logger.warning(f"Failed to hash phone for search: {e}", exc_info=True)

    return criteria_parts
