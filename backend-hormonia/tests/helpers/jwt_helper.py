"""
JWT Helper for Testing - Generate Firebase-compatible JWT tokens for RLS testing.

This module provides utilities to create valid JWT tokens that mimic Firebase authentication
tokens for testing Row Level Security policies via API endpoints.
"""
import jwt
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from uuid import uuid4


class JWTTestHelper:
    """Helper class to generate Firebase-compatible JWT tokens for testing."""

    def __init__(self, secret_key: str = "test-secret-key-for-rls-testing"):
        """
        Initialize JWT helper with a secret key.

        Args:
            secret_key: Secret key for signing JWT tokens (test only)
        """
        self.secret_key = secret_key
        self.algorithm = "HS256"

    def create_jwt_token(
        self,
        firebase_uid: str,
        email: str,
        role: str = "authenticated",
        expires_in_minutes: int = 60,
        additional_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a Firebase-compatible JWT token for testing.

        Args:
            firebase_uid: Firebase user ID (will be in 'sub' claim)
            email: User email address
            role: User role (default: 'authenticated')
            expires_in_minutes: Token expiration time in minutes
            additional_claims: Additional claims to include

        Returns:
            Encoded JWT token string
        """
        now = datetime.now(timezone.utc)
        exp = now + timedelta(minutes=expires_in_minutes)

        # Firebase JWT structure
        payload = {
            # Standard claims
            "sub": firebase_uid,  # Firebase UID - used in RLS policies
            "email": email,
            "email_verified": True,
            "aud": "sistema-oncologico-auth",  # Firebase project ID
            "iss": f"https://securetoken.google.com/sistema-oncologico-auth",
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            "auth_time": int(now.timestamp()),

            # Firebase user metadata
            "user_id": firebase_uid,
            "role": role,

            # App metadata (custom claims)
            "app_metadata": {
                "role": role,
                "provider": "firebase"
            },
            "user_metadata": {
                "email": email,
                "full_name": f"Test User {firebase_uid[:8]}"
            },

            # Firebase provider data
            "firebase": {
                "identities": {
                    "email": [email]
                },
                "sign_in_provider": "password"
            }
        }

        # Add additional claims if provided
        if additional_claims:
            payload.update(additional_claims)

        # Encode token
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token

    def create_doctor_token(
        self,
        doctor_id: Optional[str] = None,
        email: Optional[str] = None,
        name: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Create a JWT token for a doctor user.

        Args:
            doctor_id: Firebase UID for doctor (generates random if not provided)
            email: Doctor email (generates if not provided)
            name: Doctor name (generates if not provided)

        Returns:
            Dictionary with 'firebase_uid', 'email', 'token' keys
        """
        firebase_uid = doctor_id or f"doctor_{uuid4().hex[:16]}"
        doctor_email = email or f"doctor.{firebase_uid[:8]}@test.clinica.com"
        doctor_name = name or f"Dr. Test {firebase_uid[:8]}"

        token = self.create_jwt_token(
            firebase_uid=firebase_uid,
            email=doctor_email,
            role="authenticated",
            additional_claims={
                "user_metadata": {
                    "full_name": doctor_name,
                    "role": "doctor"
                }
            }
        )

        return {
            "firebase_uid": firebase_uid,
            "email": doctor_email,
            "name": doctor_name,
            "token": token
        }

    def create_admin_token(
        self,
        admin_id: Optional[str] = None,
        email: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Create a JWT token for an admin user.

        Args:
            admin_id: Firebase UID for admin (generates random if not provided)
            email: Admin email (generates if not provided)

        Returns:
            Dictionary with 'firebase_uid', 'email', 'token' keys
        """
        firebase_uid = admin_id or f"admin_{uuid4().hex[:16]}"
        admin_email = email or f"admin.{firebase_uid[:8]}@test.clinica.com"

        token = self.create_jwt_token(
            firebase_uid=firebase_uid,
            email=admin_email,
            role="authenticated",
            additional_claims={
                "app_metadata": {
                    "role": "admin",
                    "permissions": ["read", "write", "delete", "admin"]
                },
                "user_metadata": {
                    "full_name": f"Admin {firebase_uid[:8]}",
                    "role": "admin"
                }
            }
        )

        return {
            "firebase_uid": firebase_uid,
            "email": admin_email,
            "token": token
        }

    def create_expired_token(self, firebase_uid: str, email: str) -> str:
        """
        Create an expired JWT token for testing authentication failures.

        Args:
            firebase_uid: Firebase user ID
            email: User email

        Returns:
            Expired JWT token string
        """
        return self.create_jwt_token(
            firebase_uid=firebase_uid,
            email=email,
            expires_in_minutes=-60  # Expired 1 hour ago
        )

    def decode_token(self, token: str, verify: bool = False) -> Dict[str, Any]:
        """
        Decode a JWT token for inspection.

        Args:
            token: JWT token string
            verify: Whether to verify signature (default: False for testing)

        Returns:
            Decoded token payload
        """
        options = {"verify_signature": verify}
        return jwt.decode(token, self.secret_key, algorithms=[self.algorithm], options=options)


# Global helper instance for tests
jwt_helper = JWTTestHelper()
