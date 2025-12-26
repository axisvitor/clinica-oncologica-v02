"""Firebase Authentication Service

Provides Firebase JWT token validation for backend authentication.
Replaces Supabase Auth with Firebase Authentication.
"""

import logging
import os
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import firebase_admin
from firebase_admin import credentials, auth
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class FirebaseAuthService:
    """
    Firebase Authentication Service for JWT validation.

    Handles Firebase Admin SDK initialization and token verification.
    """

    _initialized = False
    _app = None

    def __init__(self, project_id: str, private_key: str, client_email: str):
        """
        Initialize Firebase Auth Service.

        Args:
            project_id: Firebase project ID
            private_key: Firebase service account private key
            client_email: Firebase service account email
        """
        self.project_id = project_id
        self.private_key = private_key
        self.client_email = client_email

        if not FirebaseAuthService._initialized:
            self._initialize_firebase()

    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK with service account credentials and timeout protection."""
        # Get timeout from environment variable, default to 10 seconds
        timeout = int(os.getenv("FIREBASE_INIT_TIMEOUT", "10"))

        def _init_firebase_app():
            """Internal function to initialize Firebase app."""
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

            cred = credentials.Certificate(cred_dict)

            # Initialize Firebase Admin SDK
            if not firebase_admin._apps:
                FirebaseAuthService._app = firebase_admin.initialize_app(cred)
                logger.info(
                    f"Firebase Admin SDK initialized successfully for project: {self.project_id}"
                )
            else:
                FirebaseAuthService._app = firebase_admin.get_app()
                logger.info("Using existing Firebase Admin SDK instance")

            return True

        try:
            # Execute initialization with timeout protection
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(_init_firebase_app)
                try:
                    future.result(timeout=timeout)
                    FirebaseAuthService._initialized = True
                except FuturesTimeoutError:
                    logger.warning(
                        f"Firebase initialization timed out after {timeout}s. "
                        "Application will continue but Firebase authentication may be unavailable."
                    )
                    # Mark as not initialized to allow retry on next request
                    FirebaseAuthService._initialized = False
                    return

        except Exception as e:
            logger.error(f"Failed to initialize Firebase Admin SDK: {str(e)}")
            # Log error but don't raise - allow app to continue
            logger.warning(
                "Firebase authentication will be unavailable. "
                "Please check Firebase credentials and network connectivity."
            )
            FirebaseAuthService._initialized = False

    async def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify Firebase JWT token and extract user information.

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

        try:
            # Verify the Firebase ID token
            decoded_token = auth.verify_id_token(token, check_revoked=True)

            # Extract custom claims from token (role, roles, permissions, etc.)
            # Firebase puts custom claims directly in the token, not in a nested field
            reserved_claims = {
                "iss",
                "aud",
                "auth_time",
                "user_id",
                "sub",
                "iat",
                "exp",
                "firebase",
                "uid",
                "email",
                "email_verified",
                "phone_number",
                "name",
                "picture",
                "identities",
            }
            custom_claims = {
                k: v for k, v in decoded_token.items() if k not in reserved_claims
            }

            # Extract user information
            user_info = {
                "uid": decoded_token.get("uid"),
                "email": decoded_token.get("email"),
                "email_verified": decoded_token.get("email_verified", False),
                "name": decoded_token.get("name"),
                "picture": decoded_token.get("picture"),
                "custom_claims": custom_claims,  # Now includes role, roles, permissions
                "auth_time": decoded_token.get("auth_time"),
                "exp": decoded_token.get("exp"),
            }

            logger.debug(
                f"Successfully verified token for user: {user_info['email']} with custom claims: {list(custom_claims.keys())}"
            )
            return user_info

        except auth.ExpiredIdTokenError:
            logger.warning("Expired token attempted")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        except auth.RevokedIdTokenError:
            logger.warning("Revoked token attempted")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        except auth.InvalidIdTokenError as e:
            logger.warning(f"Invalid token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        except auth.UserDisabledError:
            logger.warning("Disabled user attempted authentication")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account has been disabled",
                headers={"WWW-Authenticate": "Bearer"},
            )

        except Exception as e:
            logger.error(f"Unexpected error verifying token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def get_user(self, uid: str) -> Optional[Dict[str, Any]]:
        """
        Get Firebase user data by UID.

        Args:
            uid: Firebase user ID

        Returns:
            Dict containing user information or None if user not found
        """
        try:
            user_record = auth.get_user(uid)

            user_data = {
                "uid": user_record.uid,
                "email": user_record.email,
                "email_verified": user_record.email_verified,
                "display_name": user_record.display_name,
                "photo_url": user_record.photo_url,
                "disabled": user_record.disabled,
                "custom_claims": user_record.custom_claims or {},
                "provider_data": [
                    {
                        "provider_id": provider.provider_id,
                        "uid": provider.uid,
                        "email": provider.email,
                    }
                    for provider in user_record.provider_data
                ],
                "created_at": user_record.user_metadata.creation_timestamp,
                "last_sign_in": user_record.user_metadata.last_sign_in_timestamp,
            }

            logger.debug(f"Retrieved user data for UID: {uid}")
            return user_data

        except auth.UserNotFoundError:
            logger.warning(f"User not found: {uid}")
            return None

        except Exception as e:
            logger.error(f"Error fetching user {uid}: {str(e)}")
            return None

    async def set_custom_claims(self, uid: str, claims: Dict[str, Any]) -> bool:
        """
        Set custom claims for a Firebase user (useful for roles).

        Args:
            uid: Firebase user ID
            claims: Dictionary of custom claims to set

        Returns:
            True if successful, False otherwise
        """
        try:
            auth.set_custom_user_claims(uid, claims)
            logger.info(f"Set custom claims for user {uid}: {claims}")
            return True

        except Exception as e:
            logger.error(f"Error setting custom claims for {uid}: {str(e)}")
            return False

    async def revoke_refresh_tokens(self, uid: str) -> bool:
        """
        Revoke all refresh tokens for a user (force re-authentication).

        Args:
            uid: Firebase user ID

        Returns:
            True if successful, False otherwise
        """
        try:
            auth.revoke_refresh_tokens(uid)
            logger.info(f"Revoked refresh tokens for user: {uid}")
            return True

        except Exception as e:
            logger.error(f"Error revoking tokens for {uid}: {str(e)}")
            return False


# Singleton instance helper
_firebase_service_instance: Optional[FirebaseAuthService] = None


def get_firebase_auth_service(
    project_id: str, private_key: str, client_email: str
) -> FirebaseAuthService:
    """
    Get or create FirebaseAuthService singleton instance.

    Args:
        project_id: Firebase project ID
        private_key: Firebase service account private key
        client_email: Firebase service account email

    Returns:
        FirebaseAuthService instance
    """
    global _firebase_service_instance

    if _firebase_service_instance is None:
        _firebase_service_instance = FirebaseAuthService(
            project_id=project_id, private_key=private_key, client_email=client_email
        )

    return _firebase_service_instance
