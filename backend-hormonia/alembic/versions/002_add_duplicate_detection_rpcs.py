"""Add RPC functions for duplicate detection

Revision ID: 002
Revises: 001
Create Date: 2024-01-02 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '004_duplicate_detection'
down_revision = '003_flow_templates'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add RPC functions for scalable duplicate detection."""

    # Create RPC function for duplicate user emails
    op.execute("""
        CREATE OR REPLACE FUNCTION rpc_count_duplicate_user_emails()
        RETURNS TABLE(email text, cnt bigint)
        LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
          SELECT email, COUNT(*) AS cnt FROM users
          WHERE email IS NOT NULL AND email <> ''
          GROUP BY email HAVING COUNT(*) > 1
          ORDER BY cnt DESC
          LIMIT 1000;
        $$;
    """)

    # Create RPC function for duplicate patient phones
    op.execute("""
        CREATE OR REPLACE FUNCTION rpc_count_duplicate_patient_phones()
        RETURNS TABLE(phone text, cnt bigint)
        LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
          SELECT phone, COUNT(*) AS cnt FROM patients
          WHERE phone IS NOT NULL AND phone <> ''
          GROUP BY phone HAVING COUNT(*) > 1
          ORDER BY cnt DESC
          LIMIT 1000;
        $$;
    """)


def downgrade() -> None:
    """Remove RPC functions for duplicate detection."""

    # Drop RPC functions in reverse order
    op.execute("DROP FUNCTION IF EXISTS rpc_count_duplicate_patient_phones();")
    op.execute("DROP FUNCTION IF EXISTS rpc_count_duplicate_user_emails();")