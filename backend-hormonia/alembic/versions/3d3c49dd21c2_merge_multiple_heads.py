"""merge_multiple_heads

Revision ID: 3d3c49dd21c2
Revises: 039_fulltext_search, 20251007_add_sending_status, create_audit_retention
Create Date: 2025-10-07 18:41:54.966061

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3d3c49dd21c2'
down_revision = ('039_fulltext_search', '20251007_add_sending_status', 'create_audit_retention')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass