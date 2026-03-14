"""Retirement router for the legacy root ``/session/*`` surface.

The official staff-auth contract lives under ``/api/v2/auth/*`` and uses the
session cookie. The root ``/session/*`` island stays mounted only so accidental
callers receive a deterministic tombstone instead of generic 404 drift.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request, status

from app.core.exceptions import APIException

logger = logging.getLogger(__name__)

AUTH_LEGACY_SESSION_ROUTE_RETIRED = "AUTH_LEGACY_SESSION_ROUTE_RETIRED"
LEGACY_SESSION_ROUTE_MESSAGE = (
    "Legacy /session routes are retired. Use /api/v2/auth/* with the session cookie."
)

router = APIRouter(prefix="/session", tags=["Retired Session Endpoints"])

_SUPPORTED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]


def _retirement_details(request: Request) -> dict[str, Any]:
    retired_path = request.url.path.rstrip("/") or "/session"
    return {
        "retired_path": retired_path,
        "replacement_prefix": "/api/v2/auth",
        "required_transport": "session_cookie",
        "request_method": request.method,
    }


async def _raise_retired_session_route(request: Request) -> None:
    details = _retirement_details(request)
    logger.info(
        "Rejected request to retired legacy session surface method=%s path=%s",
        details["request_method"],
        details["retired_path"],
    )
    raise APIException(
        message=LEGACY_SESSION_ROUTE_MESSAGE,
        status_code=status.HTTP_410_GONE,
        error_code=AUTH_LEGACY_SESSION_ROUTE_RETIRED,
        details=details,
    )


@router.api_route("", methods=_SUPPORTED_METHODS, include_in_schema=False)
@router.api_route("/", methods=_SUPPORTED_METHODS, include_in_schema=False)
@router.api_route("/{legacy_path:path}", methods=_SUPPORTED_METHODS, include_in_schema=False)
async def retired_session_surface(request: Request, legacy_path: str = "") -> None:
    _ = legacy_path
    await _raise_retired_session_route(request)
