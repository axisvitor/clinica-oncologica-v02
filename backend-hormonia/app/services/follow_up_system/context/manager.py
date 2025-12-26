"""
Conversation context manager for follow-up system.
Handles storage, retrieval, and updates of patient conversation context.

FIX: Added async locks to prevent concurrent update race conditions (P1-004)
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime, timezone
from uuid import UUID
from weakref import WeakValueDictionary

from ..models import ConversationContext
from app.services.response_processor import StructuredResponse

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages conversation context for patient continuity."""

    # Class-level lock registry to prevent concurrent updates per patient
    # Using WeakValueDictionary to auto-cleanup unused locks
    _patient_locks: WeakValueDictionary = WeakValueDictionary()
    _locks_lock: asyncio.Lock = asyncio.Lock()

    def __init__(self, redis_store, in_memory_contexts: dict):
        """
        Initialize context manager.

        Args:
            redis_store: Redis storage instance for persistence
            in_memory_contexts: Fallback in-memory storage
        """
        self.redis_store = redis_store
        self.in_memory_contexts = in_memory_contexts

    async def _get_patient_lock(self, patient_id: UUID) -> asyncio.Lock:
        """
        Get or create a lock for a specific patient.

        FIX P1-004: Prevents concurrent updates from overwriting each other.
        """
        async with self._locks_lock:
            lock_key = str(patient_id)
            if lock_key not in self._patient_locks:
                self._patient_locks[lock_key] = asyncio.Lock()
            return self._patient_locks[lock_key]

    async def update_context(
        self, patient_id: UUID, structured_response: StructuredResponse
    ) -> None:
        """
        Update conversation context for continuity.

        FIX P1-004: Uses per-patient lock to prevent concurrent update race conditions.
        Before: Two concurrent updates could both read v1, modify independently,
        and second write would overwrite first's changes (data loss).
        After: Updates are serialized per-patient, preserving all changes.

        Args:
            patient_id: Patient UUID
            structured_response: Processed response data
        """
        # FIX P1-004: Acquire patient-specific lock to serialize updates
        patient_lock = await self._get_patient_lock(patient_id)

        async with patient_lock:
            try:
                # Get existing context or create new one
                context = await self.get_context(patient_id)
                if not context:
                    context = self._create_new_context(patient_id)

                # Add to conversation history
                context.conversation_history.append(
                    {
                        "timestamp": structured_response.timestamp.isoformat(),
                        "message": structured_response.original_message,
                        "response_type": structured_response.response_type.value,
                        "sentiment": structured_response.sentiment_analysis.get(
                            "sentiment"
                        ),
                        "concern_level": structured_response.concern_level.value,
                        "medical_concerns": structured_response.medical_concerns,
                    }
                )

                # Keep only last 20 messages
                context.conversation_history = context.conversation_history[-20:]

                # Update emotional state
                context.emotional_state = structured_response.sentiment_analysis.get(
                    "sentiment"
                )

                # Update current topic based on response category
                context.current_topic = structured_response.response_category.value

                # Update medical context
                if structured_response.medical_concerns:
                    context.medical_context["recent_concerns"] = (
                        structured_response.medical_concerns
                    )
                    context.medical_context["last_concern_time"] = (
                        structured_response.timestamp.isoformat()
                    )

                # Update preferences from extracted data
                if structured_response.patient_preferences:
                    for pref in structured_response.patient_preferences:
                        context.preferences[pref.preference_type] = {
                            "value": pref.value,
                            "confidence": pref.confidence,
                            "updated_at": pref.extracted_at.isoformat(),
                        }

                context.last_updated = datetime.now(timezone.utc)

                # Store in Redis (with fallback to in-memory)
                await self._store_context(context)

            except Exception as e:
                logger.error(f"Failed to update conversation context: {e}")

    async def get_context(self, patient_id: UUID) -> Optional[ConversationContext]:
        """
        Get conversation context for a patient.

        Args:
            patient_id: Patient UUID

        Returns:
            ConversationContext or None if not found
        """
        try:
            # Try Redis first
            context_data = await self.redis_store.get_context(patient_id)

            if context_data:
                return ConversationContext(
                    patient_id=patient_id,
                    conversation_history=context_data.get("conversation_history", []),
                    current_topic=context_data.get("current_topic"),
                    emotional_state=context_data.get("emotional_state"),
                    medical_context=context_data.get("medical_context", {}),
                    preferences=context_data.get("preferences", {}),
                )

            # Fallback to in-memory
            if patient_id in self.in_memory_contexts:
                return self.in_memory_contexts[patient_id]

            return None

        except Exception as e:
            logger.error(f"Failed to get conversation context: {e}")
            return None

    def _create_new_context(self, patient_id: UUID) -> ConversationContext:
        """Create new conversation context."""
        return ConversationContext(
            patient_id=patient_id,
            conversation_history=[],
            current_topic=None,
            emotional_state=None,
            medical_context={},
            preferences={},
        )

    async def _store_context(self, context: ConversationContext) -> None:
        """Store context in Redis with fallback to in-memory."""
        stored = await self.redis_store.store_context(context)
        if not stored:
            # Fallback to in-memory
            self.in_memory_contexts[context.patient_id] = context
            logger.debug(f"Stored context in memory for patient {context.patient_id}")
        else:
            logger.debug(f"Stored context in Redis for patient {context.patient_id}")

    async def update_context_with_message(
        self,
        patient_id: UUID,
        message_id: UUID,
        content: str,
        direction: str,
        flow_day: Optional[int] = None,
        intent: Optional[str] = None,
    ) -> None:
        """
        Update conversation context with a sent/received message.

        This method is called by the Flow Service to register messages
        in the follow-up system's conversation tracking.

        FIX P1-004: Uses per-patient lock to prevent concurrent update race conditions.

        Args:
            patient_id: Patient UUID
            message_id: Message UUID
            content: Message content
            direction: 'outbound' or 'inbound'
            flow_day: Current day in flow (optional)
            intent: Message intent/template type (optional)
        """
        # FIX P1-004: Acquire patient-specific lock to serialize updates
        patient_lock = await self._get_patient_lock(patient_id)

        async with patient_lock:
            try:
                # Get existing context or create new one
                context = await self.get_context(patient_id)
                if not context:
                    context = self._create_new_context(patient_id)

                # Add to conversation history
                history_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "message_id": str(message_id),
                    "content": content[:500],  # Limit to 500 chars
                    "direction": direction,
                }

                if flow_day is not None:
                    history_entry["flow_day"] = flow_day
                if intent:
                    history_entry["intent"] = intent

                context.conversation_history.append(history_entry)

                # Keep only last 20 messages
                context.conversation_history = context.conversation_history[-20:]

                # Update current topic if intent provided
                if intent:
                    context.current_topic = intent

                context.last_updated = datetime.now(timezone.utc)

                # Store in Redis (with fallback to in-memory)
                await self._store_context(context)

                logger.debug(
                    f"Updated context with {direction} message {message_id} for patient {patient_id}"
                )

            except Exception as e:
                logger.error(
                    f"Failed to update context with message {message_id}: {e}",
                    exc_info=True,
                )
