"""
Cache Invalidation Service.
Handles intelligent cache invalidation when data changes.
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.models.message import Message
from app.models.quiz import QuizResponse
from app.models.alert import Alert
from app.services.analytics_cache import get_analytics_cache
from app.core.monitoring_logging import monitoring_logger


logger = logging.getLogger(__name__)


class CacheInvalidationService:
    """
    Service to handle cache invalidation when data changes.
    
    Features:
    - Automatic invalidation on data changes
    - Smart invalidation based on affected data
    - Batch invalidation for performance
    - Configurable invalidation strategies
    """
    
    def __init__(self):
        """Initialize cache invalidation service."""
        self.cache_service = get_analytics_cache()
        self._register_event_listeners()
        
        logger.info("Cache Invalidation Service initialized")
    
    def _register_event_listeners(self):
        """Register SQLAlchemy event listeners for automatic cache invalidation."""
        
        @event.listens_for(Patient, 'after_insert')
        @event.listens_for(Patient, 'after_update')
        @event.listens_for(Patient, 'after_delete')
        def invalidate_patient_cache(mapper, connection, target):
            """Invalidate cache when patient data changes."""
            self._invalidate_patient_related_cache(target)
        
        @event.listens_for(Message, 'after_insert')
        @event.listens_for(Message, 'after_update')
        @event.listens_for(Message, 'after_delete')
        def invalidate_message_cache(mapper, connection, target):
            """Invalidate cache when message data changes."""
            self._invalidate_message_related_cache(target)
        
        @event.listens_for(QuizResponse, 'after_insert')
        @event.listens_for(QuizResponse, 'after_update')
        @event.listens_for(QuizResponse, 'after_delete')
        def invalidate_quiz_cache(mapper, connection, target):
            """Invalidate cache when quiz data changes."""
            self._invalidate_quiz_related_cache(target)
        
        @event.listens_for(Alert, 'after_insert')
        @event.listens_for(Alert, 'after_update')
        @event.listens_for(Alert, 'after_delete')
        def invalidate_alert_cache(mapper, connection, target):
            """Invalidate cache when alert data changes."""
            self._invalidate_alert_related_cache(target)
    
    def invalidate_dashboard_cache(self, doctor_id: Optional[UUID] = None):
        """
        Invalidate dashboard cache.
        
        Args:
            doctor_id: Optional doctor ID to invalidate specific doctor's cache
        """
        try:
            if doctor_id:
                # Invalidate specific doctor's dashboard
                cache_key_params = {
                    "doctor_id": str(doctor_id),
                    "endpoint": "dashboard"
                }
                self.cache_service.invalidate("dashboard", cache_key_params)
            else:
                # Invalidate all dashboard caches
                self.cache_service.invalidate("dashboard")
            
            monitoring_logger.log_system_event(
                event_type="cache_invalidation_dashboard",
                message="Dashboard cache invalidated",
                level="INFO",
                context={"doctor_id": str(doctor_id) if doctor_id else "all"}
            )
            
            logger.info(f"Dashboard cache invalidated for doctor: {doctor_id or 'all'}")
            
        except Exception as e:
            logger.error(f"Error invalidating dashboard cache: {e}")
    
    def invalidate_analytics_cache(self, doctor_id: Optional[UUID] = None):
        """
        Invalidate analytics cache.
        
        Args:
            doctor_id: Optional doctor ID to invalidate specific doctor's cache
        """
        try:
            # Invalidate multiple cache types that depend on analytics data
            cache_types = ["patient_analytics", "system_analytics", "engagement_chart"]
            
            for cache_type in cache_types:
                if doctor_id:
                    # Try to invalidate specific doctor's cache
                    cache_key_params = {"doctor_id": str(doctor_id)}
                    self.cache_service.invalidate(cache_type, cache_key_params)
                else:
                    # Invalidate all caches of this type
                    self.cache_service.invalidate(cache_type)
            
            monitoring_logger.log_system_event(
                event_type="cache_invalidation_analytics",
                message="Analytics cache invalidated",
                level="INFO",
                context={
                    "doctor_id": str(doctor_id) if doctor_id else "all",
                    "cache_types": cache_types
                }
            )
            
            logger.info(f"Analytics cache invalidated for doctor: {doctor_id or 'all'}")
            
        except Exception as e:
            logger.error(f"Error invalidating analytics cache: {e}")
    
    def invalidate_treatment_distribution_cache(self, doctor_id: Optional[UUID] = None):
        """
        Invalidate treatment distribution cache.
        
        Args:
            doctor_id: Optional doctor ID to invalidate specific doctor's cache
        """
        try:
            if doctor_id:
                # Invalidate all periods for this doctor
                periods = ["7d", "30d", "90d", "all"]
                for period in periods:
                    cache_key_params = {
                        "period": period,
                        "doctor_id": str(doctor_id)
                    }
                    self.cache_service.invalidate("treatment_distribution", cache_key_params)
            else:
                # Invalidate all treatment distribution caches
                self.cache_service.invalidate("treatment_distribution")
            
            logger.info(f"Treatment distribution cache invalidated for doctor: {doctor_id or 'all'}")
            
        except Exception as e:
            logger.error(f"Error invalidating treatment distribution cache: {e}")
    
    def invalidate_patterns_cache(self, patient_id: Optional[UUID] = None):
        """
        Invalidate patterns cache.
        
        Args:
            patient_id: Optional patient ID to invalidate specific patient's cache
        """
        try:
            if patient_id:
                # Invalidate specific patient's patterns
                cache_key_params = {"patient_id": str(patient_id)}
                self.cache_service.invalidate("patterns", cache_key_params)
            else:
                # Invalidate all patterns caches
                self.cache_service.invalidate("patterns")
            
            logger.info(f"Patterns cache invalidated for patient: {patient_id or 'all'}")
            
        except Exception as e:
            logger.error(f"Error invalidating patterns cache: {e}")
    
    def warm_frequently_accessed_cache(self, doctor_id: Optional[UUID] = None):
        """
        Warm frequently accessed cache entries.
        
        Args:
            doctor_id: Optional doctor ID to warm specific doctor's cache
        """
        try:
            # This would typically be called during off-peak hours
            # or when we detect cache misses for important data
            
            # For now, we'll just log the intention
            # In a full implementation, this would call the actual data generation functions
            
            monitoring_logger.log_system_event(
                event_type="cache_warming_initiated",
                message="Cache warming initiated",
                level="INFO",
                context={"doctor_id": str(doctor_id) if doctor_id else "all"}
            )
            
            logger.info(f"Cache warming initiated for doctor: {doctor_id or 'all'}")
            
        except Exception as e:
            logger.error(f"Error warming cache: {e}")
    
    def _invalidate_patient_related_cache(self, patient: Patient):
        """Invalidate cache related to patient changes."""
        try:
            doctor_id = patient.doctor_id
            
            # Invalidate dashboard and analytics for this doctor
            self.invalidate_dashboard_cache(doctor_id)
            self.invalidate_analytics_cache(doctor_id)
            self.invalidate_treatment_distribution_cache(doctor_id)
            
            # Also invalidate admin caches (doctor_id=None)
            self.invalidate_dashboard_cache(None)
            self.invalidate_analytics_cache(None)
            self.invalidate_treatment_distribution_cache(None)
            
        except Exception as e:
            logger.error(f"Error invalidating patient-related cache: {e}")
    
    def _invalidate_message_related_cache(self, message: Message):
        """Invalidate cache related to message changes."""
        try:
            # Get patient to find doctor
            if hasattr(message, 'patient') and message.patient:
                doctor_id = message.patient.doctor_id
            else:
                # If patient not loaded, invalidate all caches to be safe
                doctor_id = None
            
            # Invalidate engagement and dashboard caches
            self.invalidate_dashboard_cache(doctor_id)
            self.invalidate_analytics_cache(doctor_id)
            
            # Invalidate engagement chart cache specifically
            self.cache_service.invalidate("engagement_chart")
            
            # Also invalidate admin caches
            if doctor_id:
                self.invalidate_dashboard_cache(None)
                self.invalidate_analytics_cache(None)
            
        except Exception as e:
            logger.error(f"Error invalidating message-related cache: {e}")
    
    def _invalidate_quiz_related_cache(self, quiz_response: QuizResponse):
        """Invalidate cache related to quiz changes."""
        try:
            # Get patient to find doctor
            if hasattr(quiz_response, 'patient') and quiz_response.patient:
                doctor_id = quiz_response.patient.doctor_id
            else:
                doctor_id = None
            
            # Invalidate dashboard and analytics caches
            self.invalidate_dashboard_cache(doctor_id)
            self.invalidate_analytics_cache(doctor_id)
            
            # Also invalidate admin caches
            if doctor_id:
                self.invalidate_dashboard_cache(None)
                self.invalidate_analytics_cache(None)
            
        except Exception as e:
            logger.error(f"Error invalidating quiz-related cache: {e}")
    
    def _invalidate_alert_related_cache(self, alert: Alert):
        """Invalidate cache related to alert changes."""
        try:
            # Get patient to find doctor
            if hasattr(alert, 'patient') and alert.patient:
                doctor_id = alert.patient.doctor_id
            else:
                doctor_id = None
            
            # Invalidate dashboard and analytics caches
            self.invalidate_dashboard_cache(doctor_id)
            self.invalidate_analytics_cache(doctor_id)
            
            # Also invalidate admin caches
            if doctor_id:
                self.invalidate_dashboard_cache(None)
                self.invalidate_analytics_cache(None)
            
        except Exception as e:
            logger.error(f"Error invalidating alert-related cache: {e}")


# Global cache invalidation service instance
_invalidation_service = None


def get_cache_invalidation_service() -> CacheInvalidationService:
    """Get global cache invalidation service instance."""
    global _invalidation_service
    if _invalidation_service is None:
        _invalidation_service = CacheInvalidationService()
    return _invalidation_service


def invalidate_analytics_cache_for_doctor(doctor_id: Optional[UUID] = None):
    """
    Convenience function to invalidate analytics cache for a doctor.
    
    Args:
        doctor_id: Optional doctor ID to invalidate specific doctor's cache
    """
    service = get_cache_invalidation_service()
    service.invalidate_dashboard_cache(doctor_id)
    service.invalidate_analytics_cache(doctor_id)
    service.invalidate_treatment_distribution_cache(doctor_id)