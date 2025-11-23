#!/usr/bin/env python3
"""
Proof of Concept: Encrypt Patient.email field.

This script demonstrates the encryption migration process for one field
before rolling out to all 58 PHI/PII fields.

Process:
1. Read plaintext email from patients table
2. Encrypt each email using EncryptionService
3. Generate searchable hash using SearchableHash
4. Write encrypted data to email_encrypted and email_hash columns
5. Verify integrity

Usage:
    python scripts/encrypt_patient_email_poc.py --dry-run
    python scripts/encrypt_patient_email_poc.py
"""

import os
import sys
import argparse
import logging
from typing import List

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.encryption import EncryptionService
from app.core.searchable_hash import SearchableHash

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_database_url() -> str:
    """Get database URL from environment."""
    return os.getenv(
        "DATABASE_URL",
        "postgresql://hormonia_user:hormonia_pass@localhost:5432/hormonia_db"
    )


def encrypt_patient_emails(dry_run: bool = False, batch_size: int = 1000):
    """
    Encrypt patient email fields.

    Args:
        dry_run: If True, show what would be done without making changes
        batch_size: Number of records to process per batch
    """
    # Initialize services
    encryption_service = EncryptionService()

    # Connect to database
    engine = create_engine(get_database_url())
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Count total patients with email
        result = session.execute(
            text("SELECT COUNT(*) FROM patients WHERE email IS NOT NULL")
        )
        total = result.scalar()
        logger.info(f"Found {total} patients with email to encrypt")

        if dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
            # Show sample
            result = session.execute(
                text("SELECT id, email FROM patients WHERE email IS NOT NULL LIMIT 5")
            )
            logger.info("Sample patients:")
            for row in result:
                email_hash = SearchableHash.hash_email(row[1])
                logger.info(f"  ID: {row[0]}, Email: {row[1][:3]}***@***, Hash: {email_hash[:16]}...")
            return

        # Process in batches
        encrypted_count = 0
        for offset in range(0, total, batch_size):
            # Fetch batch
            result = session.execute(
                text("""
                    SELECT id, email
                    FROM patients
                    WHERE email IS NOT NULL
                      AND email_encrypted IS NULL
                    LIMIT :limit OFFSET :offset
                """),
                {"limit": batch_size, "offset": offset}
            )
            batch = result.fetchall()

            if not batch:
                break

            # Encrypt batch
            for patient_id, email in batch:
                try:
                    # Encrypt email
                    encrypted_email = encryption_service.encrypt(email)

                    # Generate searchable hash
                    email_hash = SearchableHash.hash_email(email)

                    # Update database
                    session.execute(
                        text("""
                            UPDATE patients
                            SET email_encrypted = :encrypted,
                                email_hash = :hash
                            WHERE id = :id
                        """),
                        {
                            "encrypted": encrypted_email,
                            "hash": email_hash,
                            "id": patient_id
                        }
                    )
                    encrypted_count += 1

                except Exception as e:
                    logger.error(f"Failed to encrypt email for patient {patient_id}: {e}")
                    raise

            # Commit batch
            session.commit()
            logger.info(f"Encrypted {encrypted_count}/{total} patient emails...")

        logger.info(f"✅ Successfully encrypted {encrypted_count} patient emails")

        # Verify integrity
        verify_encryption(session, encrypted_count)

    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        session.rollback()
        raise

    finally:
        session.close()


def verify_encryption(session, expected_count: int):
    """
    Verify encryption integrity.

    Args:
        session: Database session
        expected_count: Expected number of encrypted records
    """
    logger.info("Verifying encryption integrity...")

    # Check encrypted count
    result = session.execute(
        text("SELECT COUNT(*) FROM patients WHERE email_encrypted IS NOT NULL")
    )
    encrypted_count = result.scalar()

    if encrypted_count != expected_count:
        raise ValueError(f"Expected {expected_count} encrypted emails, found {encrypted_count}")

    # Check hash count
    result = session.execute(
        text("SELECT COUNT(*) FROM patients WHERE email_hash IS NOT NULL")
    )
    hash_count = result.scalar()

    if hash_count != expected_count:
        raise ValueError(f"Expected {expected_count} email hashes, found {hash_count}")

    # Sample decryption test
    encryption_service = EncryptionService()
    result = session.execute(
        text("""
            SELECT id, email, email_encrypted, email_hash
            FROM patients
            WHERE email_encrypted IS NOT NULL
            LIMIT 5
        """)
    )

    errors = []
    for patient_id, email, email_encrypted, email_hash in result:
        try:
            # Decrypt
            decrypted = encryption_service.decrypt(email_encrypted)

            # Verify matches original
            if decrypted != email:
                errors.append(f"Patient {patient_id}: Decryption mismatch")

            # Verify hash
            expected_hash = SearchableHash.hash_email(email)
            if email_hash != expected_hash:
                errors.append(f"Patient {patient_id}: Hash mismatch")

        except Exception as e:
            errors.append(f"Patient {patient_id}: {e}")

    if errors:
        logger.error(f"Verification failed with {len(errors)} errors:")
        for error in errors:
            logger.error(f"  - {error}")
        raise ValueError("Encryption verification failed")

    logger.info("✅ Encryption verification passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Encrypt patient email fields (POC)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1000,
        help="Number of records to process per batch (default: 1000)"
    )

    args = parser.parse_args()

    try:
        encrypt_patient_emails(dry_run=args.dry_run, batch_size=args.batch_size)
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1)
