"""
CSP Violation Report Endpoint

Receives and processes Content Security Policy violation reports
from browsers to monitor security issues and potential attacks.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict

from app.middleware.csp_nonce import csp_report_handler
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/csp-report", tags=["security"])


class CSPViolationReport(BaseModel):
    """CSP violation report schema (sent by browsers)"""

    document_uri: Optional[str] = Field(None, alias="document-uri")
    violated_directive: Optional[str] = Field(None, alias="violated-directive")
    effective_directive: Optional[str] = Field(None, alias="effective-directive")
    original_policy: Optional[str] = Field(None, alias="original-policy")
    blocked_uri: Optional[str] = Field(None, alias="blocked-uri")
    status_code: Optional[int] = Field(None, alias="status-code")
    source_file: Optional[str] = Field(None, alias="source-file")
    line_number: Optional[int] = Field(None, alias="line-number")
    column_number: Optional[int] = Field(None, alias="column-number")

    model_config = ConfigDict(populate_by_name=True)


class CSPReportWrapper(BaseModel):
    """Wrapper for CSP report (browser sends 'csp-report' key)"""

    csp_report: CSPViolationReport = Field(..., alias="csp-report")

    model_config = ConfigDict(populate_by_name=True)


@router.post("")
@router.post("/")
async def receive_csp_report(request: Request) -> JSONResponse:
    """
    Receive CSP violation report from browser.

    Browsers send CSP violation reports when content is blocked by CSP.
    This endpoint logs and analyzes these reports to detect security issues.

    Args:
        request: The HTTP request containing the CSP report

    Returns:
        Acknowledgment response
    """
    try:
        # Parse CSP report
        await request.json()

        # Handle report
        result = await csp_report_handler.handle_report(request)

        logger.info(
            "CSP violation report received",
            extra={
                "event_type": "csp_report_received",
                "violation_id": result.get("violation_id"),
                "client_ip": request.client.host if request.client else "unknown",
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            },
        )

        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)

    except Exception as e:
        logger.error(
            f"Failed to process CSP report: {str(e)}",
            exc_info=True,
            extra={"event_type": "csp_report_error", "error": str(e)},
        )

        # Return 204 anyway to not alert browser
        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)


@router.get("/violations")
async def get_csp_violations(
    limit: int = 100, severity: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get recent CSP violations (admin endpoint).

    This endpoint returns recent CSP violations for security monitoring.

    Args:
        limit: Maximum number of violations to return (default: 100)
        severity: Filter by severity: "HIGH" or None for all

    Returns:
        List of CSP violation records
    """
    try:
        violations = csp_report_handler.get_violations(
            limit=min(limit, 1000),  # Cap at 1000
            severity=severity,
        )

        return {
            "total": len(violations),
            "violations": violations,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        }

    except Exception as e:
        logger.error(f"Failed to retrieve CSP violations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve CSP violations",
        )


@router.get("/stats")
async def get_csp_stats() -> Dict[str, Any]:
    """
    Get CSP violation statistics (admin endpoint).

    Returns aggregated statistics about CSP violations for
    security monitoring and policy optimization.

    Returns:
        CSP violation statistics
    """
    try:
        violations = csp_report_handler.violations

        if not violations:
            return {
                "total_violations": 0,
                "suspicious_violations": 0,
                "by_directive": {},
                "by_uri": {},
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            }

        # Count violations by directive
        by_directive: Dict[str, int] = {}
        by_uri: Dict[str, int] = {}
        suspicious_count = 0

        for violation in violations:
            directive = violation.get("violated_directive", "unknown")
            uri = violation.get("blocked_uri", "unknown")

            by_directive[directive] = by_directive.get(directive, 0) + 1
            by_uri[uri] = by_uri.get(uri, 0) + 1

            if csp_report_handler._is_suspicious(violation):
                suspicious_count += 1

        return {
            "total_violations": len(violations),
            "suspicious_violations": suspicious_count,
            "by_directive": by_directive,
            "by_uri": by_uri,
            "top_blocked_uris": sorted(
                by_uri.items(), key=lambda x: x[1], reverse=True
            )[:10],
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        }

    except Exception as e:
        logger.error(f"Failed to retrieve CSP stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve CSP statistics",
        )


@router.delete("/violations")
async def clear_csp_violations() -> Dict[str, str]:
    """
    Clear CSP violation history (admin endpoint).

    Clears all stored CSP violation records.

    Returns:
        Confirmation message
    """
    try:
        csp_report_handler.violations.clear()

        logger.info(
            "CSP violations cleared",
            extra={
                "event_type": "csp_violations_cleared",
                "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
            },
        )

        return {
            "status": "success",
            "message": "CSP violations cleared",
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        }

    except Exception as e:
        logger.error(f"Failed to clear CSP violations: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear CSP violations",
        )
