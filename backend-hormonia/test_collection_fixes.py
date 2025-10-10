#!/usr/bin/env python3
"""
Test script to verify all test collection fixes.

This script tests that:
1. Pydantic v2 pattern field works
2. Application factory import works
3. WhatsApp queue modules can be imported
4. All test markers are valid
"""

import sys
import traceback
from pathlib import Path

def test_pydantic_v2_fix():
    """Test that Pydantic v2 pattern field works."""
    try:
        from pydantic import BaseModel, Field

        class TestModel(BaseModel):
            email: str = Field(..., pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

        # Test valid email
        model = TestModel(email="test@example.com")
        print("✓ Pydantic v2 pattern field works")
        return True
    except Exception as e:
        print(f"✗ Pydantic v2 pattern field failed: {e}")
        traceback.print_exc()
        return False

def test_application_factory_import():
    """Test that application factory import works."""
    try:
        from app.core.application_factory import create_application as create_app
        print("✓ Application factory import works")
        return True
    except Exception as e:
        print(f"✗ Application factory import failed: {e}")
        traceback.print_exc()
        return False

def test_whatsapp_queue_imports():
    """Test that WhatsApp queue modules can be imported."""
    try:
        from app.integrations.whatsapp.queue.schemas import MessageRequest, MessageResponse
        from app.integrations.whatsapp.queue.manager import QueueManager

        # Test creating a MessageRequest
        request = MessageRequest(
            instance_name="test_instance",
            to="+1234567890",
            text="Test message"
        )

        # Test creating a QueueManager
        manager = QueueManager(default_instance="test")

        print("✓ WhatsApp queue imports work")
        return True
    except Exception as e:
        print(f"✗ WhatsApp queue imports failed: {e}")
        traceback.print_exc()
        return False

def test_middleware_imports():
    """Test that middleware imports work."""
    try:
        from app.middleware import (
            EnhancedSecurityMiddleware,
            SecurityHeadersMiddleware
        )
        print("✓ Middleware imports work")
        return True
    except Exception as e:
        print(f"✗ Middleware imports failed: {e}")
        traceback.print_exc()
        return False

def test_pytest_markers():
    """Test that pytest configuration is valid."""
    try:
        import configparser

        # Read pytest.ini
        config = configparser.ConfigParser()
        config.read('pytest.ini')

        # Check that markers section exists
        if 'pytest' in config and 'markers' in config['pytest']:
            markers_text = config['pytest']['markers']
            if 'load: mark test as load/stress testing' in markers_text:
                print("✓ Pytest markers configuration is valid")
                return True
            else:
                print("✗ Load marker not found in pytest.ini")
                return False
        else:
            print("✗ Pytest markers section not found")
            return False
    except Exception as e:
        print(f"✗ Pytest configuration test failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Run all test collection fixes verification."""
    print("Testing all collection fixes...")
    print("=" * 50)

    tests = [
        test_pydantic_v2_fix,
        test_application_factory_import,
        test_whatsapp_queue_imports,
        test_middleware_imports,
        test_pytest_markers
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            results.append(False)
        print()

    print("=" * 50)
    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"🎉 All {total} tests passed! Test collection should work now.")
        return 0
    else:
        print(f"⚠️  {passed}/{total} tests passed. Some issues may remain.")
        return 1

if __name__ == "__main__":
    sys.exit(main())