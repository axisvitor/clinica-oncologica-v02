"""Create patient_flow_overrides table for per-patient flow day overrides.

Revision ID: m012_s01_patient_flow_overrides
Revises: m011_s01_patient_flow_states_index
Create Date: 2026-03-17 17:00:00.000000

Stores per-patient day-level overrides that are merged at query time with the
global flow template.  Each row replaces the global template configuration for
a single (patient_flow_state, day_number) pair.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "m012_s01_patient_flow_overrides"
down_revision = "m011_s01_patient_flow_states_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_flow_overrides",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "patient_flow_state_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patient_flow_states.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "message_type",
            sa.String(50),
            nullable=False,
            server_default="question",
        ),
        sa.Column(
            "expects_response",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "skip",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_by",
            sa.dialects.postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
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
        sa.UniqueConstraint(
            "patient_flow_state_id",
            "day_number",
            name="uq_pfo_state_day",
        ),
    )

    op.create_index(
        "idx_pfo_state_id",
        "patient_flow_overrides",
        ["patient_flow_state_id"],
    )


def downgrade() -> None:
    op.drop_table("patient_flow_overrides")
