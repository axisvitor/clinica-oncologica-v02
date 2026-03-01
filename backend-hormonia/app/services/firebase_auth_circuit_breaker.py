"""
Firebase Authentication Service with Circuit Breaker (HIGH-006)
================================================================

Enhanced Firebase auth service with circuit breaker protection to prevent
cascading failures from Firebase API outages.

Features:
- Circuit breaker pattern for all Firebase API calls
- Fallback to temporary credentials
- Graceful degradation
- Prometheus metrics integration

Author: Backend API Developer Agent
Date: 2025-11-16
"""

import logging
from typing import Optional, Dict, Any
import firebase_admin
from fastapi import HTTPException, status

from app.resilience.circuit_breaker.enhanced import (
    ServiceType,
    get_circuit_breaker_manager,
)
from app.services.firebase_auth_shared import (
    serialize_user_record,
    verify_token_and_build_user_info,
)

logger = logging.getLogger(__name__)


class FirebaseAuthServiceWithCircuitBreaker:
    """
    Firebase Authentication Service with circuit breaker protection.

    Wraps Firebase Admin SDK calls with circuit breaker to prevent
    cascading failures during Firebase outages.
    """

    _initialized = False
    _app = None

    def __init__(self, project_id: str, private_key: str, client_email: str):
        """
        Initialize Firebase Auth Service with circuit breaker.

        Args:
            project_id: Firebase project ID
            private_key: Firebase service account private key
            client_email: Firebase service account email
        """
        self.project_id = project_id
        self.private_key = private_key
        self.client_email = client_email

        # Get circuit breaker manager
        self.cb_manager = get_circuit_breaker_manager()
        self.breaker = self.cb_manager.get_breaker(ServiceType.FIREBASE)

        if not FirebaseAuthServiceWithCircuitBreaker._initialized:
            self._initialize_firebase()

    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK with service account credentials."""
        try:
            # Format private key (handle escaped newlines)
            formatted_key = self.private_key.replace("\\n", "\n")

            # Create credentials object
            cred_dict = {
                "type": "service_account",
                "project_id": self.project_id,
                "private_key": formatted_key,
                "client_email": self.client_email,
                "token_uri": "https://oauth2.googleapis.com/token",
            }

            cred = firebase_admin.credentials.Certificate(cred_dict)

            # Initialize Firebase Admin SDK
            if not firebase_admin._apps:
                FirebaseAuthServiceWithCircuitBreaker._app = (
                    firebase_admin.initialize_app(cred)
                )
                logger.info(
                    f"Firebase Admin SDK initialized with circuit breaker for project: {self.project_id}"
                )
            else:
                FirebaseAuthServiceWithCircuitBreaker._app = firebase_admin.get_app()
                logger.info("Using existing Firebase Admin SDK instance")

            FirebaseAuthServiceWithCircuitBreaker._initialized = True

        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK: {str(e)}")
            raise RuntimeError(f"Firebase initialization failed: {str(e)}")

    async def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify Firebase JWT token with circuit breaker protection.

        Args:
            token: Firebase ID token (JWT)

        Returns:
            Dict containing user information from token claims

        Raises:
            HTTPException: If token is invalid, expired, or revoked
        """
        if not token or not isinstance(token, str):
            logger.warning("Invalid token format provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Fallback function for circuit open state
        async def fallback_verify():
            logger.warning("Firebase circuit is OPEN - using degraded mode")
            # Return minimal user info to allow degraded operation
            # In production, you might decode JWT locally without verification
            return {
                "uid": "fallback_user",
                "email": "degraded@mode.com",
                "email_verified": False,
                "custom_claims": {},
                "auth_time": None,
                "exp": None,
                "degraded_mode": True,
                "warning": "Firebase authentication unavailable - operating in degraded mode",
            }

        # Wrap Firebase API call with circuit breaker
        async def _verify():
            user_info = verify_token_and_build_user_info(
                token,
                logger=logger,
                propagate_unexpected=True,
            )
            logger.debug(f"Successfully verified token for user: {user_info['email']}")
            return user_info

        # Call through circuit breaker
        return await self.breaker.call(_verify, fallback=fallback_verify)

    async def get_user(self, uid: str) -> Optional[Dict[str, Any]]:
        """
        Get Firebase user data by UID with circuit breaker protection.

        Args:
            uid: Firebase user ID

        Returns:
            Dict containing user information or None if user not found
        """

        async def fallback_get_user():
            logger.warning(
                "Firebase circuit is OPEN - returning cached/degraded user data"
            )
            return None

        async def _get_user():
            try:
                user_record = firebase_admin.auth.get_user(uid)
                user_data = serialize_user_record(user_record)

                logger.debug(f"Retrieved user data for UID: {uid}")
                return user_data

            except firebase_admin.auth.UserNotFoundError:
                logger.warning(f"User not found: {uid}")
                return None

            except Exception as e:
                logger.error(f"Error fetching user {uid}: {str(e)}")
                raise

        return await self.breaker.call(_get_user, fallback=fallback_get_user)

    async def set_custom_claims(self, uid: str, claims: Dict[str, Any]) -> bool:
        """
        Set custom claims with circuit breaker protection.

        Args:
            uid: Firebase user ID
            claims: Dictionary of custom claims to set

        Returns:
            True if successful, False otherwise
        """

        async def fallback_set_claims():
            logger.warning("Firebase circuit is OPEN - custom claims not updated")
            return False

        async def _set_claims():
            try:
                firebase_admin.auth.set_custom_user_claims(uid, claims)
                logger.info(f"Set custom claims for user {uid}: {claims}")
                return True

            except Exception as e:
                logger.error(f"Error setting custom claims for {uid}: {str(e)}")
                raise

        return await self.breaker.call(_set_claims, fallback=fallback_set_claims)

    def get_circuit_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return self.breaker.get_stats()


# Singleton instance helper
_firebase_service_instance: Optional[FirebaseAuthServiceWithCircuitBreaker] = None


def get_firebase_auth_service_with_cb(
    project_id: str, private_key: str, client_email: str
) -> FirebaseAuthServiceWithCircuitBreaker:
    """
    Get or create FirebaseAuthService with circuit breaker singleton.

    Args:
        project_id: Firebase project ID
        private_key: Firebase service account private key
        client_email: Firebase service account email

    Returns:
        FirebaseAuthServiceWithCircuitBreaker instance
    """
    global _firebase_service_instance

    if _firebase_service_instance is None:
        _firebase_service_instance = FirebaseAuthServiceWithCircuitBreaker(
            project_id=project_id, private_key=private_key, client_email=client_email
        )

    return _firebase_service_instance
