"""
AI Audit Mixin Module.

Contains all AI-related audit logging methods (HIPAA Compliant).
"""

import hashlib
from typing import Optional
from uuid import UUID

from app.models.audit_log import AuditLog


class AIAuditMixin:
    """
    Mixin providing AI-related audit logging methods with HIPAA compliance.

    Requires: log_event method from BaseAuditService
    """

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
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log AI chat request with HIPAA compliance."""
        # Hash message for privacy (don't store full patient data)
        message_hash = hashlib.sha256(message.encode()).hexdigest()[:16]
        response_summary = response[:100] + "..." if len(response) > 100 else response

        return self.log_event(  # type: ignore[attr-defined]
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
                "has_patient_context": patient_id is not None,
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90,  # HIPAA: 90 days for access logs
        )

    def log_ai_chat_error(
        self,
        user_id: UUID,
        user_role: str,
        patient_id: Optional[UUID],
        error_type: str,
        error_message: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log AI chat error."""
        return self.log_event(  # type: ignore[attr-defined]
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
                "error_message": error_message[:200],  # Truncate for privacy
            },
            result="failure",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90,
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
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log AI insights generation."""
        return self.log_event(  # type: ignore[attr-defined]
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
                "cache_hit": cache_hit,
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90,
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
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log AI recommendations generation."""
        return self.log_event(  # type: ignore[attr-defined]
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
                "cache_hit": cache_hit,
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90,
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
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log AI analysis request."""
        return self.log_event(  # type: ignore[attr-defined]
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
                "response_time_ms": response_time_ms,
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90,
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
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log AI sentiment analysis."""
        message_hash = hashlib.sha256(message.encode()).hexdigest()[:16]

        return self.log_event(  # type: ignore[attr-defined]
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
                "response_time_ms": response_time_ms,
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90,
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
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log AI response generation."""
        return self.log_event(  # type: ignore[attr-defined]
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
                "response_time_ms": response_time_ms,
            },
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90,
        )

    def log_ai_cache_hit(
        self,
        cache_key: str,
        endpoint: str,
        response_time_ms: float,
        user_id: Optional[UUID] = None,
    ) -> AuditLog:
        """Log AI cache hit for performance tracking."""
        # Hash cache key to avoid exposing sensitive data
        key_hash = hashlib.sha256(cache_key.encode()).hexdigest()[:16]

        return self.log_event(  # type: ignore[attr-defined]
            event_type="ai_cache_hit",
            event_category="access",
            severity="info",
            actor_id=user_id,
            event_data={
                "cache_key_hash": key_hash,
                "endpoint": endpoint,
                "response_time_ms": response_time_ms,
            },
            result="success",
            retention_days=30,  # Shorter retention for performance logs
        )

    def log_ai_cache_miss(
        self,
        cache_key: str,
        endpoint: str,
        response_time_ms: float,
        user_id: Optional[UUID] = None,
    ) -> AuditLog:
        """Log AI cache miss for performance tracking."""
        key_hash = hashlib.sha256(cache_key.encode()).hexdigest()[:16]

        return self.log_event(  # type: ignore[attr-defined]
            event_type="ai_cache_miss",
            event_category="access",
            severity="info",
            actor_id=user_id,
            event_data={
                "cache_key_hash": key_hash,
                "endpoint": endpoint,
                "response_time_ms": response_time_ms,
            },
            result="success",
            retention_days=30,
        )

    def log_ai_cache_invalidation(
        self,
        user_id: UUID,
        patient_id: UUID,
        invalidated_count: int,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """Log AI cache invalidation."""
        return self.log_event(  # type: ignore[attr-defined]
            event_type="ai_cache_invalidated",
            event_category="data_change",
            severity="info",
            actor_id=user_id,
            subject_id=patient_id,
            ip_address=ip_address,
            event_data={"invalidated_count": invalidated_count},
            result="success",
            data_subject_id=patient_id,
            legal_basis="legitimate_interest",
            retention_days=90,
        )
