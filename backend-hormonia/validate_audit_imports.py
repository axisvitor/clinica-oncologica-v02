#!/usr/bin/env python3
"""
Validate imports for audit service comprehensive tests.

This script checks if all required modules and dependencies
are available for the comprehensive audit service tests.
"""

import sys
from pathlib import Path

def validate_imports():
    """Validate all imports needed for audit service tests."""

    print("🔍 Validating audit service test imports...")
    print("=" * 50)

    # Track import results
    success_count = 0
    error_count = 0

    # Core Python modules
    core_modules = [
        "pytest", "hashlib", "json", "datetime", "unittest.mock",
        "typing", "uuid"
    ]

    for module in core_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
            success_count += 1
        except ImportError as e:
            print(f"❌ {module}: {e}")
            error_count += 1

    # SQLAlchemy modules
    sqlalchemy_modules = [
        "sqlalchemy.orm", "sqlalchemy"
    ]

    for module in sqlalchemy_modules:
        try:
            __import__(module)
            print(f"✅ {module}")
            success_count += 1
        except ImportError as e:
            print(f"❌ {module}: {e}")
            error_count += 1

    # FastAPI modules
    try:
        from fastapi import Request
        print("✅ fastapi.Request")
        success_count += 1
    except ImportError as e:
        print(f"❌ fastapi.Request: {e}")
        error_count += 1

    # App-specific modules
    app_modules = [
        ("app.services.audit_service", "AuditService"),
        ("app.services.audit_log", "AuditLogService"),
        ("app.models.audit_log", "AuditEventType"),
        ("app.models.user", "User, UserRole"),
    ]

    for module_path, items in app_modules:
        try:
            module = __import__(module_path, fromlist=[items])
            print(f"✅ {module_path} ({items})")
            success_count += 1
        except ImportError as e:
            print(f"❌ {module_path} ({items}): {e}")
            error_count += 1

    # Check AuditLog models separately (they might conflict)
    try:
        from app.services.audit_service import AuditLog as LGPDAuditLog
        print("✅ LGPD AuditLog model")
        success_count += 1
    except ImportError as e:
        print(f"❌ LGPD AuditLog model: {e}")
        error_count += 1

    try:
        from app.models.audit_log import AuditLog as SecurityAuditLog
        print("✅ Security AuditLog model")
        success_count += 1
    except ImportError as e:
        print(f"⚠️  Security AuditLog model: {e} (this is OK if using different models)")

    print("=" * 50)
    print(f"✅ Successfully imported: {success_count}")
    print(f"❌ Failed imports: {error_count}")

    if error_count == 0:
        print("🎉 All imports validated successfully!")
        print("📝 Ready to run comprehensive audit service tests")
        return True
    else:
        print("⚠️  Some imports failed - tests may not run properly")
        return False

def check_test_file():
    """Check if test file exists and is readable."""
    test_file = Path("tests/unit/services/test_audit_service_comprehensive.py")

    print(f"\n📁 Checking test file: {test_file}")

    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return False

    if not test_file.is_file():
        print(f"❌ Not a file: {test_file}")
        return False

    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = len(content.splitlines())
            print(f"✅ Test file exists ({lines} lines)")
            return True
    except Exception as e:
        print(f"❌ Error reading test file: {e}")
        return False

def main():
    """Main validation function."""
    print("🧪 AUDIT SERVICE TEST VALIDATION")
    print("=" * 60)

    # Validate imports
    imports_ok = validate_imports()

    # Check test file
    file_ok = check_test_file()

    print("\n" + "=" * 60)
    if imports_ok and file_ok:
        print("🎯 VALIDATION COMPLETE - READY TO RUN TESTS!")
        print("\nNext steps:")
        print("1. Run: python run_audit_tests_comprehensive.py")
        print("2. Or run: python -m pytest tests/unit/services/test_audit_service_comprehensive.py -v")
        return 0
    else:
        print("⚠️  VALIDATION ISSUES DETECTED")
        print("Please fix import issues before running tests")
        return 1

if __name__ == "__main__":
    sys.exit(main())