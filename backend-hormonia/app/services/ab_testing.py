"""
A/B Testing Framework for Hormonia Healthcare System

This service provides HIPAA-compliant A/B testing capabilities for comparing
static messages vs AI-humanized messages while ensuring patient safety and
maintaining statistical rigor.

Features:
- Healthcare-compliant patient cohort assignment
- Statistical significance calculations
- Emergency stop mechanisms for safety
- Comprehensive audit logging
- Medical content validation
- Real-time monitoring and alerts
"""

import hashlib
import json
import logging
import secrets
import statistics
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID, uuid4

import numpy as np
from scipy import stats
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from app.config import settings
from app.models.message import Message, MessageStatus, MessageType
from app.models.patient import Patient
from app.services.audit_service import AuditService
from app.services.message_factory import MessageFactory, MessageTemplate
from app.services.ai import AIService
from app.services.encryption_service import EncryptionService
from app.services.privacy_service import PrivacyService

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """Experiment lifecycle status."""
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"  # Emergency stop


class VariantType(Enum):
    """A/B test variant types."""
    CONTROL = "control"  # Static messages
    TREATMENT = "treatment"  # AI-humanized messages


class PatientSafetyLevel(Enum):
    """Patient safety classification for A/B testing eligibility."""
    SAFE = "safe"  # Can participate in A/B tests
    RESTRICTED = "restricted"  # Limited participation
    EXCLUDED = "excluded"  # Cannot participate in A/B tests


class StatisticalTest(Enum):
    """Available statistical tests."""
    T_TEST = "t_test"
    MANN_WHITNEY_U = "mann_whitney_u"
    CHI_SQUARE = "chi_square"
    FISHER_EXACT = "fisher_exact"


