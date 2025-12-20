"""
Question Humanization Service with Anti-Repetition and Medical Safety
Provides intelligent humanization for patient questions with variation control
"""

import logging
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import UUID
from app.services.ai import PatientContext, get_ai_service
from app.core.redis_unified import get_async_redis
from app.models.patient import Patient
from app.repositories.patient import PatientRepository
from app.database import SessionLocal

logger = logging.getLogger(__name__)


class QuestionHumanizer:
    """
    Intelligent question humanization with repetition control and medical safety.
    """

    # Question types that MUST remain static (never humanize)
    CRITICAL_QUESTION_TYPES = [
        "medication_verification",
        "dosage_confirmation",
        "dosage_verification",  # Alternative naming
        "allergy_check",
        "allergy_confirmation",  # Alternative naming
        "emergency_symptoms",
        "emergency_assessment",  # Alternative naming
        "emergency_protocol",  # Alternative naming
        "consent_collection",
        "legal_confirmation",
        "surgery_preparation",
        "exam_preparation",
        "medication_check",  # Alternative naming
        "vital_signs",
        "side_effects_severe",
    ]

    # Question types safe for humanization
    SAFE_QUESTION_TYPES = [
        "daily_checkin",
        "mood_assessment",
        "symptom_tracking",
        "comfort_level",
        "sleep_quality",
        "appetite_check",
        "activity_level",
        "social_support",
        "general_wellbeing",
        "feedback_request",
    ]

    # Intent patterns for variety
    INTENT_PATTERNS = {
        "daily_checkin": [
            "greeting_morning",
            "greeting_afternoon",
            "greeting_evening",
            "casual_checkin",
            "warm_inquiry",
        ],
        "symptom_tracking": [
            "direct_inquiry",
            "gentle_approach",
            "detailed_assessment",
            "quick_check",
            "comprehensive_review",
        ],
        "mood_assessment": [
            "emotional_check",
            "feeling_inquiry",
            "mood_scale",
            "emotional_support",
            "wellbeing_check",
        ],
    }

    def __init__(self):
        self.ai_service = get_ai_service()
        self._redis_client = None  # Will be initialized async
        self.history_window_hours = 72  # Track last 3 days
        self._patient_cache: Dict[str, tuple[Optional[Patient], datetime]] = {}
        self._cache_ttl_seconds = 300  # 5 minutes cache

    async def _get_redis_client(self):
        """Get Redis client, initialize if needed."""
        if self._redis_client is None:
            self._redis_client = await get_async_redis()
        return self._redis_client

    async def humanize_question(
        self,
        question: str,
        question_type: str,
        patient: Patient,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Humanize a question with anti-repetition and safety controls.

        Args:
            question: Original question text
            question_type: Type of question for safety classification
            patient: Patient object
            context: Additional context

        Returns:
            Humanized question or original if not safe/appropriate
        """
        # 1. Safety check - never humanize critical questions
        if question_type in self.CRITICAL_QUESTION_TYPES:
            logger.info(f"Critical question type '{question_type}' - keeping original")
            await self._log_telemetry(patient.id, question, question, "critical_bypass")
            return question

        # 2. Check if question type is safe for humanization
        if question_type not in self.SAFE_QUESTION_TYPES:
            logger.info(
                f"Unknown question type '{question_type}' - keeping original for safety"
            )
            await self._log_telemetry(patient.id, question, question, "unknown_type")
            return question

        # 3. Get recent question history to avoid repetition
        recent_questions = await self._get_recent_questions(patient.id)

        # 4. Select intent pattern for variety
        intent = self._select_intent_pattern(question_type, recent_questions)

        # 5. Build enriched context
        humanization_context = self._build_humanization_context(
            patient=patient,
            question_type=question_type,
            intent=intent,
            recent_questions=recent_questions,
            additional_context=context,
        )

        try:
            # 6. Generate humanized version with anti-repetition prompt
            # Build PatientContext for AIHumanizer
            patient_context = PatientContext(
                patient_id=str(patient.id),
                name=patient.name,
                treatment_type=getattr(patient, "treatment_type", "general"),
                treatment_day=getattr(patient, "current_day", 1),
                age=getattr(patient, "age", None),
                recent_responses=recent_questions[:5] if recent_questions else [],
                preferences=humanization_context.get("preferences", {}),
            )

            # Use correct signature for humanize_message
            response = await self.ai_service.humanize_message(
                template_message=question,
                patient_context=patient_context,
                message_type=question_type
                if question_type in self.SAFE_QUESTION_TYPES
                else "general",
            )

            # Extract humanized message from response
            humanized = (
                response.humanized_message
                if hasattr(response, "humanized_message")
                else question
            )

            # 7. Validate humanized output
            if self._is_too_similar(humanized, recent_questions):
                logger.info(
                    "Humanized question too similar to recent ones - using fallback variation"
                )
                humanized = self._generate_fallback_variation(question, intent)

            # 8. Store in history and telemetry with intent pattern
            await self._store_question_history(
                patient.id, humanized, question_type, intent
            )
            await self._log_telemetry(
                patient.id, question, humanized, "success", {"intent_pattern": intent}
            )

            return humanized

        except Exception as e:
            logger.error(f"Humanization failed: {e}")
            await self._log_telemetry(
                patient.id, question, question, f"error: {str(e)}"
            )
            return question  # Safe fallback

    async def humanize_quiz_question(
        self,
        question: str,
        question_id: str,
        patient_id: str,
        quiz_type: str = "monthly",
    ) -> str:
        """
        Specialized humanization for quiz questions.

        Args:
            question: Original quiz question
            question_id: Unique question identifier
            patient_id: Patient identifier
            quiz_type: Type of quiz

        Returns:
            Humanized quiz question
        """
        # Quiz questions often need consistency for scoring
        # Only humanize introduction/context, not the actual question

        if self._is_scored_question(question_id):
            # Keep scored questions consistent
            logger.info(
                f"Scored question {question_id} - keeping original for consistency"
            )
            return question

        # For non-scored questions (like open feedback), apply humanization
        try:
            patient = self._get_patient(patient_id)
            if not patient:
                return question

            return await self.humanize_question(
                question=question,
                question_type="feedback_request",
                patient=patient,
                context={"quiz_type": quiz_type, "question_id": question_id},
            )

        except Exception as e:
            logger.error(f"Quiz question humanization failed: {e}")
            return question

    async def _get_recent_questions(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get recently sent questions from Redis cache with intent patterns."""
        try:
            redis_client = await self._get_redis_client()
            key = f"patient:questions:{patient_id}"
            data = await redis_client.get(key)

            if data:
                history = json.loads(data)
                # Filter by time window
                cutoff = (
                    datetime.now(timezone.utc) - timedelta(hours=self.history_window_hours)
                ).isoformat()
                recent = [q for q in history if q.get("timestamp", "") > cutoff]
                return recent[-10:]  # Return last 10 questions with metadata

            return []

        except Exception as e:
            logger.error(f"Failed to get question history: {e}")
            return []

    async def _store_question_history(
        self,
        patient_id: str,
        question: str,
        question_type: str,
        intent_pattern: Optional[str] = None,
    ):
        """Store question in history for anti-repetition."""
        try:
            redis_client = await self._get_redis_client()
            key = f"patient:questions:{patient_id}"

            # Get existing history
            data = await redis_client.get(key)
            history = json.loads(data) if data else []

            # Add new question with intent pattern name
            history.append(
                {
                    "text": question,
                    "type": question_type,
                    "intent": intent_pattern or "default",  # Store intent pattern NAME
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "hash": hashlib.md5(question.encode()).hexdigest(),
                }
            )

            # Keep only recent history (last 20 questions)
            history = history[-20:]

            # Store with TTL of 7 days
            await redis_client.setex(
                key,
                604800,  # 7 days in seconds
                json.dumps(history),
            )

        except Exception as e:
            logger.error(f"Failed to store question history: {e}")

    def _select_intent_pattern(
        self, question_type: str, recent_questions: List[Dict[str, Any]]
    ) -> str:
        """Select an intent pattern that hasn't been used recently using FIFO rotation."""
        patterns = self.INTENT_PATTERNS.get(question_type, ["default"])

        if len(patterns) == 1:
            return patterns[0]

        # Extract recent intent names from history (filter by question_type)
        recent_intents = [
            q.get("intent", "default")
            for q in recent_questions
            if q.get("type") == question_type
        ]

        # Take last N intents (N = number of available patterns)
        recent_intents = recent_intents[-len(patterns) :]

        logger.info(
            f"Intent selection for '{question_type}': available={patterns}, recent={recent_intents}"
        )

        # Find first pattern NOT in recent intents (least recently used)
        for pattern in patterns:
            if pattern not in recent_intents:
                logger.info(f"Selected unused pattern: {pattern}")
                return pattern

        # All patterns used recently - use FIFO (rotate to next after last used)
        if recent_intents:
            last_used = recent_intents[-1]
            try:
                last_index = patterns.index(last_used)
                next_pattern = patterns[(last_index + 1) % len(patterns)]
                logger.info(
                    f"All patterns used, rotating from {last_used} to {next_pattern}"
                )
                return next_pattern
            except ValueError as e:
                logger.debug(f"Last used pattern not found in available patterns: {e}")

        # Fallback to first pattern
        logger.info(f"Fallback to first pattern: {patterns[0]}")
        return patterns[0]

    def _build_humanization_context(
        self,
        patient: Patient,
        question_type: str,
        intent: str,
        recent_questions: List[str],
        additional_context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Build comprehensive context for humanization."""
        context = {
            "patient_name": patient.name,
            "treatment_day": getattr(patient, "current_day", 1),
            "treatment_type": getattr(patient, "treatment_type", "general"),
            "question_type": question_type,
            "intent_pattern": intent,
            "time_of_day": self._get_time_of_day(),
            "recent_question_count": len(recent_questions),
            "last_interaction": getattr(patient, "last_interaction_at", None),
        }

        if additional_context:
            context.update(additional_context)

        return context

    def _generate_variety_prompt(self, recent_questions: List[Dict[str, Any]]) -> str:
        """Generate prompt instructions for variety."""
        if not recent_questions:
            return "Generate a warm, natural question."

        prompt = "Generate a natural question that is different in style and wording from these recent questions:\n"
        for i, q in enumerate(recent_questions[-3:], 1):  # Show last 3
            text = q.get("text", "") if isinstance(q, dict) else str(q)
            prompt += f"{i}. {text[:50]}...\n"
        prompt += "\nUse different greeting, structure, and tone while maintaining the core inquiry."

        return prompt

    def _get_tone_for_intent(self, intent: str) -> str:
        """Map intent pattern to appropriate tone."""
        tone_mapping = {
            "greeting_morning": "cheerful",
            "greeting_afternoon": "friendly",
            "greeting_evening": "calm",
            "casual_checkin": "conversational",
            "warm_inquiry": "caring",
            "direct_inquiry": "professional",
            "gentle_approach": "soft",
            "detailed_assessment": "thorough",
            "emotional_check": "empathetic",
            "feeling_inquiry": "understanding",
        }
        return tone_mapping.get(intent, "supportive")

    def _is_too_similar(
        self, new_question: str, recent_questions: List[Dict[str, Any]]
    ) -> bool:
        """Check if new question is too similar to recent ones."""
        if not recent_questions:
            return False

        # Simple similarity check based on word overlap
        new_words = set(new_question.lower().split())

        for recent in recent_questions:
            recent_text = (
                recent.get("text", "") if isinstance(recent, dict) else str(recent)
            )
            recent_words = set(recent_text.lower().split())
            overlap = len(new_words & recent_words) / max(
                len(new_words), len(recent_words)
            )

            if overlap > 0.8:  # 80% similarity threshold
                return True

        return False

    def _generate_fallback_variation(self, original: str, intent: str) -> str:
        """Generate simple variation when AI fails."""
        variations = {
            "greeting_morning": f"Bom dia! {original}",
            "greeting_afternoon": f"Boa tarde! {original}",
            "greeting_evening": f"Boa noite! {original}",
            "casual_checkin": f"Oi! {original}",
            "warm_inquiry": f"Olá, querido(a)! {original}",
        }
        return variations.get(intent, original)

    def _get_time_of_day(self) -> str:
        """Get current time of day for context."""
        hour = datetime.now().hour
        if hour < 12:
            return "morning"
        elif hour < 18:
            return "afternoon"
        else:
            return "evening"

    def _is_scored_question(self, question_id: str) -> bool:
        """Check if question is scored (needs consistency)."""
        # Questions with scores need exact wording for validity
        scored_patterns = ["scale_", "score_", "rating_", "level_"]
        return any(pattern in question_id.lower() for pattern in scored_patterns)

    def _get_patient(self, patient_id: str) -> Optional[Patient]:
        """
        Get patient object from database with lightweight caching.

        Args:
            patient_id: Patient UUID as string

        Returns:
            Patient object or None if not found
        """
        try:
            # Convert string to UUID
            try:
                patient_uuid = UUID(patient_id)
            except (ValueError, AttributeError) as e:
                logger.warning(f"Invalid patient_id format: {patient_id} - {e}")
                return None

            # Check cache first
            cache_key = str(patient_uuid)
            if cache_key in self._patient_cache:
                cached_patient, cached_at = self._patient_cache[cache_key]
                cache_age = (datetime.now(timezone.utc) - cached_at).total_seconds()

                if cache_age < self._cache_ttl_seconds:
                    logger.debug(
                        f"Patient {patient_id} retrieved from cache (age: {cache_age:.1f}s)"
                    )
                    return cached_patient
                else:
                    # Cache expired, remove it
                    del self._patient_cache[cache_key]

            # Fetch from database
            db: Any = SessionLocal()
            try:
                patient_repo = PatientRepository(db)
                patient = patient_repo.get(patient_uuid)

                if patient:
                    logger.info(
                        f"Patient {patient_id} fetched from database successfully"
                    )
                    # Cache the result
                    self._patient_cache[cache_key] = (patient, datetime.now(timezone.utc))
                    return patient
                else:
                    logger.warning(f"Patient {patient_id} not found in database")
                    # Cache the negative result to avoid repeated queries
                    self._patient_cache[cache_key] = (None, datetime.now(timezone.utc))
                    return None

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Error fetching patient {patient_id}: {e}", exc_info=True)
            return None

    def _clear_patient_cache(self, patient_id: Optional[str] = None):
        """
        Clear patient cache.

        Args:
            patient_id: Specific patient to clear, or None to clear all
        """
        if patient_id:
            cache_key = str(patient_id)
            if cache_key in self._patient_cache:
                del self._patient_cache[cache_key]
                logger.debug(f"Cleared cache for patient {patient_id}")
        else:
            self._patient_cache.clear()
            logger.debug("Cleared all patient cache")

    async def _log_telemetry(
        self,
        patient_id: str,
        original: str,
        result: str,
        status: str,
        metadata: Optional[Dict] = None,
    ):
        """Log telemetry for monitoring and improvement."""
        try:
            redis_client = await self._get_redis_client()
            telemetry = {
                "patient_id": patient_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "original_length": len(original),
                "result_length": len(result),
                "changed": original != result,
                "status": status,
            }

            # Add metadata (intent_pattern, etc.)
            if metadata:
                telemetry.update(metadata)

            # Store in Redis for monitoring
            key = f"telemetry:humanization:{datetime.now(timezone.utc).strftime('%Y%m%d')}"
            await redis_client.rpush(key, json.dumps(telemetry))

            # Expire after 30 days
            await redis_client.expire(key, 2592000)

        except Exception as e:
            logger.error(f"Failed to log telemetry: {e}")


# Singleton instance
_question_humanizer: Optional[QuestionHumanizer] = None


def get_question_humanizer() -> QuestionHumanizer:
    """Get or create question humanizer instance."""
    global _question_humanizer
    if _question_humanizer is None:
        _question_humanizer = QuestionHumanizer()
    return _question_humanizer
