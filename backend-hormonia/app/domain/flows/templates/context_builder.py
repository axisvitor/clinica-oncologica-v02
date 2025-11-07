"""
Template Context Builder - Build Context for Template Rendering

Creates context data structures for template rendering and personalization.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from app.models.patient import Patient


logger = logging.getLogger(__name__)


class TemplateContextBuilder:
    """
    Builds context for template rendering.

    Responsibilities:
    - Create patient context dictionaries
    - Build flow context data
    - Aggregate metadata for templates
    - Format context for AI processing
    """

    def __init__(self):
        """Initialize TemplateContextBuilder."""
        logger.info("TemplateContextBuilder initialized")

    def build_flow_context(
        self,
        patient_id: UUID,
        flow_type: str,
        current_day: int,
        operation: str,
        flow_state_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build flow execution context.

        Args:
            patient_id: Patient UUID
            flow_type: Flow type identifier
            current_day: Current treatment day
            operation: Operation type
            flow_state_id: Flow state UUID
            metadata: Additional metadata

        Returns:
            Flow context dictionary
        """
        context = {
            'patient_id': str(patient_id),
            'flow_type': flow_type,
            'current_day': current_day,
            'operation': operation,
            'timestamp': datetime.utcnow().isoformat()
        }

        if flow_state_id:
            context['flow_state_id'] = str(flow_state_id)

        if metadata:
            context['metadata'] = metadata

        logger.debug(f"Flow context built for patient {patient_id}")
        return context

    def build_patient_context(
        self,
        patient: Patient,
        include_medical_history: bool = False,
        include_preferences: bool = True
    ) -> Dict[str, Any]:
        """
        Build patient context for template rendering.

        Args:
            patient: Patient object
            include_medical_history: Include medical history
            include_preferences: Include preferences

        Returns:
            Patient context dictionary
        """
        context = {
            'patient_id': str(patient.id),
            'name': patient.name,
            'age': patient.age,
            'treatment_type': patient.treatment_type or 'general'
        }

        if include_preferences:
            context['preferences'] = {
                'timezone': getattr(patient, 'timezone', 'America/Sao_Paulo'),
                'preferred_hour': getattr(patient, 'preferred_message_hour', 10),
                'language': getattr(patient, 'language', 'pt-BR')
            }

        if include_medical_history:
            context['medical_history'] = {
                'enrollment_date': patient.enrollment_date.isoformat() if patient.enrollment_date else None,
                'created_at': patient.created_at.isoformat() if patient.created_at else None
            }

        logger.debug(f"Patient context built for {patient.id}")
        return context

    def build_message_context(
        self,
        patient: Patient,
        flow_type: str,
        current_day: int,
        template_intent: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build complete message context.

        Args:
            patient: Patient object
            flow_type: Flow type
            current_day: Current day
            template_intent: Template intent
            additional_data: Additional context data

        Returns:
            Complete message context dictionary
        """
        context = {
            'patient': self.build_patient_context(patient, include_preferences=True),
            'flow': {
                'type': flow_type,
                'day': current_day,
                'template_intent': template_intent
            },
            'timestamp': datetime.utcnow().isoformat()
        }

        if additional_data:
            context['additional_data'] = additional_data

        logger.debug(f"Message context built for patient {patient.id}, day {current_day}")
        return context

    def build_analytics_context(
        self,
        patient_id: UUID,
        event_type: str,
        flow_type: str,
        current_day: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build analytics event context.

        Args:
            patient_id: Patient UUID
            event_type: Event type
            flow_type: Flow type
            current_day: Current day
            metadata: Event metadata

        Returns:
            Analytics context dictionary
        """
        context = {
            'patient_id': str(patient_id),
            'event_type': event_type,
            'flow_type': flow_type,
            'flow_day': current_day,
            'timestamp': datetime.utcnow().isoformat()
        }

        if metadata:
            context['additional_data'] = metadata

        return context
