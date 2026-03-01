"""
Client Error Reporting API

Receives frontend error reports and logs them server-side.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from app.utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


class ClientErrorPayload(BaseModel):
    error: Optional[Dict[str, Any]] = None
    errorInfo: Optional[Dict[str, Any]] = None
    level: Optional[str] = None
    errorId: Optional[str] = None
    url: Optional[str] = None
    userAgent: Optional[str] = None
    timestamp: Optional[str] = None

    model_config = ConfigDict(extra="allow")


def _truncate(value: Optional[str], limit: int = 2000) -> Optional[str]:
    if value is None:
        return None
    if len(value) <= limit:
        return value
    return value[:limit] + "...(truncated)"


@router.post("/errors/client", status_code=status.HTTP_204_NO_CONTENT)
async def report_client_error(payload: ClientErrorPayload, request: Request) -> Response:
    """Log frontend error reports for diagnostics."""
    client_ip = request.client.host if request.client else "unknown"
    level = (payload.level or "error").lower()

    error = payload.error or {}
    error_info = payload.errorInfo or {}

    log_extra = {
        "event_type": "client_error_report",
        "client_ip": client_ip,
        "level": level,
        "error_id": payload.errorId,
        "url": payload.url,
        "user_agent": payload.userAgent,
        "error_name": error.get("name"),
        "error_message": error.get("message"),
        "error_stack": _truncate(error.get("stack")),
        "component_stack": _truncate(error_info.get("componentStack")),
        "timestamp": payload.timestamp,
    }

    if level in {"critical", "error"}:
        logger.error("Client error report received", extra=log_extra)
    else:
        logger.warning("Client error report received", extra=log_extra)

    return Response(status_code=status.HTTP_204_NO_CONTENT)
