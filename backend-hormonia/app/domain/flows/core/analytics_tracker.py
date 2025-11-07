"""
Analytics Tracker Module.
Handles flow analytics, metrics collection, and response processing.
"""
import logging
from typing import Any, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID
from sqlalchemy.orm import Session

from app.services.enhanced_flow_engine import EnhancedFlowEngine, FlowType
from app.services.template_loader import MessageTemplate
from app.services.flow_analytics import FlowAnalyticsService
from app.repositories.patient import PatientRepository
from app.repositories.flow import FlowStateRepository
from app.models.message import Message, MessageType, MessageStatus, MessageDirection

logger = logging.getLogger(__name__)


class AnalyticsTracker:
    """Manages flow analytics, metrics, and response processing."""

    def __init__(self,
                 db: Session,
                 enhanced_flow_engine: Optional[EnhancedFlowEngine] = None,
                 analytics_service: Optional[FlowAnalyticsService] = None):
        """
        Initialize analytics tracker.

        Args:
            db: Database session
            enhanced_flow_engine: Flow engine for AI processing
            analytics_service: Analytics service instance
        """
        self.db = db
        self.enhanced_flow_engine = enhanced_flow_engine or EnhancedFlowEngine(db)
        self.analytics_service = analytics_service or FlowAnalyticsService(db)
        self.patient_repo = PatientRepository(db)
        self.flow_state_repo = FlowStateRepository(db)

    async def get_flow_processing_metrics(self,
                                        date_range: Optional[Tuple[datetime, datetime]] = None) -> dict[str, Any]:
        """
        Get comprehensive flow processing metrics.

        Args:
            date_range: Optional date range for metrics

        Returns:
            Flow processing metrics
        """
        try:
            # Default to last 7 days if no range provided
            if not date_range:
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=7)
                date_range = (start_date, end_date)

            metrics = {
                'date_range': {
                    'start': date_range[0].isoformat(),
                    'end': date_range[1].isoformat()
                },
                'flow_processing': {
                    'total_patients_processed': 0,
                    'messages_generated': 0,
                    'ai_personalizations': 0,
                    'successful_deliveries': 0,
                    'failed_deliveries': 0
                },
                'flow_types': {
                    'initial_15_days': {'patients': 0, 'messages': 0},
                    'days_16_45': {'patients': 0, 'messages': 0},
                    'monthly_recurring': {'patients': 0, 'messages': 0}
                },
                'ai_performance': {
                    'personalization_success_rate': 0.0,
                    'anti_repetition_effectiveness': 0.0,
                    'sentiment_analysis_accuracy': 0.0
                },
                'delivery_performance': {
                    'average_delivery_time': None,
                    'delivery_success_rate': 0.0,
                    'retry_success_rate': 0.0
                }
            }

            # TODO: Implement actual metrics calculation
            # This would involve complex queries across multiple tables

            return metrics

        except Exception as e:
            logger.error(f"Failed to get flow processing metrics: {e}")
            return {}

    async def generate_personalized_message_preview(self,
                                                   patient_id: UUID,
                                                   flow_type: str,
                                                   day: int,
                                                   template_manager) -> dict[str, Any]:
        """
        Generate a preview of personalized message for healthcare providers.

        Args:
            patient_id: Patient UUID
            flow_type: Flow type string
            day: Day number
            template_manager: Template manager instance

        Returns:
            Message preview with AI insights
        """
        try:
            # Get message template
            flow_type_enum = FlowType(flow_type)
            message_template = await template_manager.get_message_template_for_day(flow_type_enum, day)

            if not message_template:
                return {
                    'status': 'error',
                    'error': f'No template found for {flow_type} day {day}'
                }

            # Generate personalized message
            personalized_content = await self.enhanced_flow_engine.generate_flow_message(
                patient_id, message_template
            )

            # Get patient context
            patient = self.patient_repo.get(patient_id)
            flow_state = self.flow_state_repo.get_active_flow(patient_id)

            return {
                'status': 'success',
                'preview': {
                    'patient_id': str(patient_id),
                    'patient_name': patient.name if patient else 'Unknown',
                    'flow_type': flow_type,
                    'day': day,
                    'template': {
                        'intent': message_template.intent,
                        'base_content': message_template.base_content,
                        'personalization_hints': message_template.personalization_hints
                    },
                    'personalized_content': personalized_content,
                    'ai_insights': {
                        'personalization_applied': True,
                        'anti_repetition_checked': True,
                        'sentiment_adapted': True
                    },
                    'flow_context': {
                        'current_step': flow_state.current_step if flow_state else None,
                        'started_at': flow_state.started_at.isoformat() if flow_state else None
                    }
                }
            }

        except Exception as e:
            logger.error(f"Failed to generate message preview: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    async def process_patient_response_with_flow_context(self,
                                                       patient_id: UUID,
                                                       response_text: str,
                                                       message_id: Optional[UUID] = None,
                                                       message_handler=None) -> dict[str, Any]:
        """
        Process patient response with full flow context and AI analysis.

        Args:
            patient_id: Patient UUID
            response_text: Patient's response text
            message_id: Original message ID (optional)
            message_handler: Message handler for follow-ups

        Returns:
            Response processing result with follow-up actions
        """
        try:
            # Process response using enhanced flow engine
            processing_result = await self.enhanced_flow_engine.process_patient_response(
                patient_id, response_text
            )

            # If follow-up message is needed, schedule it
            follow_up_message = processing_result.get('follow_up_message')
            if follow_up_message and message_handler:
                await message_handler.schedule_follow_up_message(
                    patient_id, follow_up_message, processing_result
                )

            # Update flow state with response data
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if flow_state:
                flow_state.state_data = flow_state.state_data or {}
                flow_state.state_data['last_response_processed'] = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'message_id': str(message_id) if message_id else None,
                    'sentiment': processing_result.get('sentiment_analysis', {}),
                    'requires_attention': processing_result.get('requires_attention', False)
                }
                self.db.commit()

                # Track response received event in analytics
                sentiment_analysis = processing_result.get('sentiment_analysis', {})
                await self.analytics_service.track_response_received(
                    patient_id=patient_id,
                    message_id=message_id,
                    flow_type=flow_state.flow_type,
                    flow_day=flow_state.current_step,
                    response_text=response_text,
                    sentiment_score=sentiment_analysis.get('score'),
                    engagement_score=processing_result.get('engagement_score'),
                    response_time_seconds=processing_result.get('response_time_seconds'),
                    additional_data={
                        'requires_attention': processing_result.get('requires_attention', False),
                        'extracted_data': processing_result.get('extracted_data', {}),
                        'follow_up_triggered': bool(processing_result.get('follow_up_message'))
                    }
                )

            return processing_result

        except Exception as e:
            logger.error(f"Failed to process patient response with flow context: {e}")
            return {
                'status': 'error',
                'patient_id': str(patient_id),
                'error': str(e)
            }

    async def track_flow_advancement(self,
                                    patient_id: UUID,
                                    flow_type: str,
                                    old_step: int,
                                    new_step: int,
                                    advancement_reason: str) -> None:
        """
        Track flow advancement in analytics.

        Args:
            patient_id: Patient UUID
            flow_type: Type of flow
            old_step: Previous step
            new_step: New step
            advancement_reason: Reason for advancement
        """
        try:
            await self.analytics_service.track_flow_event(
                patient_id=patient_id,
                flow_type=flow_type,
                event_type='flow_advanced',
                event_data={
                    'old_step': old_step,
                    'new_step': new_step,
                    'advancement_reason': advancement_reason,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            logger.info(f"Tracked flow advancement for patient {patient_id}: {old_step} -> {new_step}")
        except Exception as e:
            logger.error(f"Failed to track flow advancement: {e}")

    async def track_message_delivery(self,
                                    patient_id: UUID,
                                    message_id: UUID,
                                    delivery_status: str,
                                    delivery_time_seconds: Optional[float] = None) -> None:
        """
        Track message delivery metrics.

        Args:
            patient_id: Patient UUID
            message_id: Message UUID
            delivery_status: Delivery status
            delivery_time_seconds: Time to deliver
        """
        try:
            await self.analytics_service.track_flow_event(
                patient_id=patient_id,
                flow_type='delivery_tracking',
                event_type='message_delivered',
                event_data={
                    'message_id': str(message_id),
                    'delivery_status': delivery_status,
                    'delivery_time_seconds': delivery_time_seconds,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Failed to track message delivery: {e}")

    async def calculate_engagement_score(self, patient_id: UUID) -> float:
        """
        Calculate patient engagement score based on response patterns.

        Args:
            patient_id: Patient UUID

        Returns:
            Engagement score (0.0 to 1.0)
        """
        try:
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            if not flow_state:
                return 0.0

            state_data = flow_state.state_data or {}

            # Factors for engagement score:
            # - Response rate
            # - Response time
            # - Message interaction depth
            # - Quiz completion rate

            response_count = state_data.get('response_count', 0)
            messages_sent = state_data.get('messages_sent_count', 1)

            response_rate = response_count / max(messages_sent, 1)

            # Simple engagement score (can be enhanced)
            engagement_score = min(response_rate, 1.0)

            logger.debug(f"Calculated engagement score for patient {patient_id}: {engagement_score:.2f}")

            return engagement_score

        except Exception as e:
            logger.error(f"Failed to calculate engagement score: {e}")
            return 0.0

    async def get_patient_flow_summary(self, patient_id: UUID) -> dict[str, Any]:
        """
        Get comprehensive flow summary for a patient.

        Args:
            patient_id: Patient UUID

        Returns:
            Flow summary with statistics
        """
        try:
            flow_state = self.flow_state_repo.get_active_flow(patient_id)
            patient = self.patient_repo.get(patient_id)

            if not flow_state or not patient:
                return {'error': 'Patient or flow state not found'}

            # Calculate statistics
            engagement_score = await self.calculate_engagement_score(patient_id)

            summary = {
                'patient_id': str(patient_id),
                'patient_name': patient.name,
                'flow_type': flow_state.flow_type,
                'current_step': flow_state.current_step,
                'started_at': flow_state.started_at.isoformat() if flow_state.started_at else None,
                'engagement_score': engagement_score,
                'state_data': flow_state.state_data,
                'last_interaction': flow_state.state_data.get('last_message_sent', {}).get('timestamp') if flow_state.state_data else None
            }

            return summary

        except Exception as e:
            logger.error(f"Failed to get patient flow summary: {e}")
            return {'error': str(e)}
