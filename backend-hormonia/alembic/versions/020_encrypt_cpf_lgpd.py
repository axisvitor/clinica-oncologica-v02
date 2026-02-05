"""encrypt_cpf_lgpd

Add encrypted CPF columns for LGPD compliance

Revision ID: 020_encrypt_cpf_lgpd
Revises: 019_seed_welcome_message_template
Create Date: 2025-11-24

This migration adds encrypted CPF storage to comply with LGPD (Brazilian GDPR).
It adds two new columns:
1. cpf_encrypted: Stores AES-256 encrypted CPF
2. cpf_hash: Stores SHA-256 hash for searchable queries

The existing 'cpf' column is kept for backward compatibility during rollback.
After migration is stable, the plaintext column can be dropped in a future migration.

Security:
- AES-256-CBC encryption with PBKDF2 key derivation
- SHA-256 HMAC searchable hash
- Deterministic hashing enables searching without decryption

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
from sqlalchemy import text
from sqlalchemy.orm import Session

# revision identifiers, used by Alembic.
revision = '020_encrypt_cpf_lgpd'
down_revision = '019_seed_welcome_message_template'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add encrypted CPF columns and migrate existing data.

    Steps:
    1. Add cpf_encrypted and cpf_hash columns
    2. Create index on cpf_hash for fast lookups
    3. Migrate existing plaintext CPF data to encrypted format
    4. Update composite unique constraint to use cpf_hash
    """
    # Step 1: Add new columns
    op.add_column('patients', sa.Column('cpf_encrypted', sa.Text(), nullable=True))
    op.add_column('patients', sa.Column('cpf_hash', sa.String(64), nullable=True))

    # Step 2: Create index on cpf_hash for fast lookups
    op.create_index(
        'ix_patients_cpf_hash',
        'patients',
        ['cpf_hash'],
        unique=False
    )

    # Step 3: Migrate existing CPF data
    # This requires the encryption service to be available
    # We'll do this in Python to use our encryption service

    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        # Import encryption service
        from app.services.encryption import get_cpf_encryption_service

        service = get_cpf_encryption_service()

        # Query all patients with plaintext CPF
        result = session.execute(
            text("SELECT id, cpf FROM patients WHERE cpf IS NOT NULL AND cpf_encrypted IS NULL")
        )

        migrated_count = 0
        failed_count = 0

        for row in result:
            patient_id = row[0]
            plaintext_cpf = row[1]

            try:
                # Encrypt CPF
                encrypted_cpf, cpf_hash = service.encrypt_cpf(plaintext_cpf)

                # Update patient record
                session.execute(
                    text("""
                        UPDATE patients
                        SET cpf_encrypted = :encrypted, cpf_hash = :hash
                        WHERE id = :id
                    """),
                    {
                        'encrypted': encrypted_cpf,
                        'hash': cpf_hash,
                        'id': str(patient_id)
                    }
                )

                migrated_count += 1

            except Exception as e:
                print(f"Failed to encrypt CPF for patient {patient_id}: {e}")
                failed_count += 1
                # Continue with other records

        # Commit the migration
        session.commit()

        print(f"CPF encryption migration completed:")
        print(f"  - Successfully migrated: {migrated_count} records")
        print(f"  - Failed: {failed_count} records")

    except Exception as e:
        print(f"Migration error: {e}")
        session.rollback()
        raise
    finally:
        session.close()

    # Step 4: Update composite unique constraint
    # Drop old constraint using cpf plaintext
    op.drop_constraint('uq_patient_cpf_doctor', 'patients', type_='unique')

    # Create new constraint using cpf_hash
    op.create_unique_constraint(
        'uq_patient_cpf_hash_doctor',
        'patients',
        ['cpf_hash', 'doctor_id']
    )

    # Step 5: Drop old index on plaintext cpf
    op.drop_index('idx_patient_cpf_doctor', 'patients')

    # Create new composite index for fast lookups
    op.create_index(
        'ix_patients_cpf_hash_doctor',
        'patients',
        ['cpf_hash', 'doctor_id'],
        unique=False,
        postgresql_where=text('cpf_hash IS NOT NULL')
    )


def downgrade() -> None:
    """
    Rollback CPF encryption changes.

    WARNING: This will restore plaintext CPF storage.
    Use only if absolutely necessary for rollback.
    """
    # Drop new constraint
    op.drop_constraint('uq_patient_cpf_hash_doctor', 'patients', type_='unique')

    # Restore old constraint
    op.create_unique_constraint(
        'uq_patient_cpf_doctor',
        'patients',
        ['cpf', 'doctor_id']
    )

    # Drop new indexes
    op.drop_index('ix_patients_cpf_hash_doctor', 'patients')
    op.drop_index('ix_patients_cpf_hash', 'patients')

    # Restore old index
    op.create_index(
        'idx_patient_cpf_doctor',
        'patients',
        ['cpf', 'doctor_id'],
        postgresql_where=text('cpf IS NOT NULL')
    )

    # Drop encrypted columns
    # Note: Plaintext CPF data is preserved in the 'cpf' column
    op.drop_column('patients', 'cpf_hash')
    op.drop_column('patients', 'cpf_encrypted')

    print("WARNING: CPF encryption has been rolled back. Data is now stored in plaintext.")
