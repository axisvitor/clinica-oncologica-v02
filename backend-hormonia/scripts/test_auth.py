#!/usr/bin/env python3
"""
Authentication System Test Script
Tests Firebase authentication with provided admin credentials.

Usage:
    python3 scripts/test_auth.py
"""

import sys
import os
import requests
import json
from datetime import datetime
from typing import Dict, Optional

# Add backend to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test Configuration
BASE_URL = "http://localhost:8000"
API_VERSION = "v2"
TEST_EMAIL = "admin@neoplasiaslitoral.com"
TEST_PASSWORD = "Admin@123456!"

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text: str):
    """Print colored header"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 80}{Colors.ENDC}\n")


def print_success(text: str):
    """Print success message"""
    print(f"{Colors.OKGREEN}✓ {text}{Colors.ENDC}")


def print_error(text: str):
    """Print error message"""
    print(f"{Colors.FAIL}✗ {text}{Colors.ENDC}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.OKCYAN}ℹ {text}{Colors.ENDC}")


def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.WARNING}⚠ {text}{Colors.ENDC}")


def check_server_health() -> bool:
    """Check if backend server is running"""
    print_header("1. Checking Backend Server Health")

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print_success(f"Server is running at {BASE_URL}")
            print_info(f"Health check response: {response.json()}")
            return True
        else:
            print_error(f"Server returned status code: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print_error(f"Cannot connect to server at {BASE_URL}")
        print_info("Make sure the backend server is running:")
        print_info("  cd backend-hormonia && uvicorn app.main:app --reload")
        return False
    except Exception as e:
        print_error(f"Health check failed: {str(e)}")
        return False


def get_firebase_token() -> Optional[str]:
    """
    Get Firebase ID token for test user.

    Note: This requires Firebase client SDK which is typically used in frontend.
    For backend testing, we'll try to use the Firebase REST API.
    """
    print_header("2. Getting Firebase ID Token")

    # Firebase REST API endpoint for email/password sign in
    # This requires the Firebase Web API Key
    firebase_api_key = os.getenv("FIREBASE_WEB_API_KEY")

    if not firebase_api_key:
        print_warning("FIREBASE_WEB_API_KEY not found in environment")
        print_info("This test requires Firebase Web API Key to authenticate")
        print_info("Add FIREBASE_WEB_API_KEY to your .env file")
        print_info("You can find it in Firebase Console > Project Settings > Web API Key")
        return None

    # Firebase Auth REST API
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={firebase_api_key}"

    payload = {
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
        "returnSecureToken": True
    }

    try:
        print_info(f"Authenticating with Firebase: {TEST_EMAIL}")
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            data = response.json()
            id_token = data.get("idToken")
            print_success("Firebase authentication successful")
            print_info(f"Token expires in: {data.get('expiresIn')} seconds")
            print_info(f"User ID: {data.get('localId')}")
            return id_token
        else:
            error_data = response.json()
            error_message = error_data.get("error", {}).get("message", "Unknown error")
            print_error(f"Firebase authentication failed: {error_message}")
            print_info(f"Response: {json.dumps(error_data, indent=2)}")
            return None

    except Exception as e:
        print_error(f"Firebase authentication error: {str(e)}")
        return None


def test_backend_auth(id_token: str) -> Optional[Dict]:
    """Test backend authentication endpoint"""
    print_header("3. Testing Backend Authentication Endpoint")

    url = f"{BASE_URL}/api/{API_VERSION}/auth/firebase/verify"

    payload = {
        "id_token": id_token
    }

    headers = {
        "Content-Type": "application/json"
    }

    try:
        print_info(f"POST {url}")
        print_info(f"Payload: {json.dumps(payload, indent=2)[:100]}...")

        response = requests.post(url, json=payload, headers=headers, timeout=10)

        print_info(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print_success("Backend authentication successful!")
            print_info(f"Response: {json.dumps(data, indent=2)}")

            # Check for session cookie
            if 'session_id' in response.cookies:
                print_success(f"Session cookie set: {response.cookies.get('session_id')[:20]}...")

            # Check for X-Session-ID header
            if 'X-Session-ID' in response.headers:
                print_success(f"X-Session-ID header: {response.headers.get('X-Session-ID')[:20]}...")

            return {
                "response": data,
                "cookies": dict(response.cookies),
                "headers": dict(response.headers)
            }
        else:
            print_error("Backend authentication failed")
            print_info(f"Response: {response.text}")
            return None

    except Exception as e:
        print_error(f"Backend authentication error: {str(e)}")
        return None


def test_session_verification(auth_data: Dict) -> bool:
    """Test session verification endpoint"""
    print_header("4. Testing Session Verification")

    url = f"{BASE_URL}/api/{API_VERSION}/auth/verify-session"

    # Try with cookie first
    cookies = auth_data.get("cookies", {})

    try:
        print_info(f"GET {url}")
        print_info("Using session cookie for authentication")

        response = requests.get(url, cookies=cookies, timeout=10)

        print_info(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print_success("Session verification successful!")
            print_info(f"Response: {json.dumps(data, indent=2)}")
            return True
        else:
            print_error("Session verification failed")
            print_info(f"Response: {response.text}")
            return False

    except Exception as e:
        print_error(f"Session verification error: {str(e)}")
        return False


def test_protected_endpoint(auth_data: Dict) -> bool:
    """Test a protected endpoint with session"""
    print_header("5. Testing Protected Endpoint (Patient List)")

    url = f"{BASE_URL}/api/{API_VERSION}/patients/"
    cookies = auth_data.get("cookies", {})

    try:
        print_info(f"GET {url}")
        print_info("Using session authentication")

        response = requests.get(
            url,
            cookies=cookies,
            params={"limit": 5},  # Just get first 5 patients
            timeout=10
        )

        print_info(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print_success("Protected endpoint access successful!")

            if isinstance(data, list):
                print_info(f"Retrieved {len(data)} patients")
            elif isinstance(data, dict) and "items" in data:
                print_info(f"Retrieved {len(data['items'])} patients")
                print_info(f"Total count: {data.get('total', 'N/A')}")

            return True
        elif response.status_code == 401:
            print_error("Authentication required - session may have expired")
            print_info(f"Response: {response.text}")
            return False
        elif response.status_code == 403:
            print_error("Forbidden - insufficient permissions")
            print_info(f"Response: {response.text}")
            return False
        else:
            print_warning(f"Unexpected status code: {response.status_code}")
            print_info(f"Response: {response.text}")
            return False

    except Exception as e:
        print_error(f"Protected endpoint test error: {str(e)}")
        return False


def print_summary(results: Dict[str, bool]):
    """Print test summary"""
    print_header("Test Summary")

    total = len(results)
    passed = sum(1 for r in results.values() if r)
    failed = total - passed

    print(f"Total Tests: {total}")
    print(f"{Colors.OKGREEN}Passed: {passed}{Colors.ENDC}")
    print(f"{Colors.FAIL}Failed: {failed}{Colors.ENDC}")

    print("\nDetailed Results:")
    for test_name, result in results.items():
        status = f"{Colors.OKGREEN}PASS{Colors.ENDC}" if result else f"{Colors.FAIL}FAIL{Colors.ENDC}"
        print(f"  {test_name}: {status}")

    print()

    if failed == 0:
        print_success("All tests passed! ✓")
        return True
    else:
        print_error(f"{failed} test(s) failed!")
        return False


def main():
    """Main test execution"""
    print_header("Firebase Authentication System Test")
    print_info(f"Backend URL: {BASE_URL}")
    print_info(f"API Version: {API_VERSION}")
    print_info(f"Test Email: {TEST_EMAIL}")
    print_info(f"Test Time: {datetime.now().isoformat()}")

    results = {}

    # Test 1: Server Health
    server_ok = check_server_health()
    results["Server Health"] = server_ok

    if not server_ok:
        print_error("\nCannot proceed with tests - server is not running")
        print_summary(results)
        return 1

    # Test 2: Firebase Authentication
    id_token = get_firebase_token()
    results["Firebase Authentication"] = id_token is not None

    if not id_token:
        print_warning("\nCannot proceed with backend tests - Firebase authentication failed")
        print_info("Possible issues:")
        print_info("1. FIREBASE_WEB_API_KEY not set in .env")
        print_info("2. Invalid credentials (email/password)")
        print_info("3. User doesn't exist in Firebase")
        print_info("4. Firebase project configuration issue")
        print_summary(results)
        return 1

    # Test 3: Backend Authentication
    auth_data = test_backend_auth(id_token)
    results["Backend Authentication"] = auth_data is not None

    if not auth_data:
        print_error("\nBackend authentication failed - cannot proceed with session tests")
        print_summary(results)
        return 1

    # Test 4: Session Verification
    session_ok = test_session_verification(auth_data)
    results["Session Verification"] = session_ok

    # Test 5: Protected Endpoint
    protected_ok = test_protected_endpoint(auth_data)
    results["Protected Endpoint Access"] = protected_ok

    # Print summary
    success = print_summary(results)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
