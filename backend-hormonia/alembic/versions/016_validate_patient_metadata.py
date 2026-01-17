"""
Migration 016: Validate Patient Metadata Against JSON Schema

Reference: LOW-007 - JSONB Schema Validation
Created: 2025-11-16
Agent: Agent 18 - Validation & Error Handling Specialist

This migration validates existing patient metadata against the new JSON schema
and logs any violations without failing the migration.

Revision ID: 016_validate_patient_metadata
Revises: 015_rename_upload_metadata
Create Date: 2025-11-16 18:30:00

WHY:
- Not recorded (legacy migration).

WHAT:
- Not recorded (legacy migration).

IMPACT:
- Not recorded (legacy migration).

BENCHMARK:
- Not recorded (legacy migration).

ROLLBACK:
- Not recorded (legacy migration).

RELATED:
- Not recorded (legacy migration).

MIGRATION TYPE:
- Not recorded (legacy migration).
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import logging

# revision identifiers, used by Alembic.
revision: str = '016_validate_patient_metadata'
down_revision: Union[str, None] = '015_rename_upload_metadata'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger(__name__)


def upgrade() -> None:
    """
    Validate existing patient metadata against JSON schema.

    This migration:
    1. Checks all existing patient metadata
    2. Validates against the new JSON schema
    3. Logs violations (does not fail migration)
    4. Optionally sanitizes invalid metadata
    """
    logger.info("Starting migration 014: Validate patient metadata")

    # Import validator (runtime import to avoid circular dependencies)
    try:
        from app.utils.jsonb_validator import (
            get_validation_errors,
            sanitize_metadata,
            is_valid_metadata
        )
    except ImportError:
        logger.warning(
            "Cannot import jsonb_validator. Skipping validation. "
            "Ensure app code is in PYTHONPATH."
        )
        return

    # Connect to database
    connection = op.get_bind()

    # Query all patients with metadata
    result = connection.execute(sa.text("""
        SELECT id, name, metadata
        FROM patients
        WHERE metadata IS NOT NULL
          AND metadata::text != '{}'
        ORDER BY created_at DESC
    """))

    total_patients = 0
    valid_patients = 0
    invalid_patients = 0
    sanitized_patients = 0

    logger.info("Validating patient metadata...")

    for row in result:
        total_patients += 1
        patient_id = row[0]
        patient_name = row[1]
        metadata = row[2]

        # Validate metadata
        if is_valid_metadata(metadata):
            valid_patients += 1
        else:
            invalid_patients += 1

            # Get detailed errors
            errors = get_validation_errors(metadata)

            logger.warning(
                f"Patient {patient_id} ({patient_name}) has invalid metadata. "
                f"Errors: {len(errors)}"
            )

            for error in errors:
                logger.warning(
                    f"  - Field: {error['field']}, Error: {error['message']}"
                )

            # OPTIONAL: Sanitize invalid metadata
            # Uncomment the following lines to auto-fix invalid metadata
            #
            # sanitized = sanitize_metadata(metadata)
            # if sanitized != metadata:
            #     connection.execute(sa.text("""
            #         UPDATE patients
            #         SET metadata = :sanitized
            #         WHERE id = :patient_id
            #     """), {"sanitized": sanitized, "patient_id": patient_id})
            #     sanitized_patients += 1
            #     logger.info(f"  → Sanitized patient {patient_id} metadata")

    # Log summary
    logger.info("=" * 70)
    logger.info("Migration 014 Summary: Patient Metadata Validation")
    logger.info("=" * 70)
    logger.info(f"Total patients with metadata: {total_patients}")
    logger.info(f"Valid metadata: {valid_patients} ({valid_patients/total_patients*100 if total_patients > 0 else 0:.1f}%)")
    logger.info(f"Invalid metadata: {invalid_patients} ({invalid_patients/total_patients*100 if total_patients > 0 else 0:.1f}%)")
    if sanitized_patients > 0:
        logger.info(f"Sanitized patients: {sanitized_patients}")
    logger.info("=" * 70)

    if invalid_patients > 0:
        logger.warning(
            f"Found {invalid_patients} patients with invalid metadata. "
            f"Review warnings above. To auto-fix, uncomment sanitization code."
        )
    else:
        logger.info("✅ All patient metadata is valid!")

    # Add comment to migration
    op.execute(sa.text("""
        COMMENT ON TABLE patients IS
        'Patient table with validated JSONB metadata (Migration 014)'
    """))


def downgrade() -> None:
    """
    Downgrade migration.

    This migration only validates data (no schema changes),
    so downgrade is a no-op.
    """
    logger.info("Downgrading migration 014: No schema changes to revert")

    # Remove comment
    op.execute(sa.text("""
        COMMENT ON TABLE patients IS NULL
    """))
