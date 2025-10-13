"""Add cascade delete on messages.patient_id

Revision ID: 7b8acbbd0d3b
Revises: 243a5b025382
Create Date: 2025-10-13 22:05:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "7b8acbbd0d3b"
down_revision = "243a5b025382"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE messages
        DROP CONSTRAINT IF EXISTS messages_patient_id_fkey,
        ADD CONSTRAINT messages_patient_id_fkey
        FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE messages
        DROP CONSTRAINT IF EXISTS messages_patient_id_fkey,
        ADD CONSTRAINT messages_patient_id_fkey
        FOREIGN KEY (patient_id) REFERENCES patients(id)
        """
    )
