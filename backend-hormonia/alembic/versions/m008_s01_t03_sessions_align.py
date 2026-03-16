"""Align sessions table with Session model — add missing columns.

Revision ID: m008_s01_t03_sessions_align
Revises: m007_s04_t02_patient_flow_responses
Create Date: 2026-03-16 10:30:00.000000

The Session model expects columns (session_token, refresh_token, ip_address,
user_agent, expires_at, revoked_at, revocation_reason, device_*, location,
is_suspicious, risk_score, session_metadata) that were never added to the
sessions table. This migration adds them so login can persist session rows.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "m008_s01_t03_sessions_align"
down_revision = "m007_s04_t02_patient_flow_responses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Core session fields
    op.add_column("sessions", sa.Column("session_token", sa.String(500), nullable=True))
    op.add_column("sessions", sa.Column("refresh_token", sa.String(500), nullable=True))
    op.add_column("sessions", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))

    # Network information
    op.add_column("sessions", sa.Column("ip_address", sa.String(45), nullable=True))
    op.add_column("sessions", sa.Column("user_agent", sa.Text(), nullable=True))

    # Device information
    op.add_column("sessions", sa.Column("device_id", sa.String(200), nullable=True))
    op.add_column("sessions", sa.Column("device_name", sa.String(200), nullable=True))
    op.add_column("sessions", sa.Column("device_type", sa.String(50), nullable=True))

    # Geolocation
    op.add_column("sessions", sa.Column("location", JSONB(), nullable=True))

    # Revocation
    op.add_column("sessions", sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sessions", sa.Column("revocation_reason", sa.Text(), nullable=True))

    # Security
    op.add_column("sessions", sa.Column("is_suspicious", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("sessions", sa.Column("risk_score", sa.String(50), nullable=True))

    # Metadata
    op.add_column("sessions", sa.Column("session_metadata", JSONB(), nullable=True))

    # Backfill session_token for any existing rows, then set NOT NULL
    op.execute("UPDATE sessions SET session_token = gen_random_uuid()::text WHERE session_token IS NULL")
    op.alter_column("sessions", "session_token", nullable=False)

    # Set expires_at NOT NULL with default for existing rows
    op.execute(
        "UPDATE sessions SET expires_at = created_at + interval '5 days' WHERE expires_at IS NULL"
    )
    op.alter_column("sessions", "expires_at", nullable=False)

    # Indexes
    op.create_index("ix_sessions_session_token", "sessions", ["session_token"], unique=True)
    op.create_index("ix_sessions_refresh_token", "sessions", ["refresh_token"], unique=True)
    op.create_index("ix_sessions_device_id", "sessions", ["device_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
    op.create_index("ix_sessions_is_suspicious", "sessions", ["is_suspicious"])


def downgrade() -> None:
    op.drop_index("ix_sessions_is_suspicious", table_name="sessions")
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_index("ix_sessions_device_id", table_name="sessions")
    op.drop_index("ix_sessions_refresh_token", table_name="sessions")
    op.drop_index("ix_sessions_session_token", table_name="sessions")

    op.drop_column("sessions", "session_metadata")
    op.drop_column("sessions", "risk_score")
    op.drop_column("sessions", "is_suspicious")
    op.drop_column("sessions", "revocation_reason")
    op.drop_column("sessions", "revoked_at")
    op.drop_column("sessions", "location")
    op.drop_column("sessions", "device_type")
    op.drop_column("sessions", "device_name")
    op.drop_column("sessions", "device_id")
    op.drop_column("sessions", "user_agent")
    op.drop_column("sessions", "ip_address")
    op.drop_column("sessions", "expires_at")
    op.drop_column("sessions", "refresh_token")
    op.drop_column("sessions", "session_token")
