"""
Request context utilities for audit logging.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import Depends, Request

from app.models.user import User
from app.dependencies.auth_dependencies import get_optional_user
from app.utils.client_ip import get_client_ip


class RequestContext:
    """Container for request context information used in audit logging."""

    def __init__(
        self,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        user_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
    ):
        self.ip_address = ip_address
        self.user_agent = user_agent
        self.user_id = user_id
        self.session_id = session_id


async def get_request_context(
    request: Request, current_user: Optional[User] = Depends(get_optional_user)
) -> RequestContext:
    """Extract request context for audit logging."""
    # Extract IP address through the shared trusted-proxy boundary.
    ip_address = get_client_ip(request)

    # Extract user agent
    user_agent = request.headers.get("user-agent", "unknown")

    # Extract user ID if authenticated
    user_id = current_user.id if current_user else None

    # Extract session ID from request state or generate one
    session_id = getattr(request.state, "session_id", None)

    return RequestContext(
        ip_address=ip_address,
        user_agent=user_agent,
        user_id=user_id,
        session_id=session_id,
    )
