#!/usr/bin/env python3
"""
Module Exports Verification Script

This script verifies that all standardized __init__.py files
correctly export their intended functions and classes.

Usage:
    python scripts/verify_module_exports.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_utils_exports():
    """Test app/utils/__init__.py exports."""
    print("\n" + "=" * 70)
    print("Testing app/utils/__init__.py")
    print("=" * 70)

    try:
        from app.utils import (
            # Template & Input Sanitization
            TemplateSanitizer,
            parse_version,
            async_transaction,
            DatabaseOptimizer,
            QueryOptimizer,
            AuditLogger,
            AuditAction,
            get_logger,
        )

        print("✅ All imports successful!")
        print("\nKey Classes:")
        print(f"  - TemplateSanitizer: {TemplateSanitizer.__name__}")
        print(f"  - AuditLogger: {AuditLogger.__name__}")
        print(f"  - DatabaseOptimizer: {DatabaseOptimizer.__name__}")
        print(f"  - QueryOptimizer: {QueryOptimizer.__name__}")

        print("\nKey Functions:")
        print(f"  - parse_version: {parse_version.__name__}")
        print(f"  - async_transaction: {async_transaction.__name__}")
        print(f"  - get_logger: {get_logger.__name__}")

        print("\nEnums:")
        print(f"  - AuditAction: {AuditAction.__name__}")

        return True

    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ai_services_exports():
    """Test app/services/ai/__init__.py exports."""
    print("\n" + "=" * 70)
    print("Testing app/services/ai/__init__.py")
    print("=" * 70)

    try:
        from app.services.ai import (
            # Core AI Service
            AIService,
            PatientContext,
            CacheLayer,
            BatchProcessor,
            PatientSummaryService,
            SummaryDataAggregator,
            AggregatedPatientData,
            # NLP Utilities
            NLPUtilities,
        )

        print("✅ All imports successful!")
        print("\nCore Services:")
        print(f"  - AIService: {AIService.__name__}")
        print(f"  - PatientSummaryService: {PatientSummaryService.__name__}")
        print(f"  - NLPUtilities: {NLPUtilities.__name__}")

        print("\nData Structures:")
        print(f"  - PatientContext: {PatientContext.__name__}")
        print(f"  - AggregatedPatientData: {AggregatedPatientData.__name__}")

        print("\nProcessing:")
        print(f"  - BatchProcessor: {BatchProcessor.__name__}")
        print(f"  - SummaryDataAggregator: {SummaryDataAggregator.__name__}")

        print("\nCache Layer:")
        print(f"  - CacheLayer: {CacheLayer.__name__}")

        return True

    except Exception as e:
        print(f"❌ Import failed: {e}")
        # Don't print full traceback for known config issues
        if "APP_ENABLE_DEBUG" not in str(e):
            import traceback
            traceback.print_exc()
        else:
            print("   (Configuration issue - unrelated to exports)")
        return False


def test_ai_routers_exports():
    """Test app/api/v2/routers/ai/__init__.py exports."""
    print("\n" + "=" * 70)
    print("Testing app/api/v2/routers/ai/__init__.py")
    print("=" * 70)

    try:
        from app.api.v2.routers.ai import router

        print("✅ All imports successful!")
        print("\nRouter Information:")
        print(f"  - Type: {type(router).__name__}")
        print(f"  - Prefix: {router.prefix}")
        print(f"  - Tags: {router.tags}")
        print(f"  - Total routes: {len(router.routes)}")

        print("\nRegistered Routes:")
        for route in router.routes[:8]:  # Show first 8 routes
            if hasattr(route, 'path'):
                methods = getattr(route, 'methods', ['GET'])
                print(f"  - {list(methods)[0]:6} {route.path}")

        if len(router.routes) > 8:
            print(f"  ... and {len(router.routes) - 8} more routes")

        return True

    except Exception as e:
        print(f"❌ Import failed: {e}")
        if "APP_ENABLE_DEBUG" not in str(e):
            import traceback
            traceback.print_exc()
        else:
            print("   (Configuration issue - unrelated to exports)")
        return False


def main():
    """Run all export verification tests."""
    print("\n" + "=" * 70)
    print("MODULE EXPORTS VERIFICATION")
    print("=" * 70)
    print("\nVerifying standardized __init__.py files...")

    results = {}

    # Test utils
    results['utils'] = test_utils_exports()

    # Test AI services
    results['ai_services'] = test_ai_services_exports()

    # Test AI routers
    results['ai_routers'] = test_ai_routers_exports()

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for module, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status:10} - {module}")

    print("\n" + "-" * 70)
    print(f"Total: {passed}/{total} modules passed")

    if passed == total:
        print("\n🎉 All module exports verified successfully!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} module(s) have issues")
        return 1


if __name__ == "__main__":
    sys.exit(main())
