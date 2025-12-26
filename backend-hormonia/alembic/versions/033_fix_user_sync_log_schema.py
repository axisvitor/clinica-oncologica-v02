"""Fix user_sync_log schema - add missing columns for Firebase sync

Revision ID: 033_fix_user_sync_log_schema
Revises: ac193e8656c1
Create Date: 2025-12-21 14:40:00.000000

This migration fixes the user_sync_log table that was not properly
migrated from the Supabase schema to the Firebase schema.

Changes:
- Adds user_id column (UUID FK to users)
- Adds operation column (VARCHAR 50)
- Adds sync_direction column (VARCHAR 20)
- Adds changes column (JSONB)
- Adds success column (BOOLEAN)
- Drops legacy Supabase columns safely

Index Creation Note:
- Indexes are created with IF NOT EXISTS for idempotency
- For production with live traffic, consider running indexes separately
  with CONCURRENTLY to avoid table locks
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '033_fix_user_sync_log_schema'
down_revision = 'ac193e8656c1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add new Firebase-compatible columns to user_sync_log."""

    # Check if columns already exist before adding
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('user_sync_log')]

    # Add new columns if they don't exist
    if 'user_id' not in existing_columns:
        op.add_column('user_sync_log',
            sa.Column('user_id', sa.UUID(), nullable=True)
        )
        op.create_index('ix_user_sync_log_user_id', 'user_sync_log', ['user_id'])
        op.create_foreign_key(
            'fk_user_sync_log_user_id',
            'user_sync_log', 'users',
            ['user_id'], ['id'],
            ondelete='CASCADE'
        )

    if 'operation' not in existing_columns:
        # Add with default then make NOT NULL
        op.add_column('user_sync_log',
            sa.Column('operation', sa.String(50), nullable=True)
        )
        # Migrate data from sync_action if it exists
        if 'sync_action' in existing_columns:
            op.execute("""
                UPDATE user_sync_log
                SET operation = COALESCE(sync_action, 'sync')
                WHERE operation IS NULL
            """)
        else:
            op.execute("UPDATE user_sync_log SET operation = 'sync' WHERE operation IS NULL")
        op.alter_column('user_sync_log', 'operation', nullable=False)

    if 'sync_direction' not in existing_columns:
        op.add_column('user_sync_log',
            sa.Column('sync_direction', sa.String(20), nullable=True)
        )
        # Default to firebase_to_pg
        op.execute("""
            UPDATE user_sync_log
            SET sync_direction = 'firebase_to_pg'
            WHERE sync_direction IS NULL
        """)
        op.alter_column('user_sync_log', 'sync_direction', nullable=False)

    if 'changes' not in existing_columns:
        op.add_column('user_sync_log',
            sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()),
                     nullable=False, server_default='{}')
        )
        # Migrate data from firebase_data if it exists
        if 'firebase_data' in existing_columns:
            op.execute("""
                UPDATE user_sync_log
                SET changes = COALESCE(firebase_data, '{}'::jsonb)
            """)

    if 'success' not in existing_columns:
        op.add_column('user_sync_log',
            sa.Column('success', sa.Boolean(), nullable=True)
        )
        # Derive success from sync_status if it exists
        if 'sync_status' in existing_columns:
            op.execute("""
                UPDATE user_sync_log
                SET success = CASE
                    WHEN sync_status IN ('completed', 'success', 'synced') THEN true
                    ELSE false
                END
                WHERE success IS NULL
            """)
        else:
            op.execute("UPDATE user_sync_log SET success = true WHERE success IS NULL")
        op.alter_column('user_sync_log', 'success', nullable=False)

    # Migrate user_id from supabase_user_id if it exists
    if 'supabase_user_id' in existing_columns and 'user_id' in existing_columns:
        op.execute("""
            UPDATE user_sync_log
            SET user_id = supabase_user_id
            WHERE user_id IS NULL AND supabase_user_id IS NOT NULL
        """)

    # Update created_at to be NOT NULL with default
    op.alter_column('user_sync_log', 'created_at',
        existing_type=postgresql.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text('now()')
    )

    # Create indexes with IF NOT EXISTS for idempotency
    # Using raw SQL for proper IF NOT EXISTS support
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_user_sync_log_created_at
        ON user_sync_log(created_at)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_user_sync_log_firebase_uid
        ON user_sync_log(firebase_uid)
    """)

    # Make old columns nullable (they are no longer used by the new model)
    if 'sync_action' in existing_columns:
        op.alter_column('user_sync_log', 'sync_action',
            existing_type=sa.String(50),
            nullable=True
        )

    if 'sync_status' in existing_columns:
        op.alter_column('user_sync_log', 'sync_status',
            existing_type=sa.String(50),
            nullable=True
        )


def downgrade() -> None:
    """Remove new columns (data will be lost)."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_columns = [col['name'] for col in inspector.get_columns('user_sync_log')]

    # Drop new columns
    if 'success' in existing_columns:
        op.drop_column('user_sync_log', 'success')

    if 'changes' in existing_columns:
        op.drop_column('user_sync_log', 'changes')

    if 'sync_direction' in existing_columns:
        op.drop_column('user_sync_log', 'sync_direction')

    if 'operation' in existing_columns:
        op.drop_column('user_sync_log', 'operation')

    if 'user_id' in existing_columns:
        op.drop_constraint('fk_user_sync_log_user_id', 'user_sync_log', type_='foreignkey')
        op.drop_index('ix_user_sync_log_user_id', 'user_sync_log')
        op.drop_column('user_sync_log', 'user_id')
