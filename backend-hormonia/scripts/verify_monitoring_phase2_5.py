#!/usr/bin/env python3
"""
Verification script for Phase 2.5 Monitoring Infrastructure.

This script validates that all monitoring components are properly installed
and configured:
- Structured logging utility
- Health check endpoints
- Performance metrics middleware
- Integration with existing systems
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple

# Color codes for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_success(message: str):
    """Print success message in green."""
    print(f"{GREEN}✅ {message}{RESET}")


def print_error(message: str):
    """Print error message in red."""
    print(f"{RED}❌ {message}{RESET}")


def print_warning(message: str):
    """Print warning message in yellow."""
    print(f"{YELLOW}⚠️  {message}{RESET}")


def print_info(message: str):
    """Print info message in blue."""
    print(f"{BLUE}ℹ️  {message}{RESET}")


def print_header(message: str):
    """Print section header."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{message}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")


def verify_file_exists(file_path: Path) -> Tuple[bool, str]:
    """
    Verify that a file exists.

    Args:
        file_path: Path to the file

    Returns:
        Tuple of (success, message)
    """
    if file_path.exists():
        return True, f"File exists: {file_path}"
    else:
        return False, f"File missing: {file_path}"


def verify_file_content(file_path: Path, required_content: List[str]) -> Tuple[bool, List[str]]:
    """
    Verify that file contains required content.

    Args:
        file_path: Path to the file
        required_content: List of strings that must be in the file

    Returns:
        Tuple of (success, missing_content)
    """
    if not file_path.exists():
        return False, [f"File does not exist: {file_path}"]

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    missing = [item for item in required_content if item not in content]

    return len(missing) == 0, missing


def verify_structured_logger():
    """Verify structured logger implementation."""
    print_header("Verifying Structured Logger")

    file_path = Path("app/utils/structured_logger.py")
    success, message = verify_file_exists(file_path)

    if not success:
        print_error(message)
        return False

    print_success(message)

    # Check required classes and functions
    required_content = [
        "class StructuredLogger",
        "correlation_id: ContextVar",
        "request_id: ContextVar",
        "user_id: ContextVar",
        "request_path: ContextVar",
        "def log_performance",
        "def log_query",
        "def log_cache_operation",
        "def log_api_call",
        "def configure_logging",
        "def set_correlation_id",
        "def get_correlation_id",
    ]

    success, missing = verify_file_content(file_path, required_content)

    if success:
        print_success("All required functions present")
        return True
    else:
        print_error("Missing required functions:")
        for item in missing:
            print(f"  - {item}")
        return False


def verify_health_endpoints():
    """Verify health check endpoints implementation."""
    print_header("Verifying Health Check Endpoints")

    file_path = Path("app/routers/health.py")
    success, message = verify_file_exists(file_path)

    if not success:
        print_error(message)
        return False

    print_success(message)

    # Check required endpoints
    required_content = [
        "@router.get(\"/live\"",
        "@router.get(\"/ready\"",
        "@router.get(\"/metrics\"",
        "@router.get(\"/startup\"",
        "@router.get(\"/performance\"",
        "async def liveness_check",
        "async def readiness_check",
        "async def metrics_endpoint",
        "async def startup_validation",
        "async def performance_metrics",
        "from app.database import get_db",
        "from app.core.redis_unified import get_async_redis",
    ]

    success, missing = verify_file_content(file_path, required_content)

    if success:
        print_success("All required endpoints present")
        print_info("Available endpoints:")
        print("  - GET /health/live (liveness)")
        print("  - GET /health/ready (readiness)")
        print("  - GET /health/metrics (system metrics)")
        print("  - GET /health/performance (app metrics)")
        print("  - GET /health/startup (validation)")
        return True
    else:
        print_error("Missing required endpoints:")
        for item in missing:
            print(f"  - {item}")
        return False


def verify_metrics_middleware():
    """Verify performance metrics middleware implementation."""
    print_header("Verifying Performance Metrics Middleware")

    file_path = Path("app/middleware/metrics.py")
    success, message = verify_file_exists(file_path)

    if not success:
        print_error(message)
        return False

    print_success(message)

    # Check required classes and functions
    required_content = [
        "class MetricsCollector",
        "class PerformanceMetricsMiddleware",
        "def record_request",
        "def record_cache_operation",
        "def get_metrics",
        "def reset_metrics",
        "def record_cache_hit",
        "def record_cache_miss",
        "def increment_query_count",
        "set_request_id",
        "set_correlation_id",
        "X-Request-ID",
        "X-Correlation-ID",
        "X-Response-Time-Ms",
        "X-Query-Count",
    ]

    success, missing = verify_file_content(file_path, required_content)

    if success:
        print_success("All required components present")
        print_info("Metrics tracked:")
        print("  - Request count and duration")
        print("  - Per-endpoint performance")
        print("  - Database query count")
        print("  - Cache hit/miss rate")
        print("  - Memory usage")
        return True
    else:
        print_error("Missing required components:")
        for item in missing:
            print(f"  - {item}")
        return False


