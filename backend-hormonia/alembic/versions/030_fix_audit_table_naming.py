"""Fix audit table naming - rename audit_logs to audit_log_entries if needed

Revision ID: 030_fix_audit_naming
Revises: 029_quiz_questions
Create Date: 2025-09-29 19:42:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '030_fix_audit_naming'
down_revision = '029_quiz_questions'
branch_labels = None
depends_on = None


def upgrade():
    """
    Ensure consistent audit table naming. Check if audit_logs exists
    and rename to audit_log_entries if needed. If audit_log_entries
    already exists, this migration is a no-op.
    """
    # Check if we need to rename
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'audit_logs' in tables and 'audit_log_entries' not in tables:
        # Rename table
        op.rename_table('audit_logs', 'audit_log_entries')

        # Rename indexes
        op.execute("""
            ALTER INDEX IF EXISTS idx_audit_logs_user_id
            RENAME TO idx_audit_log_entries_user_id;
        """)

        op.execute("""
            ALTER INDEX IF EXISTS idx_audit_logs_timestamp
            RENAME TO idx_audit_log_entries_timestamp;
        """)

        op.execute("""
            ALTER INDEX IF EXISTS idx_audit_logs_action
            RENAME TO idx_audit_log_entries_action;
        """)

        op.execute("""
            ALTER INDEX IF EXISTS idx_audit_logs_entity
            RENAME TO idx_audit_log_entries_entity;
        """)

        # Update table comment
        op.execute("""
            COMMENT ON TABLE audit_log_entries IS
            'Audit trail for all system actions and data changes (renamed from audit_logs)';
        """)

    elif 'audit_log_entries' in tables:
        # Table already has correct name, no action needed
        pass

    else:
        # Neither table exists, skip
        pass


def downgrade():
    """
    Rename audit_log_entries back to audit_logs if it was renamed.
    """
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'audit_log_entries' in tables and 'audit_logs' not in tables:
        # Rename table back
        op.rename_table('audit_log_entries', 'audit_logs')

        # Rename indexes back
        op.execute("""
            ALTER INDEX IF EXISTS idx_audit_log_entries_user_id
            RENAME TO idx_audit_logs_user_id;
        """)

        op.execute("""
            ALTER INDEX IF EXISTS idx_audit_log_entries_timestamp
            RENAME TO idx_audit_logs_timestamp;
        """)

        op.execute("""
            ALTER INDEX IF EXISTS idx_audit_log_entries_action
            RENAME TO idx_audit_logs_action;
        """)

        op.execute("""
            ALTER INDEX IF EXISTS idx_audit_log_entries_entity
            RENAME TO idx_audit_logs_entity;
        """)

        # Update table comment
        op.execute("""
            COMMENT ON TABLE audit_logs IS
            'Audit trail for all system actions and data changes';
        """)