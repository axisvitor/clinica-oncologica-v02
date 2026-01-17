"""Encrypt email and phone columns for LGPD compliance

Revision ID: 028_encrypt_email_phone
Revises: 027_consolidate_duplicates
Create Date: 2025-11-26

LGPD Compliance: Article 46 - Security, Technical and Administrative Measures
This migration extends LGPD encryption compliance (started in migration 020 for CPF)
to email and phone fields.

Changes:
1. Add encrypted storage columns (email_encrypted, phone_encrypted) using AES-256
2. Add searchable hash columns (email_hash, phone_hash) for efficient queries
3. Create indexes on hash columns for performance
4. Create composite unique indexes with doctor_id for data integrity
5. Use partial indexes (WHERE ... IS NOT NULL) to allow NULL values

Security Architecture:
- Encryption: AES-256-CBC via PHIEncryptionService (same as CPF)
- Hashing: SHA-256 with application salt via SearchableHash
- Searchable: Deterministic hashing enables queries without decryption
- Performance: Hash-based indexes maintain query performance

Migration Strategy:
- Backward compatible: Keeps existing plaintext columns (email, phone)
- Gradual migration: Application layer handles both encrypted and plaintext
- Future migration (029+): Will populate encrypted columns from plaintext
- Future migration (030+): Will drop plaintext columns after full migration

Data Flow:
1. New records: Automatically encrypted at application layer
2. Existing records: Remain in plaintext until data migration
3. Queries: Use hash columns for encrypted data, direct match for plaintext
4. Display: Decryption on-demand at application layer

LGPD Articles Addressed:
- Art. 46: Technical and administrative security measures
- Art. 48: Communication of security incidents
- Art. 49: International data transfer requirements

Performance Impact:
- Minimal: 4 new columns (2 LargeBinary, 2 String)
- 4 new indexes (2 simple, 2 partial composite)
- No impact on existing queries (columns nullable)

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


# revision identifiers, used by Alembic.
revision = '028_encrypt_email_phone'
down_revision = '027_consolidate_duplicates'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add encrypted storage for email and phone fields.

    LGPD Compliance: Extends encryption strategy to all PII fields.

    Schema Changes:
    1. patients.email_encrypted (LargeBinary) - AES-256 encrypted email
    2. patients.email_hash (String(64)) - SHA-256 searchable hash
    3. patients.phone_encrypted (LargeBinary) - AES-256 encrypted phone
    4. patients.phone_hash (String(64)) - SHA-256 searchable hash

    Indexes Created:
    1. ix_patients_email_hash - Simple index for hash lookups
    2. ix_patients_phone_hash - Simple index for hash lookups
    3. ix_patients_email_hash_doctor - Composite unique (email_hash, doctor_id)
    4. ix_patients_phone_hash_doctor - Composite unique (phone_hash, doctor_id)

    All composite unique indexes use partial indexes (WHERE ... IS NOT NULL)
    to allow multiple NULL values while enforcing uniqueness for non-NULL.
    """
    # Add encrypted email columns
    op.add_column('patients', sa.Column('email_encrypted', sa.LargeBinary(), nullable=True))
    op.add_column('patients', sa.Column('email_hash', sa.String(64), nullable=True))

    # Add encrypted phone columns
    op.add_column('patients', sa.Column('phone_encrypted', sa.LargeBinary(), nullable=True))
    op.add_column('patients', sa.Column('phone_hash', sa.String(64), nullable=True))

    # Create simple indexes for hash lookups (non-unique for flexibility)
    op.create_index('ix_patients_email_hash', 'patients', ['email_hash'])
    op.create_index('ix_patients_phone_hash', 'patients', ['phone_hash'])

    # Create composite unique indexes with doctor_id for data integrity
    # Using partial indexes to allow NULL values
    op.create_index(
        'ix_patients_email_hash_doctor',
        'patients',
        ['email_hash', 'doctor_id'],
        unique=True,
        postgresql_where=sa.text('email_hash IS NOT NULL AND deleted_at IS NULL')
    )
    op.create_index(
        'ix_patients_phone_hash_doctor',
        'patients',
        ['phone_hash', 'doctor_id'],
        unique=True,
        postgresql_where=sa.text('phone_hash IS NOT NULL AND deleted_at IS NULL')
    )


def downgrade() -> None:
    """
    Remove encrypted email and phone storage.

    WARNING: This will permanently delete encrypted data.
    Only run this if you have backed up data or are in a development environment.

    Rollback Order:
    1. Drop composite unique indexes
    2. Drop simple indexes
    3. Drop encrypted columns
    """
    # Drop composite unique indexes first
    op.drop_index('ix_patients_phone_hash_doctor', table_name='patients')
    op.drop_index('ix_patients_email_hash_doctor', table_name='patients')

    # Drop simple indexes
    op.drop_index('ix_patients_phone_hash', table_name='patients')
    op.drop_index('ix_patients_email_hash', table_name='patients')

    # Drop encrypted columns
    op.drop_column('patients', 'phone_hash')
    op.drop_column('patients', 'phone_encrypted')
    op.drop_column('patients', 'email_hash')
    op.drop_column('patients', 'email_encrypted')