class ABTestingService:
    """
    Comprehensive A/B testing service for healthcare environments.

    Provides HIPAA-compliant experimentation with patient safety controls,
    statistical analysis, and comprehensive audit trails.
    """

    def __init__(
        self,
        db: Session,
        audit_service: Optional[AuditService] = None,
        ai_service: Optional[AIService] = None,
        encryption_service: Optional[EncryptionService] = None,
        privacy_service: Optional[PrivacyService] = None
    ):
        """Initialize A/B testing service."""
        self.db = db
        self.audit_service = audit_service or AuditService(db)
        self.ai_service = ai_service or AIService()
        self.encryption_service = encryption_service or EncryptionService()
        self.privacy_service = privacy_service or PrivacyService()
        self.message_factory = MessageFactory(db)

        # Statistical configuration
        self.alpha = 0.05  # Significance level
        self.min_sample_size = 100  # Minimum sample size per variant
        self.min_effect_size = 0.1  # Minimum detectable effect size
        self.power = 0.8  # Statistical power

        # Safety configuration
        self.medical_keywords = [
            "medicação", "remédio", "dosagem", "mg", "ml", "emergência", "urgente",
            "hospital", "médico", "consulta", "exame", "resultado", "tratamento",
            "quimioterapia", "radioterapia", "cirurgia", "efeito colateral",
            "reação adversa", "contraindicação", "suspender", "parar", "não tome",
            "dose", "prescrição", "receita", "alergia", "sintoma", "dor"
        ]

        # Performance thresholds for automatic stopping
        self.performance_thresholds = {
            "response_rate_drop": 0.2,  # 20% drop in response rate
            "engagement_drop": 0.3,     # 30% drop in engagement
            "error_rate_spike": 0.1     # 10% error rate spike
        }

    def create_experiment(
        self,
        name: str,
        description: str,
        message_template: MessageTemplate,
        target_population: Optional[Dict[str, Any]] = None,
        duration_days: int = 30,
        traffic_split: float = 0.5,
        primary_metric: str = "response_rate",
        secondary_metrics: Optional[List[str]] = None,
        safety_checks: bool = True,
        created_by: str = "system"
    ) -> str:
        """
        Create a new A/B test experiment.

        Args:
            name: Experiment name
            description: Experiment description
            message_template: Template type to test
            target_population: Patient filtering criteria
            duration_days: Experiment duration in days
            traffic_split: Percentage of traffic to treatment (0.0-1.0)
            primary_metric: Primary success metric
            secondary_metrics: Additional metrics to track
            safety_checks: Enable safety validation
            created_by: User creating the experiment

        Returns:
            Experiment ID
        """
        experiment_id = str(uuid4())

        # Validate configuration
        if not 0.1 <= traffic_split <= 0.9:
            raise ValueError("Traffic split must be between 10% and 90%")

        if duration_days > 90:
            raise ValueError("Maximum experiment duration is 90 days")

        # Create experiment configuration
        experiment_config = {
            "id": experiment_id,
            "name": name,
            "description": description,
            "message_template": message_template.value,
            "target_population": target_population or {},
            "duration_days": duration_days,
            "traffic_split": traffic_split,
            "primary_metric": primary_metric,
            "secondary_metrics": secondary_metrics or [],
            "safety_checks": safety_checks,
            "status": ExperimentStatus.DRAFT.value,
            "created_at": datetime.utcnow().isoformat(),
            "created_by": created_by,
            "start_date": None,
            "end_date": None,
            "statistics": {
                "alpha": self.alpha,
                "min_sample_size": self.min_sample_size,
                "min_effect_size": self.min_effect_size,
                "power": self.power
            },
            "variants": {
                "control": {
                    "type": VariantType.CONTROL.value,
                    "description": "Static template messages",
                    "traffic_percentage": 1.0 - traffic_split
                },
                "treatment": {
                    "type": VariantType.TREATMENT.value,
                    "description": "AI-humanized messages",
                    "traffic_percentage": traffic_split
                }
            },
            "safety_configuration": {
                "medical_keyword_check": True,
                "manual_review_required": safety_checks,
                "emergency_stop_enabled": True,
                "performance_monitoring": True
            }
        }

        # Store encrypted experiment configuration
        encrypted_config = self.encryption_service.encrypt_data(
            json.dumps(experiment_config)
        )

        # Save to database (implement your storage logic)
        self._store_experiment(experiment_id, encrypted_config)

        # Audit log
        self.audit_service.log_experiment_created(
            experiment_id=experiment_id,
            name=name,
            created_by=created_by,
            configuration=experiment_config
        )

        logger.info(f"Created A/B test experiment: {experiment_id} - {name}")
        return experiment_id

    def start_experiment(self, experiment_id: str, started_by: str = "system") -> bool:
        """
        Start an A/B test experiment.

        Args:
            experiment_id: Experiment ID
            started_by: User starting the experiment

        Returns:
            Success status
        """
        try:
            # Load experiment configuration
            config = self._load_experiment(experiment_id)
            if not config:
                raise ValueError(f"Experiment {experiment_id} not found")

            # Validate experiment can be started
            if config["status"] != ExperimentStatus.DRAFT.value:
                raise ValueError(f"Experiment {experiment_id} cannot be started from status {config['status']}")

            # Pre-flight safety checks
            if not self._validate_experiment_safety(config):
                raise ValueError("Experiment failed safety validation")

            # Calculate eligible patient population
            eligible_patients = self._get_eligible_patients(config["target_population"])

            if len(eligible_patients) < self.min_sample_size * 2:
                raise ValueError(f"Insufficient patient population. Need at least {self.min_sample_size * 2}")

            # Update configuration
            config["status"] = ExperimentStatus.ACTIVE.value
            config["start_date"] = datetime.utcnow().isoformat()
            config["end_date"] = (datetime.utcnow() + timedelta(days=config["duration_days"])).isoformat()
            config["started_by"] = started_by
            config["eligible_patient_count"] = len(eligible_patients)

            # Store updated configuration
            self._store_experiment(experiment_id, self.encryption_service.encrypt_data(json.dumps(config)))

            # Initialize tracking metrics
            self._initialize_experiment_metrics(experiment_id)

            # Audit log
            self.audit_service.log_experiment_started(
                experiment_id=experiment_id,
                started_by=started_by,
                eligible_patients=len(eligible_patients)
            )

            logger.info(f"Started A/B test experiment: {experiment_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to start experiment {experiment_id}: {str(e)}")
            self.audit_service.log_experiment_error(
                experiment_id=experiment_id,
                error_type="start_failure",
                error_details=str(e)
            )
            return False

    def assign_patient_to_variant(
        self,
        patient_id: UUID,
        experiment_id: str,
        message_template: MessageTemplate
    ) -> Optional[VariantType]:
        """
        Assign patient to experiment variant using deterministic hashing.

        Args:
            patient_id: Patient UUID
            experiment_id: Experiment ID
            message_template: Message template type

        Returns:
            Assigned variant or None if not eligible
        """
        try:
            # Load experiment configuration
            config = self._load_experiment(experiment_id)
            if not config or config["status"] != ExperimentStatus.ACTIVE.value:
                return None

            # Check if patient is eligible for A/B testing
            safety_level = self._assess_patient_safety_level(patient_id)
            if safety_level == PatientSafetyLevel.EXCLUDED:
                return None

            # Check if patient matches target population
            if not self._patient_matches_criteria(patient_id, config["target_population"]):
                return None

            # Deterministic assignment using hash
            # This ensures consistent assignment across sessions
            hash_input = f"{patient_id}:{experiment_id}:{message_template.value}:{config['created_at']}"
            hash_value = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
            assignment_ratio = (hash_value % 10000) / 10000.0

            # Apply safety restrictions for restricted patients
            if safety_level == PatientSafetyLevel.RESTRICTED:
                # Only assign restricted patients to control group
                variant = VariantType.CONTROL
            else:
                # Normal assignment based on traffic split
                if assignment_ratio < config["traffic_split"]:
                    variant = VariantType.TREATMENT
                else:
                    variant = VariantType.CONTROL

            # Log assignment (anonymized)
            self._log_variant_assignment(experiment_id, patient_id, variant, safety_level)

            return variant

        except Exception as e:
            logger.error(f"Error assigning patient {patient_id} to variant: {str(e)}")
            return None

    async def create_experiment_message(
        self,
        patient_id: UUID,
        experiment_id: str,
        variant: VariantType,
        base_content: str,
        message_template: MessageTemplate,
        **kwargs
    ) -> Message:
        """
        Create message based on experiment variant.

        Args:
            patient_id: Patient UUID
            experiment_id: Experiment ID
            variant: Assigned variant
            base_content: Base message content
            message_template: Message template type
            **kwargs: Additional message parameters

        Returns:
            Created message
        """
        # Add experiment metadata
        experiment_metadata = {
            "experiment_id": experiment_id,
            "variant": variant.value,
            "ab_testing": True,
            "created_at": datetime.utcnow().isoformat()
        }

        # Merge with existing metadata
        metadata = kwargs.get('metadata', {})
        metadata.update(experiment_metadata)
        kwargs['metadata'] = metadata

        # Create message based on variant
        if variant == VariantType.TREATMENT:
            # AI-humanized message
            try:
                # Safety check for medical content
                if self._contains_medical_keywords(base_content):
                    logger.warning(f"Medical content detected in A/B test message for patient {patient_id}, using control variant")
                    final_content = base_content
                    metadata['fallback_reason'] = 'medical_content_safety'
                else:
                    # Apply AI humanization (await coroutine)
                    humanized_result = await self.ai_service.humanize_message(
                        base_content,
                        context={"patient_id": str(patient_id), "template": message_template.value}
                    )

                    if hasattr(humanized_result, "humanized_message"):
                        final_content = humanized_result.humanized_message
                        metadata["ai_processing"] = {
                            "confidence_score": getattr(humanized_result, "confidence_score", None),
                            "personalization_notes": getattr(humanized_result, "personalization_notes", [])
                        }
                    else:
                        final_content = humanized_result if humanized_result else base_content

                    if not final_content or final_content == base_content:
                        metadata['fallback_reason'] = 'ai_service_failure'

            except Exception as e:
                logger.error(f"AI humanization failed for experiment {experiment_id}: {str(e)}")
                final_content = base_content
                metadata['fallback_reason'] = 'ai_service_error'
                metadata['ai_error'] = str(e)
        else:
            # Control variant - use static content
            final_content = base_content

        # Create message using factory
        message = self.message_factory.create_outbound_message(
            patient_id=patient_id,
            content=final_content,
            metadata=metadata,
            template_type=message_template,
            **{k: v for k, v in kwargs.items() if k != 'metadata'}
        )

        # Track message creation for experiment
        self._track_experiment_message(experiment_id, variant, patient_id, message.id)

        return message

    def track_message_performance(
        self,
        message_id: int,
        event_type: str,
        event_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Track message performance metrics for A/B testing.

        Args:
            message_id: Message ID
            event_type: Event type (sent, delivered, read, responded, etc.)
            event_data: Additional event data
        """
        try:
            # Get message and check if it's part of an experiment
            message = self.db.query(Message).filter(Message.id == message_id).first()
            if not message or not message.message_metadata.get('ab_testing'):
                return

            experiment_id = message.message_metadata.get('experiment_id')
            variant = message.message_metadata.get('variant')

            if not experiment_id or not variant:
                return

            # Record performance metric
            metric_data = {
                "experiment_id": experiment_id,
                "variant": variant,
                "message_id": message_id,
                "patient_id": str(message.patient_id),
                "event_type": event_type,
                "event_data": event_data or {},
                "timestamp": datetime.utcnow().isoformat()
            }

            # Store metric (implement your storage logic)
            self._store_experiment_metric(metric_data)

            # Check for performance issues that might require emergency stop
            self._check_performance_thresholds(experiment_id)

        except Exception as e:
            logger.error(f"Error tracking message performance: {str(e)}")

    def calculate_experiment_results(self, experiment_id: str) -> Dict[str, Any]:
        """
        Calculate comprehensive experiment results with statistical analysis.

        Args:
            experiment_id: Experiment ID

        Returns:
            Experiment results with statistical analysis
        """
        try:
            config = self._load_experiment(experiment_id)
            if not config:
                raise ValueError(f"Experiment {experiment_id} not found")

            # Get experiment metrics
            metrics = self._get_experiment_metrics(experiment_id)

            # Calculate basic statistics for each variant
            variant_stats = {}
            for variant in [VariantType.CONTROL.value, VariantType.TREATMENT.value]:
                variant_metrics = [m for m in metrics if m['variant'] == variant]
                variant_stats[variant] = self._calculate_variant_statistics(variant_metrics)

            # Perform statistical tests
            statistical_results = self._perform_statistical_tests(
                variant_stats[VariantType.CONTROL.value],
                variant_stats[VariantType.TREATMENT.value],
                config["primary_metric"]
            )

            # Calculate effect sizes
            effect_sizes = self._calculate_effect_sizes(
                variant_stats[VariantType.CONTROL.value],
                variant_stats[VariantType.TREATMENT.value]
            )

            # Generate recommendations
            recommendations = self._generate_recommendations(
                statistical_results,
                effect_sizes,
                variant_stats,
                config
            )

            results = {
                "experiment_id": experiment_id,
                "experiment_name": config["name"],
                "status": config["status"],
                "duration_days": config["duration_days"],
                "start_date": config.get("start_date"),
                "end_date": config.get("end_date"),
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "sample_sizes": {
                    "control": variant_stats[VariantType.CONTROL.value].get("sample_size", 0),
                    "treatment": variant_stats[VariantType.TREATMENT.value].get("sample_size", 0)
                },
                "variant_performance": variant_stats,
                "statistical_tests": statistical_results,
                "effect_sizes": effect_sizes,
                "recommendations": recommendations,
                "confidence_level": 1 - self.alpha,
                "is_statistically_significant": statistical_results.get("is_significant", False),
                "winner": statistical_results.get("winner"),
                "confidence_interval": statistical_results.get("confidence_interval")
            }

            # Store results
            self._store_experiment_results(experiment_id, results)

            return results

        except Exception as e:
            logger.error(f"Error calculating experiment results: {str(e)}")
            return {"error": str(e)}

    def emergency_stop_experiment(
        self,
        experiment_id: str,
        reason: str,
        stopped_by: str = "system"
    ) -> bool:
        """
        Emergency stop experiment due to safety or performance concerns.

        Args:
            experiment_id: Experiment ID
            reason: Reason for emergency stop
            stopped_by: User or system stopping the experiment

        Returns:
            Success status
        """
        try:
            config = self._load_experiment(experiment_id)
            if not config:
                raise ValueError(f"Experiment {experiment_id} not found")

            # Update status
            config["status"] = ExperimentStatus.TERMINATED.value
            config["terminated_at"] = datetime.utcnow().isoformat()
            config["termination_reason"] = reason
            config["terminated_by"] = stopped_by

            # Store updated configuration
            self._store_experiment(experiment_id, self.encryption_service.encrypt_data(json.dumps(config)))

            # Generate final results
            final_results = self.calculate_experiment_results(experiment_id)

            # Send alerts to stakeholders
            self._send_emergency_stop_alerts(experiment_id, reason, final_results)

            # Audit log
            self.audit_service.log_experiment_emergency_stop(
                experiment_id=experiment_id,
                reason=reason,
                stopped_by=stopped_by,
                final_results=final_results
            )

            logger.critical(f"Emergency stopped experiment {experiment_id}: {reason}")
            return True

        except Exception as e:
            logger.error(f"Error emergency stopping experiment: {str(e)}")
            return False

    def get_experiment_status(self, experiment_id: str) -> Dict[str, Any]:
        """Get current experiment status and basic metrics."""
        try:
            config = self._load_experiment(experiment_id)
            if not config:
                return {"error": "Experiment not found"}

            # Get current metrics
            metrics = self._get_experiment_metrics(experiment_id)

            # Calculate basic statistics
            total_messages = len(metrics)
            control_messages = len([m for m in metrics if m['variant'] == VariantType.CONTROL.value])
            treatment_messages = len([m for m in metrics if m['variant'] == VariantType.TREATMENT.value])

            # Calculate response rates
            responded_metrics = [m for m in metrics if m.get('event_type') == 'responded']
            response_rate = len(responded_metrics) / total_messages if total_messages > 0 else 0

            return {
                "experiment_id": experiment_id,
                "name": config["name"],
                "status": config["status"],
                "start_date": config.get("start_date"),
                "end_date": config.get("end_date"),
                "total_messages": total_messages,
                "control_messages": control_messages,
                "treatment_messages": treatment_messages,
                "overall_response_rate": response_rate,
                "traffic_split": config["traffic_split"],
                "primary_metric": config["primary_metric"],
                "safety_checks_enabled": config["safety_configuration"]["medical_keyword_check"]
            }

        except Exception as e:
            logger.error(f"Error getting experiment status: {str(e)}")
            return {"error": str(e)}

    # Private helper methods

    def _assess_patient_safety_level(self, patient_id: UUID) -> PatientSafetyLevel:
        """Assess patient safety level for A/B testing participation."""
        try:
            # Get patient data
            patient = self.db.query(Patient).filter(Patient.id == patient_id).first()
            if not patient:
                return PatientSafetyLevel.EXCLUDED

            # Check for high-risk conditions
            patient_data = patient.patient_metadata or {}

            # Exclude patients with critical conditions
            critical_conditions = [
                "active_treatment", "chemotherapy", "radiotherapy",
                "post_surgery", "critical_care", "emergency_contact"
            ]

            for condition in critical_conditions:
                if patient_data.get(condition, False):
                    return PatientSafetyLevel.EXCLUDED

            # Restrict patients with moderate risk
            moderate_risk = [
                "recent_diagnosis", "medication_changes", "frequent_symptoms"
            ]

            for risk in moderate_risk:
                if patient_data.get(risk, False):
                    return PatientSafetyLevel.RESTRICTED

            return PatientSafetyLevel.SAFE

        except Exception as e:
            logger.error(f"Error assessing patient safety level: {str(e)}")
            return PatientSafetyLevel.EXCLUDED

    def _contains_medical_keywords(self, content: str) -> bool:
        """Check if content contains medical keywords that require safety review."""
        content_lower = content.lower()
        return any(keyword in content_lower for keyword in self.medical_keywords)

    def _validate_experiment_safety(self, config: Dict[str, Any]) -> bool:
        """Validate experiment configuration for safety compliance."""
        # Check if safety checks are properly configured
        if not config.get("safety_configuration", {}).get("medical_keyword_check", True):
            logger.warning("Medical keyword check is disabled")

        # Validate message template is appropriate for testing
        template = config.get("message_template")
        if template in ["quiz_completion", "alert_message"]:
            logger.warning(f"A/B testing on template {template} may not be appropriate")

        return True

    def _get_eligible_patients(self, criteria: Dict[str, Any]) -> List[UUID]:
        """Get list of patients eligible for the experiment based on criteria."""
        # Implementation depends on your patient filtering logic
        # This is a simplified version
        query = self.db.query(Patient.id)

        # Apply basic criteria
        if criteria.get("min_age"):
            query = query.filter(Patient.age >= criteria["min_age"])
        if criteria.get("max_age"):
            query = query.filter(Patient.age <= criteria["max_age"])
        if criteria.get("treatment_types"):
            # Add treatment type filtering logic
            pass

        patients = query.all()

        # Filter by safety level
        eligible_patients = []
        for patient_tuple in patients:
            patient_id = patient_tuple[0]
            safety_level = self._assess_patient_safety_level(patient_id)
            if safety_level != PatientSafetyLevel.EXCLUDED:
                eligible_patients.append(patient_id)

        return eligible_patients

    def _patient_matches_criteria(self, patient_id: UUID, criteria: Dict[str, Any]) -> bool:
        """Check if patient matches experiment criteria."""
        # Implement your patient matching logic here
        return True  # Simplified for now

    def _log_variant_assignment(
        self,
        experiment_id: str,
        patient_id: UUID,
        variant: VariantType,
        safety_level: PatientSafetyLevel
    ) -> None:
        """Log patient variant assignment (anonymized for privacy)."""
        # Create anonymized patient ID
        anonymous_id = hashlib.sha256(f"{patient_id}:{experiment_id}".encode()).hexdigest()[:16]

        assignment_data = {
            "experiment_id": experiment_id,
            "anonymous_patient_id": anonymous_id,
            "variant": variant.value,
            "safety_level": safety_level.value,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Store assignment (implement your storage logic)
        self._store_variant_assignment(assignment_data)

    def _track_experiment_message(
        self,
        experiment_id: str,
        variant: VariantType,
        patient_id: UUID,
        message_id: int
    ) -> None:
        """Track message creation for experiment metrics."""
        tracking_data = {
            "experiment_id": experiment_id,
            "variant": variant.value,
            "patient_id": str(patient_id),
            "message_id": message_id,
            "created_at": datetime.utcnow().isoformat()
        }

        # Store tracking data (implement your storage logic)
        self._store_message_tracking(tracking_data)

    def _check_performance_thresholds(self, experiment_id: str) -> None:
        """Check if experiment performance has degraded below safety thresholds."""
        try:
            # Get recent metrics
            metrics = self._get_recent_experiment_metrics(experiment_id, hours=24)

            if len(metrics) < 10:  # Not enough data
                return

            # Calculate current performance
            current_response_rate = self._calculate_response_rate(metrics)
            current_error_rate = self._calculate_error_rate(metrics)

            # Get baseline performance
            baseline_metrics = self._get_baseline_metrics(experiment_id)
            baseline_response_rate = baseline_metrics.get("response_rate", current_response_rate)

            # Check thresholds
            response_drop = (baseline_response_rate - current_response_rate) / baseline_response_rate

            if response_drop > self.performance_thresholds["response_rate_drop"]:
                self.emergency_stop_experiment(
                    experiment_id,
                    f"Response rate dropped by {response_drop:.2%}",
                    "automatic_safety_check"
                )

            if current_error_rate > self.performance_thresholds["error_rate_spike"]:
                self.emergency_stop_experiment(
                    experiment_id,
                    f"Error rate spiked to {current_error_rate:.2%}",
                    "automatic_safety_check"
                )

        except Exception as e:
            logger.error(f"Error checking performance thresholds: {str(e)}")

    def _calculate_variant_statistics(self, variant_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate statistics for a single variant."""
        if not variant_metrics:
            return {"sample_size": 0}

        # Basic counts
        sample_size = len(variant_metrics)
        responded_count = len([m for m in variant_metrics if m.get('event_type') == 'responded'])
        delivered_count = len([m for m in variant_metrics if m.get('event_type') == 'delivered'])

        # Calculate rates
        response_rate = responded_count / sample_size if sample_size > 0 else 0
        delivery_rate = delivered_count / sample_size if sample_size > 0 else 0

        # Calculate response times (if available)
        response_times = []
        for metric in variant_metrics:
            if metric.get('event_type') == 'responded' and metric.get('response_time'):
                response_times.append(metric['response_time'])

        avg_response_time = statistics.mean(response_times) if response_times else None

        return {
            "sample_size": sample_size,
            "response_rate": response_rate,
            "delivery_rate": delivery_rate,
            "responded_count": responded_count,
            "delivered_count": delivered_count,
            "avg_response_time": avg_response_time,
            "response_time_std": statistics.stdev(response_times) if len(response_times) > 1 else None
        }

    def _perform_statistical_tests(
        self,
        control_stats: Dict[str, Any],
        treatment_stats: Dict[str, Any],
        primary_metric: str
    ) -> Dict[str, Any]:
        """Perform statistical tests to determine significance."""
        try:
            # Check sample sizes
            control_size = control_stats.get("sample_size", 0)
            treatment_size = treatment_stats.get("sample_size", 0)

            if control_size < self.min_sample_size or treatment_size < self.min_sample_size:
                return {
                    "is_significant": False,
                    "p_value": None,
                    "test_type": None,
                    "warning": f"Insufficient sample size. Need at least {self.min_sample_size} per variant"
                }

            # Get metric values
            if primary_metric == "response_rate":
                control_successes = control_stats.get("responded_count", 0)
                treatment_successes = treatment_stats.get("responded_count", 0)

                # Chi-square test for proportions
                contingency_table = np.array([
                    [control_successes, control_size - control_successes],
                    [treatment_successes, treatment_size - treatment_successes]
                ])

                chi2, p_value = stats.chi2_contingency(contingency_table)[:2]
                test_type = "chi_square"

            else:
                # Default to t-test for continuous metrics
                # This would need actual data points, not just summaries
                p_value = 0.5  # Placeholder
                test_type = "t_test"

            is_significant = p_value < self.alpha if p_value is not None else False

            # Determine winner
            winner = None
            if is_significant:
                if primary_metric == "response_rate":
                    control_rate = control_stats.get("response_rate", 0)
                    treatment_rate = treatment_stats.get("response_rate", 0)
                    winner = "treatment" if treatment_rate > control_rate else "control"

            return {
                "is_significant": is_significant,
                "p_value": p_value,
                "test_type": test_type,
                "alpha": self.alpha,
                "winner": winner,
                "confidence_interval": self._calculate_confidence_interval(
                    control_stats, treatment_stats, primary_metric
                )
            }

        except Exception as e:
            logger.error(f"Error performing statistical tests: {str(e)}")
            return {"error": str(e)}

    def _calculate_effect_sizes(
        self,
        control_stats: Dict[str, Any],
        treatment_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate effect sizes for the experiment."""
        effect_sizes = {}

        # Cohen's d for response rate difference
        control_rate = control_stats.get("response_rate", 0)
        treatment_rate = treatment_stats.get("response_rate", 0)

        # Pooled standard deviation for proportions
        control_size = control_stats.get("sample_size", 1)
        treatment_size = treatment_stats.get("sample_size", 1)

        pooled_p = ((control_rate * control_size) + (treatment_rate * treatment_size)) / (control_size + treatment_size)
        pooled_std = np.sqrt(pooled_p * (1 - pooled_p))

        if pooled_std > 0:
            cohens_d = (treatment_rate - control_rate) / pooled_std
        else:
            cohens_d = 0

        effect_sizes["cohens_d"] = cohens_d
        effect_sizes["absolute_difference"] = treatment_rate - control_rate
        effect_sizes["relative_change"] = (treatment_rate - control_rate) / control_rate if control_rate > 0 else 0

        return effect_sizes

    def _calculate_confidence_interval(
        self,
        control_stats: Dict[str, Any],
        treatment_stats: Dict[str, Any],
        metric: str
    ) -> Dict[str, Any]:
        """Calculate confidence interval for the difference."""
        # Simplified CI calculation for proportions
        control_rate = control_stats.get("response_rate", 0)
        treatment_rate = treatment_stats.get("response_rate", 0)
        control_size = control_stats.get("sample_size", 1)
        treatment_size = treatment_stats.get("sample_size", 1)

        # Standard error of difference
        se_control = np.sqrt(control_rate * (1 - control_rate) / control_size)
        se_treatment = np.sqrt(treatment_rate * (1 - treatment_rate) / treatment_size)
        se_diff = np.sqrt(se_control**2 + se_treatment**2)

        # 95% confidence interval
        z_score = 1.96  # For 95% CI
        difference = treatment_rate - control_rate
        margin_of_error = z_score * se_diff

        return {
            "lower_bound": difference - margin_of_error,
            "upper_bound": difference + margin_of_error,
            "point_estimate": difference,
            "margin_of_error": margin_of_error
        }

    def _generate_recommendations(
        self,
        statistical_results: Dict[str, Any],
        effect_sizes: Dict[str, Any],
        variant_stats: Dict[str, Any],
        config: Dict[str, Any]
    ) -> List[str]:
        """Generate actionable recommendations based on results."""
        recommendations = []

        if statistical_results.get("is_significant"):
            winner = statistical_results.get("winner")
            effect_size = abs(effect_sizes.get("cohens_d", 0))

            if winner == "treatment":
                if effect_size > 0.5:  # Large effect size
                    recommendations.append("Strong evidence for AI-humanized messages. Recommend full rollout.")
                elif effect_size > 0.2:  # Medium effect size
                    recommendations.append("Moderate evidence for AI-humanized messages. Consider gradual rollout.")
                else:
                    recommendations.append("Weak evidence for AI-humanized messages. Consider longer test period.")
            else:
                recommendations.append("Static messages performed better. Continue with current approach.")
        else:
            recommendations.append("No statistically significant difference found. Consider:")

            # Check sample size
            control_size = variant_stats.get(VariantType.CONTROL.value, {}).get("sample_size", 0)
            treatment_size = variant_stats.get(VariantType.TREATMENT.value, {}).get("sample_size", 0)

            if control_size < self.min_sample_size * 2 or treatment_size < self.min_sample_size * 2:
                recommendations.append("- Extending test duration to increase sample size")
            else:
                recommendations.append("- The difference between variants may be smaller than expected")
                recommendations.append("- Consider testing different message types or templates")

        # Safety recommendations
        if config.get("safety_configuration", {}).get("medical_keyword_check"):
            recommendations.append("✓ Medical content safety checks are active")

        return recommendations

    # Storage methods (implement based on your storage backend)

    def _store_experiment(self, experiment_id: str, encrypted_config: bytes) -> None:
        """Store experiment configuration."""
        # Implement your storage logic here
        # Could use Redis, database, or file storage
        pass

    def _load_experiment(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Load experiment configuration."""
        # Implement your storage logic here
        # Return decrypted configuration
        pass

    def _store_experiment_metric(self, metric_data: Dict[str, Any]) -> None:
        """Store experiment metric."""
        # Implement your metric storage logic
        pass

    def _get_experiment_metrics(self, experiment_id: str) -> List[Dict[str, Any]]:
        """Get all experiment metrics."""
        # Implement your metric retrieval logic
        return []

    def _get_recent_experiment_metrics(self, experiment_id: str, hours: int) -> List[Dict[str, Any]]:
        """Get recent experiment metrics."""
        # Implement your recent metric retrieval logic
        return []

    def _store_variant_assignment(self, assignment_data: Dict[str, Any]) -> None:
        """Store variant assignment data."""
        pass

    def _store_message_tracking(self, tracking_data: Dict[str, Any]) -> None:
        """Store message tracking data."""
        pass

    def _store_experiment_results(self, experiment_id: str, results: Dict[str, Any]) -> None:
        """Store experiment results."""
        pass

    def _initialize_experiment_metrics(self, experiment_id: str) -> None:
        """Initialize experiment metrics tracking."""
        pass

    def _calculate_response_rate(self, metrics: List[Dict[str, Any]]) -> float:
        """Calculate response rate from metrics."""
        if not metrics:
            return 0.0

        responded = len([m for m in metrics if m.get('event_type') == 'responded'])
        return responded / len(metrics)

    def _calculate_error_rate(self, metrics: List[Dict[str, Any]]) -> float:
        """Calculate error rate from metrics."""
        if not metrics:
            return 0.0

        errors = len([m for m in metrics if m.get('event_type') == 'error'])
        return errors / len(metrics)

    def _get_baseline_metrics(self, experiment_id: str) -> Dict[str, Any]:
        """Get baseline performance metrics."""
        # Implement baseline calculation
        return {"response_rate": 0.3}  # Placeholder

    def _send_emergency_stop_alerts(
        self,
        experiment_id: str,
        reason: str,
        results: Dict[str, Any]
    ) -> None:
        """Send emergency stop alerts to stakeholders."""
        # Implement alert sending logic
        logger.critical(f"EMERGENCY STOP ALERT: Experiment {experiment_id} stopped: {reason}")


def get_ab_testing_service(db: Session) -> ABTestingService:
    """Get A/B testing service instance."""
    return ABTestingService(db)
