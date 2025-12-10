#!/usr/bin/env python3
"""
Real Login System Test - Using actual Firebase credentials
Tests the complete authentication flow with real .env credentials

Login Credentials:
- Email: admin@neoplasiaslitoral.com
- Password: Admin@123456!
"""

import os
import sys
import json
import time
from datetime import datetime
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend-hormonia"
sys.path.insert(0, str(backend_path))

# Load environment variables
from dotenv import load_dotenv
env_path = backend_path / ".env"
load_dotenv(env_path)

print(f"\n{'='*80}")
print(f"🔐 REAL LOGIN SYSTEM TEST")
print(f"{'='*80}")
print(f"📅 Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"🔑 Using credentials from: {env_path}")
print(f"{'='*80}\n")

# Test credentials
TEST_EMAIL = "admin@neoplasiaslitoral.com"
TEST_PASSWORD = "Admin@123456!"

# Backend configuration
BACKEND_URL = os.getenv("APP_HOST", "localhost")
BACKEND_PORT = os.getenv("APP_PORT", "8000")
BASE_URL = f"http://{BACKEND_URL}:{BACKEND_PORT}"
API_VERSION = os.getenv("APP_API_VERSION", "v2")


class FirebaseAuthTester:
    """Test Firebase authentication flow"""

    def __init__(self):
        self.firebase_project_id = os.getenv("FIREBASE_ADMIN_PROJECT_ID")
        self.results = {
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "errors": []
        }

    def log_test(self, name: str, passed: bool, message: str = ""):
        """Log test result"""
        self.results["tests_run"] += 1
        status = "✅ PASSED" if passed else "❌ FAILED"

        if passed:
            self.results["tests_passed"] += 1
            print(f"{status} - {name}")
            if message:
                print(f"  └─ {message}")
        else:
            self.results["tests_failed"] += 1
            print(f"{status} - {name}")
            error_msg = f"{name}: {message}"
            self.results["errors"].append(error_msg)
            print(f"  └─ ❌ {message}")

    def test_environment_setup(self):
        """Test 1: Verify environment configuration"""
        print("\n📋 Test 1: Environment Configuration")
        print("-" * 80)

        # Check Firebase configuration
        firebase_vars = {
            "FIREBASE_ADMIN_PROJECT_ID": os.getenv("FIREBASE_ADMIN_PROJECT_ID"),
            "FIREBASE_ADMIN_CLIENT_EMAIL": os.getenv("FIREBASE_ADMIN_CLIENT_EMAIL"),
            "FIREBASE_ADMIN_PRIVATE_KEY": os.getenv("FIREBASE_ADMIN_PRIVATE_KEY"),
        }

        all_set = all(firebase_vars.values())
        self.log_test(
            "Firebase environment variables",
            all_set,
            f"Project ID: {firebase_vars['FIREBASE_ADMIN_PROJECT_ID']}" if all_set else "Missing Firebase configuration"
        )

        # Check authentication settings
        auth_vars = {
            "AUTH_JWT_SECRET_KEY": os.getenv("AUTH_JWT_SECRET_KEY"),
            "SECURITY_SECRET_KEY": os.getenv("SECURITY_SECRET_KEY"),
        }

        auth_set = all(auth_vars.values())
        self.log_test(
            "Authentication configuration",
            auth_set,
            "JWT and Security keys configured" if auth_set else "Missing auth keys"
        )

        # Check Redis configuration
        redis_enabled = os.getenv("REDIS_ENABLE_SERVICE", "false").lower() == "true"
        redis_url = os.getenv("REDIS_URL")

        self.log_test(
            "Redis configuration",
            redis_enabled and redis_url,
            f"Redis: {'Enabled' if redis_enabled else 'Disabled'}"
        )

        return all_set and auth_set

    def test_firebase_auth(self):
        """Test 2: Attempt Firebase authentication"""
        print("\n🔥 Test 2: Firebase Authentication")
        print("-" * 80)

        try:
            # Try to initialize Firebase Admin SDK
            import firebase_admin
            from firebase_admin import credentials, auth

            # Check if already initialized
            try:
                firebase_admin.get_app()
                self.log_test("Firebase SDK initialization", True, "Already initialized")
            except ValueError:
                # Initialize Firebase Admin
                cred_dict = {
                    "type": "service_account",
                    "project_id": os.getenv("FIREBASE_ADMIN_PROJECT_ID"),
                    "client_email": os.getenv("FIREBASE_ADMIN_CLIENT_EMAIL"),
                    "private_key": os.getenv("FIREBASE_ADMIN_PRIVATE_KEY", "").replace("\\n", "\n"),
                }

                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                self.log_test("Firebase SDK initialization", True, "Successfully initialized")

            # Verify we can access Firebase Auth
            try:
                # Try to get user by email
                user = auth.get_user_by_email(TEST_EMAIL)
                self.log_test(
                    "Firebase user lookup",
                    True,
                    f"Found user: {user.email} (UID: {user.uid[:8]}...)"
                )
                return True, user.uid

            except auth.UserNotFoundError:
                self.log_test(
                    "Firebase user lookup",
                    False,
                    f"User {TEST_EMAIL} not found in Firebase. User must be registered first."
                )
                return False, None
            except Exception as e:
                self.log_test(
                    "Firebase user lookup",
                    False,
                    f"Error looking up user: {str(e)}"
                )
                return False, None

        except ImportError:
            self.log_test(
                "Firebase SDK import",
                False,
                "firebase_admin package not installed. Run: pip install firebase-admin"
            )
            return False, None
        except Exception as e:
            self.log_test(
                "Firebase authentication setup",
                False,
                f"Error: {str(e)}"
            )
            return False, None

    def test_backend_health(self):
        """Test 3: Check if backend is running"""
        print("\n🏥 Test 3: Backend Health Check")
        print("-" * 80)

        try:
            import requests

            # Check main endpoint
            try:
                response = requests.get(f"{BASE_URL}/", timeout=5)
                backend_up = response.status_code in [200, 404]  # 404 is ok, means server is running
                self.log_test(
                    "Backend server",
                    backend_up,
                    f"Server responding on {BASE_URL}" if backend_up else f"Server not responding"
                )
            except requests.exceptions.ConnectionError:
                self.log_test(
                    "Backend server",
                    False,
                    f"Cannot connect to {BASE_URL}. Is the server running?"
                )
                return False

            # Check API health endpoint
            try:
                health_url = f"{BASE_URL}/api/{API_VERSION}/health"
                response = requests.get(health_url, timeout=5)
                health_ok = response.status_code == 200
                self.log_test(
                    "API health endpoint",
                    health_ok,
                    f"Status: {response.status_code}"
                )
            except Exception as e:
                self.log_test(
                    "API health endpoint",
                    False,
                    f"Health check failed: {str(e)}"
                )

            return backend_up

        except ImportError:
            self.log_test(
                "Requests library",
                False,
                "requests package not installed. Run: pip install requests"
            )
            return False

    def test_login_endpoint(self, firebase_uid: str = None):
        """Test 4: Test actual login endpoint"""
        print("\n🔐 Test 4: Login Endpoint Test")
        print("-" * 80)

        # NOTE: The actual login happens via Firebase on the client side
        # The backend endpoint /api/v2/auth/firebase/verify expects a Firebase ID token
        # We cannot generate a valid Firebase ID token without the actual Firebase credentials

        print("\n⚠️  IMPORTANT INFORMATION:")
        print("   The login system uses Firebase Authentication.")
        print("   To test the complete login flow, you need to:")
        print()
        print("   1. Use the frontend application to authenticate with Firebase")
        print("   2. Firebase will return an ID token")
        print("   3. The frontend sends this token to: POST /api/v2/auth/firebase/verify")
        print("   4. The backend verifies the token and creates a session")
        print()
        print(f"   Login credentials to use in frontend:")
        print(f"   📧 Email: {TEST_EMAIL}")
        print(f"   🔑 Password: {TEST_PASSWORD}")
        print()

        # We can test if the endpoint exists
        try:
            import requests

            verify_url = f"{BASE_URL}/api/{API_VERSION}/auth/firebase/verify"

            # Try with invalid token to see if endpoint responds correctly
            response = requests.post(
                verify_url,
                json={"id_token": "invalid_token_for_testing"},
                timeout=5
            )

            # We expect 401 or 400 for invalid token
            endpoint_exists = response.status_code in [400, 401, 422]
            self.log_test(
                "Firebase verify endpoint",
                endpoint_exists,
                f"Endpoint responds correctly (Status: {response.status_code})"
            )

            if endpoint_exists:
                print(f"\n   ✅ Login endpoint is ready: POST {verify_url}")
                print(f"   📝 Expected request format:")
                print(f'      {{"id_token": "firebase_id_token_from_client"}}')

            return endpoint_exists

        except Exception as e:
            self.log_test(
                "Login endpoint check",
                False,
                f"Error: {str(e)}"
            )
            return False

    def test_session_endpoints(self):
        """Test 5: Test session management endpoints"""
        print("\n📋 Test 5: Session Management Endpoints")
        print("-" * 80)

        try:
            import requests

            endpoints = {
                "verify-session": ("GET", f"{BASE_URL}/api/{API_VERSION}/auth/verify-session"),
                "logout": ("DELETE", f"{BASE_URL}/api/{API_VERSION}/auth/logout"),
                "logout-all": ("DELETE", f"{BASE_URL}/api/{API_VERSION}/auth/logout-all"),
                "csrf-token": ("GET", f"{BASE_URL}/api/{API_VERSION}/auth/csrf-token"),
            }

            all_ok = True
            for name, (method, url) in endpoints.items():
                try:
                    if method == "GET":
                        response = requests.get(url, timeout=5)
                    else:
                        response = requests.delete(url, timeout=5)

                    # 401 is expected for protected endpoints without auth
                    endpoint_ok = response.status_code in [200, 401, 422]
                    self.log_test(
                        f"{name} endpoint",
                        endpoint_ok,
                        f"{method} {url.split('/api/')[1]}"
                    )
                    all_ok = all_ok and endpoint_ok

                except Exception as e:
                    self.log_test(f"{name} endpoint", False, str(e))
                    all_ok = False

            return all_ok

        except ImportError:
            return False

    def print_summary(self):
        """Print test summary"""
        print(f"\n{'='*80}")
        print("📊 TEST SUMMARY")
        print(f"{'='*80}")
        print(f"Tests Run:    {self.results['tests_run']}")
        print(f"Tests Passed: {self.results['tests_passed']} ✅")
        print(f"Tests Failed: {self.results['tests_failed']} ❌")

        if self.results['errors']:
            print(f"\n❌ ERRORS:")
            for error in self.results['errors']:
                print(f"  • {error}")

        success_rate = (self.results['tests_passed'] / self.results['tests_run'] * 100) if self.results['tests_run'] > 0 else 0
        print(f"\nSuccess Rate: {success_rate:.1f}%")

        print(f"\n{'='*80}")
        print("📝 NEXT STEPS TO COMPLETE LOGIN TEST:")
        print(f"{'='*80}")
        print("1. Ensure the backend server is running:")
        print("   cd backend-hormonia")
        print("   source venv_linux/bin/activate")
        print("   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        print()
        print("2. Open the frontend application in a browser")
        print()
        print("3. Use these credentials to log in:")
        print(f"   Email: {TEST_EMAIL}")
        print(f"   Password: {TEST_PASSWORD}")
        print()
        print("4. Monitor the backend logs to verify:")
        print("   • Firebase token verification")
        print("   • Session creation in database")
        print("   • Redis session caching")
        print("   • Cookie setting")
        print()
        print("5. Check browser Developer Tools > Application > Cookies")
        print("   Look for 'session_id' cookie")
        print(f"{'='*80}\n")

        return self.results['tests_failed'] == 0

    def run_all_tests(self):
        """Run all tests"""
        print("\n🚀 Starting comprehensive login system test...\n")

        # Test 1: Environment
        env_ok = self.test_environment_setup()

        # Test 2: Firebase
        firebase_ok, firebase_uid = self.test_firebase_auth()

        # Test 3: Backend health
        backend_ok = self.test_backend_health()

        # Test 4: Login endpoint
        if backend_ok:
            login_ok = self.test_login_endpoint(firebase_uid)

        # Test 5: Session endpoints
        if backend_ok:
            session_ok = self.test_session_endpoints()

        # Summary
        return self.print_summary()


def main():
    """Main test execution"""
    tester = FirebaseAuthTester()
    success = tester.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
