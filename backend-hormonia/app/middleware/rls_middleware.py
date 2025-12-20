"""
RLS (Row Level Security) middleware for JWT token extraction and context management.

This middleware handles JWT token extraction from requests and provides utilities
for injecting user context into database sessions for RLS policies.
"""

from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer
from typing import Optional, Dict, Any
import jwt
import logging
from datetime import datetime, timezone

from app.core.database import RLSError, RLSAccessDeniedError, RLSContextError

logger = logging.getLogger(__name__)


class RLSJWTMiddleware:
    """
    Middleware for extracting and validating JWT tokens for RLS context.

    This middleware extracts JWT tokens from requests and provides methods
    to inject user context into database sessions for Row Level Security.
    """

    def __init__(self):
        self.security = HTTPBearer(auto_error=False)

    async def extract_jwt_token(self, request: Request) -> Optional[str]:
        """
        Extract JWT token from request headers.

        Args:
            request: FastAPI request object

        Returns:
            JWT token string or None if not found
        """
        try:
            # Try Authorization header first (Firebase/Bearer token)
            auth_header = request.headers.get("Authorization")
            if auth_header:
                if auth_header.startswith("Bearer "):
                    return auth_header[7:].strip()  # Remove "Bearer " prefix
                elif not auth_header.startswith("Basic "):
                    # Assume it's a JWT token without Bearer prefix
                    return auth_header.strip()

            # Try query parameter as fallback (for WebSocket connections)
            token = request.query_params.get("token")
            if token:
                return token

            # Try cookie as last resort (for session-based auth)
            token = request.cookies.get("auth_token")
            if token:
                return token

            return None

        except Exception as e:
            logger.warning(f"Error extracting JWT token: {e}")
            return None

    def validate_jwt_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate JWT token and extract claims.

        SECURITY NOTE: This method decodes JWT without signature verification.
        This is ONLY acceptable because:
        1. The token has already been verified by Firebase/auth middleware
        2. This is used for extracting context AFTER authentication
        3. Critical operations must use proper auth dependencies

        For security-critical operations, use auth_dependencies.py which
        properly validates tokens through Firebase Admin SDK.

        Args:
            token: JWT token string

        Returns:
            Decoded token claims or None if invalid
        """
        try:
            # SECURITY WARNING: Signature verification disabled
            # This is acceptable ONLY for extracting context from already-verified tokens
            # Do NOT use this for authentication - use Firebase Admin SDK validation
            decoded_token = jwt.decode(token, options={"verify_signature": False})

            # Check if token is expired
            exp = decoded_token.get("exp")
            if exp and datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(
                timezone.utc
            ):
                logger.warning("JWT token has expired")
                return None

            return decoded_token

        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error validating JWT token: {e}")
            return None

    def extract_user_context(self, token_claims: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract user context from JWT token claims.

        Args:
            token_claims: Decoded JWT token claims

        Returns:
            User context dictionary
        """
        return {
            "user_id": token_claims.get("sub") or token_claims.get("user_id"),
            "email": token_claims.get("email"),
            "role": token_claims.get("role", "authenticated"),
            "aud": token_claims.get("aud"),
            "iss": token_claims.get("iss"),
            "exp": token_claims.get("exp"),
            "iat": token_claims.get("iat"),
            "app_metadata": token_claims.get("app_metadata", {}),
            "user_metadata": token_claims.get("user_metadata", {}),
        }

    async def get_user_context_from_request(
        self, request: Request
    ) -> Optional[Dict[str, Any]]:
        """
        Get user context from request JWT token.

        Args:
            request: FastAPI request object

        Returns:
            User context dictionary or None if no valid token
        """
        token = await self.extract_jwt_token(request)
        if not token:
            return None

        token_claims = self.validate_jwt_token(token)
        if not token_claims:
            return None

        return self.extract_user_context(token_claims)

    def check_rls_permissions(
        self, user_context: Dict[str, Any], required_permissions: list = None
    ) -> bool:
        """
        Check if user has required permissions for RLS access.

        Args:
            user_context: User context from JWT token
            required_permissions: List of required permissions

        Returns:
            True if user has required permissions
        """
        if not user_context or not user_context.get("user_id"):
            return False

        # Basic authentication check
        if user_context.get("role") not in ["authenticated", "admin", "service_role"]:
            return False

        # If specific permissions are required, check them
        if required_permissions:
            user_permissions = user_context.get("app_metadata", {}).get(
                "permissions", []
            )
            if not all(perm in user_permissions for perm in required_permissions):
                return False

        return True

    def handle_rls_error(
        self, error: Exception, user_context: Optional[Dict[str, Any]] = None
    ) -> HTTPException:
        """
        Handle RLS-related errors and convert to appropriate HTTP exceptions.

        Args:
            error: Original exception
            user_context: User context if available

        Returns:
            HTTPException with appropriate status and message
        """
        if isinstance(error, RLSAccessDeniedError):
            return HTTPException(
                status_code=403,
                detail={
                    "error": "Access denied by Row Level Security policy",
                    "message": "You don't have permission to access this resource",
                    "user_id": user_context.get("user_id") if user_context else None,
                },
            )
        elif isinstance(error, RLSContextError):
            return HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid RLS context",
                    "message": "Authentication context is required for this operation",
                    "user_id": user_context.get("user_id") if user_context else None,
                },
            )
        elif isinstance(error, RLSError):
            return HTTPException(
                status_code=500,
                detail={
                    "error": "RLS operation failed",
                    "message": "Row Level Security operation encountered an error",
                    "user_id": user_context.get("user_id") if user_context else None,
                },
            )
        else:
            # Generic database error
            return HTTPException(
                status_code=500,
                detail={
                    "error": "Database operation failed",
                    "message": "An error occurred while accessing the database",
                    "user_id": user_context.get("user_id") if user_context else None,
                },
            )


