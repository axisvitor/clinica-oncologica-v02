"""Add comprehensive performance indexes for A/B testing tables

Revision ID: 028_ab_testing_indexes
Revises: 027_ab_experiment_monitoring
Create Date: 2025-09-29 19:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '028_ab_testing_indexes'
down_revision = '027_ab_experiment_monitoring'
branch_labels = None
depends_on = None


def upgrade():
    """
    Add comprehensive indexes across all A/B testing tables for optimal performance.
    """
    # ========== ab_experiments indexes ==========
    op.create_index(
        'idx_ab_experiments_status',
        'ab_experiments',
        ['status', 'start_date'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_ab_experiments_type_status',
        'ab_experiments',
        ['experiment_type', 'status'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_ab_experiments_dates',
        'ab_experiments',
        ['start_date', 'end_date'],
        postgresql_using='btree',
        postgresql_where=sa.text("status = 'active'")
    )

    op.create_index(
        'idx_ab_experiments_created_by',
        'ab_experiments',
        ['created_by'],
        postgresql_using='btree'
    )

    # ========== ab_variant_assignments indexes ==========
    op.create_index(
        'idx_ab_variant_assignments_experiment',
        'ab_variant_assignments',
        ['experiment_id', 'variant_name'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_ab_variant_assignments_user',
        'ab_variant_assignments',
        ['user_id'],
        postgresql_using='btree',
        postgresql_where=sa.text('user_id IS NOT NULL')
    )

    op.create_index(
        'idx_ab_variant_assignments_patient',
        'ab_variant_assignments',
        ['patient_id'],
        postgresql_using='btree',
        postgresql_where=sa.text('patient_id IS NOT NULL')
    )

    op.create_index(
        'idx_ab_variant_assignments_converted',
        'ab_variant_assignments',
        ['experiment_id', 'converted'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_ab_variant_assignments_exposure',
        'ab_variant_assignments',
        ['experiment_id', 'last_exposure_at'],
        postgresql_using='btree'
    )

    # ========== ab_experiment_metrics indexes ==========
    op.create_index(
        'idx_ab_experiment_metrics_experiment_variant',
        'ab_experiment_metrics',
        ['experiment_id', 'variant_name', 'metric_name'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_ab_experiment_metrics_timestamp',
        'ab_experiment_metrics',
        ['experiment_id', 'timestamp'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_ab_experiment_metrics_type',
        'ab_experiment_metrics',
        ['metric_type', 'timestamp'],
        postgresql_using='btree'
    )

    # ========== ab_experiment_results indexes ==========
    op.create_index(
        'idx_ab_experiment_results_decision',
        'ab_experiment_results',
        ['decision', 'analyzed_at'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_ab_experiment_results_winner',
        'ab_experiment_results',
        ['winner_variant'],
        postgresql_using='btree',
        postgresql_where=sa.text('winner_variant IS NOT NULL')
    )

    op.create_index(
        'idx_ab_experiment_results_analyzed_by',
        'ab_experiment_results',
        ['analyzed_by'],
        postgresql_using='btree'
    )

    # ========== ab_experiment_audit indexes ==========
    op.create_index(
        'idx_ab_experiment_audit_experiment',
        'ab_experiment_audit',
        ['experiment_id', 'timestamp'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_ab_experiment_audit_action',
        'ab_experiment_audit',
        ['action', 'timestamp'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_ab_experiment_audit_changed_by',
        'ab_experiment_audit',
        ['changed_by', 'timestamp'],
        postgresql_using='btree'
    )

    # ========== ab_experiment_monitoring indexes ==========
    op.create_index(
        'idx_ab_experiment_monitoring_experiment',
        'ab_experiment_monitoring',
        ['experiment_id', 'check_timestamp'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_ab_experiment_monitoring_health',
        'ab_experiment_monitoring',
        ['health_status', 'check_timestamp'],
        postgresql_using='btree'
    )

    op.create_index(
        'idx_ab_experiment_monitoring_issues',
        'ab_experiment_monitoring',
        ['experiment_id'],
        postgresql_using='btree',
        postgresql_where=sa.text("health_status IN ('warning', 'critical', 'degraded')")
    )

    op.create_index(
        'idx_ab_experiment_monitoring_latest',
        'ab_experiment_monitoring',
        ['experiment_id', 'check_timestamp'],
        postgresql_using='btree',
        unique=False
    )


def downgrade():
    """
    Drop all A/B testing performance indexes.
    """
    # ab_experiment_monitoring
    op.drop_index('idx_ab_experiment_monitoring_latest', table_name='ab_experiment_monitoring')
    op.drop_index('idx_ab_experiment_monitoring_issues', table_name='ab_experiment_monitoring')
    op.drop_index('idx_ab_experiment_monitoring_health', table_name='ab_experiment_monitoring')
    op.drop_index('idx_ab_experiment_monitoring_experiment', table_name='ab_experiment_monitoring')

    # ab_experiment_audit
    op.drop_index('idx_ab_experiment_audit_changed_by', table_name='ab_experiment_audit')
    op.drop_index('idx_ab_experiment_audit_action', table_name='ab_experiment_audit')
    op.drop_index('idx_ab_experiment_audit_experiment', table_name='ab_experiment_audit')

    # ab_experiment_results
    op.drop_index('idx_ab_experiment_results_analyzed_by', table_name='ab_experiment_results')
    op.drop_index('idx_ab_experiment_results_winner', table_name='ab_experiment_results')
    op.drop_index('idx_ab_experiment_results_decision', table_name='ab_experiment_results')

    # ab_experiment_metrics
    op.drop_index('idx_ab_experiment_metrics_type', table_name='ab_experiment_metrics')
    op.drop_index('idx_ab_experiment_metrics_timestamp', table_name='ab_experiment_metrics')
    op.drop_index('idx_ab_experiment_metrics_experiment_variant', table_name='ab_experiment_metrics')

    # ab_variant_assignments
    op.drop_index('idx_ab_variant_assignments_exposure', table_name='ab_variant_assignments')
    op.drop_index('idx_ab_variant_assignments_converted', table_name='ab_variant_assignments')
    op.drop_index('idx_ab_variant_assignments_patient', table_name='ab_variant_assignments')
    op.drop_index('idx_ab_variant_assignments_user', table_name='ab_variant_assignments')
    op.drop_index('idx_ab_variant_assignments_experiment', table_name='ab_variant_assignments')

    # ab_experiments
    op.drop_index('idx_ab_experiments_created_by', table_name='ab_experiments')
    op.drop_index('idx_ab_experiments_dates', table_name='ab_experiments')
    op.drop_index('idx_ab_experiments_type_status', table_name='ab_experiments')
    op.drop_index('idx_ab_experiments_status', table_name='ab_experiments')