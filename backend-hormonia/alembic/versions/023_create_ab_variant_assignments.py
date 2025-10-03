"""Create ab_variant_assignments table for tracking user assignments to experiment variants

Revision ID: 023_ab_variant_assignments
Revises: 022_ab_experiments
Create Date: 2025-09-29 19:35:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '023_ab_variant_assignments'
down_revision = '022_ab_experiments'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create ab_variant_assignments table to track which users are assigned
    to which experiment variants.
    """
    # Create ab_variant_assignments table
    op.create_table(
        'ab_variant_assignments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('patient_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('variant_name', sa.String(100), nullable=False),
        sa.Column('variant_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('first_exposure_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_exposure_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('exposure_count', sa.Integer(), default=0, nullable=False),
        sa.Column('converted', sa.Boolean(), default=False, nullable=False),
        sa.Column('converted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['experiment_id'], ['ab_experiments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.CheckConstraint('user_id IS NOT NULL OR patient_id IS NOT NULL', name='check_has_subject')
    )

    # Add unique constraint to prevent duplicate assignments
    op.create_unique_constraint(
        'uq_ab_variant_user_experiment',
        'ab_variant_assignments',
        ['experiment_id', 'user_id'],
        postgresql_where=sa.text('user_id IS NOT NULL')
    )

    op.create_unique_constraint(
        'uq_ab_variant_patient_experiment',
        'ab_variant_assignments',
        ['experiment_id', 'patient_id'],
        postgresql_where=sa.text('patient_id IS NOT NULL')
    )

    # Add comments
    op.execute("""
        COMMENT ON TABLE ab_variant_assignments IS
        'Tracks which users/patients are assigned to which experiment variants';
    """)

    op.execute("""
        COMMENT ON COLUMN ab_variant_assignments.exposure_count IS
        'Number of times the user was exposed to this variant';
    """)


def downgrade():
    """
    Drop ab_variant_assignments table.
    """
    op.drop_constraint('uq_ab_variant_patient_experiment', 'ab_variant_assignments', type_='unique')
    op.drop_constraint('uq_ab_variant_user_experiment', 'ab_variant_assignments', type_='unique')
    op.drop_table('ab_variant_assignments')