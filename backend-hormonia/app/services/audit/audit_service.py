"""
HIPAA Audit Service - Phase 3 Sprint 1

This service provides comprehensive audit logging capabilities with:
- Tamper-proof event logging (SHA-256 checksums + chain of custody)
- PHI access tracking
- Data modification tracking (before/after states)
- Automatic integrity verification
- 6-year retention policy

HIPAA Compliance:
- § 164.312(b) - Audit Controls
- § 164.312(c)(1) - Integrity Controls
- § 164.316(b)(2)(i) - Retention & Archival

Usage:
    from app.services.audit import AuditService

    audit_service = AuditService(db)
    await audit_service.log_event(
        event_type=AuditEventType.PHI_PATIENT_VIEW,
        user_id=user.id,
        resource_type="PATIENT",
        resource_id=patient.id,
        metadata={"patient_mrn": "12345"}
    )
"""
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel

from app.models.audit_log import AuditLog, AuditEventType
from app.services.audit.audit_repository import AuditRepository


class AuditEventContext(BaseModel):
    """Context information for audit events."""

    # User context
    user_id: Optional[UUID] = None
    user_email: Optional[str] = None
    user_role: Optional[str] = None
    firebase_uid: Optional[str] = None

    # Session context
    session_id: Optional[str] = None
    session_token_hash: Optional[str] = None
    device_fingerprint: Optional[str] = None

    # Network context
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    geolocation: Optional[Dict[str, Any]] = None

    # Request context
    http_method: Optional[str] = None
    endpoint: Optional[str] = None
    query_params: Optional[Dict[str, Any]] = None
    request_body_hash: Optional[str] = None
    http_status_code: Optional[int] = None

    # Resource context
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    resource_identifiers: Optional[Dict[str, Any]] = None

    # Operation context
    operation: Optional[str] = None  # CREATE, READ, UPDATE, DELETE, EXPORT, PRINT, SHARE
    description: Optional[str] = None

    # Change tracking
    changes_before: Optional[Dict[str, Any]] = None
    changes_after: Optional[Dict[str, Any]] = None
    changed_fields: Optional[List[str]] = None

    # Result context
    status: str = "SUCCESS"  # SUCCESS, FAILURE, ERROR, BLOCKED
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    error_stack_trace: Optional[str] = None
    duration_ms: Optional[int] = None

    # Additional metadata
    metadata: Optional[Dict[str, Any]] = None


