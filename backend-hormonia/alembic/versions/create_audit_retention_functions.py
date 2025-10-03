"""create audit retention functions

Revision ID: create_audit_retention
Revises: add_performance_indexes
Create Date: 2025-10-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'create_audit_retention'
down_revision = 'add_performance_indexes'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create SQL functions for 90-day audit trail retention policy.

    Functions created:
    - cleanup_old_audit_trail(): Removes audit_trail records > 90 days
    - cleanup_old_audit_log_entries(): Removes audit_log_entries records > 90 days
    - cleanup_all_audit_tables(): Calls both cleanup functions
    """

    # Create indexes for performance (if not exist)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_trail_created_at
        ON public.audit_trail(created_at);
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_audit_log_entries_timestamp
        ON public.audit_log_entries(timestamp);
    """)

    # Function 1: cleanup_old_audit_trail
    op.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_audit_trail()
        RETURNS TABLE(
            deleted_count INTEGER,
            space_before TEXT,
            space_after TEXT
        ) AS $$
        DECLARE
            v_deleted_count INTEGER;
            v_space_before BIGINT;
            v_space_after BIGINT;
        BEGIN
            -- Get table size before cleanup
            SELECT pg_total_relation_size('public.audit_trail') INTO v_space_before;

            -- Delete records older than 90 days
            WITH deleted AS (
                DELETE FROM public.audit_trail
                WHERE created_at < NOW() - INTERVAL '90 days'
                RETURNING id
            )
            SELECT COUNT(*) INTO v_deleted_count FROM deleted;

            -- Get table size after cleanup
            SELECT pg_total_relation_size('public.audit_trail') INTO v_space_after;

            -- Return results
            RETURN QUERY SELECT
                v_deleted_count,
                pg_size_pretty(v_space_before),
                pg_size_pretty(v_space_after);
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
    """)

    # Function 2: cleanup_old_audit_log_entries
    op.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_audit_log_entries()
        RETURNS TABLE(
            deleted_count INTEGER,
            space_before TEXT,
            space_after TEXT
        ) AS $$
        DECLARE
            v_deleted_count INTEGER;
            v_space_before BIGINT;
            v_space_after BIGINT;
        BEGIN
            -- Get table size before cleanup
            SELECT pg_total_relation_size('public.audit_log_entries') INTO v_space_before;

            -- Delete records older than 90 days
            WITH deleted AS (
                DELETE FROM public.audit_log_entries
                WHERE timestamp < NOW() - INTERVAL '90 days'
                RETURNING id
            )
            SELECT COUNT(*) INTO v_deleted_count FROM deleted;

            -- Get table size after cleanup
            SELECT pg_total_relation_size('public.audit_log_entries') INTO v_space_after;

            -- Return results
            RETURN QUERY SELECT
                v_deleted_count,
                pg_size_pretty(v_space_before),
                pg_size_pretty(v_space_after);
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
    """)

    # Function 3: cleanup_all_audit_tables (master function)
    op.execute("""
        CREATE OR REPLACE FUNCTION cleanup_all_audit_tables()
        RETURNS TABLE(
            table_name TEXT,
            deleted_count INTEGER,
            space_before TEXT,
            space_after TEXT
        ) AS $$
        BEGIN
            -- Cleanup audit_trail
            RETURN QUERY
            SELECT
                'audit_trail'::TEXT,
                r.deleted_count,
                r.space_before,
                r.space_after
            FROM cleanup_old_audit_trail() r;

            -- Cleanup audit_log_entries
            RETURN QUERY
            SELECT
                'audit_log_entries'::TEXT,
                r.deleted_count,
                r.space_before,
                r.space_after
            FROM cleanup_old_audit_log_entries() r;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
    """)

    # Grant execute permissions to authenticated users
    op.execute("""
        GRANT EXECUTE ON FUNCTION cleanup_old_audit_trail() TO authenticated;
        GRANT EXECUTE ON FUNCTION cleanup_old_audit_log_entries() TO authenticated;
        GRANT EXECUTE ON FUNCTION cleanup_all_audit_tables() TO authenticated;
    """)


def downgrade():
    """Drop audit retention functions and indexes."""

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS cleanup_all_audit_tables() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS cleanup_old_audit_log_entries() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS cleanup_old_audit_trail() CASCADE;")

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_audit_trail_created_at;")
    op.execute("DROP INDEX IF EXISTS idx_audit_log_entries_timestamp;")
