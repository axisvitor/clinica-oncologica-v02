"""Fix audit_logs user_id column type from String to UUID

Revision ID: 20251011_140000
Revises: 20251011_130000
Create Date: 2025-01-11 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20251011_140000'
down_revision = '20251011_130000'
branch_labels = None
depends_on = None


def upgrade():
    """
    Fix audit_logs.user_id column type from String(255) to UUID.
    
    This migration addresses the type mismatch between the SQLAlchemy model
    (which expects UUID) and the database schema (which was created as String).
    """
    conn = op.get_bind()
    table_exists = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'audit_logs'
        )
    """)).scalar()
    if not table_exists:
        return
    user_id_type = conn.execute(sa.text("""
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='audit_logs' AND column_name='user_id'
    """)).scalar()
    if user_id_type is None:
        return
    if user_id_type == 'uuid':
        op.execute("CREATE INDEX IF NOT EXISTS idx_audit_user_event_time ON audit_logs (user_id, event_type, created_at)")
        return

    temp_exists = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='audit_logs' AND column_name='user_id_temp'
        )
    """)).scalar()
    if not temp_exists:
        op.add_column('audit_logs', sa.Column('user_id_temp', postgresql.UUID(as_uuid=True), nullable=True))

    op.execute("""
        UPDATE audit_logs 
        SET user_id = NULL 
        WHERE COALESCE(user_id::text, '') = ''
    """)
    op.execute("""
        UPDATE audit_logs
        SET user_id_temp = CASE
            WHEN user_id IS NULL THEN NULL
            WHEN (user_id::text ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
                THEN user_id::uuid
            ELSE NULL
        END
    """)
    op.execute('DROP INDEX IF EXISTS public.idx_audit_user_event_time')
    op.drop_column('audit_logs', 'user_id')
    op.alter_column('audit_logs', 'user_id_temp', new_column_name='user_id')
    op.execute('CREATE INDEX IF NOT EXISTS idx_audit_user_event_time ON audit_logs (user_id, event_type, created_at)')


def downgrade():
    """
    Revert audit_logs.user_id column type from UUID back to String(255).
    
    This converts UUID values back to string format.
    """
    conn = op.get_bind()
    table_exists = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'audit_logs'
        )
    """)).scalar()
    if not table_exists:
        return
    user_id_type = conn.execute(sa.text("""
        SELECT data_type
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name='audit_logs' AND column_name='user_id'
    """)).scalar()
    if user_id_type is None or user_id_type != 'uuid':
        return

    temp_exists = conn.execute(sa.text("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema='public' AND table_name='audit_logs' AND column_name='user_id_temp'
        )
    """)).scalar()
    if not temp_exists:
        op.add_column('audit_logs', sa.Column('user_id_temp', sa.String(255), nullable=True))

    op.execute("""
        UPDATE audit_logs 
        SET user_id_temp = user_id::text 
        WHERE user_id IS NOT NULL
    """)
    op.execute("DROP INDEX IF EXISTS public.idx_audit_user_event_time")
    op.drop_column('audit_logs', 'user_id')
    op.alter_column('audit_logs', 'user_id_temp', new_column_name='user_id')
    op.execute('CREATE INDEX IF NOT EXISTS idx_audit_user_event_time ON audit_logs (user_id, event_type, created_at)')