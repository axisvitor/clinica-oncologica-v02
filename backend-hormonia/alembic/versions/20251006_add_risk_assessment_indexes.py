"""Add indexes for risk assessment performance optimization

Revision ID: 20251006_add_risk_assessment_indexes
Revises: 20251006_add_user_sync_log_updated_at
Create Date: 2025-10-06 15:00:00.000000

This migration adds database indexes to optimize the physician risk assessment
endpoint performance. Target: < 200ms for 50 patients.

Indexes added:
1. idx_patients_physician_id - For filtering patients by physician
2. idx_alerts_patient_resolved_created - Composite index for alert queries
3. idx_alerts_status_created - For filtering active alerts

Expected performance improvement: 2-5x faster queries
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251006_add_risk_assessment_indexes'
down_revision = '20251006_add_user_sync_log_updated_at'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add performance indexes for risk assessment queries."""

    # Index 1: Patient lookup by physician
    # Used in: SELECT * FROM patients WHERE doctor_id = ?
    # Expected impact: 10-50x faster for physician's patient list
    op.create_index(
        'idx_patients_physician_id',
        'patients',
        ['doctor_id'],
        unique=False
    )

    # Index 2: Alert filtering by patient, status, and creation date
    # Used in: SELECT * FROM alerts WHERE patient_id = ? AND status IN ('pending', 'active') AND created_at >= ?
    # Composite index for optimal query performance
    # Expected impact: 5-20x faster for alert queries
    op.create_index(
        'idx_alerts_patient_status_created',
        'alerts',
        ['patient_id', 'status', 'created_at'],
        unique=False
    )

    # Index 3: Alert filtering by status and creation (for global queries)
    # Used in: SELECT * FROM alerts WHERE status IN ('pending', 'active') AND created_at >= ?
    # Expected impact: 3-10x faster for global alert queries
    op.create_index(
        'idx_alerts_status_created',
        'alerts',
        ['status', 'created_at'],
        unique=False
    )

    # Index 4: Alert severity ordering (optional, for priority sorting)
    # Used in: ORDER BY severity DESC, created_at DESC
    # Expected impact: Faster sorting of alerts by severity
    op.create_index(
        'idx_alerts_severity_created',
        'alerts',
        ['severity', 'created_at'],
        unique=False
    )


def downgrade() -> None:
    """Remove risk assessment performance indexes."""

    op.drop_index('idx_alerts_severity_created', table_name='alerts')
    op.drop_index('idx_alerts_status_created', table_name='alerts')
    op.drop_index('idx_alerts_patient_status_created', table_name='alerts')
    op.drop_index('idx_patients_physician_id', table_name='patients')
