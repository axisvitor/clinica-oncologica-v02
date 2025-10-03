"""
A/B Testing Integration Service for Message Factory

Integrates A/B testing framework with the existing message factory to enable
seamless testing of static vs AI-humanized messages while maintaining
healthcare compliance and patient safety.
"""

import logging
from typing import Dict, Optional, Any, List
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.services.ab_testing import ABTestingService, VariantType
from app.services.ab_testing_audit import ABTestingAuditService, AuditEventType
from app.services.message_factory import MessageFactory, MessageTemplate
from app.services.ai import AIService
from app.models.message import Message
from app.models.patient import Patient

logger = logging.getLogger(__name__)


class ABTestingIntegration:
    """
    Integration layer between A/B testing framework and message factory.

    Provides seamless integration for testing static vs AI-humanized messages
    while maintaining all safety controls and compliance requirements.
    """

    def __init__(
        self,
        db: Session,
        ab_service: Optional[ABTestingService] = None,
        audit_service: Optional[ABTestingAuditService] = None,
        message_factory: Optional[MessageFactory] = None,
        ai_service: Optional[AIService] = None
    ):
        """Initialize A/B testing integration."""
        self.db = db
        self.ab_service = ab_service or ABTestingService(db)
        self.audit_service = audit_service or ABTestingAuditService(db)
        self.message_factory = message_factory or MessageFactory(db)
        self.ai_service = ai_service or AIService()

        # Configuration
        self.enabled_templates = [
            MessageTemplate.MONTHLY_QUIZ_LINK_INVITATION,
            MessageTemplate.MONTHLY_QUIZ_LINK_REMINDER,
            MessageTemplate.QUIZ_INTRODUCTION,
            MessageTemplate.FLOW_MESSAGE
        ]

        # Active experiments cache (refreshed periodically)
        self._active_experiments = {}
        self._last_cache_refresh = None

    def create_ab_test_message(
        self,
        patient_id: UUID,
        template: MessageTemplate,
        content: str,
        **message_kwargs
    ) -> Message:
        """
        Create message with A/B testing integration.

        This is the main entry point for creating messages that may be part
        of an A/B test comparing static vs AI-humanized versions.

        Args:
            patient_id: Patient UUID
            template: Message template type
            content: Base message content
            **message_kwargs: Additional message creation parameters

        Returns:
            Created message with A/B test tracking
        """
        try:
            # Check if A/B testing is active for this template
            active_experiment = self._get_active_experiment_for_template(template)

            if not active_experiment:
                # No active experiment - create normal message
                return self.message_factory.create_outbound_message(
                    patient_id=patient_id,
                    content=content,
                    template_type=template,
                    **message_kwargs
                )

            # A/B testing is active - assign variant and create appropriate message
            variant = self.ab_service.assign_patient_to_variant(
                patient_id=patient_id,
                experiment_id=active_experiment["id"],
                message_template=template
            )

            if variant is None:
                # Patient not eligible for A/B test - create normal message
                self.audit_service.log_patient_interaction(
                    experiment_id=active_experiment["id"],
                    patient_id=patient_id,
                    action=AuditEventType.PATIENT_EXCLUDED,
                    assignment_reason="eligibility_criteria_not_met"
                )
                return self.message_factory.create_outbound_message(
                    patient_id=patient_id,
                    content=content,
                    template_type=template,
                    **message_kwargs
                )

            # Create A/B test message
            message = self.ab_service.create_experiment_message(
                patient_id=patient_id,
                experiment_id=active_experiment["id"],
                variant=variant,
                base_content=content,
                message_template=template,
                **message_kwargs
            )

            # Log successful assignment
            self.audit_service.log_patient_interaction(
                experiment_id=active_experiment["id"],
                patient_id=patient_id,
                action=AuditEventType.PATIENT_ASSIGNED,
                variant=variant.value
            )

            logger.info(f"Created A/B test message for patient {patient_id}, variant: {variant.value}")
            return message

        except Exception as e:
            logger.error(f"Error creating A/B test message: {str(e)}")
            # Fallback to normal message creation
            return self.message_factory.create_outbound_message(
                patient_id=patient_id,
                content=content,
                template_type=template,
                **message_kwargs
            )

    def track_message_event(
        self,
        message: Message,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None,
        response_time_seconds: Optional[float] = None,
        engagement_score: Optional[float] = None
    ) -> None:
        """
        Track message event for A/B testing analytics.

        Args:
            message: Message object
            event_type: Event type (sent, delivered, read, responded, etc.)
            event_data: Additional event data
            response_time_seconds: Response time in seconds
            engagement_score: Engagement quality score (0-1)
        """
        try:
            # Check if message is part of an A/B test
            if not message.message_metadata.get("ab_testing"):
                return

            experiment_id = message.message_metadata.get("experiment_id")
            if not experiment_id:
                return

            # Track performance
            self.ab_service.track_message_performance(
                message_id=message.id,
                event_type=event_type,
                event_data=event_data
            )

            # Log message activity for audit
            variant = message.message_metadata.get("variant", "unknown")
            ai_processing = message.message_metadata.get("ai_processing")
            safety_checks = message.message_metadata.get("safety_checks")

            performance_data = {
                "response_time_seconds": response_time_seconds,
                "engagement_score": engagement_score,
                "delivery_status": event_type
            }

            self.audit_service.log_message_activity(
                experiment_id=experiment_id,
                message_id=message.id,
                action=f"message_{event_type}",
                variant=variant,
                patient_id=message.patient_id,
                ai_processing=ai_processing,
                safety_checks=safety_checks,
                performance_data=performance_data
            )

            logger.debug(f"Tracked A/B test event: {event_type} for message {message.id}")

        except Exception as e:
            logger.error(f"Error tracking message event: {str(e)}")

    def setup_experiment_for_template(
        self,
        template: MessageTemplate,
        experiment_name: str,
        duration_days: int = 30,
        traffic_split: float = 0.5,
        target_population: Optional[Dict[str, Any]] = None,
        created_by: str = "system"
    ) -> str:
        """
        Setup A/B experiment for a specific message template.

        Args:
            template: Message template to test
            experiment_name: Experiment name
            duration_days: Experiment duration
            traffic_split: Percentage of traffic to treatment
            target_population: Target population criteria
            created_by: User creating the experiment

        Returns:
            Experiment ID
        """
        try:
            # Create experiment
            experiment_id = self.ab_service.create_experiment(
                name=experiment_name,
                description=f"A/B test for {template.value}: Static vs AI-humanized messages",
                message_template=template,
                target_population=target_population,
                duration_days=duration_days,
                traffic_split=traffic_split,
                primary_metric="response_rate",
                secondary_metrics=["engagement_score", "response_time"],
                safety_checks=True,
                created_by=created_by
            )

            # Refresh active experiments cache
            self._refresh_active_experiments()

            logger.info(f"Created A/B experiment {experiment_id} for template {template.value}")
            return experiment_id

        except Exception as e:
            logger.error(f"Error setting up experiment: {str(e)}")
            raise

    def get_experiment_performance_summary(self, experiment_id: str) -> Dict[str, Any]:
        """
        Get performance summary for an experiment.

        Args:
            experiment_id: Experiment ID

        Returns:
            Performance summary
        """
        try:
            # Get experiment status
            status = self.ab_service.get_experiment_status(experiment_id)

            # Get detailed results if available
            try:
                results = self.ab_service.calculate_experiment_results(experiment_id)
            except Exception as e:
                logger.warning(f"Could not calculate detailed results: {str(e)}")
                results = {"error": str(e)}

            return {
                "experiment_id": experiment_id,
                "status": status,
                "results": results,
                "last_updated": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Error getting performance summary: {str(e)}")
            return {"error": str(e)}

    def handle_monthly_quiz_ab_test(
        self,
        patient_id: UUID,
        patient_name: str,
        link_url: str,
        quiz_session_id: str,
        message_type: str = "invitation"
    ) -> Message:
        """
        Handle A/B testing for monthly quiz messages.

        Args:
            patient_id: Patient UUID
            patient_name: Patient name
            link_url: Quiz link URL
            quiz_session_id: Quiz session ID
            message_type: Type of message (invitation, reminder)

        Returns:
            Created message with A/B test integration
        """
        try:
            # Determine template
            if message_type == "invitation":
                template = MessageTemplate.MONTHLY_QUIZ_LINK_INVITATION
                base_content = f"""Olá {patient_name}! 🌸

Chegou o momento do seu questionário mensal de bem-estar! 📋

Acesse através do link: {link_url}

⏰ Válido por 72 horas

Sua participação é muito importante para acompanharmos seu progresso."""

            elif message_type == "reminder":
                template = MessageTemplate.MONTHLY_QUIZ_LINK_REMINDER
                base_content = f"""Oi {patient_name}! ⏰

Lembrete: você ainda não respondeu ao questionário mensal.

Por favor, acesse: {link_url}

⚠️ Expira em breve

Contamos com você!"""
            else:
                raise ValueError(f"Unsupported message type: {message_type}")

            # Create A/B test message
            message = self.create_ab_test_message(
                patient_id=patient_id,
                template=template,
                content=base_content,
                metadata={
                    "quiz_session_id": quiz_session_id,
                    "link_url": link_url,
                    "message_type": f"monthly_quiz_{message_type}"
                }
            )

            return message

        except Exception as e:
            logger.error(f"Error handling monthly quiz A/B test: {str(e)}")
            # Fallback to regular message creation
            if message_type == "invitation":
                return self.message_factory.create_monthly_quiz_link_message(
                    patient_id=patient_id,
                    patient_name=patient_name,
                    link_url=link_url,
                    quiz_session_id=quiz_session_id
                )
            else:
                return self.message_factory.create_monthly_quiz_reminder_message(
                    patient_id=patient_id,
                    patient_name=patient_name,
                    link_url=link_url,
                    quiz_session_id=quiz_session_id,
                    hours_remaining=24
                )

    def generate_experiment_report(self, experiment_id: str, report_type: str = "summary") -> Dict[str, Any]:
        """
        Generate comprehensive experiment report.

        Args:
            experiment_id: Experiment ID
            report_type: Report type (summary, detailed, compliance)

        Returns:
            Experiment report
        """
        try:
            # Get experiment performance
            performance = self.get_experiment_performance_summary(experiment_id)

            # Get audit trail
            audit_trail = self.audit_service.get_audit_trail(experiment_id)

            # Get compliance report
            compliance_report = self.audit_service.generate_compliance_report(
                experiment_id, report_type
            )

            report = {
                "experiment_id": experiment_id,
                "report_type": report_type,
                "generated_at": datetime.utcnow().isoformat(),
                "performance_summary": performance,
                "compliance_status": compliance_report,
                "total_audit_entries": len(audit_trail)
            }

            if report_type == "detailed":
                report["detailed_audit_trail"] = audit_trail

            return report

        except Exception as e:
            logger.error(f"Error generating experiment report: {str(e)}")
            return {"error": str(e)}

    def cleanup_completed_experiments(self, days_threshold: int = 90) -> int:
        """
        Clean up data from old completed experiments.

        Args:
            days_threshold: Days after completion to clean up

        Returns:
            Number of experiments cleaned up
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_threshold)

            # Get completed experiments older than threshold
            from app.models.ab_experiment import ExperimentStatus
            old_experiments = self.db.query(ABExperiment).filter(
                and_(
                    ABExperiment.status == ExperimentStatus.COMPLETED,
                    ABExperiment.end_date < cutoff_date
                )
            ).all()

            cleanup_count = 0
            for experiment in old_experiments:
                try:
                    # Archive experiment data before cleanup
                    self._archive_experiment_data(experiment.id)

                    # Clean up metrics (keeping summary results)
                    self.db.query(ABExperimentMetric).filter(
                        ABExperimentMetric.experiment_id == experiment.id
                    ).delete()

                    cleanup_count += 1
                    logger.info(f"Cleaned up experiment {experiment.id}")

                except Exception as e:
                    logger.error(f"Error cleaning up experiment {experiment.id}: {str(e)}")

            self.db.commit()
            return cleanup_count

        except Exception as e:
            logger.error(f"Error in cleanup: {str(e)}")
            self.db.rollback()
            return 0

    # Private helper methods

    def _get_active_experiment_for_template(self, template: MessageTemplate) -> Optional[Dict[str, Any]]:
        """Get active experiment for a message template."""
        # Refresh cache if needed
        if (self._last_cache_refresh is None or
            datetime.utcnow() - self._last_cache_refresh > timedelta(minutes=5)):
            self._refresh_active_experiments()

        return self._active_experiments.get(template.value)

    def _refresh_active_experiments(self) -> None:
        """Refresh cache of active experiments."""
        try:
            from app.models.ab_experiment import ExperimentStatus

            active_experiments = self.db.query(ABExperiment).filter(
                ABExperiment.status == ExperimentStatus.ACTIVE
            ).all()

            self._active_experiments = {}
            for exp in active_experiments:
                if exp.message_template in [t.value for t in self.enabled_templates]:
                    self._active_experiments[exp.message_template] = {
                        "id": str(exp.id),
                        "name": exp.name,
                        "traffic_split": exp.traffic_split,
                        "safety_checks_enabled": exp.safety_checks_enabled
                    }

            self._last_cache_refresh = datetime.utcnow()
            logger.debug(f"Refreshed active experiments cache: {len(self._active_experiments)} active")

        except Exception as e:
            logger.error(f"Error refreshing active experiments: {str(e)}")

    def _archive_experiment_data(self, experiment_id: str) -> None:
        """Archive experiment data before cleanup."""
        try:
            # Generate final report
            final_report = self.generate_experiment_report(experiment_id, "detailed")

            # Store in archive (implement based on your archival strategy)
            # Could be file storage, separate database, etc.
            archive_path = f"archives/experiment_{experiment_id}_{datetime.utcnow().isoformat()}.json"

            # Log archival
            logger.info(f"Archived experiment {experiment_id} data to {archive_path}")

        except Exception as e:
            logger.error(f"Error archiving experiment data: {str(e)}")


# Utility functions for easy integration

def create_ab_test_monthly_quiz_invitation(
    db: Session,
    patient_id: UUID,
    patient_name: str,
    link_url: str,
    quiz_session_id: str
) -> Message:
    """
    Convenience function to create A/B tested monthly quiz invitation.

    Args:
        db: Database session
        patient_id: Patient UUID
        patient_name: Patient name
        link_url: Quiz link URL
        quiz_session_id: Quiz session ID

    Returns:
        Created message with A/B test integration
    """
    integration = ABTestingIntegration(db)
    return integration.handle_monthly_quiz_ab_test(
        patient_id=patient_id,
        patient_name=patient_name,
        link_url=link_url,
        quiz_session_id=quiz_session_id,
        message_type="invitation"
    )


def track_message_response(
    db: Session,
    message: Message,
    response_time_seconds: Optional[float] = None,
    engagement_score: Optional[float] = None
) -> None:
    """
    Convenience function to track message response for A/B testing.

    Args:
        db: Database session
        message: Message object
        response_time_seconds: Response time in seconds
        engagement_score: Engagement quality score (0-1)
    """
    integration = ABTestingIntegration(db)
    integration.track_message_event(
        message=message,
        event_type="responded",
        response_time_seconds=response_time_seconds,
        engagement_score=engagement_score
    )


def get_ab_testing_integration(db: Session) -> ABTestingIntegration:
    """Get A/B testing integration service instance."""
    return ABTestingIntegration(db)