"""merge_multiple_heads

Revision ID: 54ab19a5b23f
Revises: 011_remove_nurse_role, 017_remove_legacy_templates, add_dedicated_patient_columns
Create Date: 2025-09-29 17:29:08.811929

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '54ab19a5b23f'
down_revision = ('011_remove_nurse_role', '017_remove_legacy_templates', 'add_dedicated_patient_columns')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass