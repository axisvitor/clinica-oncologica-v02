"""Create ab_experiment_audit table for tracking changes to experiments

Revision ID: 026_ab_experiment_audit
Revises: 025_ab_experiment_results
Create Date: 2025-09-29 19:38:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '026_ab_experiment_audit'
down_revision = '025_ab_experiment_results'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create ab_experiment_audit table to track all changes made to experiments
    for compliance and audit purposes.
    """
    # Create enum for audit action types
    op.execute("""
        CREATE TYPE experiment_audit_action AS ENUM (
            'created',
            'updated',
            'status_changed',
            'started',
            'paused',
            'resumed',
            'completed',
            'archived',
            'variant_added',
            'variant_removed',
            'config_changed'
        );
    """)

    # Create ab_experiment_audit table
    op.create_table(
        'ab_experiment_audit',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.Enum('created', 'updated', 'status_changed', 'started', 'paused', 'resumed', 'completed', 'archived', 'variant_added', 'variant_removed', 'config_changed', name='experiment_audit_action'), nullable=False),
        sa.Column('changed_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('previous_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_state', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(255), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ondelete='RESTRICT')
    )

    # Add comments
    op.execute("""
        COMMENT ON TABLE ab_experiment_audit IS
        'Audit trail for all changes made to A/B experiments';
    """)


def downgrade():
    """
    Drop ab_experiment_audit table and related enum.
    """
    op.drop_table('ab_experiment_audit')
    op.execute("DROP TYPE IF EXISTS experiment_audit_action CASCADE;")