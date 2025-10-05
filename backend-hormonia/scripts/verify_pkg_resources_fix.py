#!/usr/bin/env python3
"""
Verification script for pkg_resources deprecation fix.

This script checks if all Google packages are updated to versions
that don't use the deprecated pkg_resources API.

Run with: python scripts/verify_pkg_resources_fix.py
"""

import sys
import warnings
from typing import Dict, List, Tuple


def check_package_version(package_name: str, min_version: str) -> Tuple[bool, str]:
    """
    Check if a package meets the minimum version requirement.

    Args:
        package_name: Name of the package to check
        min_version: Minimum required version

    Returns:
        Tuple of (is_valid, installed_version)
    """
    try:
        import importlib.metadata as metadata

        installed_version = metadata.version(package_name)

        # Simple version comparison (works for most cases)
        installed_parts = [int(x) for x in installed_version.split('.')[:3]]
        required_parts = [int(x) for x in min_version.split('.')[:3]]

        is_valid = installed_parts >= required_parts
        return is_valid, installed_version
    except Exception as e:
        return False, f"Error: {str(e)}"


def verify_google_packages() -> Dict[str, Tuple[bool, str, str]]:
    """
    Verify all Google packages are at required versions.

    Returns:
        Dictionary mapping package names to (is_valid, installed_version, required_version)
    """
    required_packages = {
        'googleapis-common-protos': '1.70.0',
        'google-api-core': '2.25.0',
        'google-auth': '2.40.0',
        'proto-plus': '1.26.0',
        'firebase-admin': '6.9.0',
        # NOTE: Removed grpcio/grpcio-status (HTTP-only OTLP)
        # NOTE: google-generativeai removed (LangChain-only approach)
        'langchain-google-genai': '2.1.12',
        'google-ai-generativelanguage': '0.7.0',
    }

    results = {}
    for package, min_version in required_packages.items():
        is_valid, installed = check_package_version(package, min_version)
        results[package] = (is_valid, installed, min_version)

    return results


def test_imports() -> List[str]:
    """
    Test that all critical imports work without warnings.

    Returns:
        List of any warning messages encountered
    """
    warning_messages = []

    # Capture warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        try:
            # Test Google imports
            import google.api_core
            import google.auth
            import firebase_admin
            # NOTE: google.generativeai removed (LangChain-only approach)
            from langchain_google_genai import ChatGoogleGenerativeAI
            import grpc

            # Check for pkg_resources warnings
            for warning in w:
                if 'pkg_resources' in str(warning.message).lower():
                    warning_messages.append(str(warning.message))

        except ImportError as e:
            warning_messages.append(f"Import error: {str(e)}")

    return warning_messages


def main():
    """Main verification function."""
    print("=" * 70)
    print("pkg_resources Deprecation Fix Verification")
    print("=" * 70)
    print()

    # Check package versions
    print("Checking package versions...")
    print("-" * 70)
    results = verify_google_packages()

    all_valid = True
    for package, (is_valid, installed, required) in results.items():
        status = "✅ OK" if is_valid else "❌ FAIL"
        print(f"{status} {package:30} (required: >={required}, installed: {installed})")
        if not is_valid:
            all_valid = False

    print()

    # Test imports
    print("Testing imports for pkg_resources warnings...")
    print("-" * 70)
    warnings_found = test_imports()

    if warnings_found:
        print("❌ WARNINGS DETECTED:")
        for warning in warnings_found:
            print(f"   - {warning}")
        all_valid = False
    else:
        print("✅ No pkg_resources warnings detected!")

    print()
    print("=" * 70)

    if all_valid:
        print("✅ SUCCESS: All checks passed!")
        print()
        print("Your Google packages are up to date and don't use pkg_resources.")
        return 0
    else:
        print("❌ FAILED: Some checks did not pass.")
        print()
        print("To fix:")
        print("  1. Run: py -m pip install --upgrade -r requirements.txt")
        print("  2. If issues persist: py -m pip cache purge && py -m pip install --upgrade --force-reinstall -r requirements.txt")
        print()
        print("See docs/PKG_RESOURCES_FIX.md for more details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
