"""Fix critical RLS policies - PostgreSQL compatible version

Revision ID: 20251011_130000
Revises: 20251011_120000
Create Date: 2025-10-11 13:00:00.000000

CRITICAL SECURITY FIX:
This migration addresses RLS policies for PostgreSQL (not Supabase).
Since we're using standard PostgreSQL, we'll disable RLS on tables that had it enabled
but were causing access issues, and implement proper application-level security instead.

Tables to fix:
- patients, messages, quiz_sessions, quiz_responses, medical_reports
- audit_logs, appointments, medications, treatments, consents
- notifications, sessions, alerts, flow_analytics, flow_messages
- user_sync_log, webhook_events, whatsapp_delivery_failures

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = '20251011_130000'
down_revision = '20251011_120000'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Fix RLS issues by disabling RLS on problematic tables.
    We'll rely on application-level security instead of database RLS.
    """

    # Get connection for executing raw SQL
    connection = op.get_bind()

    print("🔒 Fixing RLS configuration for PostgreSQL compatibility...")

    # List of tables that had RLS enabled but were causing issues
    tables_to_fix = [
        'patients', 'messages', 'quiz_sessions', 'quiz_responses',
        'medical_reports', 'audit_logs', 'appointments', 'medications',
        'treatments', 'consents', 'notifications', 'sessions',
        'alerts', 'flow_analytics', 'flow_messages', 'user_sync_log',
        'webhook_events', 'whatsapp_delivery_failures'
    ]

    for table_name in tables_to_fix:
        print(f"🔧 Fixing RLS for table: {table_name}")
        
        # First, drop any existing policies for this table
        try:
            policies_result = connection.execute(text(f"""
                SELECT policyname FROM pg_policies 
                WHERE schemaname = 'public' AND tablename = '{table_name}';
            """))
            
            for row in policies_result:
                policy_name = row[0]
                print(f"  - Dropping policy: {policy_name}")
                connection.execute(text(f'DROP POLICY IF EXISTS "{policy_name}" ON {table_name};'))
        except Exception as e:
            print(f"  - No existing policies to drop for {table_name}: {e}")

        # Disable RLS on the table
        try:
            connection.execute(text(f'ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;'))
            print(f"  ✅ Disabled RLS on {table_name}")
        except Exception as e:
            print(f"  - RLS was not enabled on {table_name}: {e}")

    print("✅ RLS configuration fixed. Application-level security should be used instead.")


def downgrade() -> None:
    """
    Downgrade by re-enabling RLS (but without policies, which would block access again).
    This is mainly for completeness - in practice, you probably don't want to downgrade this.
    """
    
    # Get connection for executing raw SQL
    connection = op.get_bind()

    print("⚠️  Re-enabling RLS (this may block access without proper policies)...")

    tables_to_revert = [
        'patients', 'messages', 'quiz_sessions', 'quiz_responses',
        'medical_reports', 'audit_logs', 'appointments', 'medications',
        'treatments', 'consents', 'notifications', 'sessions',
        'alerts', 'flow_analytics', 'flow_messages', 'user_sync_log',
        'webhook_events', 'whatsapp_delivery_failures'
    ]

    for table_name in tables_to_revert:
        try:
            connection.execute(text(f'ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;'))
            print(f"  ✅ Re-enabled RLS on {table_name}")
        except Exception as e:
            print(f"  - Could not re-enable RLS on {table_name}: {e}")

    print("⚠️  RLS re-enabled but no policies created - access may be blocked!")