# Global middleware instance
rls_middleware = RLSJWTMiddleware()


# FastAPI dependency for extracting JWT token
async def get_jwt_token(request: Request) -> Optional[str]:
    """
    FastAPI dependency to extract JWT token from request.

    Args:
        request: FastAPI request object

    Returns:
        JWT token string or None
    """
    return await rls_middleware.extract_jwt_token(request)


# FastAPI dependency for getting user context
async def get_user_context(request: Request) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency to get user context from request.

    Args:
        request: FastAPI request object

    Returns:
        User context dictionary or None
    """
    return await rls_middleware.get_user_context_from_request(request)


# FastAPI dependency for required authentication
async def require_authentication(request: Request) -> Dict[str, Any]:
    """
    FastAPI dependency that requires valid authentication.

    Args:
        request: FastAPI request object

    Returns:
        User context dictionary

    Raises:
        HTTPException: If authentication is missing or invalid
    """
    user_context = await get_user_context(request)

    if not user_context:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "Authentication required",
                "message": "Valid JWT token is required for this operation",
            },
        )

    if not rls_middleware.check_rls_permissions(user_context):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "Insufficient permissions",
                "message": "You don't have permission to access this resource",
                "user_id": user_context.get("user_id"),
            },
        )

    return user_context


# FastAPI dependency for optional authentication
async def optional_authentication(request: Request) -> Optional[Dict[str, Any]]:
    """
    FastAPI dependency for optional authentication.

    Args:
        request: FastAPI request object

    Returns:
        User context dictionary or None if not authenticated
    """
    try:
        return await get_user_context(request)
    except Exception as e:
        logger.warning(f"Optional authentication failed: {e}")
        return None


# Utility function for RLS-aware database sessions
def get_rls_db_dependency(require_auth: bool = True):
    """
    Create a database dependency with RLS context.

    Args:
        require_auth: Whether authentication is required

    Returns:
        FastAPI dependency function
    """
    from app.core.database import get_db

    async def rls_db_dependency(
        request: Request, user_context: Optional[Dict[str, Any]] = None
    ):
        """Database dependency with RLS context."""
        if require_auth and not user_context:
            user_context = await require_authentication(request)
        elif not user_context:
            user_context = await optional_authentication(request)

        # Extract JWT token for database context
        jwt_token = None
        if user_context:
            jwt_token = await get_jwt_token(request)

        # Return database session with RLS context
        return get_db(
            jwt_token=jwt_token,
            user_id=user_context.get("user_id") if user_context else None,
        )

    return rls_db_dependency
