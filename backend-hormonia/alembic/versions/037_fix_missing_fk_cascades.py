"""Fix missing FK cascades for Alert, Report, MedicalReport, EvolutionWebhookEvent

Revision ID: 037_fix_missing_fk_cascades
Revises: 036_add_saga_step_data_column
Create Date: 2025-12-26

This migration adds proper CASCADE/SET NULL behavior to foreign key constraints
that were missing these options, ensuring proper cleanup when referenced records
are deleted.

Changes:
- alerts.patient_id: Add ON DELETE CASCADE
- alerts.acknowledged_by: Add ON DELETE SET NULL
- medical_reports.patient_id: Add ON DELETE CASCADE
- medical_reports.generated_by: Add ON DELETE SET NULL
- reports.patient_id: Add ON DELETE CASCADE
- webhook_events: Add optional FK constraints for related_message_id and related_patient_id

Note: The webhook_events table has related_message_id and related_patient_id as plain
UUID columns without FK constraints. This migration adds proper FK constraints with
SET NULL behavior to maintain referential integrity while allowing flexibility.

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

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "037_fix_missing_fk_cascades"
down_revision = "036_add_saga_step_data_column"
branch_labels = None
depends_on = None


def get_existing_constraint_name(inspector, table_name: str, column_name: str) -> str | None:
    """Get the actual FK constraint name from the database for a given column."""
    try:
        fks = inspector.get_foreign_keys(table_name)
        for fk in fks:
            if column_name in fk.get("constrained_columns", []):
                return fk.get("name")
    except Exception:
        pass
    return None


def constraint_exists(inspector, table_name: str, constraint_name: str) -> bool:
    """Check if a constraint exists on a table."""
    try:
        fks = inspector.get_foreign_keys(table_name)
        return any(fk.get("name") == constraint_name for fk in fks)
    except Exception:
        return False


def upgrade() -> None:
    """Add CASCADE/SET NULL to FK constraints."""

    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)

    # =========================================================================
    # 1. ALERTS TABLE - patient_id (CASCADE) and acknowledged_by (SET NULL)
    # =========================================================================
    print("[INFO] Processing alerts table...")

    # alerts.patient_id -> patients.id with CASCADE
    patient_fk = get_existing_constraint_name(inspector, "alerts", "patient_id")
    if patient_fk:
        print(f"  [DROP] {patient_fk}")
        op.drop_constraint(patient_fk, "alerts", type_="foreignkey")

    op.create_foreign_key(
        "alerts_patient_id_fkey",
        "alerts",
        "patients",
        ["patient_id"],
        ["id"],
        ondelete="CASCADE",
    )
    print("  [CREATE] alerts_patient_id_fkey with ON DELETE CASCADE")

    # alerts.acknowledged_by -> users.id with SET NULL
    ack_fk = get_existing_constraint_name(inspector, "alerts", "acknowledged_by")
    if ack_fk:
        print(f"  [DROP] {ack_fk}")
        op.drop_constraint(ack_fk, "alerts", type_="foreignkey")

    op.create_foreign_key(
        "alerts_acknowledged_by_fkey",
        "alerts",
        "users",
        ["acknowledged_by"],
        ["id"],
        ondelete="SET NULL",
    )
    print("  [CREATE] alerts_acknowledged_by_fkey with ON DELETE SET NULL")

    # =========================================================================
    # 2. MEDICAL_REPORTS TABLE - patient_id (CASCADE) and generated_by (SET NULL)
    # =========================================================================
    print("[INFO] Processing medical_reports table...")

    # medical_reports.patient_id -> patients.id with CASCADE
    mr_patient_fk = get_existing_constraint_name(inspector, "medical_reports", "patient_id")
    if mr_patient_fk:
        print(f"  [DROP] {mr_patient_fk}")
        op.drop_constraint(mr_patient_fk, "medical_reports", type_="foreignkey")

    op.create_foreign_key(
        "medical_reports_patient_id_fkey",
        "medical_reports",
        "patients",
        ["patient_id"],
        ["id"],
        ondelete="CASCADE",
    )
    print("  [CREATE] medical_reports_patient_id_fkey with ON DELETE CASCADE")

    # medical_reports.generated_by -> users.id with SET NULL
    mr_gen_fk = get_existing_constraint_name(inspector, "medical_reports", "generated_by")
    if mr_gen_fk:
        print(f"  [DROP] {mr_gen_fk}")
        op.drop_constraint(mr_gen_fk, "medical_reports", type_="foreignkey")

    op.create_foreign_key(
        "medical_reports_generated_by_fkey",
        "medical_reports",
        "users",
        ["generated_by"],
        ["id"],
        ondelete="SET NULL",
    )
    print("  [CREATE] medical_reports_generated_by_fkey with ON DELETE SET NULL")

    # =========================================================================
    # 3. REPORTS TABLE - patient_id (CASCADE)
    # =========================================================================
    print("[INFO] Processing reports table...")

    # reports.patient_id -> patients.id with CASCADE
    rpt_patient_fk = get_existing_constraint_name(inspector, "reports", "patient_id")
    if rpt_patient_fk:
        print(f"  [DROP] {rpt_patient_fk}")
        op.drop_constraint(rpt_patient_fk, "reports", type_="foreignkey")

    op.create_foreign_key(
        "reports_patient_id_fkey",
        "reports",
        "patients",
        ["patient_id"],
        ["id"],
        ondelete="CASCADE",
    )
    print("  [CREATE] reports_patient_id_fkey with ON DELETE CASCADE")

    # =========================================================================
    # 4. WEBHOOK_EVENTS TABLE - Add FK constraints for related_message_id and related_patient_id
    # Note: These columns exist as UUID but currently have no FK constraint
    # =========================================================================
    print("[INFO] Processing webhook_events table...")

    # Check if FK already exists for related_message_id
    msg_fk = get_existing_constraint_name(inspector, "webhook_events", "related_message_id")
    if not msg_fk:
        # Add FK constraint with SET NULL (allows orphan cleanup without breaking events)
        op.create_foreign_key(
            "webhook_events_related_message_id_fkey",
            "webhook_events",
            "messages",
            ["related_message_id"],
            ["id"],
            ondelete="SET NULL",
        )
        print("  [CREATE] webhook_events_related_message_id_fkey with ON DELETE SET NULL")
    else:
        print(f"  [SKIP] FK for related_message_id already exists: {msg_fk}")

    # Check if FK already exists for related_patient_id
    patient_fk = get_existing_constraint_name(inspector, "webhook_events", "related_patient_id")
    if not patient_fk:
        # Add FK constraint with SET NULL
        op.create_foreign_key(
            "webhook_events_related_patient_id_fkey",
            "webhook_events",
            "patients",
            ["related_patient_id"],
            ["id"],
            ondelete="SET NULL",
        )
        print("  [CREATE] webhook_events_related_patient_id_fkey with ON DELETE SET NULL")
    else:
        print(f"  [SKIP] FK for related_patient_id already exists: {patient_fk}")

    print("[OK] Migration completed successfully")


def downgrade() -> None:
    """Remove CASCADE/SET NULL and restore original FK constraints."""

    from sqlalchemy import inspect
    conn = op.get_bind()
    inspector = inspect(conn)

    # =========================================================================
    # 4. WEBHOOK_EVENTS - Remove FK constraints (they didn't exist before)
    # =========================================================================
    print("[INFO] Reverting webhook_events table...")

    if constraint_exists(inspector, "webhook_events", "webhook_events_related_patient_id_fkey"):
        op.drop_constraint("webhook_events_related_patient_id_fkey", "webhook_events", type_="foreignkey")
        print("  [DROP] webhook_events_related_patient_id_fkey")

    if constraint_exists(inspector, "webhook_events", "webhook_events_related_message_id_fkey"):
        op.drop_constraint("webhook_events_related_message_id_fkey", "webhook_events", type_="foreignkey")
        print("  [DROP] webhook_events_related_message_id_fkey")

    # =========================================================================
    # 3. REPORTS - Restore FK without CASCADE
    # =========================================================================
    print("[INFO] Reverting reports table...")

    op.drop_constraint("reports_patient_id_fkey", "reports", type_="foreignkey")
    op.create_foreign_key(
        "reports_patient_id_fkey",
        "reports",
        "patients",
        ["patient_id"],
        ["id"],
    )
    print("  [RESTORE] reports_patient_id_fkey without ON DELETE")

    # =========================================================================
    # 2. MEDICAL_REPORTS - Restore FKs without CASCADE/SET NULL
    # =========================================================================
    print("[INFO] Reverting medical_reports table...")

    op.drop_constraint("medical_reports_generated_by_fkey", "medical_reports", type_="foreignkey")
    op.create_foreign_key(
        "medical_reports_generated_by_fkey",
        "medical_reports",
        "users",
        ["generated_by"],
        ["id"],
    )
    print("  [RESTORE] medical_reports_generated_by_fkey without ON DELETE")

    op.drop_constraint("medical_reports_patient_id_fkey", "medical_reports", type_="foreignkey")
    op.create_foreign_key(
        "medical_reports_patient_id_fkey",
        "medical_reports",
        "patients",
        ["patient_id"],
        ["id"],
    )
    print("  [RESTORE] medical_reports_patient_id_fkey without ON DELETE")

    # =========================================================================
    # 1. ALERTS - Restore FKs without CASCADE/SET NULL
    # =========================================================================
    print("[INFO] Reverting alerts table...")

    op.drop_constraint("alerts_acknowledged_by_fkey", "alerts", type_="foreignkey")
    op.create_foreign_key(
        "alerts_acknowledged_by_fkey",
        "alerts",
        "users",
        ["acknowledged_by"],
        ["id"],
    )
    print("  [RESTORE] alerts_acknowledged_by_fkey without ON DELETE")

    op.drop_constraint("alerts_patient_id_fkey", "alerts", type_="foreignkey")
    op.create_foreign_key(
        "alerts_patient_id_fkey",
        "alerts",
        "patients",
        ["patient_id"],
        ["id"],
    )
    print("  [RESTORE] alerts_patient_id_fkey without ON DELETE")

    print("[OK] Downgrade completed successfully")
