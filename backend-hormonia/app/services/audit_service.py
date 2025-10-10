"""
Audit Service for LGPD Compliance and Security Logging.

This service provides comprehensive audit logging for all security-relevant
events in the monthly quiz system, ensuring LGPD compliance and traceability.
"""

import logging
import hashlib
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from sqlalchemy import Column, String, DateTime, JSON, Integer, func
from sqlalchemy.ext.declarative import declarative_base

from app.database import Base
from app.utils.security import mask_sensitive_url, mask_dict_secrets
from app.models.audit_log import AuditLog  # Import existing model instead of redefining

logger = logging.getLogger(__name__)


class AuditService:
    """Service for comprehensive audit logging with LGPD compliance."""

    def __init__(self, db: Session):
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
        patient_id: Optional[UUID] = None
    ) -> AuditLog:
        """
        Log an audit event.

        Args:
            event_type: Type of event (e.g., 'link_created', 'quiz_accessed')
            event_category: Category (security, access, data_change, consent)
            severity: Severity level (info, warning, error, critical)
            actor_id: ID of the user/system performing the action
            subject_id: ID of the entity affected by the action
            session_id: Quiz session ID
            ip_address: IP address of the client
            user_agent: User agent string
            event_data: Additional event data (will be sanitized)
            result: Result of the action (success, failure, blocked)
            data_subject_id: LGPD data subject identifier
            legal_basis: Legal basis for processing (LGPD)
            retention_days: Days to retain this log
            user_id: (Deprecated) Use actor_id instead
            patient_id: (Deprecated) Use subject_id instead
        """
        # Handle backward compatibility
        if actor_id is None and user_id is not None:
            actor_id = user_id
        if subject_id is None and patient_id is not None:
            subject_id = patient_id

        # Sanitize event data to prevent logging sensitive information
        sanitized_data = mask_dict_secrets(event_data or {})

        # Calculate retention date
        retention_until = datetime.utcnow() + timedelta(days=retention_days)

        audit_log = AuditLog(
            event_type=event_type,
            event_category=event_category,
            severity=severity,
            actor_id=str(actor_id) if actor_id else None,
            subject_id=str(subject_id) if subject_id else None,
            user_id=str(user_id) if user_id else None,  # Legacy
            patient_id=str(patient_id) if patient_id else None,  # Legacy
            session_id=str(session_id) if session_id else None,
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,  # Limit length
            event_data=sanitized_data,
            result=result,
            data_subject_id=str(data_subject_id) if data_subject_id else None,
            legal_basis=legal_basis,
            retention_until=retention_until
        )

        self.db.add(audit_log)
        self.db.commit()

        # Also log to application logger
        self.logger.info(
            f"Audit: {event_type}",
            extra={
                'audit_id': audit_log.id,
                'category': event_category,
                'severity': severity,
                'result': result,
                'actor_id': str(actor_id) if actor_id else None,
                'subject_id': str(subject_id) if subject_id else None
            }
        )

        return audit_log

    def log_link_created(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        delivery_method: str,
        expires_at: datetime,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log quiz link creation."""
        return self.log_event(
            event_type="monthly_quiz_link_created",
            event_category="access",
            severity="info",
            actor_id=actor_id,
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "delivery_method": delivery_method,
                "expires_at": expires_at.isoformat()
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_link_accessed(
        self,
        patient_id: UUID,
        session_id: UUID,
        ip_address: str,
        user_agent: str,
        token_prefix: str
    ) -> AuditLog:
        """Log quiz link access."""
        return self.log_event(
            event_type="monthly_quiz_link_accessed",
            event_category="access",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "token_prefix": token_prefix
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="consent"
        )

    def log_response_submitted(
        self,
        patient_id: UUID,
        session_id: UUID,
        question_id: str,
        response_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log quiz response submission."""
        return self.log_event(
            event_type="monthly_quiz_response_submitted",
            event_category="data_change",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "question_id": question_id,
                "response_id": str(response_id)
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="consent"
        )

    def log_invalid_access_attempt(
        self,
        ip_address: str,
        user_agent: str,
        reason: str,
        token_prefix: Optional[str] = None
    ) -> AuditLog:
        """Log invalid access attempt."""
        return self.log_event(
            event_type="monthly_quiz_invalid_access",
            event_category="security",
            severity="warning",
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "reason": reason,
                "token_prefix": token_prefix
            },
            result="blocked"
        )

    def log_token_expired(
        self,
        patient_id: UUID,
        session_id: UUID
    ) -> AuditLog:
        """Log token expiration."""
        return self.log_event(
            event_type="monthly_quiz_token_expired",
            event_category="security",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            result="expired"
        )

    def log_link_resent(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        delivery_method: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log quiz link resend action."""
        return self.log_event(
            event_type="monthly_quiz_link_resent",
            event_category="access",
            severity="info",
            actor_id=actor_id,
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "delivery_method": delivery_method
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_link_regenerated(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        regeneration_count: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log quiz link regeneration action."""
        return self.log_event(
            event_type="monthly_quiz_link_regenerated",
            event_category="security",
            severity="info",
            actor_id=actor_id,
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "regeneration_count": regeneration_count
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_link_cancelled(
        self,
        actor_id: UUID,
        patient_id: UUID,
        session_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log quiz link cancellation action."""
        return self.log_event(
            event_type="monthly_quiz_link_cancelled",
            event_category="access",
            severity="info",
            actor_id=actor_id,
            subject_id=patient_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={},
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_link_expired(
        self,
        patient_id: UUID,
        session_id: UUID,
        fallback_activated: bool = False
    ) -> AuditLog:
        """Log quiz link expiration."""
        return self.log_event(
            event_type="monthly_quiz_link_expired",
            event_category="security",
            severity="warning" if not fallback_activated else "info",
            subject_id=patient_id,
            session_id=session_id,
            event_data={
                "fallback_activated": fallback_activated
            },
            result="expired",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_fallback_activated(
        self,
        patient_id: UUID,
        session_id: UUID,
        fallback_reason: str,
        fallback_method: str = "whatsapp_conversational"
    ) -> AuditLog:
        """Log fallback to WhatsApp conversational flow."""
        return self.log_event(
            event_type="monthly_quiz_fallback_activated",
            event_category="access",
            severity="warning",
            subject_id=patient_id,
            session_id=session_id,
            event_data={
                "fallback_reason": fallback_reason,
                "fallback_method": fallback_method
            },
            result="fallback",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_reminder_sent(
        self,
        patient_id: UUID,
        session_id: UUID,
        delivery_channel: str,
        is_retry: bool = False,
        retry_count: int = 0
    ) -> AuditLog:
        """Log quiz reminder sent."""
        return self.log_event(
            event_type="monthly_quiz_reminder_sent",
            event_category="access",
            severity="info",
            subject_id=patient_id,
            session_id=session_id,
            event_data={
                "delivery_channel": delivery_channel,
                "is_retry": is_retry,
                "retry_count": retry_count
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_reminder_failed(
        self,
        patient_id: UUID,
        session_id: UUID,
        delivery_channel: str,
        failure_reason: str,
        retry_count: int = 0
    ) -> AuditLog:
        """Log quiz reminder failure."""
        return self.log_event(
            event_type="monthly_quiz_reminder_failed",
            event_category="access",
            severity="error",
            subject_id=patient_id,
            session_id=session_id,
            event_data={
                "delivery_channel": delivery_channel,
                "failure_reason": failure_reason,
                "retry_count": retry_count
            },
            result="failure",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest"
        )

    def log_consent_given(
        self,
        patient_id: UUID,
        consent_type: str,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """Log LGPD consent given."""
        return self.log_event(
            event_type="lgpd_consent_given",
            event_category="consent",
            severity="info",
            patient_id=patient_id,
            ip_address=ip_address,
            event_data={
                "consent_type": consent_type
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="consent",
            retention_days=2555  # 7 years for LGPD compliance
        )

    def log_data_deletion(
        self,
        patient_id: UUID,
        user_id: UUID,
        deletion_scope: str,
        reason: str
    ) -> AuditLog:
        """Log data deletion (right to be forgotten)."""
        return self.log_event(
            event_type="lgpd_data_deleted",
            event_category="data_change",
            severity="warning",
            actor_id=user_id,
            subject_id=patient_id,
            event_data={
                "deletion_scope": deletion_scope,
                "reason": reason
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legal_obligation",
            retention_days=2555  # 7 years retention
        )

    def get_patient_audit_trail(
        self,
        patient_id: UUID,
        limit: int = 100
    ) -> list[AuditLog]:
        """Get audit trail for a specific patient (for LGPD export)."""
        return self.db.query(AuditLog).filter(
            AuditLog.patient_id == str(patient_id)
        ).order_by(
            AuditLog.timestamp.desc()
        ).limit(limit).all()

    def cleanup_expired_logs(self) -> int:
        """Clean up logs past retention period."""
        deleted = self.db.query(AuditLog).filter(
            AuditLog.retention_until < datetime.utcnow()
        ).delete()

        self.db.commit()

        self.logger.info(f"Cleaned up {deleted} expired audit logs")
        return deleted

    # ========================================================================
    # AI-Specific Audit Methods (HIPAA Compliant)
    # ========================================================================

    def log_ai_chat_request(
        self,
        user_id: UUID,
        user_role: str,
        patient_id: Optional[UUID],
        message: str,
        response: str,
        response_time_ms: float,
        cache_hit: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log AI chat request with HIPAA compliance."""
        # Hash message for privacy (don't store full patient data)
        message_hash = hashlib.sha256(message.encode()).hexdigest()[:16]
        response_summary = response[:100] + "..." if len(response) > 100 else response

        return self.log_event(
            event_type="ai_chat_request",
            event_category="access",
            severity="info",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "user_role": user_role,
                "message_hash": message_hash,
                "message_length": len(message),
                "response_summary": response_summary,
                "response_length": len(response),
                "response_time_ms": response_time_ms,
                "cache_hit": cache_hit,
                "has_patient_context": patient_id is not None
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90  # HIPAA: 90 days for access logs
        )

    def log_ai_chat_error(
        self,
        user_id: UUID,
        user_role: str,
        patient_id: Optional[UUID],
        error_type: str,
        error_message: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log AI chat error."""
        return self.log_event(
            event_type="ai_chat_error",
            event_category="security",
            severity="error",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "user_role": user_role,
                "error_type": error_type,
                "error_message": error_message[:200]  # Truncate for privacy
            },
            result="failure",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90
        )

    def log_ai_insights_generation(
        self,
        user_id: UUID,
        user_role: str,
        patient_id: UUID,
        timeframe_days: int,
        insights_count: int,
        risk_level: str,
        response_time_ms: float,
        cache_hit: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log AI insights generation."""
        return self.log_event(
            event_type="ai_insights_generated",
            event_category="access",
            severity="info",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "user_role": user_role,
                "timeframe_days": timeframe_days,
                "insights_count": insights_count,
                "risk_level": risk_level,
                "response_time_ms": response_time_ms,
                "cache_hit": cache_hit
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90
        )

    def log_ai_recommendations_generation(
        self,
        user_id: UUID,
        user_role: str,
        patient_id: UUID,
        recommendations_count: int,
        action_items_count: int,
        confidence_level: float,
        response_time_ms: float,
        cache_hit: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log AI recommendations generation."""
        return self.log_event(
            event_type="ai_recommendations_generated",
            event_category="access",
            severity="info",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "user_role": user_role,
                "recommendations_count": recommendations_count,
                "action_items_count": action_items_count,
                "confidence_level": confidence_level,
                "response_time_ms": response_time_ms,
                "cache_hit": cache_hit
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90
        )

    def log_ai_analysis_request(
        self,
        user_id: UUID,
        user_role: str,
        patient_id: UUID,
        analysis_type: str,
        date_range_days: int,
        include_messages: bool,
        include_medical_history: bool,
        response_time_ms: float,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log AI analysis request."""
        return self.log_event(
            event_type="ai_analysis_request",
            event_category="access",
            severity="info",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "user_role": user_role,
                "analysis_type": analysis_type,
                "date_range_days": date_range_days,
                "include_messages": include_messages,
                "include_medical_history": include_medical_history,
                "response_time_ms": response_time_ms
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90
        )

    def log_ai_sentiment_analysis(
        self,
        user_id: UUID,
        user_role: str,
        patient_id: Optional[UUID],
        message: str,
        sentiment: str,
        concern_level: str,
        confidence: float,
        response_time_ms: float,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log AI sentiment analysis."""
        message_hash = hashlib.sha256(message.encode()).hexdigest()[:16]

        return self.log_event(
            event_type="ai_sentiment_analysis",
            event_category="access",
            severity="info",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "user_role": user_role,
                "message_hash": message_hash,
                "message_length": len(message),
                "sentiment": sentiment,
                "concern_level": concern_level,
                "confidence": confidence,
                "response_time_ms": response_time_ms
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90
        )

    def log_ai_response_generation(
        self,
        user_id: UUID,
        user_role: str,
        patient_id: UUID,
        message_type: str,
        template_length: int,
        generated_length: int,
        readability_score: float,
        response_time_ms: float,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditLog:
        """Log AI response generation."""
        return self.log_event(
            event_type="ai_response_generated",
            event_category="access",
            severity="info",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            user_agent=user_agent,
            event_data={
                "user_role": user_role,
                "message_type": message_type,
                "template_length": template_length,
                "generated_length": generated_length,
                "readability_score": readability_score,
                "response_time_ms": response_time_ms
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90
        )

    def log_ai_cache_hit(
        self,
        cache_key: str,
        endpoint: str,
        response_time_ms: float,
        user_id: Optional[UUID] = None
    ) -> AuditLog:
        """Log AI cache hit for performance tracking."""
        # Hash cache key to avoid exposing sensitive data
        key_hash = hashlib.sha256(cache_key.encode()).hexdigest()[:16]

        return self.log_event(
            event_type="ai_cache_hit",
            event_category="access",
            severity="info",
            actor_id=user_id,
            event_data={
                "cache_key_hash": key_hash,
                "endpoint": endpoint,
                "response_time_ms": response_time_ms
            },
            result="success",
            retention_days=30  # Shorter retention for performance logs
        )

    def log_ai_cache_miss(
        self,
        cache_key: str,
        endpoint: str,
        response_time_ms: float,
        user_id: Optional[UUID] = None
    ) -> AuditLog:
        """Log AI cache miss for performance tracking."""
        key_hash = hashlib.sha256(cache_key.encode()).hexdigest()[:16]

        return self.log_event(
            event_type="ai_cache_miss",
            event_category="access",
            severity="info",
            actor_id=user_id,
            event_data={
                "cache_key_hash": key_hash,
                "endpoint": endpoint,
                "response_time_ms": response_time_ms
            },
            result="success",
            retention_days=30
        )

    def log_ai_cache_invalidation(
        self,
        user_id: UUID,
        patient_id: UUID,
        invalidated_count: int,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """Log AI cache invalidation."""
        return self.log_event(
            event_type="ai_cache_invalidated",
            event_category="data_change",
            severity="info",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            event_data={
                "invalidated_count": invalidated_count
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90
        )

    # ========================================================================
    # Query Methods for Compliance Reporting
    # ========================================================================

    def get_ai_audit_report(
        self,
        start_date: datetime,
        end_date: datetime,
        event_types: Optional[List[str]] = None,
        user_id: Optional[UUID] = None,
        patient_id: Optional[UUID] = None
    ) -> List[AuditLog]:
        """Get AI audit report for compliance."""
        query = self.db.query(AuditLog).filter(
            AuditLog.timestamp >= start_date,
            AuditLog.timestamp <= end_date,
            AuditLog.event_type.like('ai_%')
        )

        if event_types:
            query = query.filter(AuditLog.event_type.in_(event_types))
        if user_id:
            query = query.filter(AuditLog.actor_id == str(user_id))
        if patient_id:
            query = query.filter(AuditLog.subject_id == str(patient_id))

        return query.order_by(AuditLog.timestamp.desc()).all()

    def get_ai_performance_metrics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Get AI performance metrics from audit logs."""
        # Query for all AI-related logs in date range
        logs = self.db.query(AuditLog).filter(
            AuditLog.timestamp >= start_date,
            AuditLog.timestamp <= end_date,
            AuditLog.event_type.like('ai_%')
        ).all()

        # Calculate metrics
        total_requests = len(logs)
        cache_hits = sum(1 for log in logs if log.event_type == 'ai_cache_hit')
        cache_misses = sum(1 for log in logs if log.event_type == 'ai_cache_miss')
        errors = sum(1 for log in logs if log.result == 'failure')

        # Calculate average response times
        response_times = [
            log.event_data.get('response_time_ms', 0)
            for log in logs
            if log.event_data and 'response_time_ms' in log.event_data
        ]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        return {
            "total_requests": total_requests,
            "cache_hit_rate": cache_hits / (cache_hits + cache_misses) if (cache_hits + cache_misses) > 0 else 0,
            "error_rate": errors / total_requests if total_requests > 0 else 0,
            "average_response_time_ms": avg_response_time,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }

    def get_patient_ai_access_history(
        self,
        patient_id: UUID,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get AI access history for a patient (HIPAA compliance)."""
        return self.db.query(AuditLog).filter(
            AuditLog.subject_id == str(patient_id),
            AuditLog.event_type.like('ai_%')
        ).order_by(
            AuditLog.timestamp.desc()
        ).limit(limit).all()

    def get_user_ai_activity(
        self,
        user_id: UUID,
        start_date: datetime,
        end_date: datetime
    ) -> List[AuditLog]:
        """Get user AI activity for audit purposes."""
        return self.db.query(AuditLog).filter(
            AuditLog.actor_id == str(user_id),
            AuditLog.event_type.like('ai_%'),
            AuditLog.timestamp >= start_date,
            AuditLog.timestamp <= end_date
        ).order_by(
            AuditLog.timestamp.desc()
        ).all()

    def get_ai_security_events(
        self,
        start_date: datetime,
        end_date: datetime,
        severity: Optional[str] = None
    ) -> List[AuditLog]:
        """Get AI security events for monitoring."""
        query = self.db.query(AuditLog).filter(
            AuditLog.event_category == 'security',
            AuditLog.event_type.like('ai_%'),
            AuditLog.timestamp >= start_date,
            AuditLog.timestamp <= end_date
        )

        if severity:
            query = query.filter(AuditLog.severity == severity)

        return query.order_by(AuditLog.timestamp.desc()).all()

    def export_ai_audit_data(
        self,
        patient_id: UUID,
        format: str = 'json'
    ) -> Dict[str, Any]:
        """Export AI audit data for a patient (HIPAA compliance)."""
        logs = self.get_patient_ai_access_history(patient_id, limit=1000)

        export_data = {
            "patient_id": str(patient_id),
            "export_date": datetime.utcnow().isoformat(),
            "total_logs": len(logs),
            "logs": [
                {
                    "timestamp": log.timestamp.isoformat(),
                    "event_type": log.event_type,
                    "event_category": log.event_category,
                    "severity": log.severity,
                    "actor_id": log.actor_id,
                    "result": log.result,
                    "event_data": log.event_data
                }
                for log in logs
            ]
        }

        return export_data


