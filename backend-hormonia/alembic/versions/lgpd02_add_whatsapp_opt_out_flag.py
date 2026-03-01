"""Add messaging_stopped_at column to patients table for WhatsApp opt-out.

Revision ID: lgpd02_add_whatsapp_opt_out_flag
Revises: lgpd01_add_patient_deletion_audit
Create Date: 2026-02-22

WHY:
LGPD Art. 18 requires immediate and unconditional response to consent
revocation. When a patient sends STOP/PARAR/CANCELAR via WhatsApp the
application must halt all outbound messaging instantly.

This migration adds a nullable timestamp column that records the exact
moment the patient opted out. A non-NULL value acts as the authoritative
signal that messaging must stop. A partial index (WHERE NOT NULL) provides
efficient filtering for the minority of opted-out patients without
burdening queries over the majority of NULL rows.

WHAT:
- Adds messaging_stopped_at (timestamptz, nullable) to patients table.
- Creates partial index idx_patients_messaging_stopped for fast opt-out
  lookups.

IMPACT:
- Column is nullable with no default, so existing rows are unaffected.
- The webhook message handler (message_handler.py) and
  UnifiedWhatsAppService (unified_whatsapp_service.py) are updated
  separately to read/write this column.

ROLLBACK:
- drop_index then drop_column — safe because the column is additive.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "lgpd02_add_whatsapp_opt_out_flag"
down_revision = "lgpd01_add_patient_deletion_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "patients",
        sa.Column("messaging_stopped_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_patients_messaging_stopped",
        "patients",
        ["messaging_stopped_at"],
        postgresql_where=sa.text("messaging_stopped_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_patients_messaging_stopped", table_name="patients")
    op.drop_column("patients", "messaging_stopped_at")
