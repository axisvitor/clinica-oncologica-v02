"""seed_welcome_message_template

Revision ID: 019_seed_welcome_message_template
Revises: 27ee28e62ff8
Create Date: 2025-11-22 21:45:00.000000

Seeds the welcome message template used in the patient onboarding saga.

WHY:
- Not recorded (legacy migration).

WHAT:
- Not recorded (legacy migration).

IMPACT:
- Not recorded (legacy migration).

BENCHMARK:
- Not recorded (legacy migration).

ROLLBACK:
- Not recorded (legacy migration).

RELATED:
- Not recorded (legacy migration).

MIGRATION TYPE:
- Not recorded (legacy migration).
"""

from __future__ import annotations

import uuid

from alembic import op
import sqlalchemy as sa

from alembic_runtime_helpers import now_sao_paulo_naive

# revision identifiers, used by Alembic.
revision = "019_seed_welcome_message_template"
down_revision = "27ee28e62ff8"
branch_labels = None
depends_on = None

WELCOME_TEMPLATE_ID = uuid.UUID("00000000-0000-0000-0000-000000000003")
TEMPLATE_NAME = "welcome_message"



def upgrade() -> None:
    """Seed welcome message template."""
    conn = op.get_bind()

    result = conn.execute(
        sa.text("SELECT id FROM message_templates WHERE name = :name"),
        {"name": TEMPLATE_NAME},
    ).fetchone()

    if not result:
        conn.execute(
            sa.text(
                """
                INSERT INTO message_templates (id, name, content, variables, message_type, is_active, created_at, updated_at)
                VALUES (:id, :name, :content, :variables, :message_type, :is_active, :created_at, :updated_at)
                """
            ),
            {
                "id": str(WELCOME_TEMPLATE_ID),
                "name": TEMPLATE_NAME,
                "content": "Olá {patient_name}, bem-vindo(a) à Clínica Hormonia! Seu cadastro foi realizado com sucesso. Em breve entraremos em contato para dar início ao seu acompanhamento.",
                "variables": '["patient_name"]',
                "message_type": "text",
                "is_active": True,
                "created_at": now_sao_paulo_naive(),
                "updated_at": now_sao_paulo_naive(),
            },
        )
        print(f"✅ Created template: {TEMPLATE_NAME} (ID: {WELCOME_TEMPLATE_ID})")
    else:
        print(f"ℹ️  Template '{TEMPLATE_NAME}' already exists, skipping...")



def downgrade() -> None:
    """Remove seeded welcome message template."""
    conn = op.get_bind()

    conn.execute(
        sa.text("DELETE FROM message_templates WHERE name = :name"),
        {"name": TEMPLATE_NAME},
    )

    print(f"✅ Template '{TEMPLATE_NAME}' removed!")
