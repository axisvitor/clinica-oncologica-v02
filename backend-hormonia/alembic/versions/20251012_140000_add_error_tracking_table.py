"""Add error tracking table for centralized error handling

Revision ID: 20251012_140000
Revises: 20251011_140000
Create Date: 2025-10-12 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251012_140000'
down_revision = '20251011_140000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create error tracking table and indexes for centralized error handling."""

    # Create error_logs table
    op.create_table(
        'error_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False, 
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('error_type', sa.String(100), nullable=False,
                  comment='Type of error (DI_GENERATOR, ROLE_ENUM, SCHEMA_MISMATCH, etc.)'),
        sa.Column('error_message', sa.Text, nullable=False,
                  comment='The error message or description'),
        sa.Column('stack_trace', sa.Text, nullable=True,
                  comment='Full stack trace of the error (optional)'),
        sa.Column('context', postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"),
                  comment='Additional context data as JSON (request info, user data, etc.)'),
        sa.Column('count', sa.Integer, nullable=False, server_default=sa.text('1'),
                  comment='Number of times this error has occurred (for deduplication)'),
        sa.Column('first_seen', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP'),
                  comment='When this error was first encountered'),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP'),
                  comment='When this error was last encountered'),
        sa.Column('resolved', sa.Boolean, nullable=False, server_default=sa.text('false'),
                  comment='Whether this error has been resolved'),
        sa.Column('severity', sa.String(20), nullable=False, server_default=sa.text("'ERROR'"),
                  comment='Error severity level (DEBUG, INFO, WARNING, ERROR, CRITICAL)'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text('CURRENT_TIMESTAMP')),
        comment='Error tracking table for monitoring and debugging critical system errors'
    )

    # Create basic indexes for efficient querying
    op.create_index('idx_error_logs_error_type', 'error_logs', ['error_type'])
    op.create_index('idx_error_logs_severity', 'error_logs', ['severity'])
    op.create_index('idx_error_logs_resolved', 'error_logs', ['resolved'])
    op.create_index('idx_error_logs_first_seen', 'error_logs', ['first_seen'])
    op.create_index('idx_error_logs_last_seen', 'error_logs', ['last_seen'])
    op.create_index('idx_error_logs_count', 'error_logs', ['count'])

    # Create composite indexes for common queries
    op.create_index(
        'idx_error_logs_type_resolved',
        'error_logs',
        ['error_type', 'resolved']
    )

    op.create_index(
        'idx_error_logs_severity_time',
        'error_logs',
        ['severity', 'last_seen']
    )

    op.create_index(
        'idx_error_logs_unresolved_recent',
        'error_logs',
        ['resolved', 'last_seen']
    )

    # Create GIN index for JSONB context column for efficient JSON queries
    try:
        op.create_index(
            'idx_error_logs_context_gin',
            'error_logs',
            ['context'],
            postgresql_using='gin'
        )
        print("✅ GIN index for context JSONB column created successfully")
    except Exception as e:
        print(f"⚠️ Could not create GIN index for context: {e}")

    # Create unique index for error deduplication
    op.create_index(
        'idx_error_logs_deduplication',
        'error_logs',
        ['error_type', sa.text('md5(error_message)')],
        unique=True
    )

    print("✅ Error tracking table migration completed successfully")


def downgrade() -> None:
    """Drop error tracking table and all related indexes."""
    
    # Drop the table (this will automatically drop all indexes)
    op.drop_table('error_logs')
    print("✅ Error tracking table dropped successfully")