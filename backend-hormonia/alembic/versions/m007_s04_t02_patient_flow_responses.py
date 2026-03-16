"""Create patient_flow_responses table for structured response storage.

Revision ID: m007_s04_t02_patient_flow_responses
Revises: m006_s02_t03_drop_users_firebase_residue
Create Date: 2026-03-16 00:20:00.000000

Stores every patient free-text response with flow context (day, message index,
timestamps) so responses are queryable by period without parsing step_data JSONB.
Dual-written alongside existing step_data in process_patient_response().
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "m007_s04_t02_patient_flow_responses"
down_revision = "m006_s02_t03_drop_users_firebase_residue"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "patient_flow_responses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "flow_state_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patient_flow_states.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "patient_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("patients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("day_number", sa.Integer(), nullable=True),
        sa.Column("message_index", sa.Integer(), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=False),
        sa.Column(
            "responded_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column("prompt_message_id", sa.String(255), nullable=True),
        sa.Column("response_message_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_pfr_patient_id", "patient_flow_responses", ["patient_id"])
    op.create_index("ix_pfr_flow_state_id", "patient_flow_responses", ["flow_state_id"])
    op.create_index("ix_pfr_responded_at", "patient_flow_responses", ["responded_at"])
    op.create_index(
        "ix_pfr_patient_responded",
        "patient_flow_responses",
        ["patient_id", "responded_at"],
    )


def downgrade() -> None:
    op.drop_table("patient_flow_responses")
