"""
Audit Reports Mixin for Compliance Reporting.

Provides query methods for generating audit reports, analytics,
and compliance exports for LGPD and HIPAA.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.models.audit_log import AuditLog


class AuditReportsMixin:
    """Mixin class for audit reporting and query methods."""

    def get_ai_audit_report(
        self,
        start_date: datetime,
        end_date: datetime,
        event_types: Optional[List[str]] = None,
        user_id: Optional[UUID] = None,
        patient_id: Optional[UUID] = None,
    ) -> List[AuditLog]:
        """
        Get AI audit report for compliance.

        Args:
            start_date: Start date for report period
            end_date: End date for report period
            event_types: List of event types to filter (optional)
            user_id: Filter by specific user (optional)
            patient_id: Filter by specific patient (optional)

        Returns:
            List[AuditLog]: List of audit log entries matching criteria

        Note:
            The new AuditLog schema doesn't have dedicated AI event types in the Enum yet.
            This method filters broadly and relies on event_metadata for AI-specific filtering.
            Consider adding AI event types to AuditEventType enum in a future migration.
        """
        query = self.db.query(AuditLog).filter(
            AuditLog.created_at >= start_date, AuditLog.created_at <= end_date
        )

        # TODO: Add AI event types to AuditEventType Enum in future migration
        # For now, we skip event_types filtering as the Enum doesn't support legacy AI events

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
        """
        Get AI performance metrics from audit logs.

        Args:
            start_date: Start date for metrics period
            end_date: End date for metrics period

        Returns:
            Dict[str, Any]: Performance metrics including:
                - total_requests: Total number of AI requests
                - cache_hit_rate: Percentage of cache hits
                - error_rate: Percentage of errors
                - average_response_time_ms: Average response time

        Note:
            This is a placeholder implementation that returns zero values.
            Full implementation requires aggregating metadata fields from audit logs.
        """
        # Placeholder implementation
        # TODO: Implement actual metrics aggregation from event_metadata
        return {
            "total_requests": 0,
            "cache_hit_rate": 0,
            "error_rate": 0,
            "average_response_time_ms": 0,
        }

    def get_patient_ai_access_history(
        self, patient_id: UUID, limit: int = 100
    ) -> List[AuditLog]:
        """
        Get AI access history for a patient (HIPAA compliance).

        Args:
            patient_id: Patient to get access history for
            limit: Maximum number of records to return

        Returns:
            List[AuditLog]: List of AI access events for the patient
        """
        # Filter by metadata subject_id since patient_id is not a top-level column
        return (
            self.db.query(AuditLog)
            .filter(AuditLog.event_metadata["subject_id"].astext == str(patient_id))
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_user_ai_activity(
        self, user_id: UUID, start_date: datetime, end_date: datetime
    ) -> List[AuditLog]:
        """
        Get user AI activity for audit purposes.

        Args:
            user_id: User to get activity for
            start_date: Start date for activity period
            end_date: End date for activity period

        Returns:
            List[AuditLog]: List of AI activity events for the user
        """
        return (
            self.db.query(AuditLog)
            .filter(
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
        """
        Get AI security events for monitoring.

        Args:
            start_date: Start date for monitoring period
            end_date: End date for monitoring period
            severity: Filter by severity level (optional)

        Returns:
            List[AuditLog]: List of security events

        Note:
            Severity is stored in event_metadata in the new schema.
        """
        query = self.db.query(AuditLog).filter(
            AuditLog.created_at >= start_date, AuditLog.created_at <= end_date
        )

        if severity:
            query = query.filter(AuditLog.event_metadata["severity"].astext == severity)

        return query.order_by(AuditLog.created_at.desc()).all()

    def export_ai_audit_data(
        self, patient_id: UUID, format: str = "json"
    ) -> Dict[str, Any]:
        """
        Export AI audit data for a patient (HIPAA compliance).

        Args:
            patient_id: Patient to export data for
            format: Export format (currently only 'json' is supported)

        Returns:
            Dict[str, Any]: Exported audit data including:
                - patient_id: Patient identifier
                - export_date: Date of export
                - total_logs: Number of log entries
                - logs: List of log entries with details
        """
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
