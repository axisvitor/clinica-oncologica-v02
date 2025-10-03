"""Add Firebase authentication fields to users table

Revision ID: add_firebase_fields
Revises: 20250930_011500
Create Date: 2025-09-30 16:54:00.000000

FIREBASE INTEGRATION:
Adds Firebase authentication support alongside existing local auth.

Changes:
1. Firebase UID and auth provider fields
2. Firebase metadata (email verification, display name, photo)
3. Custom claims for role management (ADMIN, DOCTOR only)
4. Audit table for sync operations
5. Makes hashed_password nullable for Firebase-only users

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = 'add_firebase_fields'
down_revision = '20250930_011500'
branch_labels = None
depends_on = None


def upgrade():
    """Add Firebase authentication fields to users table."""

    # Add Firebase authentication columns
    op.add_column('users',
        sa.Column('firebase_uid', sa.String(255), unique=True, nullable=True)
    )
    op.add_column('users',
        sa.Column('auth_provider', sa.String(50), nullable=False, server_default='local')
    )
    op.add_column('users',
        sa.Column('firebase_last_sign_in', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column('users',
        sa.Column('firebase_created_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column('users',
        sa.Column('firebase_email_verified', sa.Boolean, nullable=False, server_default='false')
    )
    op.add_column('users',
        sa.Column('firebase_display_name', sa.String(255), nullable=True)
    )
    op.add_column('users',
        sa.Column('firebase_photo_url', sa.String(500), nullable=True)
    )
    op.add_column('users',
        sa.Column('firebase_custom_claims', JSONB, nullable=False, server_default='{}')
    )
    op.add_column('users',
        sa.Column('last_firebase_sync', sa.DateTime(timezone=True), nullable=True)
    )

    # Make hashed_password nullable (Firebase users don't need password)
    op.alter_column('users', 'hashed_password', nullable=True)

    # Create indexes for performance
    op.create_index('idx_users_firebase_uid', 'users', ['firebase_uid'], unique=True)
    op.create_index('idx_users_auth_provider', 'users', ['auth_provider'])

    # Create audit table for sync operations
    op.create_table(
        'user_sync_log',
        sa.Column('id', sa.UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('firebase_uid', sa.String(255), nullable=False),
        sa.Column('user_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True),
        sa.Column('operation', sa.String(50), nullable=False),  # create, update, link
        sa.Column('sync_direction', sa.String(20), nullable=False),  # firebase_to_pg, pg_to_firebase
        sa.Column('changes', JSONB, nullable=False, server_default='{}'),
        sa.Column('success', sa.Boolean, nullable=False),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()'))
    )

    # Create indexes for audit table
    op.create_index('idx_user_sync_log_firebase_uid', 'user_sync_log', ['firebase_uid'])
    op.create_index('idx_user_sync_log_user_id', 'user_sync_log', ['user_id'])
    op.create_index('idx_user_sync_log_created_at', 'user_sync_log', ['created_at'])


def downgrade():
    """Remove Firebase authentication fields from users table."""

    # Drop audit table
    op.drop_index('idx_user_sync_log_created_at')
    op.drop_index('idx_user_sync_log_user_id')
    op.drop_index('idx_user_sync_log_firebase_uid')
    op.drop_table('user_sync_log')

    # Drop indexes
    op.drop_index('idx_users_auth_provider')
    op.drop_index('idx_users_firebase_uid')

    # Remove Firebase columns
    op.drop_column('users', 'last_firebase_sync')
    op.drop_column('users', 'firebase_custom_claims')
    op.drop_column('users', 'firebase_photo_url')
    op.drop_column('users', 'firebase_display_name')
    op.drop_column('users', 'firebase_email_verified')
    op.drop_column('users', 'firebase_created_at')
    op.drop_column('users', 'firebase_last_sign_in')
    op.drop_column('users', 'auth_provider')
    op.drop_column('users', 'firebase_uid')

    # Restore hashed_password as required
    op.alter_column('users', 'hashed_password', nullable=False)