class AuditService:
    """
    HIPAA-compliant audit logging service with tamper-proof integrity controls.
    """

    def __init__(self, db: AsyncSession):
        """Initialize audit service with database session."""
        self.db = db
        self.repository = AuditRepository(db)

    async def log_event(
        self,
        event_type: AuditEventType,
        event_category: str,
        context: AuditEventContext,
    ) -> AuditLog:
        """
        Log an audit event with tamper-proof integrity controls.

        Args:
            event_type: Type of event (from AuditEventType enum)
            event_category: Event category (AUTHENTICATION, PHI_ACCESS, etc.)
            context: Complete event context

        Returns:
            Created AuditLog instance

        Example:
            await audit_service.log_event(
                event_type=AuditEventType.PHI_PATIENT_VIEW,
                event_category="PHI_ACCESS",
                context=AuditEventContext(
                    user_id=user.id,
                    resource_type="PATIENT",
                    resource_id=patient.id,
                    ip_address="192.168.1.1",
                    status="SUCCESS"
                )
            )
        """
        # Calculate changed fields if before/after provided
        if context.changes_before and context.changes_after:
            context.changed_fields = self._calculate_changed_fields(
                context.changes_before,
                context.changes_after
            )

        # Create audit log entry
        audit_log = AuditLog(
            # Event information
            event_type=event_type,
            event_category=event_category,
            event_status=context.status.lower(),  # Legacy field compatibility
            status=context.status,

            # User identification
            user_id=context.user_id,
            user_email=context.user_email,
            user_role=context.user_role,
            firebase_uid=context.firebase_uid,

            # Session tracking
            session_id=context.session_id,
            session_token_hash=context.session_token_hash,
            device_fingerprint=context.device_fingerprint,
            geolocation=context.geolocation,

            # Network information
            ip_address=context.ip_address,
            user_agent=context.user_agent,

            # Request information
            http_method=context.http_method,
            endpoint=context.endpoint,
            query_params=context.query_params,
            request_body_hash=context.request_body_hash,
            http_status_code=context.http_status_code,

            # Resource information
            resource_type=context.resource_type,
            resource_id=context.resource_id,
            resource_identifiers=context.resource_identifiers,
            resource=context.endpoint,  # Legacy field compatibility
            action=context.operation,  # Legacy field compatibility

            # Operation details
            operation=context.operation,
            description=context.description,

            # Change tracking
            changes_before=context.changes_before,
            changes_after=context.changes_after,
            changed_fields=context.changed_fields,

            # Result information
            error_code=context.error_code,
            error_details=context.error_message,  # Legacy field compatibility
            error_stack_trace=context.error_stack_trace,
            message=context.description,  # Legacy field compatibility
            duration_ms=context.duration_ms,

            # Additional metadata
            event_metadata=context.metadata or {},

            # Retention (will be set by trigger)
            retention_period_years=6,
            # archive_eligible_at will be auto-calculated by trigger
        )

        # Note: Checksum, previous_checksum, and archive_eligible_at
        # are automatically calculated by the database trigger

        # Save to database
        self.db.add(audit_log)
        await self.db.commit()
        await self.db.refresh(audit_log)

        return audit_log

    async def verify_integrity(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Verify the integrity of audit logs using checksums and chain of custody.

        Args:
            start_date: Start date for verification range (optional)
            end_date: End date for verification range (optional)

        Returns:
            Dictionary with verification results:
            - total_checked: Number of logs verified
            - valid_count: Number of valid logs
            - invalid_count: Number of tampered logs
            - chain_breaks: Number of chain breaks
            - invalid_log_ids: List of compromised log IDs

        Example:
            result = await audit_service.verify_integrity()
            if result['invalid_count'] > 0:
                # Alert security team!
                pass
        """
        return await self.repository.verify_integrity(start_date, end_date)

    async def archive_old_logs(self) -> int:
        """
        Archive audit logs older than 1 year to the archive table.

        Returns:
            Number of logs archived

        Note:
            This calls the PostgreSQL archive_old_audit_logs() function
            which moves logs to the partitioned archive table.
        """
        return await self.repository.archive_old_logs()

    async def get_phi_access_logs(
        self,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Retrieve PHI access logs for compliance reporting.

        Args:
            resource_type: Filter by resource type (PATIENT, MEDICATION, etc.)
            resource_id: Filter by specific resource ID
            user_id: Filter by user who accessed the data
            start_date: Start date for query range
            end_date: End date for query range
            limit: Maximum number of results

        Returns:
            List of PHI access audit logs
        """
        query = select(AuditLog).where(
            AuditLog.event_category == "PHI_ACCESS"
        )

        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
        if start_date:
            query = query.where(AuditLog.created_at >= start_date)
        if end_date:
            query = query.where(AuditLog.created_at <= end_date)

        query = query.order_by(AuditLog.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_data_modifications(
        self,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        operation: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Retrieve data modification logs with before/after states.

        Args:
            resource_type: Filter by resource type
            resource_id: Filter by specific resource
            operation: Filter by operation (CREATE, UPDATE, DELETE)
            start_date: Start date for query range
            end_date: End date for query range
            limit: Maximum number of results

        Returns:
            List of data modification audit logs
        """
        query = select(AuditLog).where(
            AuditLog.event_category == "DATA_MODIFICATION"
        )

        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
        if operation:
            query = query.where(AuditLog.operation == operation)
        if start_date:
            query = query.where(AuditLog.created_at >= start_date)
        if end_date:
            query = query.where(AuditLog.created_at <= end_date)

        query = query.order_by(AuditLog.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_user_activity(
        self,
        user_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Retrieve all activity for a specific user.

        Args:
            user_id: User ID to query
            start_date: Start date for query range
            end_date: End date for query range
            limit: Maximum number of results

        Returns:
            List of audit logs for the user
        """
        query = select(AuditLog).where(AuditLog.user_id == user_id)

        if start_date:
            query = query.where(AuditLog.created_at >= start_date)
        if end_date:
            query = query.where(AuditLog.created_at <= end_date)

        query = query.order_by(AuditLog.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_anomalous_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        min_score: float = 70.0,
        limit: int = 100
    ) -> List[AuditLog]:
        """
        Retrieve anomalous events for security review.

        Args:
            start_date: Start date for query range
            end_date: End date for query range
            min_score: Minimum anomaly score (0-100)
            limit: Maximum number of results

        Returns:
            List of anomalous audit logs
        """
        query = select(AuditLog).where(
            and_(
                AuditLog.is_anomalous == True,
                AuditLog.anomaly_score >= min_score
            )
        )

        if start_date:
            query = query.where(AuditLog.created_at >= start_date)
        if end_date:
            query = query.where(AuditLog.created_at <= end_date)

        query = query.order_by(AuditLog.anomaly_score.desc(), AuditLog.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_compliance_statistics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Generate compliance statistics for reporting.

        Args:
            start_date: Start date for statistics
            end_date: End date for statistics

        Returns:
            Dictionary with compliance statistics
        """
        # Total events
        total_query = select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.created_at >= start_date,
                AuditLog.created_at <= end_date
            )
        )
        total_result = await self.db.execute(total_query)
        total_events = total_result.scalar() or 0

        # Events by category
        category_query = select(
            AuditLog.event_category,
            func.count(AuditLog.id)
        ).where(
            and_(
                AuditLog.created_at >= start_date,
                AuditLog.created_at <= end_date
            )
        ).group_by(AuditLog.event_category)

        category_result = await self.db.execute(category_query)
        events_by_category = dict(category_result.all())

        # Failed events
        failed_query = select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.created_at >= start_date,
                AuditLog.created_at <= end_date,
                AuditLog.status.in_(['FAILURE', 'ERROR'])
            )
        )
        failed_result = await self.db.execute(failed_query)
        failed_events = failed_result.scalar() or 0

        # Anomalous events
        anomaly_query = select(func.count(AuditLog.id)).where(
            and_(
                AuditLog.created_at >= start_date,
                AuditLog.created_at <= end_date,
                AuditLog.is_anomalous == True
            )
        )
        anomaly_result = await self.db.execute(anomaly_query)
        anomalous_events = anomaly_result.scalar() or 0

        # Unique users
        users_query = select(func.count(func.distinct(AuditLog.user_id))).where(
            and_(
                AuditLog.created_at >= start_date,
                AuditLog.created_at <= end_date,
                AuditLog.user_id.isnot(None)
            )
        )
        users_result = await self.db.execute(users_query)
        unique_users = users_result.scalar() or 0

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_events": total_events,
            "events_by_category": events_by_category,
            "failed_events": failed_events,
            "anomalous_events": anomalous_events,
            "unique_users": unique_users,
            "compliance_rate": round((total_events - failed_events) / total_events * 100, 2) if total_events > 0 else 100.0
        }

    @staticmethod
    def _calculate_changed_fields(before: Dict[str, Any], after: Dict[str, Any]) -> List[str]:
        """Calculate which fields changed between before and after states."""
        changed = []
        all_keys = set(before.keys()) | set(after.keys())

        for key in all_keys:
            before_val = before.get(key)
            after_val = after.get(key)

            if before_val != after_val:
                changed.append(key)

        return changed

    @staticmethod
    def calculate_checksum(data: Dict[str, Any]) -> str:
        """
        Calculate SHA-256 checksum for data.

        Args:
            data: Dictionary of data to hash

        Returns:
            SHA-256 hex digest
        """
        # Create deterministic JSON string
        json_str = json.dumps(data, sort_keys=True, default=str)

        # Calculate SHA-256
        return hashlib.sha256(json_str.encode()).hexdigest()

    @staticmethod
    def hash_session_token(token: str) -> str:
        """
        Hash session token for storage (don't store plaintext tokens).

        Args:
            token: Any token

        Returns:
            SHA-256 hex digest
        """
        return hashlib.sha256(token.encode()).hexdigest()
