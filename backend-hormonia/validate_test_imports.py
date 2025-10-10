#!/usr/bin/env python3
"""
Validate that comprehensive authentication test imports work correctly.
"""

import sys
import os
from pathlib import Path

def main():
    """Test imports for comprehensive authentication tests."""
    backend_dir = Path(__file__).parent
    sys.path.insert(0, str(backend_dir))

    print("🔍 Validating Test Imports")
    print("=" * 50)

    tests = []

    # Test 1: Firebase Auth Service imports
    try:
        from app.services.firebase_auth_service import FirebaseAuthService, get_firebase_auth_service
        print("✅ Firebase Auth Service imports - OK")
        tests.append(("Firebase Auth Service", True))
    except Exception as e:
        print(f"❌ Firebase Auth Service imports - FAILED: {e}")
        tests.append(("Firebase Auth Service", False))

    # Test 2: Audit Service imports
    try:
        from app.services.audit_service import AuditService
        from app.services.audit_log import AuditLogService
        print("✅ Audit Services imports - OK")
        tests.append(("Audit Services", True))
    except Exception as e:
        print(f"❌ Audit Services imports - FAILED: {e}")
        tests.append(("Audit Services", False))

    # Test 3: Auth Service imports
    try:
        from app.services.auth import AuthService
        print("✅ Auth Service imports - OK")
        tests.append(("Auth Service", True))
    except Exception as e:
        print(f"❌ Auth Service imports - FAILED: {e}")
        tests.append(("Auth Service", False))

    # Test 4: Model imports
    try:
        from app.models.audit_log import AuditLog, AuditEventType
        from app.models.user import User, UserRole
        print("✅ Model imports - OK")
        tests.append(("Model imports", True))
    except Exception as e:
        print(f"❌ Model imports - FAILED: {e}")
        tests.append(("Model imports", False))

    # Test 5: Test dependencies
    try:
        import pytest
        import pytest_asyncio
        from unittest.mock import Mock, patch, MagicMock, AsyncMock
        import firebase_admin
        from fastapi import HTTPException, status
        print("✅ Test dependencies - OK")
        tests.append(("Test dependencies", True))
    except Exception as e:
        print(f"❌ Test dependencies - FAILED: {e}")
        tests.append(("Test dependencies", False))

    # Test 6: Check comprehensive test files exist
    test_files = [
        "tests/unit/services/test_firebase_auth_service_comprehensive.py",
        "tests/unit/services/test_auth_service_comprehensive.py",
        "tests/unit/services/test_audit_service_comprehensive.py",
        "tests/integration/test_auth_flows_comprehensive.py"
    ]

    missing_files = []
    for test_file in test_files:
        if not Path(test_file).exists():
            missing_files.append(test_file)

    if missing_files:
        print(f"❌ Missing test files: {missing_files}")
        tests.append(("Test files exist", False))
    else:
        print("✅ All comprehensive test files exist - OK")
        tests.append(("Test files exist", True))

    print("\n" + "=" * 50)
    print("📊 VALIDATION SUMMARY")
    print("=" * 50)

    passed = sum(1 for test, result in tests if result)
    total = len(tests)

    for test_name, result in tests:
        status_icon = "✅" if result else "❌"
        print(f"{status_icon} {test_name}")

    print(f"\nResult: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All validations passed! Tests are ready to run.")
        return 0
    else:
        print("⚠️ Some validations failed. Check imports and dependencies.")
        return 1


if __name__ == "__main__":
    sys.exit(main())