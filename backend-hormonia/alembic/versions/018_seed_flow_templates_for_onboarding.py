"""seed_flow_templates_for_onboarding

Revision ID: 018_seed_flow_templates
Revises: 017_add_patient_soft_delete
Create Date: 2025-10-17 11:59:51.705745

Seeds the flow_kinds and flow_template_versions tables with the initial onboarding flow template.
This is required for the patient onboarding saga to create flow states.

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
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime


from app.utils.timezone import now_sao_paulo_naive
# revision identifiers, used by Alembic.
revision = '018_seed_flow_templates'
down_revision = '017_add_patient_soft_delete'
branch_labels = None
depends_on = None


# Define the flow kind and template data
ONBOARDING_FLOW_KIND_ID = uuid.UUID('00000000-0000-0000-0000-000000000001')
ONBOARDING_TEMPLATE_VERSION_ID = uuid.UUID('00000000-0000-0000-0000-000000000002')


def upgrade() -> None:
    """Seed flow templates for patient onboarding."""

    # Get connection
    conn = op.get_bind()

    # Check if flow kind already exists (idempotent)
    result = conn.execute(
        sa.text("SELECT id FROM flow_kinds WHERE kind_key = 'initial_15_days'")
    ).fetchone()

    flow_kind_id = None
    if not result:
        # Insert flow kind
        conn.execute(
            sa.text("""
                INSERT INTO flow_kinds (id, kind_key, display_name, description, is_active, created_at, updated_at)
                VALUES (:id, :kind_key, :display_name, :description, :is_active, :created_at, :updated_at)
            """),
            {
                'id': str(ONBOARDING_FLOW_KIND_ID),
                'kind_key': 'initial_15_days',
                'display_name': 'Initial 15 Days Onboarding',
                'description': 'Standard patient onboarding flow for the first 15 days',
                'is_active': True,
                'created_at': now_sao_paulo_naive(),
                'updated_at': now_sao_paulo_naive()
            }
        )
        flow_kind_id = str(ONBOARDING_FLOW_KIND_ID)
        print(f"✅ Created flow kind: initial_15_days (ID: {ONBOARDING_FLOW_KIND_ID})")
    else:
        flow_kind_id = str(result[0])
        print(f"ℹ️  Flow kind 'initial_15_days' already exists (ID: {flow_kind_id}), skipping...")

    # Check if template version already exists (idempotent)
    # Check by flow_kind_id and version_number (unique constraint)
    result = conn.execute(
        sa.text("SELECT id FROM flow_template_versions WHERE flow_kind_id = :flow_kind_id AND version_number = :version_number"),
        {'flow_kind_id': flow_kind_id, 'version_number': 1}
    ).fetchone()

    if not result:
        # Define the onboarding message steps
        onboarding_steps = [
            {
                "step": 0,
                "day": 0,
                "message": "Olá! Bem-vindo(a) à Clínica Oncológica. Estamos aqui para acompanhá-lo(a) durante todo o seu tratamento.",
                "delay_hours": 0
            },
            {
                "step": 1,
                "day": 1,
                "message": "Como você está se sentindo hoje? Lembre-se de que nossa equipe está sempre disponível para ajudá-lo(a).",
                "delay_hours": 24
            },
            {
                "step": 2,
                "day": 3,
                "message": "Não se esqueça de manter-se hidratado(a) e seguir as orientações médicas. Estamos torcendo por você!",
                "delay_hours": 48
            },
            {
                "step": 3,
                "day": 7,
                "message": "Já se passou uma semana! Como tem sido sua experiência? Estamos aqui para qualquer dúvida.",
                "delay_hours": 96
            },
            {
                "step": 4,
                "day": 15,
                "message": "Parabéns por completar os primeiros 15 dias! Continue seguindo as orientações e conte conosco sempre.",
                "delay_hours": 192
            }
        ]

        # Insert template version
        import json
        steps_json = json.dumps(onboarding_steps)
        metadata_json = json.dumps({})

        conn.execute(
            sa.text("""
                INSERT INTO flow_template_versions
                (id, flow_kind_id, version_number, template_name, description, is_active, is_draft, steps, metadata, created_at, updated_at)
                VALUES (:id, :flow_kind_id, :version_number, :template_name, :description, :is_active, :is_draft, CAST(:steps AS jsonb), CAST(:metadata AS jsonb), :created_at, :updated_at)
            """),
            {
                'id': str(ONBOARDING_TEMPLATE_VERSION_ID),
                'flow_kind_id': flow_kind_id,  # Use the actual ID from database
                'version_number': 1,
                'template_name': 'Onboarding v1.0',
                'description': 'Initial version of the 15-day onboarding flow',
                'is_active': True,
                'is_draft': False,
                'steps': steps_json,
                'metadata': metadata_json,
                'created_at': now_sao_paulo_naive(),
                'updated_at': now_sao_paulo_naive()
            }
        )
        print(f"✅ Created template version: Onboarding v1.0 (ID: {ONBOARDING_TEMPLATE_VERSION_ID})")
    else:
        template_version_id = str(result[0])
        print(f"ℹ️  Template version already exists (ID: {template_version_id}), skipping...")

    print("✅ Flow template seeding complete!")


def downgrade() -> None:
    """Remove seeded flow templates."""

    conn = op.get_bind()

    # Delete template version first (due to foreign key)
    conn.execute(
        sa.text("DELETE FROM flow_template_versions WHERE id = :id"),
        {'id': str(ONBOARDING_TEMPLATE_VERSION_ID)}
    )

    # Delete flow kind
    conn.execute(
        sa.text("DELETE FROM flow_kinds WHERE id = :id"),
        {'id': str(ONBOARDING_FLOW_KIND_ID)}
    )

    print("✅ Flow template seeding rolled back!")
