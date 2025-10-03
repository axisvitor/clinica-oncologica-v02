"""Create ab_experiment_monitoring table for real-time experiment health tracking

Revision ID: 027_ab_experiment_monitoring
Revises: 026_ab_experiment_audit
Create Date: 2025-09-29 19:39:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '027_ab_experiment_monitoring'
down_revision = '026_ab_experiment_audit'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create ab_experiment_monitoring table to track real-time health metrics
    and detect issues with running experiments.
    """
    # Create enum for health status
    op.execute("""
        CREATE TYPE experiment_health_status AS ENUM (
            'healthy',
            'warning',
            'critical',
            'degraded'
        );
    """)

    # Create ab_experiment_monitoring table
    op.create_table(
        'ab_experiment_monitoring',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('health_status', sa.Enum('healthy', 'warning', 'critical', 'degraded', name='experiment_health_status'), nullable=False),
        sa.Column('check_timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('sample_ratio_mismatch', sa.Boolean(), default=False, nullable=False),
        sa.Column('expected_ratio', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('actual_ratio', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('variance_detected', sa.Boolean(), default=False, nullable=False),
        sa.Column('anomaly_score', sa.Float(), nullable=True),
        sa.Column('alerts_triggered', postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column('current_participants', sa.Integer(), nullable=False),
        sa.Column('target_participants', sa.Integer(), nullable=True),
        sa.Column('days_running', sa.Integer(), nullable=False),
        sa.Column('estimated_days_remaining', sa.Integer(), nullable=True),
        sa.Column('variant_stats', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('issues_detected', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('recommendations', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ondelete='CASCADE'),
        sa.CheckConstraint('current_participants >= 0', name='check_current_participants'),
        sa.CheckConstraint('days_running >= 0', name='check_days_running')
    )

    # Add comments
    op.execute("""
        COMMENT ON TABLE ab_experiment_monitoring IS
        'Real-time health monitoring and issue detection for running experiments';
    """)

    op.execute("""
        COMMENT ON COLUMN ab_experiment_monitoring.sample_ratio_mismatch IS
        'True if the actual traffic allocation differs from expected';
    """)


def downgrade():
    """
    Drop ab_experiment_monitoring table and related enum.
    """
    op.drop_table('ab_experiment_monitoring')
    op.execute("DROP TYPE IF EXISTS experiment_health_status CASCADE;")