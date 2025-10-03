"""Add flow states updated index

Revision ID: 20250929_200009
Revises: 20250929_200008
Create Date: 2025-09-29

Performance optimization for recently updated flows dashboard.
Note: This is a standalone timestamp index, complementing existing composite indexes.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250929_200009'
down_revision = '20250929_200008'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create standalone index on patient_flow_states table for updated_at.

    Query pattern: Recently updated flows dashboard
    SELECT * FROM patient_flow_states ORDER BY updated_at DESC LIMIT 50

    Benefits:
    - Optimizes dashboard queries for recently updated flows
    - Supports real-time flow monitoring
    - Complements existing composite indexes for specific use cases
    - Critical for administrative overview dashboards

    Note: This migration checks if the index already exists in add_performance_indexes
    migration and only creates it if missing.
    """
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_flow_states_updated_at
        ON patient_flow_states (updated_at DESC)
    """)

    # Add comment for performance tracking
    op.execute("""
        COMMENT ON INDEX idx_flow_states_updated_at IS
        'Optimizes recently updated flows dashboard queries'
    """)


def downgrade():
    """Remove flow states updated index"""
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_flow_states_updated_at")