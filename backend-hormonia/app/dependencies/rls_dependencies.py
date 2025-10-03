"""
RLS-aware database dependency for incremental Row Level Security rollout.

This module provides database session dependencies that inject JWT claims
for RLS enforcement. Use these dependencies on endpoints that need to
respect RLS policies.

Usage:
    from app.dependencies.rls_dependencies import get_rls_db

    @router.get("/patients")
    async def list_patients(db: Session = Depends(get_rls_db)):
        # This query will respect RLS policies
        return db.query(Patient).all()
"""

from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
import json
import logging

from app.database import SessionLocal
from app.dependencies.auth_dependencies import get_current_user
from app.models.user import User
from app.config import settings

logger = logging.getLogger(__name__)


def get_rls_db(
    current_user: Optional[User] = Depends(get_current_user)
) -> Generator[Session, None, None]:
    """
    Get database session with RLS context injected.

    This dependency injects the JWT claims into the PostgreSQL session
    to enable Row Level Security policies. Use this for endpoints that
    should respect RLS policies.

    Args:
        current_user: The authenticated user (optional for public endpoints)

    Returns:
        Database session with RLS context

    Raises:
        HTTPException: If RLS is required but user is not authenticated
    """
    db = SessionLocal()

    try:
        # Inject JWT claims if user is authenticated
        if current_user:
            claims = {
                "sub": str(current_user.id),
                "email": current_user.email,
                "role": current_user.role,
                "aud": "authenticated",
                "exp": 9999999999  # Far future, actual expiry handled by auth
            }

            # Set the JWT claims in PostgreSQL session
            # This enables auth.uid() and auth.jwt() functions in RLS policies
            db.execute(
                "SELECT set_config('request.jwt.claims', :claims, true)",
                {"claims": json.dumps(claims)}
            )

            if settings.DEBUG:
                logger.debug(f"RLS context set for user {current_user.id} with role {current_user.role}")
        else:
            # For public endpoints, set anonymous context
            if settings.SUPABASE_ANON_KEY:
                claims = {
                    "role": "anon",
                    "aud": "public"
                }
                db.execute(
                    "SELECT set_config('request.jwt.claims', :claims, true)",
                    {"claims": json.dumps(claims)}
                )

                if settings.DEBUG:
                    logger.debug("RLS context set for anonymous user")

        yield db

    except Exception as e:
        logger.error(f"Error setting RLS context: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database context error"
        )
    finally:
        # Clear RLS context before closing
        try:
            db.execute("SELECT set_config('request.jwt.claims', NULL, true)")
        except:
            pass
        db.close()


def get_rls_db_required(
    current_user: User = Depends(get_current_user)
) -> Generator[Session, None, None]:
    """
    Get database session with RLS context, authentication required.

    This is a stricter version that requires authentication.
    Use this for endpoints that must have an authenticated user.

    Args:
        current_user: The authenticated user (required)

    Returns:
        Database session with RLS context
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for this endpoint"
        )

    # Delegate to the main RLS db function
    yield from get_rls_db(current_user)


def get_rls_db_admin(
    current_user: User = Depends(get_current_user)
) -> Generator[Session, None, None]:
    """
    Get database session for admin users with RLS context.

    This dependency requires admin role and still sets RLS context
    for audit purposes.

    Args:
        current_user: The authenticated admin user

    Returns:
        Database session with admin RLS context

    Raises:
        HTTPException: If user is not an admin
    """
    if not current_user or current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    # Admins still get RLS context for audit trail
    yield from get_rls_db(current_user)


# Utility functions for RLS management

def test_rls_connection(db: Session) -> dict:
    """
    Test if RLS context is properly set in the database session.

    Args:
        db: Database session to test

    Returns:
        Dictionary with RLS status information
    """
    try:
        # Check if JWT claims are set
        result = db.execute(
            "SELECT current_setting('request.jwt.claims', true) as claims"
        ).first()

        claims = None
        if result and result.claims:
            claims = json.loads(result.claims)

        # Check if auth.uid() works
        auth_uid = None
        if claims:
            try:
                auth_result = db.execute("SELECT auth.uid() as uid").first()
                if auth_result:
                    auth_uid = str(auth_result.uid)
            except:
                # auth.uid() might not be available if not using Supabase
                pass

        return {
            "has_claims": bool(claims),
            "claims": claims,
            "auth_uid": auth_uid,
            "rls_ready": bool(claims and claims.get("sub"))
        }

    except Exception as e:
        return {
            "has_claims": False,
            "error": str(e),
            "rls_ready": False
        }


# Export the dependencies
__all__ = [
    "get_rls_db",
    "get_rls_db_required",
    "get_rls_db_admin",
    "test_rls_connection"
]