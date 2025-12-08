#!/usr/bin/env python3
"""
Pre-Migration 030 Validation Script

This script validates that all LGPD-sensitive data (email, phone, cpf)
has been properly encrypted before running migration 030 which drops
the plaintext columns.

CRITICAL: Run this BEFORE executing migration 030 (drop_plaintext_columns)

Usage:
    python scripts/validate_pre_migration_030.py [--fix] [--dry-run]

Options:
    --fix       Attempt to encrypt any remaining plaintext data
    --dry-run   Only report issues without making changes
    --verbose   Show detailed output for each record
"""

import sys
import os
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker


def get_database_url() -> str:
    """Get database URL from environment."""
    from dotenv import load_dotenv
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL not found. Set it in .env or environment."
        )
    return database_url


def create_session():
    """Create database session."""
    database_url = get_database_url()
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session(), engine


class PreMigration030Validator:
    """Validator for migration 030 readiness."""

    def __init__(self, session, engine, verbose: bool = False):
        self.session = session
        self.engine = engine
        self.verbose = verbose
        self.issues: List[Dict[str, Any]] = []
        self.stats = {
            'total_patients': 0,
            'encrypted_email': 0,
            'encrypted_phone': 0,
            'encrypted_cpf': 0,
            'plaintext_email': 0,
            'plaintext_phone': 0,
            'plaintext_cpf': 0,
            'hash_email': 0,
            'hash_phone': 0,
            'hash_cpf': 0,
            'missing_hash_email': 0,
            'missing_hash_phone': 0,
            'missing_hash_cpf': 0,
        }

    def check_column_exists(self, table: str, column: str) -> bool:
        """Check if column exists in table."""
        inspector = inspect(self.engine)
        columns = [c['name'] for c in inspector.get_columns(table)]
        return column in columns

    def run_all_checks(self) -> Tuple[bool, Dict]:
        """Run all pre-migration validations."""
        print("\n" + "=" * 60)
        print("PRE-MIGRATION 030 VALIDATION")
        print("=" * 60)
        print(f"Started at: {datetime.now().isoformat()}")
        print()

        checks_passed = True

        # Check 1: Verify required columns exist
        print("\n[1/6] Checking required columns...")
        if not self._check_required_columns():
            checks_passed = False

        # Check 2: Count total records
        print("\n[2/6] Counting patient records...")
        self._count_patients()

        # Check 3: Validate encrypted columns
        print("\n[3/6] Validating encrypted columns...")
        if not self._validate_encrypted_columns():
            checks_passed = False

        # Check 4: Validate hash columns
        print("\n[4/6] Validating hash columns...")
        if not self._validate_hash_columns():
            checks_passed = False

        # Check 5: Check for plaintext data
        print("\n[5/6] Checking for plaintext data...")
        if not self._check_plaintext_data():
            checks_passed = False

        # Check 6: Validate unique constraints readiness
        print("\n[6/6] Validating unique constraint readiness...")
        if not self._check_unique_constraints():
            checks_passed = False

        return checks_passed, self.stats

    def _check_required_columns(self) -> bool:
        """Verify all required columns exist."""
        required = {
            'patients': [
                # Encrypted columns (LGPD)
                ('email_encrypted', 'LGPD encrypted email'),
                ('phone_encrypted', 'LGPD encrypted phone'),
                ('cpf_encrypted', 'LGPD encrypted CPF'),
                # Hash columns (for searches)
                ('email_hash', 'Email search hash'),
                ('phone_hash', 'Phone search hash'),
                ('cpf_hash', 'CPF search hash'),
            ]
        }

        all_exist = True
        for table, columns in required.items():
            for col_name, description in columns:
                exists = self.check_column_exists(table, col_name)
                status = "✅" if exists else "❌"
                print(f"  {status} {table}.{col_name} ({description})")
                if not exists:
                    all_exist = False
                    self.issues.append({
                        'type': 'missing_column',
                        'table': table,
                        'column': col_name,
                        'description': description
                    })

        return all_exist

    def _count_patients(self) -> None:
        """Count total patient records."""
        result = self.session.execute(
            text("SELECT COUNT(*) FROM patients")
        ).scalar()
        self.stats['total_patients'] = result
        print(f"  Total patients: {result}")

    def _validate_encrypted_columns(self) -> bool:
        """Validate that encrypted columns have data."""
        valid = True

        # Check email_encrypted
        query = text("""
            SELECT COUNT(*) FROM patients
            WHERE email_encrypted IS NOT NULL
            AND email_encrypted != ''
        """)
        count = self.session.execute(query).scalar()
        self.stats['encrypted_email'] = count

        query_total = text("""
            SELECT COUNT(*) FROM patients
            WHERE email IS NOT NULL AND email != ''
        """)
        total_with_email = self.session.execute(query_total).scalar()

        if count < total_with_email:
            valid = False
            missing = total_with_email - count
            print(f"  ❌ email_encrypted: {count}/{total_with_email} "
                  f"(missing {missing})")
            self.issues.append({
                'type': 'unencrypted_data',
                'field': 'email',
                'count': missing
            })
        else:
            print(f"  ✅ email_encrypted: {count}/{total_with_email}")

        # Check phone_encrypted
        query = text("""
            SELECT COUNT(*) FROM patients
            WHERE phone_encrypted IS NOT NULL
            AND phone_encrypted != ''
        """)
        count = self.session.execute(query).scalar()
        self.stats['encrypted_phone'] = count

        query_total = text("""
            SELECT COUNT(*) FROM patients
            WHERE phone IS NOT NULL AND phone != ''
        """)
        total_with_phone = self.session.execute(query_total).scalar()

        if count < total_with_phone:
            valid = False
            missing = total_with_phone - count
            print(f"  ❌ phone_encrypted: {count}/{total_with_phone} "
                  f"(missing {missing})")
            self.issues.append({
                'type': 'unencrypted_data',
                'field': 'phone',
                'count': missing
            })
        else:
            print(f"  ✅ phone_encrypted: {count}/{total_with_phone}")

        # Check cpf_encrypted
        query = text("""
            SELECT COUNT(*) FROM patients
            WHERE cpf_encrypted IS NOT NULL
            AND cpf_encrypted != ''
        """)
        count = self.session.execute(query).scalar()
        self.stats['encrypted_cpf'] = count

        query_total = text("""
            SELECT COUNT(*) FROM patients
            WHERE cpf IS NOT NULL AND cpf != ''
        """)
        total_with_cpf = self.session.execute(query_total).scalar()

        if count < total_with_cpf:
            valid = False
            missing = total_with_cpf - count
            print(f"  ❌ cpf_encrypted: {count}/{total_with_cpf} "
                  f"(missing {missing})")
            self.issues.append({
                'type': 'unencrypted_data',
                'field': 'cpf',
                'count': missing
            })
        else:
            print(f"  ✅ cpf_encrypted: {count}/{total_with_cpf}")

        return valid

    def _validate_hash_columns(self) -> bool:
        """Validate that hash columns are populated."""
        valid = True

        # Email hash
        query = text("""
            SELECT COUNT(*) FROM patients
            WHERE email_hash IS NOT NULL
            AND email_hash != ''
        """)
        count = self.session.execute(query).scalar()
        self.stats['hash_email'] = count

        query_total = text("""
            SELECT COUNT(*) FROM patients
            WHERE email IS NOT NULL AND email != ''
        """)
        total = self.session.execute(query_total).scalar()

        if count < total:
            missing = total - count
            self.stats['missing_hash_email'] = missing
            print(f"  ⚠️  email_hash: {count}/{total} (missing {missing})")
            self.issues.append({
                'type': 'missing_hash',
                'field': 'email',
                'count': missing
            })
            valid = False
        else:
            print(f"  ✅ email_hash: {count}/{total}")

        # Phone hash
        query = text("""
            SELECT COUNT(*) FROM patients
            WHERE phone_hash IS NOT NULL
            AND phone_hash != ''
        """)
        count = self.session.execute(query).scalar()
        self.stats['hash_phone'] = count

        query_total = text("""
            SELECT COUNT(*) FROM patients
            WHERE phone IS NOT NULL AND phone != ''
        """)
        total = self.session.execute(query_total).scalar()

        if count < total:
            missing = total - count
            self.stats['missing_hash_phone'] = missing
            print(f"  ⚠️  phone_hash: {count}/{total} (missing {missing})")
            self.issues.append({
                'type': 'missing_hash',
                'field': 'phone',
                'count': missing
            })
            valid = False
        else:
            print(f"  ✅ phone_hash: {count}/{total}")

        # CPF hash
        query = text("""
            SELECT COUNT(*) FROM patients
            WHERE cpf_hash IS NOT NULL
            AND cpf_hash != ''
        """)
        count = self.session.execute(query).scalar()
        self.stats['hash_cpf'] = count

        query_total = text("""
            SELECT COUNT(*) FROM patients
            WHERE cpf IS NOT NULL AND cpf != ''
        """)
        total = self.session.execute(query_total).scalar()

        if count < total:
            missing = total - count
            self.stats['missing_hash_cpf'] = missing
            print(f"  ⚠️  cpf_hash: {count}/{total} (missing {missing})")
            self.issues.append({
                'type': 'missing_hash',
                'field': 'cpf',
                'count': missing
            })
            valid = False
        else:
            print(f"  ✅ cpf_hash: {count}/{total}")

        return valid

    def _check_plaintext_data(self) -> bool:
        """Check that plaintext columns can be safely dropped."""
        valid = True

        # Get records where plaintext exists but encrypted doesn't
        query = text("""
            SELECT id, name, email, phone
            FROM patients
            WHERE (email IS NOT NULL AND email != '' AND email_encrypted IS NULL)
               OR (phone IS NOT NULL AND phone != '' AND phone_encrypted IS NULL)
            LIMIT 10
        """)
        results = self.session.execute(query).fetchall()

        if results:
            valid = False
            print(f"  ❌ Found {len(results)} records with plaintext but no encryption:")
            for row in results[:5]:
                print(f"      Patient ID: {row[0]}, Name: {row[1]}")
            if len(results) > 5:
                print(f"      ... and {len(results) - 5} more")
            self.issues.append({
                'type': 'plaintext_without_encrypted',
                'count': len(results)
            })
        else:
            print("  ✅ No orphan plaintext data found")

        return valid

    def _check_unique_constraints(self) -> bool:
        """Check for potential unique constraint violations after migration."""
        valid = True

        # Check for duplicate email hashes per doctor
        query = text("""
            SELECT email_hash, doctor_id, COUNT(*) as cnt
            FROM patients
            WHERE email_hash IS NOT NULL
            GROUP BY email_hash, doctor_id
            HAVING COUNT(*) > 1
        """)
        results = self.session.execute(query).fetchall()

        if results:
            valid = False
            print(f"  ❌ Found {len(results)} duplicate email_hash per doctor")
            self.issues.append({
                'type': 'duplicate_hash',
                'field': 'email_hash',
                'count': len(results)
            })
        else:
            print("  ✅ No duplicate email_hash per doctor")

        # Check for duplicate phone hashes per doctor
        query = text("""
            SELECT phone_hash, doctor_id, COUNT(*) as cnt
            FROM patients
            WHERE phone_hash IS NOT NULL
            GROUP BY phone_hash, doctor_id
            HAVING COUNT(*) > 1
        """)
        results = self.session.execute(query).fetchall()

        if results:
            valid = False
            print(f"  ❌ Found {len(results)} duplicate phone_hash per doctor")
            self.issues.append({
                'type': 'duplicate_hash',
                'field': 'phone_hash',
                'count': len(results)
            })
        else:
            print("  ✅ No duplicate phone_hash per doctor")

        # Check for duplicate CPF hashes per doctor
        query = text("""
            SELECT cpf_hash, doctor_id, COUNT(*) as cnt
            FROM patients
            WHERE cpf_hash IS NOT NULL
            GROUP BY cpf_hash, doctor_id
            HAVING COUNT(*) > 1
        """)
        results = self.session.execute(query).fetchall()

        if results:
            valid = False
            print(f"  ❌ Found {len(results)} duplicate cpf_hash per doctor")
            self.issues.append({
                'type': 'duplicate_hash',
                'field': 'cpf_hash',
                'count': len(results)
            })
        else:
            print("  ✅ No duplicate cpf_hash per doctor")

        return valid

    def fix_missing_encryption(self) -> int:
        """Attempt to encrypt any plaintext data that's missing encryption."""
        try:
            from app.services.encryption import get_unified_encryption_service
            from app.services.encryption.unified_encryption_service import FieldType
        except ImportError:
            print("  ❌ Cannot import encryption service")
            return 0

        encryption = get_unified_encryption_service()
        fixed = 0

        # Fix missing email encryption
        query = text("""
            SELECT id, email FROM patients
            WHERE email IS NOT NULL
            AND email != ''
            AND (email_encrypted IS NULL OR email_hash IS NULL)
        """)
        results = self.session.execute(query).fetchall()

        for row in results:
            patient_id, email = row
            try:
                encrypted, email_hash = encryption.encrypt_email(email)
                self.session.execute(
                    text("""
                        UPDATE patients
                        SET email_encrypted = :encrypted,
                            email_hash = :hash
                        WHERE id = :id
                    """),
                    {'id': patient_id, 'encrypted': encrypted, 'hash': email_hash}
                )
                fixed += 1
            except Exception as e:
                print(f"  ⚠️  Failed to encrypt email for patient {patient_id}: {e}")

        # Fix missing phone encryption
        query = text("""
            SELECT id, phone FROM patients
            WHERE phone IS NOT NULL
            AND phone != ''
            AND (phone_encrypted IS NULL OR phone_hash IS NULL)
        """)
        results = self.session.execute(query).fetchall()

        for row in results:
            patient_id, phone = row
            try:
                encrypted, phone_hash = encryption.encrypt_phone(phone)
                self.session.execute(
                    text("""
                        UPDATE patients
                        SET phone_encrypted = :encrypted,
                            phone_hash = :hash
                        WHERE id = :id
                    """),
                    {'id': patient_id, 'encrypted': encrypted, 'hash': phone_hash}
                )
                fixed += 1
            except Exception as e:
                print(f"  ⚠️  Failed to encrypt phone for patient {patient_id}: {e}")

        if fixed > 0:
            self.session.commit()

        return fixed

    def print_summary(self, passed: bool) -> None:
        """Print validation summary."""
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)

        print(f"\nTotal Patients: {self.stats['total_patients']}")
        print("\nEncryption Status:")
        print(f"  Email: {self.stats['encrypted_email']} encrypted")
        print(f"  Phone: {self.stats['encrypted_phone']} encrypted")
        print(f"  CPF:   {self.stats['encrypted_cpf']} encrypted")

        print("\nHash Status:")
        print(f"  Email: {self.stats['hash_email']} hashed")
        print(f"  Phone: {self.stats['hash_phone']} hashed")
        print(f"  CPF:   {self.stats['hash_cpf']} hashed")

        if self.issues:
            print(f"\n⚠️  ISSUES FOUND: {len(self.issues)}")
            for issue in self.issues:
                print(f"  - {issue['type']}: {issue}")

        print("\n" + "=" * 60)
        if passed:
            print("✅ VALIDATION PASSED - Safe to run migration 030")
        else:
            print("❌ VALIDATION FAILED - DO NOT run migration 030")
            print("\nFix the issues above before proceeding.")
            print("You can use --fix flag to attempt automatic fixes.")
        print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description='Validate readiness for migration 030 (drop plaintext columns)'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Attempt to fix missing encryption'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Only report issues, do not make changes'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output'
    )

    args = parser.parse_args()

    try:
        session, engine = create_session()
        validator = PreMigration030Validator(session, engine, args.verbose)

        passed, stats = validator.run_all_checks()

        if not passed and args.fix and not args.dry_run:
            print("\n🔧 Attempting to fix issues...")
            fixed = validator.fix_missing_encryption()
            print(f"  Fixed {fixed} records")

            # Re-run validation
            print("\n🔄 Re-running validation after fixes...")
            validator = PreMigration030Validator(session, engine, args.verbose)
            passed, stats = validator.run_all_checks()

        validator.print_summary(passed)

        session.close()

        return 0 if passed else 1

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
