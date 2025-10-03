"""Create ab_experiments table for A/B testing framework

Revision ID: 022_ab_experiments
Revises: 021_webhook_events_indexes
Create Date: 2025-09-29 19:34:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '022_ab_experiments'
down_revision = '021_webhook_events_indexes'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create ab_experiments table for managing A/B tests on messaging templates,
    flows, and other features.
    """
    # Create enum for experiment status
    op.execute("""
        CREATE TYPE experiment_status_type AS ENUM (
            'draft',
            'active',
            'paused',
            'completed',
            'archived'
        );
    """)

    # Create ab_experiments table
    op.create_table(
        'ab_experiments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('hypothesis', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('draft', 'active', 'paused', 'completed', 'archived', name='experiment_status_type'), nullable=False, default='draft'),
        sa.Column('experiment_type', sa.String(50), nullable=False),
        sa.Column('target_metric', sa.String(100), nullable=False),
        sa.Column('success_criteria', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('traffic_allocation', sa.Float(), nullable=False, default=1.0),
        sa.Column('min_sample_size', sa.Integer(), nullable=False, default=100),
        sa.Column('confidence_level', sa.Float(), nullable=False, default=0.95),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='RESTRICT'),
        sa.CheckConstraint('traffic_allocation > 0 AND traffic_allocation <= 1', name='check_traffic_allocation'),
        sa.CheckConstraint('confidence_level > 0 AND confidence_level < 1', name='check_confidence_level'),
        sa.CheckConstraint('min_sample_size > 0', name='check_min_sample_size')
    )

    # Add unique constraint for active experiment names
    op.create_unique_constraint(
        'uq_ab_experiments_active_name',
        'ab_experiments',
        ['name'],
        postgresql_where=sa.text("status = 'active'")
    )

    # Add comments
    op.execute("""
        COMMENT ON TABLE ab_experiments IS
        'A/B testing experiments for optimizing messaging templates and flows';
    """)

    op.execute("""
        COMMENT ON COLUMN ab_experiments.traffic_allocation IS
        'Percentage of traffic allocated to this experiment (0.0-1.0)';
    """)


def downgrade():
    """
    Drop ab_experiments table and related enum.
    """
    op.drop_constraint('uq_ab_experiments_active_name', 'ab_experiments', type_='unique')
    op.drop_table('ab_experiments')
    op.execute("DROP TYPE IF EXISTS experiment_status_type CASCADE;")