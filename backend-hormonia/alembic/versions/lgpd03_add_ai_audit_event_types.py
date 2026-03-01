"""Add AI event types to audit_event_type enum (LGPD-03).

Revision ID: lgpd03_add_ai_audit_event_types
Revises: lgpd02_add_whatsapp_opt_out_flag
Create Date: 2026-02-22

WHY:
LGPD requires accountability for automated processing of patient data
(Art. 20 — right to explanation of automated decisions). AI calls for
humanization, sentiment analysis, follow-up generation, and general
queries currently have no audit trail in the PostgreSQL audit_event_type
enum.

This migration adds four new values to the PostgreSQL native enum so that
AuditService.log_event() can record AI processing events via the existing
audit infrastructure.

WHAT:
- Adds ai_query to audit_event_type (general Gemini/LangGraph queries)
- Adds ai_humanization to audit_event_type (quiz humanization calls)
- Adds ai_sentiment to audit_event_type (sentiment analysis calls)
- Adds ai_follow_up to audit_event_type (follow-up generation calls)

Each value is added with an idempotent IF NOT EXISTS guard using the
project's standard DO $$ pattern, making this migration safely re-runnable.
PostgreSQL 13+ (AWS RDS) supports ALTER TYPE ADD VALUE inside transactions,
so no autocommit workaround is required.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "lgpd03_add_ai_audit_event_types"
down_revision = "lgpd02_add_whatsapp_opt_out_flag"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'audit_event_type'
                  AND e.enumlabel = 'ai_query'
            ) THEN
                ALTER TYPE audit_event_type ADD VALUE 'ai_query';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'audit_event_type'
                  AND e.enumlabel = 'ai_humanization'
            ) THEN
                ALTER TYPE audit_event_type ADD VALUE 'ai_humanization';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'audit_event_type'
                  AND e.enumlabel = 'ai_sentiment'
            ) THEN
                ALTER TYPE audit_event_type ADD VALUE 'ai_sentiment';
            END IF;

            IF NOT EXISTS (
                SELECT 1 FROM pg_enum e
                JOIN pg_type t ON t.oid = e.enumtypid
                WHERE t.typname = 'audit_event_type'
                  AND e.enumlabel = 'ai_follow_up'
            ) THEN
                ALTER TYPE audit_event_type ADD VALUE 'ai_follow_up';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # PostgreSQL does not support removing enum values.
    # The values are harmless if unused.
    pass
