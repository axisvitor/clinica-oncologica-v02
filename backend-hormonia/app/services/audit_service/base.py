"""
Base Audit Service with Core Logging Functionality.

Provides the foundational log_event method that adapts legacy method calls
to the new AuditLog model schema.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from app.models.audit_log import AuditLog, AuditEventType
from app.utils.security import mask_dict_secrets

logger = logging.getLogger(__name__)


class AuditServiceBase:
    """
    Base service for audit logging with LGPD compliance.

    ADAPTER: Adapts legacy method calls to the new AuditLog schema.
    """

    def __init__(self, db: Any):
        """Initialize the audit service with database session."""
        self.db = db
        self.logger = logging.getLogger(__name__)

    def log_event(
        self,
        event_type: str,
        event_category: str,
        severity: str = "info",
        actor_id: Optional[UUID] = None,
        subject_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        result: str = "success",
        data_subject_id: Optional[UUID] = None,
        legal_basis: Optional[str] = None,
        retention_days: int = 365,
        # Legacy parameters for backward compatibility
        user_id: Optional[UUID] = None,
        patient_id: Optional[UUID] = None,
    ) -> AuditLog:
        """
        Log an audit event (Legacy Adapter).

        Maps legacy arguments to the new AuditLog model schema.

        Args:
            event_type: Type of event being logged
            event_category: Category (access, security, data_change, consent)
            severity: Severity level (info, warning, error)
            actor_id: ID of user performing the action
            subject_id: ID of entity being acted upon
            session_id: Session identifier
            ip_address: IP address of request
            user_agent: User agent string
            event_data: Additional event metadata
            result: Result of the event (success, failure, blocked, etc.)
            data_subject_id: LGPD data subject identifier
            legal_basis: Legal basis for processing (LGPD)
            retention_days: Days to retain the log
            user_id: (Legacy) Alias for actor_id
            patient_id: (Legacy) Alias for subject_id

        Returns:
            AuditLog: Created audit log entry
        """
        # Handle backward compatibility for IDs
        final_user_id = actor_id if actor_id else user_id

        # Prepare metadata with fields that no longer have dedicated columns
        metadata = event_data or {}
        metadata.update(
            {
                "event_category": event_category,
                "severity": severity,
                "subject_id": str(subject_id)
                if subject_id
                else (str(patient_id) if patient_id else None),
                "session_id": str(session_id) if session_id else None,
                "data_subject_id": str(data_subject_id) if data_subject_id else None,
                "legal_basis": legal_basis,
                "retention_days": retention_days,
                "adapter_version": "legacy_v2",
            }
        )

        # Sanitize metadata
        sanitized_metadata = mask_dict_secrets(metadata)

        # Map event_type to Enum if possible, otherwise use a default or try to coerce
        # This is critical because the new model enforces Enum
        try:
            # Try direct mapping if string matches enum value
            mapped_event_type = AuditEventType(event_type)
        except ValueError:
            # Fallback mapping for known legacy events
            if "login" in event_type:
                mapped_event_type = (
                    AuditEventType.LOGIN_SUCCESS
                    if result == "success"
                    else AuditEventType.LOGIN_FAILURE
                )
            elif "access" in event_type:
                mapped_event_type = (
                    AuditEventType.ACCESS_DENIED
                    if result != "success"
                    else AuditEventType.SUSPICIOUS_ACTIVITY
                )
            elif "quiz" in event_type:
                # Generic mapping for quiz events not in Enum
                mapped_event_type = AuditEventType.SUSPICIOUS_ACTIVITY
                sanitized_metadata["original_event_type"] = event_type
            else:
                # Default fallback
                mapped_event_type = AuditEventType.SUSPICIOUS_ACTIVITY
                sanitized_metadata["original_event_type"] = event_type

        audit_log = AuditLog(
            event_type=mapped_event_type,
            event_status=result,
            user_id=final_user_id,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            event_metadata=sanitized_metadata,
            message=f"{event_category}: {event_type}",
            created_at=datetime.now(timezone.utc),
        )

        self.db.add(audit_log)
        self.db.commit()

        # Also log to application logger
        self.logger.info(
            f"Audit (Legacy): {event_type}",
            extra={
                "audit_id": getattr(audit_log, "id", "unknown"),
                "category": event_category,
                "result": result,
                "user_id": str(final_user_id) if final_user_id else None,
            },
        )

        return audit_log
