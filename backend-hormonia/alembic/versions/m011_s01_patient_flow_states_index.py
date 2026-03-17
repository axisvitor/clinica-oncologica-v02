"""Add composite index on patient_flow_states(patient_id, started_at DESC).

Revision ID: m011_s01_patient_flow_states_index
Revises: m008_s01_t03_sessions_align
Create Date: 2026-03-17 12:25:00.000000

The physician/patients endpoint uses a ROW_NUMBER() window function that
partitions by patient_id and orders by started_at DESC. Without a composite
index PostgreSQL falls back to sequential scan + in-memory sort per patient.
This index eliminates both for that query pattern.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "m011_s01_patient_flow_states_index"
down_revision = "m008_s01_t03_sessions_align"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_pfs_patient_started",
        "patient_flow_states",
        ["patient_id", sa.text("started_at DESC")],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("idx_pfs_patient_started", table_name="patient_flow_states")
