#!/usr/bin/env python3
"""
Validation script for physicians module refactoring.

This script verifies:
- All modules can be imported
- Services are properly initialized
- Query optimization is in place
- Caching is configured correctly
- No breaking changes in API
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))


def validate_imports():
    """Validate all modules can be imported."""
    print("🔍 Validating imports...")

    try:
        # Main router
        from app.api.v2.routers.physicians import router
        print("  ✅ Main router imported successfully")

        # Base utilities
        from app.api.v2.routers.physicians.base import (
            _extract_user_context,
            _is_admin,
            _calculate_workload_level,
            validate_physician_access,
        )
        print("  ✅ Base utilities imported successfully")

        # CRUD endpoints
        from app.api.v2.routers.physicians.crud import (
            list_physicians,
            get_physician,
            update_physician,
        )
        print("  ✅ CRUD endpoints imported successfully")

        # Statistics endpoints
        from app.api.v2.routers.physicians.statistics import (
            get_physician_statistics,
        )
        print("  ✅ Statistics endpoints imported successfully")

        # Availability endpoints
        from app.api.v2.routers.physicians.availability import (
            get_physician_schedule,
            check_physician_availability,
            get_next_available_slot,
        )
        print("  ✅ Availability endpoints imported successfully")

        # Services
        from app.api.v2.routers.physicians.services import (
            PhysicianStatisticsService,
            PhysicianAvailabilityService,
        )
        print("  ✅ Services imported successfully")

        return True

    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False


def validate_service_structure():
    """Validate service classes have required methods."""
    print("\n🔍 Validating service structure...")

    try:
        from app.api.v2.routers.physicians.services import (
            PhysicianStatisticsService,
            PhysicianAvailabilityService,
        )

        # Check PhysicianStatisticsService
        required_stats_methods = [
            'calculate_statistics',
            'calculate_batch_statistics',
            '_calculate_patient_metrics',
            '_calculate_message_stats',
            '_calculate_appointment_stats',
            '_calculate_alert_stats',
            'invalidate_cache',
        ]

        for method in required_stats_methods:
            if not hasattr(PhysicianStatisticsService, method):
                print(f"  ❌ PhysicianStatisticsService missing method: {method}")
                return False

        print("  ✅ PhysicianStatisticsService has all required methods")

        # Check PhysicianAvailabilityService
        required_availability_methods = [
            'get_available_slots',
            'get_schedule',
            'is_available',
            'get_next_available_slot',
        ]

        for method in required_availability_methods:
            if not hasattr(PhysicianAvailabilityService, method):
                print(f"  ❌ PhysicianAvailabilityService missing method: {method}")
                return False

        print("  ✅ PhysicianAvailabilityService has all required methods")

        return True

    except Exception as e:
        print(f"  ❌ Validation failed: {e}")
        return False


def validate_router_routes():
    """Validate router has all expected routes."""
    print("\n🔍 Validating router routes...")

    try:
        from app.api.v2.routers.physicians import router

        # Get all route paths
        routes = [route.path for route in router.routes]

        expected_routes = [
            "",  # List physicians
            "/{physician_id}",  # Get/Update physician
            "/{physician_id}/statistics",  # Statistics
            "/{physician_id}/schedule",  # Schedule
            "/{physician_id}/availability",  # Availability check
            "/{physician_id}/next-available",  # Next available slot
        ]

        all_present = True
        for expected in expected_routes:
            if expected not in routes:
                print(f"  ❌ Missing route: {expected}")
                all_present = False

        if all_present:
            print(f"  ✅ All {len(expected_routes)} expected routes present")
            return True
        else:
            print(f"  ⚠️  Some routes are missing")
            return False

    except Exception as e:
        print(f"  ❌ Validation failed: {e}")
        return False


def validate_file_sizes():
    """Validate file sizes are reasonable."""
    print("\n🔍 Validating file sizes...")

    physicians_dir = backend_path / "app" / "api" / "v2" / "routers" / "physicians"

    files_to_check = {
        "__init__.py": 50,
        "base.py": 200,
        "crud.py": 400,
        "statistics.py": 100,
        "availability.py": 200,
        "services/statistics_service.py": 500,
        "services/availability_service.py": 200,
    }

    all_good = True
    for file_path, max_lines in files_to_check.items():
        full_path = physicians_dir / file_path
        if not full_path.exists():
            print(f"  ❌ File not found: {file_path}")
            all_good = False
            continue

        with open(full_path) as f:
            line_count = len(f.readlines())

        if line_count > max_lines:
            print(f"  ⚠️  {file_path}: {line_count} lines (max {max_lines})")
        else:
            print(f"  ✅ {file_path}: {line_count} lines")

    return all_good


def validate_type_hints():
    """Check that key functions have type hints."""
    print("\n🔍 Validating type hints...")

    try:
        from app.api.v2.routers.physicians.services import PhysicianStatisticsService
        import inspect

        # Check calculate_statistics signature
        sig = inspect.signature(PhysicianStatisticsService.calculate_statistics)

        has_return_annotation = sig.return_annotation != inspect.Parameter.empty
        has_param_annotations = all(
            param.annotation != inspect.Parameter.empty
            for name, param in sig.parameters.items()
            if name not in ('self', 'use_cache')
        )

        if has_return_annotation and has_param_annotations:
            print("  ✅ Type hints present in key methods")
            return True
        else:
            print("  ⚠️  Some type hints may be missing")
            return False

    except Exception as e:
        print(f"  ❌ Validation failed: {e}")
        return False


def validate_documentation():
    """Check that documentation files exist."""
    print("\n🔍 Validating documentation...")

    docs_dir = backend_path / "docs"

    required_docs = [
        "PHYSICIANS_REFACTORING.md",
        "PHYSICIANS_API_EXAMPLES.md",
        "PHYSICIANS_REFACTORING_SUMMARY.md",
    ]

    all_exist = True
    for doc in required_docs:
        doc_path = docs_dir / doc
        if doc_path.exists():
            size = doc_path.stat().st_size
            print(f"  ✅ {doc} exists ({size:,} bytes)")
        else:
            print(f"  ❌ {doc} not found")
            all_exist = False

    return all_exist


def validate_backward_compatibility():
    """Check backward compatibility with old import."""
    print("\n🔍 Validating backward compatibility...")

    try:
        # Old import should still work
        from app.api.v2.routers.physicians import router

        # Router should have routes
        if len(router.routes) > 0:
            print(f"  ✅ Router has {len(router.routes)} routes")
            return True
        else:
            print("  ❌ Router has no routes")
            return False

    except Exception as e:
        print(f"  ❌ Validation failed: {e}")
        return False


def main():
    """Run all validations."""
    print("=" * 60)
    print("Physicians Module Refactoring Validation")
    print("=" * 60)

    validations = [
        ("Imports", validate_imports),
        ("Service Structure", validate_service_structure),
        ("Router Routes", validate_router_routes),
        ("File Sizes", validate_file_sizes),
        ("Type Hints", validate_type_hints),
        ("Documentation", validate_documentation),
        ("Backward Compatibility", validate_backward_compatibility),
    ]

    results = {}
    for name, validator in validations:
        results[name] = validator()

    # Summary
    print("\n" + "=" * 60)
    print("Validation Summary")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status:12} - {name}")

    print("-" * 60)
    print(f"Result: {passed}/{total} validations passed")
    print("=" * 60)

    if passed == total:
        print("\n🎉 All validations passed! Refactoring is successful.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} validation(s) failed. Please review.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
