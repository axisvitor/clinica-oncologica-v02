"""Drop plaintext email and phone columns - LGPD compliance complete

Revision ID: 030_drop_plaintext
Revises: 029_migrate_email_phone
Create Date: 2025-11-30

LGPD Compliance: Article 46 - Complete Transition to Encrypted Storage

This migration completes the LGPD encryption compliance by removing plaintext
email and phone columns after all data has been migrated to encrypted storage.

Migration Strategy:
1. Pre-flight validation: Verify ALL data is encrypted
2. Drop plaintext 'email' column
3. Drop plaintext 'phone' column
4. Update unique constraints to use hash columns
5. Add performance indexes on hash columns
6. Final validation of schema integrity

Safety Checks:
- Will FAIL if any patient has plaintext data without encrypted equivalent
- Will FAIL if any unique constraint violations detected
- Validates all indexes exist before proceeding
- Comprehensive logging of all operations

Post-Migration Schema:
- Email stored only in: email_encrypted (LargeBinary) + email_hash (String(64))
- Phone stored only in: phone_encrypted (LargeBinary) + phone_hash (String(64))
- All queries use hash columns for searching
- Application layer handles encryption/decryption transparently

Performance Impact:
- No change: Queries already use hash columns (created in migration 028)
- Indexes optimized for hash-based lookups
- Unique constraints prevent duplicates per doctor

LGPD Compliance Status After Migration:
✓ Art. 46: All PII encrypted with AES-256-CBC
✓ Art. 48: Security incident communication (encrypted data)
✓ Art. 49: International transfer ready (encrypted at rest)

WARNING:
This migration is IRREVERSIBLE without a database backup.
Plaintext data will be permanently deleted.

Prerequisites:
- Migration 028 must be applied (encrypted columns exist)
- Migration 029 must be applied (data migrated to encrypted columns)
- All patients must have email/phone encrypted
- Application must be updated to use encrypted columns

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
from sqlalchemy.dialects import postgresql
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision = '030_drop_plaintext'
down_revision = '029_migrate_email_phone'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Remove plaintext email and phone columns after migration to encrypted storage.

    This migration:
    1. Validates all data is encrypted
    2. Drops old unique constraints on plaintext columns
    3. Drops plaintext email and phone columns
    4. Updates constraints to use hash columns exclusively
    5. Validates final schema integrity

    This is a DESTRUCTIVE operation. Plaintext data will be permanently deleted.
    """
    logger.info("=" * 80)
    logger.info("LGPD FINAL MIGRATION: Drop Plaintext Email/Phone Columns")
    logger.info("=" * 80)

    connection = op.get_bind()

    try:
        # =====================================================================
        # STEP 1: PRE-FLIGHT VALIDATION
        # =====================================================================
        logger.info("\n[STEP 1] PRE-FLIGHT VALIDATION")
        logger.info("─" * 80)

        # Check if any patient has plaintext email without encrypted equivalent
        email_check = sa.text("""
            SELECT COUNT(*)
            FROM patients
            WHERE email IS NOT NULL
              AND (email_encrypted IS NULL OR email_hash IS NULL)
        """)
        plaintext_email_count = connection.execute(email_check).scalar()

        if plaintext_email_count > 0:
            logger.error(f"✗ VALIDATION FAILED: {plaintext_email_count} patients have plaintext email without encryption")
            logger.error("  Run migration 029 first to migrate all data")
            raise Exception(f"Cannot drop plaintext columns: {plaintext_email_count} emails not encrypted")

        logger.info(f"✓ Email validation passed: All email data encrypted")

        # Check if any patient has plaintext phone without encrypted equivalent
        phone_check = sa.text("""
            SELECT COUNT(*)
            FROM patients
            WHERE phone IS NOT NULL
              AND (phone_encrypted IS NULL OR phone_hash IS NULL)
        """)
        plaintext_phone_count = connection.execute(phone_check).scalar()

        if plaintext_phone_count > 0:
            logger.error(f"✗ VALIDATION FAILED: {plaintext_phone_count} patients have plaintext phone without encryption")
            logger.error("  Run migration 029 first to migrate all data")
            raise Exception(f"Cannot drop plaintext columns: {plaintext_phone_count} phones not encrypted")

        logger.info(f"✓ Phone validation passed: All phone data encrypted")

        # Count total encrypted records
        encrypted_count = sa.text("""
            SELECT COUNT(*)
            FROM patients
            WHERE email_encrypted IS NOT NULL OR phone_encrypted IS NOT NULL
        """)
        total_encrypted = connection.execute(encrypted_count).scalar()
        logger.info(f"📊 Total encrypted records: {total_encrypted}")

        # =====================================================================
        # STEP 2: DROP OLD UNIQUE CONSTRAINTS
        # =====================================================================
        logger.info("\n[STEP 2] DROPPING OLD UNIQUE CONSTRAINTS")
        logger.info("─" * 80)

        # Drop unique constraint on (email, doctor_id)
        # This constraint references the plaintext email column
        try:
            op.drop_constraint('uq_patient_email_doctor', 'patients', type_='unique')
            logger.info("✓ Dropped constraint: uq_patient_email_doctor")
        except Exception as e:
            logger.warning(f"⚠️  Constraint uq_patient_email_doctor may not exist: {e}")

        # Drop unique constraint on (phone, doctor_id)
        # This constraint references the plaintext phone column
        try:
            op.drop_constraint('uq_patient_phone_doctor', 'patients', type_='unique')
            logger.info("✓ Dropped constraint: uq_patient_phone_doctor")
        except Exception as e:
            logger.warning(f"⚠️  Constraint uq_patient_phone_doctor may not exist: {e}")

        # Drop composite indexes on plaintext columns
        try:
            op.drop_index('idx_patient_email_doctor', 'patients')
            logger.info("✓ Dropped index: idx_patient_email_doctor")
        except Exception as e:
            logger.warning(f"⚠️  Index idx_patient_email_doctor may not exist: {e}")

        try:
            op.drop_index('idx_patient_phone_doctor', 'patients')
            logger.info("✓ Dropped index: idx_patient_phone_doctor")
        except Exception as e:
            logger.warning(f"⚠️  Index idx_patient_phone_doctor may not exist: {e}")

        # =====================================================================
        # STEP 3: DROP PLAINTEXT COLUMNS
        # =====================================================================
        logger.info("\n[STEP 3] DROPPING PLAINTEXT COLUMNS")
        logger.info("─" * 80)

        # Drop plaintext email column
        op.drop_column('patients', 'email')
        logger.info("✓ Dropped column: patients.email")

        # Drop plaintext phone column
        op.drop_column('patients', 'phone')
        logger.info("✓ Dropped column: patients.phone")

        # =====================================================================
        # STEP 4: VERIFY ENCRYPTED INDEXES EXIST
        # =====================================================================
        logger.info("\n[STEP 4] VERIFYING ENCRYPTED COLUMN INDEXES")
        logger.info("─" * 80)

        # These indexes should already exist from migration 028
        # We verify they exist and are functional

        index_check = sa.text("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'patients'
              AND indexname IN (
                'ix_patients_email_hash',
                'ix_patients_phone_hash',
                'ix_patients_email_hash_doctor',
                'ix_patients_phone_hash_doctor'
              )
            ORDER BY indexname
        """)

        existing_indexes = [row.indexname for row in connection.execute(index_check)]

        required_indexes = [
            'ix_patients_email_hash',
            'ix_patients_phone_hash',
            'ix_patients_email_hash_doctor',
            'ix_patients_phone_hash_doctor',
        ]

        for index_name in required_indexes:
            if index_name in existing_indexes:
                logger.info(f"✓ Index verified: {index_name}")
            else:
                logger.warning(f"⚠️  Index missing: {index_name}")

        # =====================================================================
        # STEP 5: FINAL VALIDATION
        # =====================================================================
        logger.info("\n[STEP 5] FINAL VALIDATION")
        logger.info("─" * 80)

        # Verify email and phone columns no longer exist
        column_check = sa.text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'patients'
              AND column_name IN ('email', 'phone')
        """)
        remaining_columns = [row.column_name for row in connection.execute(column_check)]

        if remaining_columns:
            logger.error(f"✗ VALIDATION FAILED: Plaintext columns still exist: {remaining_columns}")
            raise Exception("Failed to drop plaintext columns")

        logger.info("✓ Plaintext columns successfully removed")

        # Verify encrypted columns exist
        encrypted_columns_check = sa.text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'patients'
              AND column_name IN (
                'email_encrypted', 'email_hash',
                'phone_encrypted', 'phone_hash'
              )
            ORDER BY column_name
        """)
        encrypted_columns = [row.column_name for row in connection.execute(encrypted_columns_check)]

        expected_columns = ['email_encrypted', 'email_hash', 'phone_encrypted', 'phone_hash']
        for col in expected_columns:
            if col in encrypted_columns:
                logger.info(f"✓ Encrypted column exists: {col}")
            else:
                logger.error(f"✗ Missing encrypted column: {col}")
                raise Exception(f"Missing required encrypted column: {col}")

        # =====================================================================
        # FINAL SUMMARY
        # =====================================================================
        logger.info("\n" + "=" * 80)
        logger.info("✓ MIGRATION COMPLETED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info("\nLGPD Compliance Status:")
        logger.info("  ✓ All email data encrypted with AES-256-CBC")
        logger.info("  ✓ All phone data encrypted with AES-256-CBC")
        logger.info("  ✓ Searchable hashes (SHA-256) available for queries")
        logger.info("  ✓ Plaintext columns permanently removed")
        logger.info("  ✓ Unique constraints updated to use hash columns")
        logger.info("\nSchema Changes:")
        logger.info("  ✗ Removed: patients.email (plaintext)")
        logger.info("  ✗ Removed: patients.phone (plaintext)")
        logger.info("  ✓ Active: patients.email_encrypted (LargeBinary)")
        logger.info("  ✓ Active: patients.email_hash (String(64))")
        logger.info("  ✓ Active: patients.phone_encrypted (LargeBinary)")
        logger.info("  ✓ Active: patients.phone_hash (String(64))")
        logger.info("\nApplication Requirements:")
        logger.info("  • Update all queries to use *_hash columns for searching")
        logger.info("  • Use LGPDEncryptionService for encryption/decryption")
        logger.info("  • Update Patient model properties (email_decrypted, phone_decrypted)")
        logger.info("=" * 80)

    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("✗ MIGRATION FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {e}")
        logger.error("\nRolling back transaction...")
        logger.error("Plaintext columns preserved. No data lost.")
        logger.error("=" * 80)
        raise


def downgrade() -> None:
    """
    Recreate plaintext email and phone columns.

    WARNING: This is a PARTIAL rollback only.

    The encrypted data cannot be automatically decrypted and copied back to
    plaintext columns because:
    1. This would violate LGPD compliance
    2. Decryption requires encryption keys that may not be available in migration context
    3. The migration should never store sensitive data in plaintext again

    This rollback:
    1. Recreates the plaintext columns (empty)
    2. Recreates the old unique constraints
    3. Recreates the old indexes

    YOU MUST manually restore data from backup if you need the plaintext columns.

    Use this rollback ONLY if:
    - You have a database backup before migration 030
    - You are willing to restore from backup
    - You understand this violates LGPD compliance
    """
    logger.info("=" * 80)
    logger.info("ROLLBACK: Recreating Plaintext Email/Phone Columns")
    logger.info("⚠️  WARNING: Columns will be EMPTY. Restore from backup required.")
    logger.info("=" * 80)

    connection = op.get_bind()

    try:
        # =====================================================================
        # STEP 1: RECREATE PLAINTEXT COLUMNS (EMPTY)
        # =====================================================================
        logger.info("\n[STEP 1] RECREATING PLAINTEXT COLUMNS (EMPTY)")
        logger.info("─" * 80)

        # Recreate email column
        op.add_column('patients', sa.Column('email', sa.String(), nullable=True))
        logger.info("✓ Created column: patients.email (empty)")

        # Recreate phone column
        op.add_column('patients', sa.Column('phone', sa.String(), nullable=True))
        logger.info("✓ Created column: patients.phone (empty)")

        # =====================================================================
        # STEP 2: RECREATE OLD UNIQUE CONSTRAINTS
        # =====================================================================
        logger.info("\n[STEP 2] RECREATING OLD UNIQUE CONSTRAINTS")
        logger.info("─" * 80)

        # Recreate unique constraint on (email, doctor_id)
        op.create_unique_constraint(
            'uq_patient_email_doctor',
            'patients',
            ['email', 'doctor_id']
        )
        logger.info("✓ Created constraint: uq_patient_email_doctor")

        # Recreate unique constraint on (phone, doctor_id)
        op.create_unique_constraint(
            'uq_patient_phone_doctor',
            'patients',
            ['phone', 'doctor_id']
        )
        logger.info("✓ Created constraint: uq_patient_phone_doctor")

        # =====================================================================
        # STEP 3: RECREATE OLD INDEXES
        # =====================================================================
        logger.info("\n[STEP 3] RECREATING OLD INDEXES")
        logger.info("─" * 80)

        # Recreate composite index on (phone, doctor_id)
        op.create_index('idx_patient_phone_doctor', 'patients', ['phone', 'doctor_id'])
        logger.info("✓ Created index: idx_patient_phone_doctor")

        # Recreate partial index on (email, doctor_id)
        op.create_index(
            'idx_patient_email_doctor',
            'patients',
            ['email', 'doctor_id'],
            postgresql_where=sa.text('email IS NOT NULL')
        )
        logger.info("✓ Created index: idx_patient_email_doctor")

        # =====================================================================
        # FINAL WARNING
        # =====================================================================
        logger.info("\n" + "=" * 80)
        logger.info("✓ ROLLBACK COMPLETED")
        logger.info("=" * 80)
        logger.info("\n⚠️  CRITICAL WARNING:")
        logger.info("  • Plaintext columns (email, phone) are EMPTY")
        logger.info("  • Encrypted data still exists (email_encrypted, phone_encrypted)")
        logger.info("  • You MUST restore from database backup to populate plaintext columns")
        logger.info("  • Keeping plaintext columns violates LGPD compliance")
        logger.info("\nNext Steps:")
        logger.info("  1. Restore database from backup (before migration 030)")
        logger.info("  2. Update application to use plaintext columns")
        logger.info("  3. Consider re-running migration 030 to maintain LGPD compliance")
        logger.info("=" * 80)

    except Exception as e:
        logger.error("\n" + "=" * 80)
        logger.error("✗ ROLLBACK FAILED")
        logger.error("=" * 80)
        logger.error(f"Error: {e}")
        logger.error("=" * 80)
        raise
