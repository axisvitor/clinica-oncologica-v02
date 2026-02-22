"""Add patient_deletion_audit table with immutability rules.

Revision ID: lgpd01_add_patient_deletion_audit
Revises: ('015_rename_upload_metadata', 'a9c4e1d2b7f0')
Create Date: 2026-02-22

WHY:
LGPD Art. 16 / Art. 18 require that patient-data deletion events be
permanently recorded.  Railway log rotation means application logs are
ephemeral and cannot serve as a compliance record.  This table provides
a durable, tamper-proof audit trail that survives log rotation and
even hard-deletion of the patient row itself (no FK to patients.id).

WHAT:
- Creates the patient_deletion_audit table (append-only).
- Adds PostgreSQL RULE objects that silently discard any UPDATE or DELETE
  against the table, making rows immutable at the database level.
- Two composite indexes for compliance query patterns.

IMPACT:
- New table, no changes to existing tables.
- The delete_patient() service method is updated separately to INSERT
  a row inside the same transaction as the soft-delete (see crud_service.py).

BENCHMARK:
- INSERT cost is negligible (single row per deletion event).
- Query pattern: range scans on deleted_at or equality on patient_id —
  both covered by the indexes created here.

ROLLBACK:
- downgrade() drops the immutability rules first, then drops the table.
- WARNING: Running downgrade on a production database removes the LGPD
  audit trail.  Only use in development/testing.

RELATED:
- backend-hormonia/app/models/patient_deletion_audit.py
- backend-hormonia/app/services/patient/crud_service.py
- LGPD-01 requirement in REQUIREMENTS.md
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
# This migration merges the two current heads into a single chain so
# subsequent LGPD migrations have a single down_revision to reference.
revision = "lgpd01_add_patient_deletion_audit"
down_revision = ("015_rename_upload_metadata", "a9c4e1d2b7f0")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create patient_deletion_audit table and apply immutability rules.

    The RULE objects (not triggers) are used intentionally because they
    operate at the rewrite level and cannot be bypassed by superusers
    the way triggers can.  This matches the pattern used in 011_hipaa_audit
    for the audit_logs table.
    """

    # -----------------------------------------------------------------------
    # 1. Create the table
    # -----------------------------------------------------------------------
    op.create_table(
        "patient_deletion_audit",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            comment="Primary key",
        ),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            comment="UUID of the deleted patient (no FK — intentional)",
        ),
        sa.Column(
            "deleted_by_user_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
            comment="UUID of the user who triggered the deletion",
        ),
        sa.Column(
            "deleted_by_email",
            sa.String(255),
            nullable=True,
            comment="Email of the executor at deletion time",
        ),
        sa.Column(
            "deletion_reason",
            sa.Text,
            nullable=True,
            comment="Human-readable reason for the deletion",
        ),
        sa.Column(
            "patient_name_hash",
            sa.String(64),
            nullable=True,
            comment="SHA-256 hex digest of the patient name — NOT plaintext",
        ),
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Timezone-aware timestamp of the deletion event",
        ),
    )

    # -----------------------------------------------------------------------
    # 2. Add indexes
    # -----------------------------------------------------------------------
    # Fast lookup by patient ID (compliance queries: "show me all deletions
    # for patient X")
    op.create_index(
        "idx_pda_patient_id",
        "patient_deletion_audit",
        ["patient_id"],
        unique=False,
    )

    # Composite for the most common compliance query pattern:
    # range scans by deleted_at with patient_id filter
    op.create_index(
        "idx_pda_patient_deleted_at",
        "patient_deletion_audit",
        ["patient_id", "deleted_at"],
        unique=False,
    )

    # Range scans across all deletions within a date window
    op.create_index(
        "idx_pda_deleted_at",
        "patient_deletion_audit",
        ["deleted_at"],
        unique=False,
    )

    # -----------------------------------------------------------------------
    # 3. Apply immutability rules (LGPD compliance — rows must be permanent)
    #
    # Pattern copied directly from 011_hipaa_audit.py (audit_logs table).
    # Using RULE instead of trigger because RULEs intercept at the rewrite
    # layer and cannot be disabled per-session the way trigger-disable can.
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE RULE patient_deletion_audit_no_update AS
            ON UPDATE TO patient_deletion_audit DO INSTEAD NOTHING;
    """)

    op.execute("""
        CREATE RULE patient_deletion_audit_no_delete AS
            ON DELETE TO patient_deletion_audit DO INSTEAD NOTHING;
    """)


def downgrade() -> None:
    """
    Remove immutability rules then drop the patient_deletion_audit table.

    WARNING: Running this on a production database permanently destroys
    the LGPD compliance audit trail.  Only use in development/testing.
    """

    # Must drop rules before dropping the table
    op.execute(
        "DROP RULE IF EXISTS patient_deletion_audit_no_delete "
        "ON patient_deletion_audit;"
    )
    op.execute(
        "DROP RULE IF EXISTS patient_deletion_audit_no_update "
        "ON patient_deletion_audit;"
    )

    # Drop indexes explicitly (op.drop_table would cascade, but being explicit
    # avoids surprises when running partial downgrades)
    op.drop_index("idx_pda_deleted_at", table_name="patient_deletion_audit")
    op.drop_index("idx_pda_patient_deleted_at", table_name="patient_deletion_audit")
    op.drop_index("idx_pda_patient_id", table_name="patient_deletion_audit")

    op.drop_table("patient_deletion_audit")
