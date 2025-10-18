"""Add idempotency_key to messages table

Revision ID: 001_add_idempotency_key
Revises:
Create Date: 2024-01-15 10:00:00.000000

CRITICAL FIX #5: Add idempotency_key field to messages table to prevent duplicate message sends.

This migration:
1. Adds idempotency_key column to messages table
2. Creates unique index on (patient_id, idempotency_key) to enforce uniqueness
3. Backfills existing messages with generated idempotency keys
4. Makes column NOT NULL after backfill

Safety:
- Backfills data before adding constraint
- Uses partial index (WHERE idempotency_key IS NOT NULL) for safety
- Handles rollback cleanly
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import hashlib
import uuid


# revision identifiers, used by Alembic.
revision = "001_add_idempotency_key"
down_revision = None
branch_labels = None
depends_on = None


def generate_idempotency_key(patient_id: str, content: str, created_at: str) -> str:
    """Generate idempotency key for existing messages."""
    components = f"{patient_id}:{content}:{created_at}"
    hash_digest = hashlib.sha256(components.encode("utf-8")).hexdigest()
    return f"msg_{hash_digest[:32]}"


def upgrade() -> None:
    """Add idempotency_key to messages table."""

    # Step 1: Add column as nullable first
    print("Step 1: Adding idempotency_key column as nullable...")
    op.add_column(
        "messages", sa.Column("idempotency_key", sa.String(length=255), nullable=True)
    )

    # Step 2: Backfill existing messages with generated idempotency keys
    print("Step 2: Backfilling idempotency keys for existing messages...")
    connection = op.get_bind()

    # Get all messages without idempotency_key
    result = connection.execute(
        sa.text("""
            SELECT id, patient_id, content, created_at
            FROM messages
            WHERE idempotency_key IS NULL
            ORDER BY created_at
        """)
    )

    messages = result.fetchall()
    print(f"Found {len(messages)} messages to backfill")

    # Update in batches
    batch_size = 1000
    for i in range(0, len(messages), batch_size):
        batch = messages[i : i + batch_size]

        for msg in batch:
            msg_id, patient_id, content, created_at = msg

            # Generate idempotency key
            idempotency_key = generate_idempotency_key(
                str(patient_id), content or "", str(created_at)
            )

            # Update message
            connection.execute(
                sa.text("""
                    UPDATE messages
                    SET idempotency_key = :idempotency_key
                    WHERE id = :id
                """),
                {"idempotency_key": idempotency_key, "id": msg_id},
            )

        if (i + batch_size) % 5000 == 0:
            print(f"Backfilled {i + batch_size} messages...")

    print(f"Backfilled {len(messages)} messages total")

    # Step 3: Create unique index (partial index for safety)
    print("Step 3: Creating unique index on (patient_id, idempotency_key)...")
    op.create_index(
        "idx_messages_patient_idempotency",
        "messages",
        ["patient_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    # Step 4: Add regular index on idempotency_key for lookups
    print("Step 4: Creating index on idempotency_key...")
    op.create_index(
        "idx_messages_idempotency_key", "messages", ["idempotency_key"], unique=False
    )

    # Step 5: Make column NOT NULL (all existing messages now have values)
    print("Step 5: Making idempotency_key NOT NULL...")
    op.alter_column(
        "messages",
        "idempotency_key",
        nullable=False,
        existing_type=sa.String(length=255),
    )

    print("[OK] Migration completed successfully!")


def downgrade() -> None:
    """Remove idempotency_key from messages table."""

    print("Rolling back: Removing idempotency_key...")

    # Step 1: Drop indexes
    print("Step 1: Dropping indexes...")
    op.drop_index("idx_messages_idempotency_key", "messages")
    op.drop_index("idx_messages_patient_idempotency", "messages")

    # Step 2: Drop column
    print("Step 2: Dropping idempotency_key column...")
    op.drop_column("messages", "idempotency_key")

    print("[OK] Rollback completed successfully!")
