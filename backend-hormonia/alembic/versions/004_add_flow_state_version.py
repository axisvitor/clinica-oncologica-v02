"""Add version field to patient_flow_states for optimistic locking

Revision ID: 004_add_flow_state_version
Revises: 003_add_last_retry_at
Create Date: 2025-11-07 11:00:00.000000

Sprint 1 - Fix: Add optimistic locking to prevent race conditions in flow state updates

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
revision = "004_add_flow_state_version"
down_revision = "003_add_last_retry_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add version column for optimistic locking."""

    # Add version column with default value 0
    op.add_column(
        "patient_flow_states",
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
    )

    # Create index for efficient version queries
    op.create_index(
        "idx_patient_flow_states_version",
        "patient_flow_states",
        ["id", "version"],
    )

    print("[OK] Campo version adicionado com sucesso à tabela patient_flow_states")


def downgrade() -> None:
    """Remove version column."""

    # Drop index
    op.drop_index("idx_patient_flow_states_version", "patient_flow_states")

    # Drop column
    op.drop_column("patient_flow_states", "version")

    print("[OK] Rollback: Campo version removido")
