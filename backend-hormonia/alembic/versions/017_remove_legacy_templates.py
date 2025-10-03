"""Remove all legacy template system components

Revision ID: 017_remove_legacy_templates
Revises: 016_backfill_template_versioning_data
Create Date: 2025-09-27

This migration removes all legacy template system components:
1. Drops flow_templates table completely
2. Removes legacy columns from patient_flow_states
3. Removes legacy columns from flow_states
4. Cleans up any remaining legacy data

IMPORTANT: This is a breaking change - ensure all data has been migrated
to the new versioning system before running this migration.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '017_remove_legacy_templates'
down_revision = '016_backfill_template_versioning_data'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove all legacy template components."""
    connection = op.get_bind()

    # Step 1: Drop legacy flow_templates table
    print("Dropping legacy flow_templates table...")
    op.drop_table('flow_templates')

    # Step 2: Remove legacy columns from patient_flow_states
    try:
        print("Removing legacy columns from patient_flow_states...")
        op.drop_column('patient_flow_states', 'flow_type')
        op.drop_column('patient_flow_states', 'template_version')
    except Exception as e:
        print(f"Note: patient_flow_states legacy columns may not exist: {e}")

    # Step 3: Remove legacy columns from flow_states (if exists)
    try:
        print("Removing legacy columns from flow_states...")
        op.drop_column('flow_states', 'flow_type')
        op.drop_column('flow_states', 'template_version')
    except Exception as e:
        print(f"Note: flow_states legacy columns may not exist: {e}")

    # Step 4: Drop any legacy indexes related to flow_templates
    try:
        op.drop_index('idx_flow_templates_flow_type', table_name='flow_templates')
        op.drop_index('idx_flow_templates_is_active', table_name='flow_templates')
        op.drop_index('idx_flow_templates_version', table_name='flow_templates')
    except Exception:
        pass  # Indexes might not exist

    # Step 5: Drop legacy tables that might exist from old versions
    legacy_tables = [
        'flow_template_versions_v2',  # Old versioning attempt
        'quiz_template_versions_v2'   # Old quiz versioning attempt
    ]

    for table_name in legacy_tables:
        try:
            result = connection.execute(text(f"SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}'"))
            if result.fetchone():
                op.drop_table(table_name)
                print(f"Dropped legacy table: {table_name}")
        except Exception as e:
            print(f"Could not drop {table_name}: {e}")

    # Step 6: Make template_version_id NOT NULL in patient_flow_states
    # (Now that all data has been migrated)
    try:
        op.alter_column('patient_flow_states', 'template_version_id',
                       existing_type=postgresql.UUID(as_uuid=True),
                       nullable=False)
        print("Made template_version_id NOT NULL in patient_flow_states")
    except Exception as e:
        print(f"Note: Could not alter patient_flow_states.template_version_id: {e}")

    # Step 7: Make template_version_id NOT NULL in flow_states
    try:
        op.alter_column('flow_states', 'template_version_id',
                       existing_type=postgresql.UUID(as_uuid=True),
                       nullable=False)
        print("Made template_version_id NOT NULL in flow_states")
    except Exception as e:
        print(f"Note: Could not alter flow_states.template_version_id: {e}")

    print("Legacy template system removal completed!")


def downgrade() -> None:
    """
    Restore legacy template system (NOT RECOMMENDED).
    This downgrade is provided for emergency rollback only.
    Data will need to be restored from backups.
    """
    # Recreate flow_templates table
    op.create_table('flow_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('flow_type', sa.String(50), nullable=False, unique=True),
        sa.Column('version', sa.String(20), nullable=False, default='1.0.0'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('duration_days', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True, nullable=False),
        sa.Column('template_data', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )

    # Recreate indexes
    op.create_index('idx_flow_templates_flow_type', 'flow_templates', ['flow_type'])
    op.create_index('idx_flow_templates_is_active', 'flow_templates', ['is_active'])
    op.create_index('idx_flow_templates_version', 'flow_templates', ['version'])

    # Add back legacy columns to patient_flow_states
    try:
        op.add_column('patient_flow_states',
                     sa.Column('flow_type', sa.String(50), nullable=True))
        op.add_column('patient_flow_states',
                     sa.Column('template_version', sa.String(20), nullable=True, default='1.0.0'))
    except Exception:
        pass

    # Add back legacy columns to flow_states
    try:
        op.add_column('flow_states',
                     sa.Column('flow_type', sa.String(50), nullable=True))
        op.add_column('flow_states',
                     sa.Column('template_version', sa.String(20), nullable=True, default='1.0.0'))
    except Exception:
        pass

    # Make template_version_id nullable again
    try:
        op.alter_column('patient_flow_states', 'template_version_id',
                       existing_type=postgresql.UUID(as_uuid=True),
                       nullable=True)
    except Exception:
        pass

    try:
        op.alter_column('flow_states', 'template_version_id',
                       existing_type=postgresql.UUID(as_uuid=True),
                       nullable=True)
    except Exception:
        pass

    print("WARNING: Legacy tables restored but data needs to be restored from backups!")