def verify_router_integration():
    """Verify health router is registered."""
    print_header("Verifying Router Integration")

    file_path = Path("app/core/router_registry.py")
    success, message = verify_file_exists(file_path)

    if not success:
        print_error(message)
        return False

    print_success(message)

    # Check router import and registration
    required_content = [
        "from app.routers.health import router as health_monitoring",
        "app.include_router(health_monitoring",
    ]

    success, missing = verify_file_content(file_path, required_content)

    if success:
        print_success("Health router properly registered")
        return True
    else:
        print_error("Health router not registered:")
        for item in missing:
            print(f"  - {item}")
        return False


def verify_middleware_integration():
    """Verify metrics middleware is configured."""
    print_header("Verifying Middleware Integration")

    file_path = Path("app/core/middleware_setup.py")
    success, message = verify_file_exists(file_path)

    if not success:
        print_error(message)
        return False

    print_success(message)

    # Check middleware import and setup
    required_content = [
        "from app.middleware.metrics import PerformanceMetricsMiddleware",
        "app.add_middleware(PerformanceMetricsMiddleware)",
    ]

    success, missing = verify_file_content(file_path, required_content)

    if success:
        print_success("Metrics middleware properly configured")
        return True
    else:
        print_error("Metrics middleware not configured:")
        for item in missing:
            print(f"  - {item}")
        return False


def verify_logging_configuration():
    """Verify structured logging is configured at startup."""
    print_header("Verifying Logging Configuration")

    file_path = Path("app/core/lifespan.py")
    success, message = verify_file_exists(file_path)

    if not success:
        print_error(message)
        return False

    print_success(message)

    # Check logging configuration
    required_content = [
        "from app.utils.structured_logger import configure_logging as configure_structured_logging",
        "configure_structured_logging",
    ]

    success, missing = verify_file_content(file_path, required_content)

    if success:
        print_success("Structured logging configured at startup")
        return True
    else:
        print_error("Structured logging not configured:")
        for item in missing:
            print(f"  - {item}")
        return False


def verify_documentation():
    """Verify documentation files exist."""
    print_header("Verifying Documentation")

    docs = [
        Path("docs/monitoring/PHASE_2_5_MONITORING_INFRASTRUCTURE.md"),
        Path("docs/monitoring/QUICK_START_MONITORING.md"),
        Path("PHASE_2_5_MONITORING_SUMMARY.md"),
    ]

    all_exist = True
    for doc_path in docs:
        success, message = verify_file_exists(doc_path)
        if success:
            print_success(message)
        else:
            print_error(message)
            all_exist = False

    return all_exist


def verify_imports():
    """Verify that all modules can be imported."""
    print_header("Verifying Module Imports")

    # Change to project root
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))

    modules_to_import = [
        "app.utils.structured_logger",
        "app.routers.health",
        "app.middleware.metrics",
    ]

    all_imported = True
    for module_name in modules_to_import:
        try:
            __import__(module_name)
            print_success(f"Successfully imported: {module_name}")
        except Exception as e:
            print_error(f"Failed to import {module_name}: {e}")
            all_imported = False

    return all_imported


def main():
    """Run all verification checks."""
    print(f"\n{BLUE}{'='*60}")
    print("Phase 2.5 Monitoring Infrastructure Verification")
    print(f"{'='*60}{RESET}\n")

    # Track overall success
    all_checks_passed = True

    # Run verification checks
    checks = [
        ("Structured Logger", verify_structured_logger),
        ("Health Endpoints", verify_health_endpoints),
        ("Metrics Middleware", verify_metrics_middleware),
        ("Router Integration", verify_router_integration),
        ("Middleware Integration", verify_middleware_integration),
        ("Logging Configuration", verify_logging_configuration),
        ("Documentation", verify_documentation),
    ]

    results = {}
    for check_name, check_func in checks:
        try:
            results[check_name] = check_func()
            all_checks_passed = all_checks_passed and results[check_name]
        except Exception as e:
            print_error(f"Check failed with exception: {e}")
            results[check_name] = False
            all_checks_passed = False

    # Try importing modules (optional, may fail if dependencies not installed)
    print_warning("Module import check (optional - may fail if not in virtual env):")
    try:
        import_success = verify_imports()
        results["Module Imports"] = import_success
    except Exception as e:
        print_warning(f"Could not verify imports (this is OK if not in venv): {e}")
        results["Module Imports"] = None  # Don't fail overall check

    # Print summary
    print_header("Verification Summary")

    for check_name, success in results.items():
        if success is True:
            print_success(f"{check_name}: PASSED")
        elif success is False:
            print_error(f"{check_name}: FAILED")
        else:
            print_warning(f"{check_name}: SKIPPED")

    print()

    if all_checks_passed:
        print_success("✨ All verification checks passed!")
        print_info("Phase 2.5 Monitoring Infrastructure is ready for testing.")
        print()
        print_info("Next steps:")
        print("  1. Start the application: uvicorn app.main:app --reload")
        print("  2. Test health endpoints: curl http://localhost:8000/health/live")
        print("  3. Check documentation: docs/monitoring/QUICK_START_MONITORING.md")
        return 0
    else:
        print_error("Some verification checks failed!")
        print_info("Please review the errors above and fix the issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
