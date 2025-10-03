"""Create ab_experiment_results table for storing final experiment outcomes

Revision ID: 025_ab_experiment_results
Revises: 024_ab_experiment_metrics
Create Date: 2025-09-29 19:37:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '025_ab_experiment_results'
down_revision = '024_ab_experiment_metrics'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create ab_experiment_results table to store final results and
    statistical analysis of completed experiments.
    """
    # Create enum for result decision
    op.execute("""
        CREATE TYPE experiment_decision_type AS ENUM (
            'winner_found',
            'no_significant_difference',
            'inconclusive',
            'early_stop_success',
            'early_stop_failure'
        );
    """)

    # Create ab_experiment_results table
    op.create_table(
        'ab_experiment_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column('winner_variant', sa.String(100), nullable=True),
        sa.Column('decision', sa.Enum('winner_found', 'no_significant_difference', 'inconclusive', 'early_stop_success', 'early_stop_failure', name='experiment_decision_type'), nullable=False),
        sa.Column('statistical_significance', sa.Float(), nullable=False),
        sa.Column('p_value', sa.Float(), nullable=True),
        sa.Column('effect_size', sa.Float(), nullable=True),
        sa.Column('total_participants', sa.Integer(), nullable=False),
        sa.Column('duration_days', sa.Integer(), nullable=False),
        sa.Column('variant_performance', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('analysis_summary', sa.Text(), nullable=True),
        sa.Column('recommendations', sa.Text(), nullable=True),
        sa.Column('analyzed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['analyzed_by'], ['users.id'], ondelete='SET NULL'),
        sa.CheckConstraint('total_participants >= 0', name='check_total_participants'),
        sa.CheckConstraint('duration_days >= 0', name='check_duration_days'),
        sa.CheckConstraint('statistical_significance >= 0 AND statistical_significance <= 1', name='check_significance'),
        sa.CheckConstraint('p_value IS NULL OR (p_value >= 0 AND p_value <= 1)', name='check_p_value')
    )

    # Add comments
    op.execute("""
        COMMENT ON TABLE ab_experiment_results IS
        'Stores final statistical analysis and outcomes of completed A/B experiments';
    """)

    op.execute("""
        COMMENT ON COLUMN ab_experiment_results.variant_performance IS
        'JSON object containing detailed performance metrics for each variant';
    """)


def downgrade():
    """
    Drop ab_experiment_results table and related enum.
    """
    op.drop_table('ab_experiment_results')
    op.execute("DROP TYPE IF EXISTS experiment_decision_type CASCADE;")