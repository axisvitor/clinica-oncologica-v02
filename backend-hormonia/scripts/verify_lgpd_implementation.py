#!/usr/bin/env python3
"""
LGPD Implementation Verification Script

This script verifies that all LGPD encryption and compliance components
are properly installed and functional.

Run this script after deploying the LGPD implementation to verify:
1. Migrations are available
2. Services can be imported
3. Middleware can be initialized
4. Patient model has encryption properties
5. Repository has hard_delete method

Usage:
    python scripts/verify_lgpd_implementation.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def print_section(title: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def check_migrations():
    """Verify migration files exist."""
    print_section("Checking Migrations")

    migrations_dir = project_root / "alembic" / "versions"

    required_migrations = [
        "027_consolidate_duplicate_migrations.py",
        "028_encrypt_email_phone_lgpd.py"
    ]

    all_found = True
    for migration_file in required_migrations:
        file_path = migrations_dir / migration_file
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"✅ Found: {migration_file} ({size:,} bytes)")
        else:
            print(f"❌ Missing: {migration_file}")
            all_found = False

    return all_found

def check_services():
    """Verify services can be imported."""
    print_section("Checking Services")

    try:
        from app.services.encryption import (
            get_lgpd_encryption_service
        )
        # Get the service to check it's available
        service = get_lgpd_encryption_service()
        print("✅ LGPDEncryptionService imported successfully")
        print(f"✅ Service initialized: {type(service).__name__}")

        # Test methods exist
        required_methods = [
            'encrypt_email', 'decrypt_email', 'hash_email_for_search',
            'encrypt_phone', 'decrypt_phone', 'hash_phone_for_search',
            'encrypt_cpf', 'decrypt_cpf', 'hash_cpf_for_search'
        ]

        for method in required_methods:
            if hasattr(service, method):
                print(f"  ✅ Method: {method}")
            else:
                print(f"  ❌ Missing method: {method}")
                return False

        return True

    except Exception as e:
        print(f"❌ Failed to import service: {e}")
        return False

def check_middleware():
    """Verify middleware can be imported."""
    print_section("Checking Middleware")

    try:
        from app.middleware.lgpd_middleware import LGPDMiddleware
        print("✅ LGPDMiddleware imported successfully")

        # Check class attributes
        print(f"  ✅ Class: {LGPDMiddleware.__name__}")
        print(f"  ✅ Docstring: {LGPDMiddleware.__doc__[:50]}...")

        return True

    except Exception as e:
        print(f"❌ Failed to import middleware: {e}")
        return False

def check_patient_model():
    """Verify Patient model has encryption properties."""
    print_section("Checking Patient Model")

    try:
        from app.models.patient import Patient
        print("✅ Patient model imported successfully")

        # Check new columns
        required_columns = [
            'email_encrypted', 'email_hash',
            'phone_encrypted', 'phone_hash'
        ]

        for column in required_columns:
            if hasattr(Patient, column):
                print(f"  ✅ Column: {column}")
            else:
                print(f"  ❌ Missing column: {column}")
                return False

        # Check new properties
        required_properties = [
            'email_decrypted', 'set_email',
            'phone_decrypted', 'set_phone'
        ]

        for prop in required_properties:
            if hasattr(Patient, prop):
                print(f"  ✅ Property/Method: {prop}")
            else:
                print(f"  ❌ Missing property/method: {prop}")
                return False

        return True

    except Exception as e:
        print(f"❌ Failed to check Patient model: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_repository():
    """Verify PatientRepository has hard_delete method."""
    print_section("Checking Patient Repository")

    try:
        from app.repositories.patient import PatientRepository
        print("✅ PatientRepository imported successfully")

        # Check hard_delete method
        if hasattr(PatientRepository, 'hard_delete'):
            print(f"  ✅ Method: hard_delete")

            # Check method signature
            import inspect
            sig = inspect.signature(PatientRepository.hard_delete)
            params = list(sig.parameters.keys())
            print(f"  ✅ Parameters: {params}")

            # Verify audit_reason parameter
            if 'audit_reason' in params:
                print(f"  ✅ Audit reason parameter present")
            else:
                print(f"  ❌ Missing audit_reason parameter")
                return False

            return True
        else:
            print(f"  ❌ Missing method: hard_delete")
            return False

    except Exception as e:
        print(f"❌ Failed to check repository: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_dependencies():
    """Check required dependencies are installed."""
    print_section("Checking Dependencies")

    required_packages = [
        'sqlalchemy',
        'alembic',
        'cryptography',
    ]

    all_found = True
    for package in required_packages:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} not installed")
            all_found = False

    return all_found

def main():
    """Run all verification checks."""
    print("\n" + "="*60)
    print("  LGPD Implementation Verification")
    print("  Backend Hormonia Clinic System")
    print("="*60)

    checks = [
        ("Dependencies", check_dependencies),
        ("Migrations", check_migrations),
        ("Services", check_services),
        ("Middleware", check_middleware),
        ("Patient Model", check_patient_model),
        ("Patient Repository", check_repository),
    ]

    results = {}
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"\n❌ Error checking {name}: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    # Summary
    print_section("Verification Summary")

    all_passed = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("  ✅ All checks passed!")
        print("  LGPD implementation is ready for testing.")
        print("="*60 + "\n")
        return 0
    else:
        print("  ❌ Some checks failed!")
        print("  Review the errors above and fix before deployment.")
        print("="*60 + "\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
