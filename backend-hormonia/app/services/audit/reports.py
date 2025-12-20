"""
Audit Reports Mixin Module.

Contains all query and reporting methods for compliance and analytics.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class AuditReportsMixin:
    """
    Mixin providing audit reporting and query methods.

    Requires: db attribute from BaseAuditService
    """

    def get_patient_audit_trail(
        self, patient_id: UUID, limit: int = 100
    ) -> list[AuditLog]:
        """Get audit trail for a specific patient (for LGPD export)."""
        # This query might need adjustment if patient_id is not directly in AuditLog
        # For now, assume we filter by metadata subject_id which is safer
        return (
            self.db.query(AuditLog)
            .filter(  # type: ignore[attr-defined]
                AuditLog.event_metadata["subject_id"].astext == str(patient_id)
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def cleanup_expired_logs(self) -> int:
        """Clean up logs past retention period."""
        # Retention is now handled by metadata or dedicated job, this is a placeholder
        # that logs intent but does nothing to avoid accidental deletion with new schema
        logger.info(
            "Cleanup called on legacy adapter - deferring to system retention policy"
        )
        return 0

    def get_ai_audit_report(
        self,
        start_date: datetime,
        end_date: datetime,
        event_types: Optional[List[str]] = None,
        user_id: Optional[UUID] = None,
        patient_id: Optional[UUID] = None,
    ) -> List[AuditLog]:
        """Get AI audit report for compliance."""
        # Query modified to work with new schema structure (no specific AI methods in core AuditLog)
        # We filter by event_type pattern or list
        query = self.db.query(AuditLog).filter(  # type: ignore[attr-defined]
            AuditLog.created_at >= start_date, AuditLog.created_at <= end_date
        )

        # Attempt to filter by AI events (legacy check)
        # Ideally, event_type would be checked against Enum values
        # but here we use a broad filter assuming legacy event types were strings
        # The new Enum doesn't have AI events explicitly defined yet, so we rely on metadata

        # TODO: Add AI event types to AuditEventType Enum in future migration

        if event_types:
            # This might fail if event_types are strings and DB expects Enums
            # We skip for now as this is a legacy report method
            pass

        if user_id:
            query = query.filter(AuditLog.user_id == user_id)

        # For patient_id, we check metadata as it's not a top-level column anymore
        if patient_id:
            query = query.filter(
                AuditLog.event_metadata["subject_id"].astext == str(patient_id)
            )

        return query.order_by(AuditLog.created_at.desc()).all()

    def get_ai_performance_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Get AI performance metrics from audit logs."""
        # Placeholder implementation
        return {
            "total_requests": 0,
            "cache_hit_rate": 0,
            "error_rate": 0,
            "average_response_time_ms": 0,
        }

    def get_patient_ai_access_history(
        self, patient_id: UUID, limit: int = 100
    ) -> List[AuditLog]:
        """Get AI access history for a patient (HIPAA compliance)."""
        # Filter by metadata subject_id
        return (
            self.db.query(AuditLog)
            .filter(  # type: ignore[attr-defined]
                AuditLog.event_metadata["subject_id"].astext == str(patient_id)
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_user_ai_activity(
        self, user_id: UUID, start_date: datetime, end_date: datetime
    ) -> List[AuditLog]:
        """Get user AI activity for audit purposes."""
        return (
            self.db.query(AuditLog)
            .filter(  # type: ignore[attr-defined]
                AuditLog.user_id == user_id,
                AuditLog.created_at >= start_date,
                AuditLog.created_at <= end_date,
            )
            .order_by(AuditLog.created_at.desc())
            .all()
        )

    def get_ai_security_events(
        self, start_date: datetime, end_date: datetime, severity: Optional[str] = None
    ) -> List[AuditLog]:
        """Get AI security events for monitoring."""
        # Severity is now in metadata
        query = self.db.query(AuditLog).filter(  # type: ignore[attr-defined]
            AuditLog.created_at >= start_date, AuditLog.created_at <= end_date
        )

        if severity:
            query = query.filter(AuditLog.event_metadata["severity"].astext == severity)

        return query.order_by(AuditLog.created_at.desc()).all()

    def export_ai_audit_data(
        self, patient_id: UUID, format: str = "json"
    ) -> Dict[str, Any]:
        """Export AI audit data for a patient (HIPAA compliance)."""
        logs = self.get_patient_ai_access_history(patient_id, limit=1000)

        export_data = {
            "patient_id": str(patient_id),
            "export_date": datetime.now(timezone.utc).isoformat(),
            "total_logs": len(logs),
            "logs": [
                {
                    "timestamp": log.created_at.isoformat(),
                    "event_type": log.event_type.value
                    if hasattr(log.event_type, "value")
                    else str(log.event_type),
                    "actor_id": str(log.user_id),
                    "result": log.event_status,
                    "event_data": log.event_metadata,
                }
                for log in logs
            ],
        }

        return export_data
