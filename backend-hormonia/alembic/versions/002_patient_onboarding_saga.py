"""Add patient_onboarding_saga table

Revision ID: 002_patient_onboarding_saga
Revises: 001_add_idempotency_key
Create Date: 2025-01-15 10:00:00.000000

Sprint 1 - Transação Distribuída no Cadastro

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
revision = "002_patient_onboarding_saga"
down_revision = "001_add_idempotency_key"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add patient_onboarding_saga table for saga pattern implementation."""

    # Check if saga_status enum already exists
    conn = op.get_bind()
    result = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM pg_type WHERE typname = 'saga_status'
        )
    """))
    enum_exists = result.scalar()

    # Define saga_status enum (will be used in table creation)
    saga_status = postgresql.ENUM(
        "STARTED",
        "STEP_1_PATIENT_CREATED",
        "STEP_2_FIREBASE_USER_CREATED",
        "STEP_3_FLOW_INITIALIZED",
        "STEP_4_MESSAGE_SENT",
        "COMPLETED",
        "FAILED",
        "COMPENSATING",
        "COMPENSATED",
        "RETRY_SCHEDULED",
        name="saga_status",
        create_type=False,  # We'll create it manually if needed
    )

    # Create enum only if it doesn't exist
    if not enum_exists:
        saga_status.create(op.get_bind(), checkfirst=False)

    # Create patient_onboarding_saga table
    op.create_table(
        "patient_onboarding_saga",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("patient_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("doctor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", saga_status, nullable=False, server_default="STARTED"),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("patient_data", postgresql.JSONB, nullable=False),
        sa.Column(
            "execution_log", postgresql.JSONB, nullable=False, server_default="[]"
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("error_type", sa.String(255), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Create indexes
    op.create_index(
        "idx_patient_onboarding_saga_patient_id",
        "patient_onboarding_saga",
        ["patient_id"],
    )

    op.create_index(
        "idx_patient_onboarding_saga_status",
        "patient_onboarding_saga",
        ["status"],
    )

    op.create_index(
        "idx_patient_onboarding_saga_doctor_id",
        "patient_onboarding_saga",
        ["doctor_id"],
    )

    op.create_index(
        "idx_patient_onboarding_saga_retry",
        "patient_onboarding_saga",
        ["status", "next_retry_at"],
        postgresql_where=sa.text("status = 'RETRY_SCHEDULED'"),
    )

    # Add foreign keys
    op.create_foreign_key(
        "fk_patient_onboarding_saga_patient_id",
        "patient_onboarding_saga",
        "patients",
        ["patient_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_foreign_key(
        "fk_patient_onboarding_saga_doctor_id",
        "patient_onboarding_saga",
        "users",
        ["doctor_id"],
        ["id"],
        ondelete="CASCADE",
    )

    print("[OK] Tabela patient_onboarding_saga criada com sucesso")


def downgrade() -> None:
    """Remove patient_onboarding_saga table."""

    print("Removendo tabela patient_onboarding_saga...")

    # Drop foreign keys
    op.drop_constraint(
        "fk_patient_onboarding_saga_doctor_id",
        "patient_onboarding_saga",
        type_="foreignkey",
    )

    op.drop_constraint(
        "fk_patient_onboarding_saga_patient_id",
        "patient_onboarding_saga",
        type_="foreignkey",
    )

    # Drop indexes
    op.drop_index("idx_patient_onboarding_saga_retry", "patient_onboarding_saga")
    op.drop_index("idx_patient_onboarding_saga_doctor_id", "patient_onboarding_saga")
    op.drop_index("idx_patient_onboarding_saga_status", "patient_onboarding_saga")
    op.drop_index("idx_patient_onboarding_saga_patient_id", "patient_onboarding_saga")

    # Drop table
    op.drop_table("patient_onboarding_saga")

    # Drop enum
    saga_status = postgresql.ENUM(name="saga_status")
    saga_status.drop(op.get_bind(), checkfirst=True)

    print("[OK] Rollback completado com sucesso")
