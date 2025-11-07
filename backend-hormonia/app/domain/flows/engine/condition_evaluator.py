"""
Condition evaluator for flow execution.
Handles AI-powered message humanization and content evaluation.
"""
from typing import Optional
from datetime import datetime
import asyncio
import logging
from uuid import UUID
from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.services.template_loader import FlowStep
from app.config import is_ai_humanization_enabled, should_humanize_message, get_humanization_config

logger = logging.getLogger(__name__)


class ConditionEvaluator:
    """Evaluates conditions and humanizes message content using AI."""

    def __init__(self, db: Session):
        self.db = db
        self.patient_repo = PatientRepository(db)

        # AI services (lazy initialization)
        self.ai_service = None
        self.ai_context_builder = None
        self.humanization_config = get_humanization_config()

        # Redis client for caching (optional)
        self.redis_client = None
        try:
            from app.config import settings
            import redis.asyncio as redis
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                max_connections=10
            )
            logger.info("ConditionEvaluator initialized with Redis cache support")
        except Exception as e:
            logger.warning(f"ConditionEvaluator initialized without Redis cache: {e}")

    async def _ensure_ai_services(self):
        """Ensure AI services are initialized (lazy loading)."""
        if self.ai_service is None:
            from app.services.ai.ai_service import get_ai_service
            self.ai_service = await get_ai_service()
        if self.ai_context_builder is None:
            from app.services.ai.ai_service import get_ai_service
            self.ai_context_builder = await get_ai_service()

    async def humanize_message_content(
        self,
        content: str,
        patient_id: UUID,
        message_type: str = "general",
        context_builder = None
    ) -> str:
        """
        Humanize message content using AI with safety controls and fallback.

        Args:
            content: Original message content
            patient_id: Patient UUID
            message_type: Type of message (welcome, check_in, reminder, etc.)
            context_builder: Optional context builder for getting recent messages

        Returns:
            Humanized message content or original content if AI fails/disabled
        """
        # Check if AI humanization is enabled
        if not is_ai_humanization_enabled():
            logger.debug("AI humanization disabled, using original content")
            return content

        # Safety check: Don't humanize critical medical content
        if not should_humanize_message(content):
            logger.info(f"Message contains critical keywords, skipping AI humanization: {content[:100]}...")
            return content

        try:
            # Ensure AI services are initialized
            await self._ensure_ai_services()

            # Get patient for context
            patient = self.patient_repo.get(patient_id)
            if not patient:
                logger.warning(f"Patient {patient_id} not found for humanization")
                return content

            # Check patient-level opt-out flags
            metadata = patient.patient_data or patient.patient_metadata or {}
            if metadata.get('no_ai_messages', False):
                logger.info(f"Patient {patient_id} has AI restriction (no_ai_messages) - skipping humanization")
                return content
            if metadata.get('critical_condition', False):
                logger.info(f"Patient {patient_id} in critical condition - skipping AI humanization")
                return content

            # Check cache first (deterministic caching)
            import hashlib
            cache_key = None
            cached_humanized = None

            try:
                # Generate cache key based on patient, content, type, and day
                content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()[:12]
                treatment_day = getattr(patient, 'current_day', 1)
                cache_key = f"ai:humanized:{patient_id}:{content_hash}:{message_type}:{treatment_day}"

                # Try to get from cache (Redis)
                if hasattr(self, 'redis_client') and self.redis_client:
                    cached_humanized = await self.redis_client.get(cache_key)
                    if cached_humanized:
                        logger.info(f"Cache HIT for humanization: {cache_key}")
                        return cached_humanized
                    else:
                        logger.debug(f"Cache MISS for humanization: {cache_key}")
            except Exception as e:
                logger.warning(f"Cache read error for humanization: {e}")

            # Get recent messages for context
            recent_messages = []
            if context_builder:
                recent_messages = context_builder._get_recent_messages(patient_id)

            # Build patient context for AI
            patient_context = await self.ai_context_builder.build_patient_context(
                patient_id=str(patient_id),
                patient_data={
                    "name": patient.name,
                    "treatment_type": getattr(patient, 'treatment_type', 'hormone_therapy'),
                    "current_day": getattr(patient, 'current_day', 1),
                    "treatment_start_date": patient.treatment_start_date.isoformat() if hasattr(patient, 'treatment_start_date') and patient.treatment_start_date else None
                },
                recent_messages=recent_messages
            )

            # Attempt AI humanization with retries
            max_retries = self.humanization_config["max_retries"]
            timeout = self.humanization_config["timeout"]

            for attempt in range(max_retries + 1):
                try:
                    # Call AI humanizer with timeout
                    humanization_task = self.ai_service.humanize_message(
                        template_message=content,
                        patient_context=patient_context,
                        message_type=message_type
                    )

                    # Apply timeout to the AI call
                    humanized_response = await asyncio.wait_for(
                        humanization_task,
                        timeout=timeout
                    )

                    # Extract humanized content
                    humanized_content = humanized_response.humanized_message

                    # POST-GENERATION SAFETY CHECK: Verify no critical keywords were introduced
                    if not should_humanize_message(humanized_content):
                        logger.warning(f"AI output contains critical keywords - using original content for patient {patient_id}")
                        return content

                    # Log successful humanization
                    logger.info(f"Message successfully humanized for patient {patient_id} (attempt {attempt + 1})")

                    # Store humanization metadata
                    humanization_metadata = {
                        "ai_humanized": True,
                        "original_length": len(content),
                        "humanized_length": len(humanized_content),
                        "attempt_count": attempt + 1,
                        "personalization_notes": getattr(humanized_response, 'personalization_notes', [])
                    }

                    # Cache the humanized content (24 hours TTL)
                    if cache_key and hasattr(self, 'redis_client') and self.redis_client:
                        try:
                            await self.redis_client.setex(cache_key, 86400, humanized_content)  # 24h TTL
                            logger.debug(f"Cached humanized content: {cache_key}")
                        except Exception as e:
                            logger.warning(f"Cache write error for humanization: {e}")

                    return humanized_content

                except asyncio.TimeoutError:
                    logger.warning(f"AI humanization timeout on attempt {attempt + 1} for patient {patient_id}")
                    if attempt == max_retries:
                        break
                    await asyncio.sleep(0.5 * (attempt + 1))  # Progressive delay

                except Exception as e:
                    logger.warning(f"AI humanization failed on attempt {attempt + 1} for patient {patient_id}: {e}")
                    if attempt == max_retries:
                        break
                    await asyncio.sleep(0.5 * (attempt + 1))  # Progressive delay

            # All retry attempts failed
            logger.error(f"AI humanization failed after {max_retries + 1} attempts for patient {patient_id}")

        except Exception as e:
            logger.error(f"Critical error in AI humanization for patient {patient_id}: {e}")

        # Fallback to original content
        if self.humanization_config["fallback_enabled"]:
            logger.info(f"Using fallback to original content for patient {patient_id}")
            return content
        else:
            logger.warning(f"Fallback disabled, returning empty content for patient {patient_id}")
            return "Mensagem temporariamente indisponível. Entre em contato se precisar de assistência."

    def determine_question_type(self, step: FlowStep) -> str:
        """
        Determine the type of question for selective humanization.

        Args:
            step: Flow step containing question/message

        Returns:
            Question type identifier for humanization control
        """
        # Check step metadata for question type
        if hasattr(step, 'metadata') and step.metadata:
            if 'question_type' in step.metadata:
                return step.metadata['question_type']

            # Check for critical keywords in metadata
            if any(key in str(step.metadata).lower() for key in ['medication', 'dosage', 'emergency', 'consent']):
                return 'medication_verification'

        # Analyze step content for patterns
        content_lower = step.content.lower() if step.content else ""

        # Critical patterns (never humanize)
        if any(word in content_lower for word in ['medicação', 'medicamento', 'dose', 'mg', 'ml', 'emergência']):
            return 'medication_verification'

        if any(word in content_lower for word in ['cirurgia', 'procedimento', 'exame', 'jejum']):
            return 'surgery_preparation'

        if any(word in content_lower for word in ['consentimento', 'autorizo', 'concordo']):
            return 'consent_collection'

        # Safe patterns (can humanize)
        if any(word in content_lower for word in ['como você está', 'como se sente', 'sentindo']):
            return 'daily_checkin'

        if any(word in content_lower for word in ['humor', 'ânimo', 'emocional', 'ansiedade']):
            return 'mood_assessment'

        if any(word in content_lower for word in ['sintoma', 'dor', 'desconforto', 'náusea']):
            return 'symptom_tracking'

        if any(word in content_lower for word in ['sono', 'dormiu', 'descanso']):
            return 'sleep_quality'

        if any(word in content_lower for word in ['apetite', 'alimentação', 'comendo']):
            return 'appetite_check'

        # Check step type
        if step.type == 'quiz':
            # Quiz questions default to feedback unless marked critical
            return 'feedback_request'

        # Default to general wellbeing (safe to humanize)
        return 'general_wellbeing'
