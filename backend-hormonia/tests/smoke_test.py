#!/usr/bin/env python3
"""
Smoke Tests for Critical Railway Endpoints

Quick validation tests for production deployment.
Tests basic connectivity and authentication flows.
"""
import requests
import sys
import json
from typing import Dict, Any

# Railway backend URL (update with actual deployment URL)
BASE_URL = "https://backend-hormonia-production.up.railway.app"  # Update this
# Fallback to local if needed
# BASE_URL = "http://localhost:8080"


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_test(name: str, status: str, details: str = ""):
    """Print test result with color coding."""
    if status == "PASS":
        symbol = f"{Colors.GREEN}[PASS]{Colors.END}"
        color = Colors.GREEN
    elif status == "FAIL":
        symbol = f"{Colors.RED}[FAIL]{Colors.END}"
        color = Colors.RED
    else:
        symbol = f"{Colors.YELLOW}[WARN]{Colors.END}"
        color = Colors.YELLOW

    try:
        print(f"{symbol} {name}: {color}{status}{Colors.END}")
        if details:
            print(f"  {details}")
    except UnicodeEncodeError:
        # Fallback for Windows console encoding issues
        print(f"[{status}] {name}")
        if details:
            print(f"  {details}")


def test_health_endpoint() -> bool:
    """Test basic health check endpoint."""
    print(f"\n{Colors.BLUE}Testing Health Endpoint{Colors.END}")
    print("-" * 50)

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)

        if response.status_code == 200:
            data = response.json()
            print_test("Health Check", "PASS", f"Status: {data.get('status', 'unknown')}")

            # Check database connectivity
            if "database" in data:
                db_status = data["database"].get("status", "unknown")
                print_test("Database Connection", "PASS" if db_status == "healthy" else "WARN",
                          f"Status: {db_status}")

            # Check Redis connectivity
            if "redis" in data:
                redis_status = data["redis"].get("status", "unknown")
                print_test("Redis Connection", "PASS" if redis_status == "healthy" else "WARN",
                          f"Status: {redis_status}")

            return True
        else:
            print_test("Health Check", "FAIL", f"Status code: {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print_test("Health Check", "FAIL", "Connection refused - backend may be down")
        return False
    except Exception as e:
        print_test("Health Check", "FAIL", f"Error: {str(e)}")
        return False


def test_api_docs() -> bool:
    """Test API documentation endpoint (OpenAPI)."""
    print(f"\n{Colors.BLUE}Testing API Documentation{Colors.END}")
    print("-" * 50)

    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=10)

        if response.status_code == 200:
            print_test("OpenAPI Docs", "PASS", "Swagger UI accessible")
            return True
        else:
            print_test("OpenAPI Docs", "FAIL", f"Status code: {response.status_code}")
            return False

    except Exception as e:
        print_test("OpenAPI Docs", "FAIL", f"Error: {str(e)}")
        return False


def test_root_endpoint() -> bool:
    """Test root endpoint."""
    print(f"\n{Colors.BLUE}Testing Root Endpoint{Colors.END}")
    print("-" * 50)

    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)

        if response.status_code == 200:
            data = response.json()
            print_test("Root Endpoint", "PASS", f"Message: {data.get('message', 'N/A')}")
            return True
        else:
            print_test("Root Endpoint", "FAIL", f"Status code: {response.status_code}")
            return False

    except Exception as e:
        print_test("Root Endpoint", "FAIL", f"Error: {str(e)}")
        return False


def test_cors_headers() -> bool:
    """Test CORS headers for frontend compatibility."""
    print(f"\n{Colors.BLUE}Testing CORS Configuration{Colors.END}")
    print("-" * 50)

    try:
        headers = {
            "Origin": "https://frontend-hormonia.vercel.app",
            "Access-Control-Request-Method": "GET"
        }
        response = requests.options(f"{BASE_URL}/health", headers=headers, timeout=10)

        cors_headers = {
            "access-control-allow-origin": response.headers.get("access-control-allow-origin"),
            "access-control-allow-credentials": response.headers.get("access-control-allow-credentials"),
        }

        if cors_headers["access-control-allow-origin"]:
            print_test("CORS Headers", "PASS",
                      f"Origin: {cors_headers['access-control-allow-origin']}")
            return True
        else:
            print_test("CORS Headers", "WARN", "CORS headers not found")
            return False

    except Exception as e:
        print_test("CORS Headers", "FAIL", f"Error: {str(e)}")
        return False


def test_404_handling() -> bool:
    """Test 404 error handling."""
    print(f"\n{Colors.BLUE}Testing Error Handling{Colors.END}")
    print("-" * 50)

    try:
        response = requests.get(f"{BASE_URL}/nonexistent-endpoint-12345", timeout=10)

        if response.status_code == 404:
            print_test("404 Handling", "PASS", "Returns proper 404 for invalid routes")
            return True
        else:
            print_test("404 Handling", "WARN", f"Expected 404, got {response.status_code}")
            return False

    except Exception as e:
        print_test("404 Handling", "FAIL", f"Error: {str(e)}")
        return False


def test_authentication_required() -> bool:
    """Test that protected endpoints require authentication."""
    print(f"\n{Colors.BLUE}Testing Authentication Requirements{Colors.END}")
    print("-" * 50)

    protected_endpoints = [
        "/api/v1/admin/system-stats",
        "/api/v1/medico/dashboard-stats",
        "/api/v1/patients",
    ]

    all_protected = True
    for endpoint in protected_endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=10)

            # Should return 401 or 403 (not 200)
            if response.status_code in [401, 403]:
                print_test(f"Protected: {endpoint}", "PASS",
                          f"Returns {response.status_code} (auth required)")
            else:
                print_test(f"Protected: {endpoint}", "WARN",
                          f"Expected 401/403, got {response.status_code}")
                all_protected = False

        except Exception as e:
            print_test(f"Protected: {endpoint}", "FAIL", f"Error: {str(e)}")
            all_protected = False

    return all_protected


def main():
    """Run all smoke tests."""
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}Railway Backend Smoke Tests{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"Target: {BASE_URL}")

    results = {
        "Health Endpoint": test_health_endpoint(),
        "Root Endpoint": test_root_endpoint(),
        "API Documentation": test_api_docs(),
        "CORS Configuration": test_cors_headers(),
        "404 Handling": test_404_handling(),
        "Authentication": test_authentication_required(),
    }

    # Summary
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}Test Summary{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, passed_status in results.items():
        status = f"{Colors.GREEN}PASS{Colors.END}" if passed_status else f"{Colors.RED}FAIL{Colors.END}"
        print(f"{test_name}: {status}")

    print(f"\n{Colors.BLUE}Results: {passed}/{total} tests passed{Colors.END}")

    # Exit code
    if passed == total:
        print(f"\n{Colors.GREEN}All smoke tests passed! Backend is operational.{Colors.END}\n")
        sys.exit(0)
    else:
        print(f"\n{Colors.RED}Some tests failed. Check backend configuration.{Colors.END}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
