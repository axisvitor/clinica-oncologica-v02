"""Add template versioning tables for flow and quiz management

Revision ID: 015_add_template_versioning_tables
Revises: add_performance_indexes
Create Date: 2025-09-27

This migration implements the template versioning refactoring plan:
1. Creates flow_kinds table to separate flow types from versions
2. Creates flow_template_versions table for version management
3. Adds template_version_id to patient_flow_states for FK tracking
4. Adds status and published_at to quiz_templates for lifecycle management
5. Creates proper indexes and constraints for performance

This allows doctors to update templates without rebuilding the entire database.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '015_add_template_versioning_tables'
down_revision = 'add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create flow_kinds table
    op.create_table('flow_kinds',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('flow_type', sa.String(100), nullable=False, unique=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('display_order', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('metadata', postgresql.JSONB(), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )

    # Create flow_template_versions table
    op.create_table('flow_template_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('kind_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('messages', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('quiz_templates', postgresql.JSONB(), nullable=True, server_default='{}'),
        sa.Column('alerts', postgresql.JSONB(), nullable=True, server_default='{}'),
        sa.Column('changelog', sa.Text(), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('approved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )

    # Add foreign key constraints
    op.create_foreign_key(
        'fk_flow_template_versions_kind_id',
        'flow_template_versions', 'flow_kinds',
        ['kind_id'], ['id'],
        ondelete='CASCADE'
    )

    # Add template_version_id column to patient_flow_states (if exists) for FK tracking
    # This column will be nullable initially during migration
    try:
        op.add_column('patient_flow_states',
            sa.Column('template_version_id', postgresql.UUID(as_uuid=True), nullable=True)
        )
        op.create_foreign_key(
            'fk_patient_flow_states_template_version',
            'patient_flow_states', 'flow_template_versions',
            ['template_version_id'], ['id'],
            ondelete='SET NULL'
        )
    except Exception:
        # Table might not exist yet or column might already exist
        pass

    # Add template_version_id column to flow_states (alternative name) for FK tracking
    try:
        op.add_column('flow_states',
            sa.Column('template_version_id', postgresql.UUID(as_uuid=True), nullable=True)
        )
        op.create_foreign_key(
            'fk_flow_states_template_version',
            'flow_states', 'flow_template_versions',
            ['template_version_id'], ['id'],
            ondelete='SET NULL'
        )
    except Exception:
        # Table might not exist yet or column might already exist
        pass

    # Add status and published_at columns to quiz_templates
    try:
        op.add_column('quiz_templates',
            sa.Column('status', sa.String(20), nullable=False, server_default='published')
        )
        op.add_column('quiz_templates',
            sa.Column('published_at', sa.DateTime(timezone=True), nullable=True)
        )
    except Exception:
        # Columns might already exist
        pass

    # Create unique constraint on flow_template_versions (kind_id, version)
    op.create_unique_constraint(
        'uq_flow_template_versions_kind_version',
        'flow_template_versions',
        ['kind_id', 'version']
    )

    # Create indexes for performance
    op.create_index('idx_flow_kinds_flow_type', 'flow_kinds', ['flow_type'])
    op.create_index('idx_flow_template_versions_kind_id', 'flow_template_versions', ['kind_id'])
    op.create_index('idx_flow_template_versions_status', 'flow_template_versions', ['status'])
    op.create_index('idx_flow_template_versions_published_at', 'flow_template_versions', ['published_at'])
    op.create_index('idx_quiz_templates_status', 'quiz_templates', ['status'])
    op.create_index('idx_quiz_templates_published_at', 'quiz_templates', ['published_at'])

    # Create triggers for updated_at columns
    op.execute("""
        CREATE TRIGGER update_flow_kinds_updated_at
        BEFORE UPDATE ON flow_kinds
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """)

    op.execute("""
        CREATE TRIGGER update_flow_template_versions_updated_at
        BEFORE UPDATE ON flow_template_versions
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """)


def downgrade() -> None:
    # Drop triggers
    op.execute("DROP TRIGGER IF EXISTS update_flow_template_versions_updated_at ON flow_template_versions")
    op.execute("DROP TRIGGER IF EXISTS update_flow_kinds_updated_at ON flow_kinds")

    # Drop indexes
    op.drop_index('idx_quiz_templates_published_at', 'quiz_templates')
    op.drop_index('idx_quiz_templates_status', 'quiz_templates')
    op.drop_index('idx_flow_template_versions_published_at', 'flow_template_versions')
    op.drop_index('idx_flow_template_versions_status', 'flow_template_versions')
    op.drop_index('idx_flow_template_versions_kind_id', 'flow_template_versions')
    op.drop_index('idx_flow_kinds_flow_type', 'flow_kinds')

    # Drop unique constraint
    op.drop_constraint('uq_flow_template_versions_kind_version', 'flow_template_versions')

    # Remove columns from quiz_templates
    try:
        op.drop_column('quiz_templates', 'published_at')
        op.drop_column('quiz_templates', 'status')
    except Exception:
        pass

    # Remove template_version_id column from flow_states
    try:
        op.drop_constraint('fk_flow_states_template_version', 'flow_states')
        op.drop_column('flow_states', 'template_version_id')
    except Exception:
        pass

    # Remove template_version_id column from patient_flow_states
    try:
        op.drop_constraint('fk_patient_flow_states_template_version', 'patient_flow_states')
        op.drop_column('patient_flow_states', 'template_version_id')
    except Exception:
        pass

    # Drop foreign key constraints
    op.drop_constraint('fk_flow_template_versions_kind_id', 'flow_template_versions')

    # Drop tables
    op.drop_table('flow_template_versions')
    op.drop_table('flow_kinds')