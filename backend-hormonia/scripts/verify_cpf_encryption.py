#!/usr/bin/env python3
"""
CPF Encryption Verification Script

This script verifies that CPF encryption is working correctly.
Run after migration to ensure everything is set up properly.

Usage:
    python scripts/verify_cpf_encryption.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.encryption import get_cpf_encryption_service
from app.database import SessionLocal
from app.models.patient import Patient
from sqlalchemy import func


def test_encryption_service():
    """Test CPF encryption service functionality"""
    print("=" * 60)
    print("TESTING CPF ENCRYPTION SERVICE")
    print("=" * 60)

    service = get_cpf_encryption_service()

    # Test 1: Basic encryption/decryption
    print("\n[1/5] Testing basic encryption/decryption...")
    cpf = "12345678901"
    encrypted, hash_val = service.encrypt_cpf(cpf)

    assert encrypted.startswith("encrypted:"), "Encrypted value should have prefix"
    assert len(hash_val) == 64, "Hash should be 64 characters"

    decrypted = service.decrypt_cpf(encrypted)
    assert decrypted == cpf, "Decryption should return original CPF"
    print("   ✅ Encryption/decryption working")

    # Test 2: Format normalization
    print("\n[2/5] Testing format normalization...")
    formatted_cpf = "123.456.789-01"
    hash1 = service.hash_cpf_for_search(formatted_cpf)
    hash2 = service.hash_cpf_for_search(cpf)
    assert hash1 == hash2, "Same CPF with different formats should have same hash"
    print("   ✅ Format normalization working")

    # Test 3: Display formatting
    print("\n[3/5] Testing display formatting...")
    formatted = service.format_cpf_for_display(cpf, mask=False)
    assert formatted == "123.456.789-01", "Should format with dots and dash"

    masked = service.format_cpf_for_display(cpf, mask=True)
    assert "789" in masked, "Masked should show middle digits"
    assert "***" in masked, "Masked should have asterisks"
    print("   ✅ Display formatting working")

    # Test 4: Validation
    print("\n[4/5] Testing CPF validation...")
    assert service._validate_cpf_format("12345678901"), "Valid CPF should pass"
    assert not service._validate_cpf_format("123"), "Invalid length should fail"
    assert not service._validate_cpf_format("00000000000"), "All zeros should fail"
    print("   ✅ CPF validation working")

    # Test 5: Different encryptions same hash
    print("\n[5/5] Testing deterministic hashing...")
    enc1, hash_a = service.encrypt_cpf(cpf)
    enc2, hash_b = service.encrypt_cpf(cpf)
    assert enc1 != enc2, "Different encryptions (random IV)"
    assert hash_a == hash_b, "Same hash (deterministic)"
    print("   ✅ Deterministic hashing working")

    print("\n" + "=" * 60)
    print("✅ ALL ENCRYPTION SERVICE TESTS PASSED")
    print("=" * 60)
    return True


def test_database_migration():
    """Test database migration status"""
    print("\n" + "=" * 60)
    print("CHECKING DATABASE MIGRATION STATUS")
    print("=" * 60)

    db = SessionLocal()

    try:
        # Check if columns exist
        print("\n[1/4] Checking if encrypted columns exist...")
        result = db.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'patients'
            AND column_name IN ('cpf_encrypted', 'cpf_hash')
            ORDER BY column_name;
        """)
        columns = [row[0] for row in result]

        if 'cpf_encrypted' in columns and 'cpf_hash' in columns:
            print("   ✅ Encrypted columns exist")
        else:
            print("   ❌ Encrypted columns missing!")
            print(f"   Found columns: {columns}")
            return False

        # Check if indexes exist
        print("\n[2/4] Checking if indexes exist...")
        result = db.execute("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'patients'
            AND indexname LIKE '%cpf_hash%'
            ORDER BY indexname;
        """)
        indexes = [row[0] for row in result]

        if indexes:
            print(f"   ✅ Found {len(indexes)} CPF hash index(es)")
            for idx in indexes:
                print(f"      - {idx}")
        else:
            print("   ⚠️  No CPF hash indexes found (may impact performance)")

        # Check migration status
        print("\n[3/4] Checking migration status...")
        total = db.query(func.count(Patient.id)).scalar()

        if total == 0:
            print("   ℹ️  No patients in database yet")
            return True

        encrypted = db.query(func.count(Patient.id)).filter(
            Patient.cpf_encrypted.isnot(None)
        ).scalar()

        has_cpf = db.query(func.count(Patient.id)).filter(
            Patient.cpf.isnot(None)
        ).scalar()

        print(f"   Total patients: {total}")
        print(f"   With encrypted CPF: {encrypted}")
        print(f"   With plaintext CPF: {has_cpf}")

        if encrypted > 0:
            print("   ✅ Migration has encrypted records")
        else:
            print("   ⚠️  No encrypted records yet")

        # Test patient model
        print("\n[4/4] Testing Patient model methods...")
        patient = db.query(Patient).filter(
            Patient.cpf_encrypted.isnot(None)
        ).first()

        if patient:
            cpf = patient.cpf_decrypted
            if cpf:
                print(f"   ✅ cpf_decrypted working: {cpf[:3]}...{cpf[-2:]}")
            else:
                print("   ❌ cpf_decrypted returned None")
                return False

            display = patient.get_cpf_display(mask=True)
            print(f"   ✅ get_cpf_display working: {display}")
        else:
            print("   ℹ️  No patients with encrypted CPF to test")

        print("\n" + "=" * 60)
        print("✅ DATABASE MIGRATION VERIFIED")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ Error checking database: {e}")
        return False
    finally:
        db.close()


def test_environment_config():
    """Test environment configuration"""
    print("\n" + "=" * 60)
    print("CHECKING ENVIRONMENT CONFIGURATION")
    print("=" * 60)

    errors = []

    # Check PHI_ENCRYPTION_KEY
    phi_key = os.getenv("PHI_ENCRYPTION_KEY")
    if not phi_key:
        errors.append("PHI_ENCRYPTION_KEY not set")
        print("   ❌ PHI_ENCRYPTION_KEY not set")
    elif len(phi_key) < 32:
        errors.append("PHI_ENCRYPTION_KEY too short (should be 32+ characters)")
        print("   ⚠️  PHI_ENCRYPTION_KEY seems too short")
    else:
        print("   ✅ PHI_ENCRYPTION_KEY configured")

    # Check HASH_SALT
    hash_salt = os.getenv("HASH_SALT")
    if not hash_salt:
        errors.append("HASH_SALT not set")
        print("   ❌ HASH_SALT not set")
    elif len(hash_salt) < 32:
        errors.append("HASH_SALT too short (should be 32+ characters)")
        print("   ⚠️  HASH_SALT seems too short")
    else:
        print("   ✅ HASH_SALT configured")

    if errors:
        print("\n" + "=" * 60)
        print("⚠️  ENVIRONMENT ISSUES FOUND")
        print("=" * 60)
        for error in errors:
            print(f"   - {error}")
        print("\nGenerate keys with:")
        print("   python -c 'import secrets; print(secrets.token_hex(32))'")
        return False
    else:
        print("\n" + "=" * 60)
        print("✅ ENVIRONMENT CONFIGURATION OK")
        print("=" * 60)
        return True


def main():
    """Run all verification tests"""
    print("\n" + "=" * 60)
    print("CPF ENCRYPTION VERIFICATION")
    print("=" * 60)

    results = {
        "environment": False,
        "service": False,
        "database": False
    }

    # Test 1: Environment
    try:
        results["environment"] = test_environment_config()
    except Exception as e:
        print(f"\n❌ Environment check failed: {e}")

    # Test 2: Service
    try:
        results["service"] = test_encryption_service()
    except Exception as e:
        print(f"\n❌ Service test failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 3: Database
    try:
        results["database"] = test_database_migration()
    except Exception as e:
        print(f"\n❌ Database check failed: {e}")
        import traceback
        traceback.print_exc()

    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    print(f"   Environment Config: {'✅ PASS' if results['environment'] else '❌ FAIL'}")
    print(f"   Encryption Service: {'✅ PASS' if results['service'] else '❌ FAIL'}")
    print(f"   Database Migration: {'✅ PASS' if results['database'] else '❌ FAIL'}")
    print("=" * 60)

    if all(results.values()):
        print("\n🎉 ALL CHECKS PASSED - CPF ENCRYPTION IS READY!")
        return 0
    else:
        print("\n⚠️  SOME CHECKS FAILED - PLEASE REVIEW ERRORS ABOVE")
        return 1


if __name__ == "__main__":
    sys.exit(main())
