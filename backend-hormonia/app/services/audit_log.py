"""
Audit Logging Service for Security Event Tracking.

This service provides comprehensive audit logging for critical security events
including authentication, authorization, and account management operations.

Features:
- Asynchronous logging to avoid blocking API requests
- IP address and user agent tracking
- Flexible metadata support
- Query capabilities for security analysis
- Integration with existing authentication flows
"""

import logging
from typing import Optional, Dict, Any, List, Union
from datetime import datetime, timedelta, timezone
from uuid import UUID
from sqlalchemy import desc, func
from fastapi import Request

from app.models.audit_log import AuditLog, AuditEventType
from app.models.user import User
from app.utils.timezone import now_sao_paulo

logger = logging.getLogger(__name__)


class AuditLogService:
    """Service for managing security audit logs."""

    def __init__(self, db: Any):
        """
        Initialize audit log service.

        Args:
            db: Database session
        """
        self.db = db

    def _extract_client_info(self, request: Optional[Request]) -> Dict[str, Any]:
        """
        Extract client information from request.

        Args:
            request: FastAPI request object

        Returns:
            Dictionary with ip_address and user_agent
        """
        if not request:
            return {"ip_address": None, "user_agent": None}

        # Extract IP address (handle proxy headers)
        ip_address = None
        if hasattr(request, "client") and request.client:
            ip_address = request.client.host

        # Check for forwarded IP (behind proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take first IP in the chain
            ip_address = forwarded_for.split(",")[0].strip()

        # Real IP header (some proxies use this)
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            ip_address = real_ip.strip()

        # Extract user agent
        user_agent = request.headers.get("User-Agent", "Unknown")

        return {"ip_address": ip_address, "user_agent": user_agent}

    @staticmethod
    def _strip_legacy_firebase_uid(
        payload: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not payload:
            return {}
        return {key: value for key, value in payload.items() if key != "firebase_uid"}

    def _sanitize_canonical_audit_inputs(
        self,
        *,
        event_type: AuditEventType,
        firebase_uid: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        sanitized_metadata = self._strip_legacy_firebase_uid(metadata)
        stripped_metadata = bool(metadata) and "firebase_uid" in metadata

        if firebase_uid is not None or stripped_metadata:
            logger.debug(
                "Dropping legacy firebase_uid from canonical audit write",
                extra={
                    "event_type": event_type.value
                    if hasattr(event_type, "value")
                    else str(event_type)
                },
            )

        return sanitized_metadata

    def log_event(
        self,
        event_type: AuditEventType,
        event_status: str = "success",
        user_id: Optional[Union[str, UUID]] = None,
        user_email: Optional[str] = None,
        firebase_uid: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        message: Optional[str] = None,
        error_details: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """
        Log a security event to audit log.

        Args:
            event_type: Type of security event
            event_status: Event outcome (success, failure, error)
            user_id: User ID (if known)
            user_email: User email (for failed login tracking)
            firebase_uid: Legacy compatibility input; canonical audit writes discard it
            ip_address: Client IP address
            user_agent: Client user agent
            resource: Resource accessed
            action: Action performed
            message: Human-readable event description
            error_details: Error details for failed events
            metadata: Additional event metadata
            request: FastAPI request object (auto-extracts IP and user agent)

        Returns:
            Created AuditLog entry
        """
        try:
            # Extract client info from request if provided
            if request:
                client_info = self._extract_client_info(request)
                if not ip_address:
                    ip_address = client_info["ip_address"]
                if not user_agent:
                    user_agent = client_info["user_agent"]

            sanitized_metadata = self._sanitize_canonical_audit_inputs(
                event_type=event_type,
                firebase_uid=firebase_uid,
                metadata=metadata,
            )

            # Create audit log entry
            audit_entry = AuditLog(
                event_type=event_type,
                event_status=event_status,
                user_id=user_id,
                user_email=user_email,
                ip_address=ip_address,
                user_agent=user_agent,
                resource=resource,
                action=action,
                message=message,
                error_details=error_details,
                metadata=sanitized_metadata,
            )

            self.db.add(audit_entry)
            self.db.commit()
            self.db.refresh(audit_entry)

            logger.info(
                f"Audit log created: {event_type.value} - "
                f"user_id={user_id}, status={event_status}, ip={ip_address}"
            )

            return audit_entry

        except Exception as e:
            logger.error(f"Failed to create audit log: {e}", exc_info=True)
            self.db.rollback()
            # Don't fail the main operation if audit logging fails
            raise

    # Authentication event logging

    def log_login_success(
        self,
        user: User,
        request: Optional[Request] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Log successful login event."""
        return self.log_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            event_status="success",
            user_id=user.id,
            user_email=user.email,
            firebase_uid=user.firebase_uid,
            resource="/auth/login",
            action="login",
            message=f"User {user.email} logged in successfully",
            metadata=metadata,
            request=request,
        )

    def log_login_failure(
        self,
        email: str,
        reason: str,
        request: Optional[Request] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Log failed login attempt."""
        return self.log_event(
            event_type=AuditEventType.LOGIN_FAILURE,
            event_status="failure",
            user_email=email,
            resource="/auth/login",
            action="login",
            message=f"Failed login attempt for {email}",
            error_details=reason,
            metadata=metadata,
            request=request,
        )

    def log_logout(
        self,
        user: User,
        request: Optional[Request] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Log logout event."""
        return self.log_event(
            event_type=AuditEventType.LOGOUT,
            event_status="success",
            user_id=user.id,
            user_email=user.email,
            firebase_uid=user.firebase_uid,
            resource="/auth/logout",
            action="logout",
            message=f"User {user.email} logged out",
            metadata=metadata,
            request=request,
        )

    def log_session_created(
        self,
        user: User,
        session_id: str,
        request: Optional[Request] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Log session creation event."""
        session_metadata = metadata or {}
        session_metadata["session_id"] = session_id

        return self.log_event(
            event_type=AuditEventType.SESSION_CREATED,
            event_status="success",
            user_id=user.id,
            user_email=user.email,
            firebase_uid=user.firebase_uid,
            resource="/session",
            action="session_create",
            message=f"Session created for user {user.email}",
            metadata=session_metadata,
            request=request,
        )

    def log_session_invalidated(
        self,
        user_id: Union[str, UUID],
        session_id: str,
        reason: str = "logout",
        request: Optional[Request] = None,
    ) -> AuditLog:
        """Log session invalidation event."""
        return self.log_event(
            event_type=AuditEventType.SESSION_INVALIDATED,
            event_status="success",
            user_id=user_id,
            resource="/session/logout",
            action="session_invalidate",
            message=f"Session invalidated: {reason}",
            metadata={"session_id": session_id, "reason": reason},
            request=request,
        )

    def log_password_changed(
        self,
        user: User,
        request: Optional[Request] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Log password change event."""
        return self.log_event(
            event_type=AuditEventType.PASSWORD_CHANGED,
            event_status="success",
            user_id=user.id,
            user_email=user.email,
            firebase_uid=user.firebase_uid,
            resource="/auth/password",
            action="password_change",
            message=f"Password changed for user {user.email}",
            metadata=metadata,
            request=request,
        )

    def log_access_denied(
        self,
        user_id: Optional[Union[str, UUID]],
        resource: str,
        reason: str,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """Log access denied event."""
        return self.log_event(
            event_type=AuditEventType.ACCESS_DENIED,
            event_status="failure",
            user_id=user_id,
            resource=resource,
            action="access",
            message=f"Access denied to {resource}",
            error_details=reason,
            request=request,
        )

    def log_rate_limit_exceeded(
        self,
        user_email: Optional[str],
        resource: str,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """Log rate limit exceeded event."""
        return self.log_event(
            event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
            event_status="failure",
            user_email=user_email,
            resource=resource,
            action="rate_limit",
            message=f"Rate limit exceeded for {resource}",
            request=request,
        )

    # Query methods

    def get_user_audit_logs(
        self,
        user_id: Union[str, UUID],
        limit: int = 100,
        offset: int = 0,
        event_types: Optional[List[AuditEventType]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[AuditLog]:
        """
        Get audit logs for a specific user.

        Args:
            user_id: User ID
            limit: Maximum number of results
            offset: Result offset for pagination
            event_types: Filter by event types
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            List of AuditLog entries
        """
        query = self.db.query(AuditLog).filter(AuditLog.user_id == user_id)

        if event_types:
            query = query.filter(AuditLog.event_type.in_(event_types))

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)

        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        return (
            query.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset).all()
        )

    def get_security_events(
        self,
        limit: int = 100,
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[AuditLog]:
        """
        Get security-related events (failures, suspicious activity).

        Args:
            limit: Maximum number of results
            offset: Result offset for pagination
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            List of AuditLog entries
        """
        security_events = [
            AuditEventType.LOGIN_FAILURE,
            AuditEventType.ACCESS_DENIED,
            AuditEventType.SUSPICIOUS_ACTIVITY,
            AuditEventType.RATE_LIMIT_EXCEEDED,
            AuditEventType.INVALID_TOKEN,
            AuditEventType.CSRF_VIOLATION,
        ]

        query = self.db.query(AuditLog).filter(AuditLog.event_type.in_(security_events))

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)

        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        return (
            query.order_by(desc(AuditLog.created_at)).limit(limit).offset(offset).all()
        )

    def get_failed_login_attempts(
        self,
        email: Optional[str] = None,
        ip_address: Optional[str] = None,
        hours: int = 24,
    ) -> List[AuditLog]:
        """
        Get failed login attempts within time window.

        Args:
            email: Filter by email
            ip_address: Filter by IP address
            hours: Time window in hours

        Returns:
            List of failed login AuditLog entries
        """
        start_date = now_sao_paulo() - timedelta(hours=hours)

        query = self.db.query(AuditLog).filter(
            AuditLog.event_type == AuditEventType.LOGIN_FAILURE,
            AuditLog.created_at >= start_date,
        )

        if email:
            query = query.filter(AuditLog.user_email == email)

        if ip_address:
            query = query.filter(AuditLog.ip_address == ip_address)

        return query.order_by(desc(AuditLog.created_at)).all()

    def get_audit_statistics(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get audit log statistics.

        Args:
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            Dictionary with statistics
        """
        query = self.db.query(AuditLog)

        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)

        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)

        # Count by event type
        event_counts = (
            query.with_entities(
                AuditLog.event_type, func.count(AuditLog.id).label("count")
            )
            .group_by(AuditLog.event_type)
            .all()
        )

        # Count failures
        failure_count = query.filter(AuditLog.event_status == "failure").count()

        # Count unique users
        unique_users = (
            query.with_entities(AuditLog.user_id)
            .filter(AuditLog.user_id.isnot(None))
            .distinct()
            .count()
        )

        return {
            "total_events": query.count(),
            "failure_count": failure_count,
            "unique_users": unique_users,
            "events_by_type": {
                event_type.value: count for event_type, count in event_counts
            },
        }
