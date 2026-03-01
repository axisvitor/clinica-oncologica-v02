"""
CSP Report Handler - Content Security Policy Violation Reporting

Extracted from csp_nonce.py. Receives and processes CSP violation reports
from browsers to monitor security issues and potential attacks.
"""

from typing import Optional

from fastapi import Request

from app.utils.logging import get_logger
from app.utils.timezone import now_sao_paulo

logger = get_logger(__name__)


class CSPReportHandler:
    """
    Handler for CSP violation reports.

    Receives and processes CSP violation reports from browsers
    to monitor security issues and potential attacks.
    """

    def __init__(self):
        self.violations = []
        self.max_violations = 1000  # Keep last 1000 violations

    async def handle_report(self, request: Request) -> dict:
        """
        Process CSP violation report.

        Args:
            request: Request containing CSP violation report

        Returns:
            Acknowledgment response
        """
        try:
            report = await request.json()

            # Extract violation details
            csp_report = report.get("csp-report", {})

            violation = {
                "timestamp": now_sao_paulo().isoformat(),
                "document_uri": csp_report.get("document-uri"),
                "violated_directive": csp_report.get("violated-directive"),
                "effective_directive": csp_report.get("effective-directive"),
                "original_policy": csp_report.get("original-policy"),
                "blocked_uri": csp_report.get("blocked-uri"),
                "status_code": csp_report.get("status-code"),
                "source_file": csp_report.get("source-file"),
                "line_number": csp_report.get("line-number"),
                "column_number": csp_report.get("column-number"),
            }

            # Store violation
            self.violations.append(violation)

            # Keep only recent violations
            if len(self.violations) > self.max_violations:
                self.violations = self.violations[-self.max_violations :]

            # Log violation
            logger.warning(
                f"CSP violation: {violation['violated_directive']}",
                extra={"event_type": "csp_violation", **violation},
            )

            # Alert on suspicious patterns
            if self._is_suspicious(violation):
                logger.error(
                    "Suspicious CSP violation detected",
                    extra={
                        "event_type": "csp_suspicious_violation",
                        "severity": "HIGH",
                        **violation,
                    },
                )

            return {"status": "accepted", "violation_id": len(self.violations)}

        except Exception as e:
            logger.error(f"Failed to process CSP report: {str(e)}", exc_info=True)
            return {"status": "error", "message": str(e)}

    def _is_suspicious(self, violation: dict) -> bool:
        """
        Check if violation indicates potential attack.

        Args:
            violation: CSP violation details

        Returns:
            True if violation appears suspicious
        """
        suspicious_patterns = [
            "eval",
            "inline",
            "data:",
            "javascript:",
            "vbscript:",
            "blob:",
            "filesystem:",
        ]

        blocked_uri = violation.get("blocked_uri", "").lower()
        violated_directive = violation.get("violated_directive", "").lower()

        return any(
            pattern in blocked_uri or pattern in violated_directive
            for pattern in suspicious_patterns
        )

    def get_violations(
        self, limit: int = 100, severity: Optional[str] = None
    ) -> list[dict]:
        """
        Get recent CSP violations.

        Args:
            limit: Maximum number of violations to return
            severity: Filter by severity (optional)

        Returns:
            List of violation records
        """
        violations = self.violations[-limit:]

        if severity:
            violations = [
                v for v in violations if self._is_suspicious(v) == (severity == "HIGH")
            ]

        return violations


# Global CSP report handler instance
csp_report_handler = CSPReportHandler()
