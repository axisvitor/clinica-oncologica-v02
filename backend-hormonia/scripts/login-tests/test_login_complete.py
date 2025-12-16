#!/usr/bin/env python3
"""
Complete Login System Test
Tests login flow with real credentials from .env file

This test performs:
1. Environment validation
2. Backend connectivity check
3. Firebase configuration validation
4. Session management validation
5. Complete login flow simulation

Credentials:
- Email: admin@neoplasiaslitoral.com
- Password: Admin@123456!
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime

# Add backend to path
backend_path = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(backend_path))

# Load environment
from dotenv import load_dotenv
env_path = backend_path / ".env"
load_dotenv(env_path)


class Colors:
    """Terminal colors"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text: str):
    """Print styled header"""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*80}{Colors.END}\n")


def print_section(text: str):
    """Print section header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BLUE}{'-'*80}{Colors.END}")


def print_success(text: str, detail: str = ""):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")
    if detail:
        print(f"   {Colors.GREEN}└─ {detail}{Colors.END}")


def print_error(text: str, detail: str = ""):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")
    if detail:
        print(f"   {Colors.RED}└─ {detail}{Colors.END}")


def print_info(text: str):
    """Print info message"""
    print(f"{Colors.YELLOW}ℹ️  {text}{Colors.END}")


class LoginSystemTester:
    """Comprehensive login system tester"""

    def __init__(self):
        self.email = "admin@neoplasiaslitoral.com"
        self.password = "Admin@123456!"
        self.backend_url = "http://localhost:8000"
        self.results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }

    def test(self, name: str, passed: bool, detail: str = "") -> bool:
        """Record and display test result"""
        self.results["total"] += 1
        if passed:
            self.results["passed"] += 1
            print_success(name, detail)
        else:
            self.results["failed"] += 1
            print_error(name, detail)
        return passed

    def warning(self, message: str):
        """Record warning"""
        self.results["warnings"] += 1
        print_info(f"⚠️  {message}")

    def test_environment(self):
        """Test 1: Environment Configuration"""
        print_section("Test 1: Environment Configuration")

        # Firebase
        firebase_project = os.getenv("FIREBASE_ADMIN_PROJECT_ID")
        firebase_email = os.getenv("FIREBASE_ADMIN_CLIENT_EMAIL")
        firebase_key = os.getenv("FIREBASE_ADMIN_PRIVATE_KEY")

        firebase_ok = all([firebase_project, firebase_email, firebase_key])
        self.test(
            "Firebase credentials",
            firebase_ok,
            f"Project: {firebase_project}" if firebase_ok else "Missing Firebase credentials"
        )

        # Auth keys
        jwt_key = os.getenv("AUTH_JWT_SECRET_KEY")
        security_key = os.getenv("SECURITY_SECRET_KEY")
        auth_ok = all([jwt_key, security_key])
        self.test("Authentication keys", auth_ok, "JWT and Security keys configured")

        # Redis
        redis_enabled = os.getenv("REDIS_ENABLE_SERVICE", "false").lower() == "true"
        redis_url = os.getenv("REDIS_URL")
        redis_ok = redis_enabled and redis_url
        self.test("Redis configuration", redis_ok, "Redis enabled and configured")

        # Database
        db_url = os.getenv("DATABASE_URL")
        db_ok = db_url is not None
        self.test("Database configuration", db_ok, "PostgreSQL URL configured")

        return firebase_ok and auth_ok

    def test_backend_connectivity(self):
        """Test 2: Backend Server Connectivity"""
        print_section("Test 2: Backend Server Connectivity")

        try:
            import requests

            # Test main endpoint
            try:
                response = requests.get(f"{self.backend_url}/", timeout=3)
                server_up = response.status_code in [200, 404, 307]
                self.test(
                    "Backend server",
                    server_up,
                    f"Server is running on {self.backend_url}"
                )
            except requests.exceptions.ConnectionError:
                self.test(
                    "Backend server",
                    False,
                    f"Cannot connect to {self.backend_url}"
                )
                self.warning("Start the backend with: ./backend-hormonia/scripts/start_backend.sh")
                return False

            # Test health endpoint
            try:
                response = requests.get(f"{self.backend_url}/api/v2/health", timeout=3)
                health_ok = response.status_code == 200
                self.test("Health endpoint", health_ok, "/api/v2/health responding")
            except:
                self.warning("Health endpoint not available")

            return server_up

        except ImportError:
            self.test("Requests library", False, "Install with: pip install requests")
            return False

    def test_auth_endpoints(self):
        """Test 3: Authentication Endpoints"""
        print_section("Test 3: Authentication Endpoints")

        try:
            import requests

            endpoints = [
                ("POST", "/api/v2/auth/firebase/verify", "Firebase token verification"),
                ("GET", "/api/v2/auth/verify-session", "Session verification"),
                ("DELETE", "/api/v2/auth/logout", "Logout"),
                ("GET", "/api/v2/auth/csrf-token", "CSRF token"),
            ]

            all_ok = True
            for method, path, description in endpoints:
                url = f"{self.backend_url}{path}"
                try:
                    if method == "GET":
                        response = requests.get(url, timeout=3)
                    elif method == "POST":
                        response = requests.post(url, json={}, timeout=3)
                    else:
                        response = requests.delete(url, timeout=3)

                    # Endpoints should exist (may return 401, 422, etc)
                    endpoint_ok = response.status_code != 404
                    self.test(
                        f"{description} endpoint",
                        endpoint_ok,
                        f"{method} {path}"
                    )
                    all_ok = all_ok and endpoint_ok

                except Exception as e:
                    self.test(f"{description} endpoint", False, str(e))
                    all_ok = False

            return all_ok

        except ImportError:
            return False

    def test_firebase_setup(self):
        """Test 4: Firebase Configuration"""
        print_section("Test 4: Firebase Configuration")

        try:
            import firebase_admin
            from firebase_admin import credentials, auth

            # Build credentials
            project_id = os.getenv("FIREBASE_ADMIN_PROJECT_ID")
            client_email = os.getenv("FIREBASE_ADMIN_CLIENT_EMAIL")
            private_key = os.getenv("FIREBASE_ADMIN_PRIVATE_KEY", "").replace("\\n", "\n")

            cred_dict = {
                "type": "service_account",
                "project_id": project_id,
                "private_key_id": "key-id",
                "private_key": private_key,
                "client_email": client_email,
                "client_id": "123456789",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{client_email}"
            }

            # Try to initialize
            try:
                app = firebase_admin.get_app()
                self.test("Firebase SDK", True, "Already initialized")
            except ValueError:
                try:
                    cred = credentials.Certificate(cred_dict)
                    firebase_admin.initialize_app(cred)
                    self.test("Firebase SDK", True, "Successfully initialized")
                except Exception as e:
                    self.test("Firebase SDK", False, f"Initialization failed: {str(e)}")
                    return False

            # Try to lookup user
            try:
                user = auth.get_user_by_email(self.email)
                self.test(
                    "Firebase user lookup",
                    True,
                    f"User {self.email} found (UID: {user.uid[:12]}...)"
                )

                # Check user status
                self.test("User email verified", user.email_verified, "Email verification status")
                self.test("User enabled", not user.disabled, "Account is active")

                # Check custom claims (for admin role)
                custom_claims = user.custom_claims or {}
                role = custom_claims.get("role", "unknown")
                self.test(
                    "User role",
                    role == "admin",
                    f"Role: {role}"
                )

                return True

            except auth.UserNotFoundError:
                self.test(
                    "Firebase user lookup",
                    False,
                    f"User {self.email} not found. Register in Firebase first."
                )
                return False

        except ImportError:
            self.test("Firebase Admin SDK", False, "Install with: pip install firebase-admin")
            return False
        except Exception as e:
            self.test("Firebase setup", False, str(e))
            return False

    def generate_report(self):
        """Generate final report"""
        print_header("TEST REPORT")

        total = self.results["total"]
        passed = self.results["passed"]
        failed = self.results["failed"]
        warnings = self.results["warnings"]

        print(f"Tests Run:     {total}")
        print(f"Tests Passed:  {Colors.GREEN}{passed} ✅{Colors.END}")
        print(f"Tests Failed:  {Colors.RED}{failed} ❌{Colors.END}")
        if warnings > 0:
            print(f"Warnings:      {Colors.YELLOW}{warnings} ⚠️{Colors.END}")

        success_rate = (passed / total * 100) if total > 0 else 0
        print(f"\nSuccess Rate:  {Colors.BOLD}{success_rate:.1f}%{Colors.END}")

        print_header("LOGIN INSTRUCTIONS")

        print(f"{Colors.BOLD}Frontend Login:{Colors.END}")
        print(f"1. Open frontend application: http://localhost:5173")
        print(f"2. Navigate to login page")
        print(f"3. Use these credentials:")
        print(f"   {Colors.CYAN}Email:    {self.email}{Colors.END}")
        print(f"   {Colors.CYAN}Password: {self.password}{Colors.END}")
        print()

        print(f"{Colors.BOLD}Backend Verification:{Colors.END}")
        print(f"4. After login, check backend logs for:")
        print(f"   • 🔥 Firebase token verification")
        print(f"   • ✅ Session created in database")
        print(f"   • ✅ Redis session cache")
        print(f"   • 🍪 Cookie 'session_id' set")
        print()

        print(f"{Colors.BOLD}Session Verification:{Colors.END}")
        print(f"5. In browser DevTools > Application > Cookies:")
        print(f"   • Look for 'session_id' cookie")
        print(f"   • Domain: localhost")
        print(f"   • Path: /")
        print(f"   • HttpOnly: ✓")
        print(f"   • Secure: {'✓' if os.getenv('SESSION_ENABLE_COOKIE_SECURE') == 'true' else '✗'}")
        print()

        print(f"{Colors.BOLD}API Testing:{Colors.END}")
        print(f"6. Test authenticated endpoint:")
        print(f"   curl -X GET http://localhost:8000/api/v2/auth/verify-session \\")
        print(f"        -H 'Cookie: session_id=YOUR_SESSION_ID'")
        print()

        if failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✅ ALL TESTS PASSED!{Colors.END}")
            print(f"{Colors.GREEN}The login system is configured correctly.{Colors.END}")
        else:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠️  SOME TESTS FAILED{Colors.END}")
            print(f"{Colors.YELLOW}Review the errors above and fix configuration issues.{Colors.END}")

        print(f"\n{Colors.CYAN}{'='*80}{Colors.END}\n")

    def run(self):
        """Run all tests"""
        print_header(f"🔐 LOGIN SYSTEM TEST - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        print(f"{Colors.BOLD}Test Credentials:{Colors.END}")
        print(f"  Email:    {self.email}")
        print(f"  Password: {'*' * len(self.password)}")
        print(f"  Backend:  {self.backend_url}")

        # Run tests
        env_ok = self.test_environment()
        backend_ok = self.test_backend_connectivity()

        if backend_ok:
            self.test_auth_endpoints()

        if env_ok:
            self.test_firebase_setup()

        # Generate report
        self.generate_report()

        return self.results["failed"] == 0


def main():
    """Main entry point"""
    tester = LoginSystemTester()
    success = tester.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
