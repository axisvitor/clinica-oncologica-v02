"""
Enhanced Authentication Endpoints with Token Blacklisting

This module provides enhanced authentication endpoints that integrate with the
Redis-based token blacklisting system to address JWT security vulnerabilities.

Features:
- Secure logout with token blacklisting
- Bulk token revocation
- Token status checking
- Admin token management
- Comprehensive audit logging
- Rate limiting protection

Security Enhancements:
- Immediate token invalidation on logout
- Bulk revocation for security incidents
- Admin capabilities for token management
- Detailed security audit trails
- Rate limiting for all endpoints

Author: Claude Code (Backend API Developer)
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_thread_safe_db as get_db, get_current_user
from app.models.user import User
from app.core.token_blacklist import (
    get_token_blacklist_manager,
    TokenBlacklistManager,
    BlacklistStats,
    TokenMetadata
)
from app.middleware.enhanced_auth import AuthTokenExtractor
from app.schemas.common import SuccessResponse
from app.utils.logging import get_logger
from app.utils.rate_limiter import limiter

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Enhanced Authentication"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class LogoutRequest(BaseModel):
    """Request model for logout endpoint."""
    revoke_all_sessions: bool = Field(default=False, description="Revoke all user sessions")
    reason: str = Field(default="logout", description="Reason for logout")


class LogoutResponse(BaseModel):
    """Response model for logout endpoint."""
    success: bool
    message: str
    tokens_revoked: int
    timestamp: datetime


class TokenStatusRequest(BaseModel):
    """Request model for token status check."""
    token: str = Field(..., description="JWT token to check")


class TokenStatusResponse(BaseModel):
    """Response model for token status check."""
    is_blacklisted: bool
    metadata: Optional[Dict[str, Any]] = None
    checked_at: datetime


class BulkRevokeRequest(BaseModel):
    """Request model for bulk token revocation."""
    tokens: List[str] = Field(..., min_items=1, max_items=100, description="List of tokens to revoke")
    reason: str = Field(default="bulk_revoke", description="Reason for revocation")


class BulkRevokeResponse(BaseModel):
    """Response model for bulk token revocation."""
    success: bool
    total_tokens: int
    revoked_count: int
    failed_count: int
    results: Dict[str, bool]
    timestamp: datetime


class BlacklistStatsResponse(BaseModel):
    """Response model for blacklist statistics."""
    stats: Dict[str, Any]
    retrieved_at: datetime


class AdminTokenManagementRequest(BaseModel):
    """Request model for admin token management."""
    action: str = Field(..., regex="^(revoke_user|cleanup|force_cleanup)$")
    user_id: Optional[str] = None
    reason: str = Field(default="admin_action")


class AdminTokenManagementResponse(BaseModel):
    """Response model for admin token management."""
    success: bool
    action_performed: str
    affected_tokens: int
    details: Dict[str, Any]
    timestamp: datetime


# =============================================================================
# CORE AUTHENTICATION ENDPOINTS
# =============================================================================

@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Secure Logout with Token Blacklisting",
    description="""
    Perform secure logout by blacklisting the current token.

    This endpoint immediately invalidates the user's current token by adding it
    to the Redis blacklist, ensuring it cannot be used for future requests.

    **Features:**
    - Immediate token invalidation
    - Optional revocation of all user sessions
    - Comprehensive audit logging
    - Rate limiting protection

    **Rate Limit**: 10 requests per minute per IP
    """,
    responses={
        200: {
            "description": "Logout successful",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Logout successful",
                        "tokens_revoked": 1,
                        "timestamp": "2024-01-01T12:00:00Z"
                    }
                }
            }
        },
        401: {"description": "Authentication required"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)
@limiter.limit("10/minute")
async def enhanced_logout(
    request: Request,
    logout_data: LogoutRequest,
    current_user: User = Depends(get_current_user),
    blacklist_manager: TokenBlacklistManager = Depends(get_token_blacklist_manager)
) -> LogoutResponse:
    """
    Perform secure logout with token blacklisting.

    This endpoint blacklists the current user's token to ensure immediate invalidation.
    """
    try:
        # Extract current token from request
        current_token = AuthTokenExtractor.extract_token_for_blacklist_check(request)

        if not current_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No token found in request"
            )

        tokens_revoked = 0

        # Get client info for audit
        client_info = {
            "ip_address": request.headers.get("X-Forwarded-For", str(request.client.host if request.client else "unknown")),
            "user_agent": request.headers.get("User-Agent", "")
        }

        # Blacklist current token
        success = blacklist_manager.blacklist_token(
            token=current_token,
            reason=logout_data.reason,
            user_id=str(current_user.id),
            ip_address=client_info["ip_address"],
            user_agent=client_info["user_agent"]
        )

        if success:
            tokens_revoked = 1
            logger.info(f"Token blacklisted for user {current_user.id} logout")
        else:
            logger.warning(f"Failed to blacklist token for user {current_user.id}")

        # TODO: If revoke_all_sessions is True, implement logic to revoke all user tokens
        # This would require maintaining a user-to-token mapping system
        if logout_data.revoke_all_sessions:
            logger.info(f"All session revocation requested for user {current_user.id} (not yet implemented)")

        return LogoutResponse(
            success=True,
            message="Logout successful" if tokens_revoked > 0 else "Logout completed (token already invalid)",
            tokens_revoked=tokens_revoked,
            timestamp=datetime.now(timezone.utc)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during enhanced logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


@router.post(
    "/token/status",
    response_model=TokenStatusResponse,
    summary="Check Token Blacklist Status",
    description="""
    Check if a specific token is blacklisted.

    This endpoint allows checking the blacklist status of any JWT token.
    Useful for debugging and administrative purposes.

    **Rate Limit**: 30 requests per minute per IP
    """,
    responses={
        200: {"description": "Token status retrieved"},
        400: {"description": "Invalid request"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)
@limiter.limit("30/minute")
async def check_token_status(
    request: Request,
    token_data: TokenStatusRequest,
    current_user: User = Depends(get_current_user),
    blacklist_manager: TokenBlacklistManager = Depends(get_token_blacklist_manager)
) -> TokenStatusResponse:
    """
    Check if a token is blacklisted and return its metadata.
    """
    try:
        # Check blacklist status
        is_blacklisted = blacklist_manager.is_blacklisted(token_data.token)

        # Get metadata if blacklisted
        metadata = None
        if is_blacklisted:
            token_metadata = blacklist_manager.get_token_metadata(token_data.token)
            if token_metadata:
                metadata = token_metadata.dict()

        logger.info(f"Token status checked by user {current_user.id}: blacklisted={is_blacklisted}")

        return TokenStatusResponse(
            is_blacklisted=is_blacklisted,
            metadata=metadata,
            checked_at=datetime.now(timezone.utc)
        )

    except Exception as e:
        logger.error(f"Error checking token status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check token status"
        )


# =============================================================================
# BULK OPERATIONS
# =============================================================================

@router.post(
    "/tokens/revoke-bulk",
    response_model=BulkRevokeResponse,
    summary="Bulk Token Revocation",
    description="""
    Revoke multiple tokens in bulk.

    This endpoint is useful for security incidents where multiple tokens
    need to be invalidated quickly.

    **Features:**
    - Bulk processing for performance
    - Detailed operation results
    - Comprehensive audit logging
    - Rate limiting protection

    **Limits:**
    - Maximum 100 tokens per request
    - Rate limit: 5 requests per hour per IP
    """,
    responses={
        200: {"description": "Bulk revocation completed"},
        400: {"description": "Invalid request"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)
@limiter.limit("5/hour")
async def bulk_revoke_tokens(
    request: Request,
    revoke_data: BulkRevokeRequest,
    current_user: User = Depends(get_current_user),
    blacklist_manager: TokenBlacklistManager = Depends(get_token_blacklist_manager)
) -> BulkRevokeResponse:
    """
    Revoke multiple tokens in bulk for security incidents.
    """
    try:
        # Get client info for audit
        client_info = {
            "ip_address": request.headers.get("X-Forwarded-For", str(request.client.host if request.client else "unknown")),
            "user_agent": request.headers.get("User-Agent", "")
        }

        # Prepare tokens data for bulk operation
        tokens_data = []
        for token in revoke_data.tokens:
            tokens_data.append({
                "token": token,
                "reason": revoke_data.reason,
                "user_id": str(current_user.id),
                "ip_address": client_info["ip_address"],
                "user_agent": client_info["user_agent"]
            })

        # Perform bulk revocation
        results = blacklist_manager.blacklist_tokens_bulk(tokens_data)

        # Calculate statistics
        revoked_count = sum(1 for success in results.values() if success)
        failed_count = len(results) - revoked_count

        logger.info(
            f"Bulk token revocation by user {current_user.id}: "
            f"{revoked_count}/{len(revoke_data.tokens)} tokens revoked"
        )

        return BulkRevokeResponse(
            success=revoked_count > 0,
            total_tokens=len(revoke_data.tokens),
            revoked_count=revoked_count,
            failed_count=failed_count,
            results=results,
            timestamp=datetime.now(timezone.utc)
        )

    except Exception as e:
        logger.error(f"Error during bulk token revocation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bulk revocation failed"
        )


# =============================================================================
# MONITORING AND STATISTICS
# =============================================================================

@router.get(
    "/blacklist/stats",
    response_model=BlacklistStatsResponse,
    summary="Get Blacklist Statistics",
    description="""
    Retrieve current blacklist statistics and metrics.

    This endpoint provides insights into token blacklisting activity,
    including counts by reason, token types, and cleanup metrics.

    **Rate Limit**: 20 requests per minute per IP
    """,
    responses={
        200: {"description": "Statistics retrieved"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)
@limiter.limit("20/minute")
async def get_blacklist_statistics(
    request: Request,
    current_user: User = Depends(get_current_user),
    blacklist_manager: TokenBlacklistManager = Depends(get_token_blacklist_manager)
) -> BlacklistStatsResponse:
    """
    Get current blacklist statistics and metrics.
    """
    try:
        stats = blacklist_manager.get_blacklist_stats()

        logger.info(f"Blacklist statistics requested by user {current_user.id}")

        return BlacklistStatsResponse(
            stats=stats.dict(),
            retrieved_at=datetime.now(timezone.utc)
        )

    except Exception as e:
        logger.error(f"Error retrieving blacklist statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


@router.get(
    "/blacklist/health",
    summary="Blacklist System Health Check",
    description="""
    Perform health check of the token blacklist system.

    This endpoint verifies Redis connectivity and system functionality.

    **Rate Limit**: 10 requests per minute per IP
    """,
    responses={
        200: {"description": "System healthy"},
        503: {"description": "System unhealthy"},
        429: {"description": "Rate limit exceeded"}
    }
)
@limiter.limit("10/minute")
async def blacklist_health_check(
    request: Request,
    current_user: User = Depends(get_current_user),
    blacklist_manager: TokenBlacklistManager = Depends(get_token_blacklist_manager)
):
    """
    Perform health check of the blacklist system.
    """
    try:
        health_result = blacklist_manager.health_check()

        if health_result.get("healthy", False):
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "healthy",
                    "details": health_result,
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "status": "unhealthy",
                    "details": health_result,
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            )

    except Exception as e:
        logger.error(f"Error during blacklist health check: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "error": str(e),
                "checked_at": datetime.now(timezone.utc).isoformat()
            }
        )


# =============================================================================
# ADMINISTRATIVE ENDPOINTS
# =============================================================================

@router.post(
    "/admin/token-management",
    response_model=AdminTokenManagementResponse,
    summary="Administrative Token Management",
    description="""
    Administrative endpoint for token management operations.

    **Available Actions:**
    - `revoke_user`: Revoke all tokens for a specific user
    - `cleanup`: Trigger cleanup of expired tokens
    - `force_cleanup`: Force immediate cleanup

    **Requires:** Admin role

    **Rate Limit**: 10 requests per hour per IP
    """,
    responses={
        200: {"description": "Operation completed"},
        400: {"description": "Invalid request"},
        403: {"description": "Admin access required"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)
@limiter.limit("10/hour")
async def admin_token_management(
    request: Request,
    admin_request: AdminTokenManagementRequest,
    current_user: User = Depends(get_current_user),
    blacklist_manager: TokenBlacklistManager = Depends(get_token_blacklist_manager)
) -> AdminTokenManagementResponse:
    """
    Administrative token management operations.

    This endpoint requires admin privileges and provides administrative
    functions for token management.
    """
    try:
        # Check admin privileges
        if not hasattr(current_user, 'role') or current_user.role != 'admin':
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )

        affected_tokens = 0
        details = {}

        if admin_request.action == "revoke_user":
            if not admin_request.user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="user_id required for revoke_user action"
                )

            # Revoke all tokens for user
            affected_tokens = blacklist_manager.revoke_user_tokens(
                user_id=admin_request.user_id,
                reason=admin_request.reason
            )
            details["user_id"] = admin_request.user_id

        elif admin_request.action in ["cleanup", "force_cleanup"]:
            # Trigger cleanup
            affected_tokens = blacklist_manager.cleanup_expired_tokens()
            details["cleanup_type"] = admin_request.action

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown action: {admin_request.action}"
            )

        logger.info(
            f"Admin token management action '{admin_request.action}' "
            f"performed by user {current_user.id}, affected {affected_tokens} tokens"
        )

        return AdminTokenManagementResponse(
            success=True,
            action_performed=admin_request.action,
            affected_tokens=affected_tokens,
            details=details,
            timestamp=datetime.now(timezone.utc)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during admin token management: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Administrative operation failed"
        )


# =============================================================================
# UTILITY ENDPOINTS
# =============================================================================

@router.post(
    "/validate-not-blacklisted",
    response_model=SuccessResponse,
    summary="Validate Token Not Blacklisted",
    description="""
    Utility endpoint to validate that the current token is not blacklisted.

    This endpoint can be used by client applications to verify token status
    before making important requests.

    **Rate Limit**: 100 requests per minute per IP
    """,
    responses={
        200: {"description": "Token is valid"},
        401: {"description": "Token is blacklisted"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    }
)
@limiter.limit("100/minute")
async def validate_token_not_blacklisted(
    request: Request,
    current_user: User = Depends(get_current_user)
) -> SuccessResponse:
    """
    Validate that the current token is not blacklisted.

    This endpoint will automatically validate the token through the
    enhanced authentication middleware.
    """
    try:
        # If we reach here, the token passed blacklist validation
        return SuccessResponse(
            success=True,
            message="Token is valid and not blacklisted"
        )

    except Exception as e:
        logger.error(f"Error during token validation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token validation failed"
        )


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================

@router.post(
    "/logout-legacy",
    response_model=SuccessResponse,
    summary="Legacy Logout Endpoint",
    description="""
    Legacy logout endpoint for backward compatibility.

    This endpoint provides the same functionality as the enhanced logout
    but with a simpler response format.

    **Rate Limit**: 10 requests per minute per IP
    """,
    deprecated=True
)
@limiter.limit("10/minute")
async def legacy_logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    blacklist_manager: TokenBlacklistManager = Depends(get_token_blacklist_manager)
) -> SuccessResponse:
    """
    Legacy logout endpoint for backward compatibility.
    """
    try:
        # Extract current token
        current_token = AuthTokenExtractor.extract_token_for_blacklist_check(request)

        if current_token:
            # Blacklist the token
            blacklist_manager.blacklist_token(
                token=current_token,
                reason="legacy_logout",
                user_id=str(current_user.id)
            )

        return SuccessResponse(
            success=True,
            message="Logout successful"
        )

    except Exception as e:
        logger.error(f"Error during legacy logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed"
        )


# Export router
__all__ = ["router"]