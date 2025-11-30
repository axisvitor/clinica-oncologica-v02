"""drop_plaintext_cpf

Remove deprecated plaintext CPF column for full LGPD compliance.

Revision ID: 024_drop_plaintext_cpf
Revises: 023_add_user_permissions
Create Date: 2025-11-26

This migration completes the LGPD compliance by removing the plaintext
CPF column that was kept for backward compatibility during migration 020.

IMPORTANT: This migration is IRREVERSIBLE. Ensure that:
1. Migration 020 (encrypt_cpf_lgpd) has been successfully applied
2. All CPF data has been encrypted to cpf_encrypted column
3. All queries use cpf_hash for lookups (not plaintext cpf)

Security Benefits:
- Eliminates plaintext PII storage
- Full LGPD Article 6 compliance for CPF data
- Reduces data breach exposure risk
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = '024_drop_plaintext_cpf'
down_revision = '023_add_user_permissions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Drop the plaintext CPF column.

    Pre-flight checks:
    1. Verify all patients with CPF have encrypted versions
    2. Verify no code depends on plaintext cpf column
    """
    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        # Pre-flight check: Ensure no patients have plaintext CPF without encrypted version
        result = session.execute(
            text("""
                SELECT COUNT(*)
                FROM patients
                WHERE cpf IS NOT NULL
                AND cpf_encrypted IS NULL
            """)
        )
        unencrypted_count = result.scalar()

        if unencrypted_count and unencrypted_count > 0:
            raise Exception(
                f"Cannot drop plaintext CPF column: {unencrypted_count} patients "
                "have plaintext CPF but no encrypted version. "
                "Run migration 020 first to encrypt all CPF data."
            )

        # Pre-flight check: Verify encrypted data exists
        result = session.execute(
            text("SELECT COUNT(*) FROM patients WHERE cpf_encrypted IS NOT NULL")
        )
        encrypted_count = result.scalar() or 0
        print(f"Verified {encrypted_count} patients with encrypted CPF data")

    finally:
        session.close()

    # Drop the plaintext CPF column
    # Note: Any old constraints referencing 'cpf' should have been dropped in migration 020
    op.drop_column('patients', 'cpf')

    print("Successfully dropped plaintext CPF column - LGPD compliance complete")


def downgrade() -> None:
    """
    IRREVERSIBLE MIGRATION

    This migration cannot be safely reversed because:
    1. Plaintext CPF data has been permanently deleted
    2. Decrypting all CPF values would require the encryption key
    3. Re-adding plaintext storage would violate LGPD compliance

    If rollback is absolutely necessary:
    1. Re-add the column as nullable
    2. Decrypt and restore data manually using the encryption service
    """
    # Re-add column as nullable (data will be empty)
    op.add_column(
        'patients',
        sa.Column('cpf', sa.String(11), nullable=True)
    )

    print("WARNING: Plaintext CPF column re-added but DATA IS LOST.")
    print("You must manually decrypt and restore CPF data if needed.")
    print("Consider LGPD compliance implications before storing plaintext CPF.")
