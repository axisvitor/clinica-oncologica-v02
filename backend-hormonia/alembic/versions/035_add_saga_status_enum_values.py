"""Add missing saga_status enum values

Revision ID: 035_add_saga_status_enum_values
Revises: 034_add_performance_indexes
Create Date: 2025-12-25 17:10:00.000000

Adds IN_PROGRESS and COMPLETED_WITH_WARNINGS to saga_status enum
to match the Python model definition in app/models/patient_onboarding_saga.py

Bug Fix: The Python model had these enum values but the database was missing them,
causing queries with these values to fail with:
    "invalid input value for enum saga_status: 'IN_PROGRESS'"

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

# revision identifiers, used by Alembic.
revision = "035_add_saga_status_enum_values"
down_revision = "034_add_performance_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add IN_PROGRESS and COMPLETED_WITH_WARNINGS to saga_status enum."""

    conn = op.get_bind()

    # Check which values already exist
    result = conn.execute(sa.text("""
        SELECT enumlabel FROM pg_enum
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'saga_status')
    """))
    existing_values = {row[0] for row in result.fetchall()}

    print(f"[INFO] Existing saga_status values: {existing_values}")

    # Add IN_PROGRESS after STARTED (if not exists)
    # Note: ALTER TYPE ADD VALUE cannot run inside a transaction block,
    # so we use IF NOT EXISTS which is idempotent
    if "IN_PROGRESS" not in existing_values:
        op.execute(sa.text("""
            ALTER TYPE saga_status ADD VALUE IF NOT EXISTS 'IN_PROGRESS' AFTER 'STARTED'
        """))
        print("[OK] Added IN_PROGRESS to saga_status enum")
    else:
        print("[SKIP] IN_PROGRESS already exists")

    # Add COMPLETED_WITH_WARNINGS after COMPLETED (if not exists)
    if "COMPLETED_WITH_WARNINGS" not in existing_values:
        op.execute(sa.text("""
            ALTER TYPE saga_status ADD VALUE IF NOT EXISTS 'COMPLETED_WITH_WARNINGS' AFTER 'COMPLETED'
        """))
        print("[OK] Added COMPLETED_WITH_WARNINGS to saga_status enum")
    else:
        print("[SKIP] COMPLETED_WITH_WARNINGS already exists")

    # Verify final state
    result = conn.execute(sa.text("""
        SELECT enumlabel FROM pg_enum
        WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'saga_status')
        ORDER BY enumsortorder
    """))
    final_values = [row[0] for row in result.fetchall()]
    print(f"[OK] Final saga_status values: {final_values}")


def downgrade() -> None:
    """
    Note: PostgreSQL does not support removing enum values directly.
    To downgrade, you would need to:
    1. Create a new enum without the values
    2. Update all columns using the old enum
    3. Drop the old enum
    4. Rename the new enum

    Since IN_PROGRESS and COMPLETED_WITH_WARNINGS are additive and don't break
    existing functionality, we leave this as a no-op.
    """
    print("[WARN] Cannot remove enum values in PostgreSQL. Migration is not reversible.")
    print("[INFO] Values IN_PROGRESS and COMPLETED_WITH_WARNINGS will remain in the enum.")
    print("[INFO] This is safe as existing code handles these values gracefully.")
