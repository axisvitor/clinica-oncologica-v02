"""seed_welcome_message_template

Revision ID: 019_seed_welcome_message_template
Revises: 018_seed_flow_templates
Create Date: 2025-11-22 21:45:00.000000

Seeds the welcome message template used in the patient onboarding saga.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '019_seed_welcome_message_template'
down_revision = '27ee28e62ff8'
branch_labels = None
depends_on = None

# Define the template data
WELCOME_TEMPLATE_ID = uuid.UUID('00000000-0000-0000-0000-000000000003')
TEMPLATE_NAME = "welcome_message"

def upgrade() -> None:
    """Seed welcome message template."""
    conn = op.get_bind()

    # Check if template already exists
    result = conn.execute(
        sa.text("SELECT id FROM message_templates WHERE name = :name"),
        {'name': TEMPLATE_NAME}
    ).fetchone()

    if not result:
        conn.execute(
            sa.text("""
                INSERT INTO message_templates (id, name, content, variables, message_type, is_active, created_at, updated_at)
                VALUES (:id, :name, :content, :variables, :message_type, :is_active, :created_at, :updated_at)
            """),
            {
                'id': str(WELCOME_TEMPLATE_ID),
                'name': TEMPLATE_NAME,
                'content': "Olá {patient_name}, bem-vindo(a) à Clínica Hormonia! Seu cadastro foi realizado com sucesso. Em breve entraremos em contato para dar início ao seu acompanhamento.",
                'variables': '["patient_name"]',  # JSON string
                'message_type': 'text',
                'is_active': True,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
        )
        print(f"✅ Created template: {TEMPLATE_NAME} (ID: {WELCOME_TEMPLATE_ID})")
    else:
        print(f"ℹ️  Template '{TEMPLATE_NAME}' already exists, skipping...")

    conn.commit()

def downgrade() -> None:
    """Remove seeded welcome message template."""
    conn = op.get_bind()

    conn.execute(
        sa.text("DELETE FROM message_templates WHERE name = :name"),
        {'name': TEMPLATE_NAME}
    )
    
    conn.commit()
    print(f"✅ Template '{TEMPLATE_NAME}' removed!")
