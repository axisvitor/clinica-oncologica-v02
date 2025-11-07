"""Add last_retry_at field to patient_onboarding_saga

Revision ID: 003_add_last_retry_at
Revises: 002_patient_onboarding_saga
Create Date: 2025-11-07 10:00:00.000000

Sprint 1 - Fix: Add missing last_retry_at field for retry tracking
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "003_add_last_retry_at"
down_revision = "002_patient_onboarding_saga"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add last_retry_at column to track when last retry attempt was made."""

    # Add last_retry_at column
    op.add_column(
        "patient_onboarding_saga",
        sa.Column("last_retry_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create index for efficient retry queries
    op.create_index(
        "idx_patient_onboarding_saga_last_retry",
        "patient_onboarding_saga",
        ["last_retry_at"],
    )

    print("[OK] Campo last_retry_at adicionado com sucesso à tabela patient_onboarding_saga")


def downgrade() -> None:
    """Remove last_retry_at column."""

    # Drop index
    op.drop_index("idx_patient_onboarding_saga_last_retry", "patient_onboarding_saga")

    # Drop column
    op.drop_column("patient_onboarding_saga", "last_retry_at")

    print("[OK] Rollback: Campo last_retry_at removido")
