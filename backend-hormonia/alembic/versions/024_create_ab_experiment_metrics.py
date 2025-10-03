"""Create ab_experiment_metrics table for tracking experiment performance

Revision ID: 024_ab_experiment_metrics
Revises: 023_ab_variant_assignments
Create Date: 2025-09-29 19:36:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '024_ab_experiment_metrics'
down_revision = '023_ab_variant_assignments'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create ab_experiment_metrics table to store detailed metrics
    for each experiment variant.
    """
    # Create ab_experiment_metrics table
    op.create_table(
        'ab_experiment_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('variant_name', sa.String(100), nullable=False),
        sa.Column('metric_name', sa.String(100), nullable=False),
        sa.Column('metric_type', sa.String(50), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('sample_size', sa.Integer(), nullable=False),
        sa.Column('confidence_interval_lower', sa.Float(), nullable=True),
        sa.Column('confidence_interval_upper', sa.Float(), nullable=True),
        sa.Column('standard_deviation', sa.Float(), nullable=True),
        sa.Column('standard_error', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ondelete='CASCADE'),
        sa.CheckConstraint('sample_size >= 0', name='check_sample_size')
    )

    # Add comments
    op.execute("""
        COMMENT ON TABLE ab_experiment_metrics IS
        'Stores calculated metrics for each experiment variant over time';
    """)

    op.execute("""
        COMMENT ON COLUMN ab_experiment_metrics.metric_type IS
        'Type of metric: conversion_rate, click_through_rate, engagement_score, etc.';
    """)


def downgrade():
    """
    Drop ab_experiment_metrics table.
    """
    op.drop_table('ab_experiment_metrics')