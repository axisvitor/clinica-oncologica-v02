"""
Conversation memory system using Redis for pattern tracking and anti-repetition.
Stores and analyzes conversation patterns to avoid repetitive messaging.
"""

import json
import logging
import re
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from uuid import UUID
from app.utils.timezone import now_sao_paulo


logger = logging.getLogger(__name__)


class ConversationPattern:
    """Represents a conversation pattern extracted from messages."""

    def __init__(
        self,
        greeting_words: List[str] = None,
        question_structures: List[str] = None,
        emotional_words: List[str] = None,
        sentence_starters: List[str] = None,
        message_length: int = 0,
        emoji_count: int = 0,
        timestamp: datetime = None,
        engagement_score: float = 0.0,
    ):
        self.greeting_words = greeting_words or []
        self.question_structures = question_structures or []
        self.emotional_words = emotional_words or []
        self.sentence_starters = sentence_starters or []
        self.message_length = message_length
        self.emoji_count = emoji_count
        self.timestamp = timestamp or now_sao_paulo()
        self.engagement_score = engagement_score

    def to_dict(self) -> Dict[str, Any]:
        """Convert pattern to dictionary for storage."""
        return {
            "greeting_words": self.greeting_words,
            "question_structures": self.question_structures,
            "emotional_words": self.emotional_words,
            "sentence_starters": self.sentence_starters,
            "message_length": self.message_length,
            "emoji_count": self.emoji_count,
            "timestamp": self.timestamp.isoformat(),
            "engagement_score": self.engagement_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationPattern":
        """Create pattern from dictionary."""
        return cls(
            greeting_words=data.get("greeting_words", []),
            question_structures=data.get("question_structures", []),
            emotional_words=data.get("emotional_words", []),
            sentence_starters=data.get("sentence_starters", []),
            message_length=data.get("message_length", 0),
            emoji_count=data.get("emoji_count", 0),
            timestamp=datetime.fromisoformat(
                data.get("timestamp", now_sao_paulo().isoformat())
            ),
            engagement_score=data.get("engagement_score", 0.0),
        )


class PatternExtractor:
    """Extract basic conversation patterns for repetition detection."""

    def __init__(self):
        self.greeting_phrases = [
            "oi",
            "olá",
            "ola",
            "bom dia",
            "boa tarde",
            "boa noite",
            "eai",
            "e ai",
            "hey",
        ]
        self.question_words = {
            "como",
            "qual",
            "quando",
            "onde",
            "porque",
            "por",
            "que",
            "o",
            "quem",
            "quanto",
        }
        self.positive_words = {
            "bem",
            "otimo",
            "ótimo",
            "melhor",
            "tranquilo",
            "feliz",
            "obrigado",
            "obrigada",
        }
        self.negative_words = {
            "mal",
            "pior",
            "dor",
            "cansado",
            "cansada",
            "triste",
            "ansioso",
            "ansiosa",
            "preocupado",
            "preocupada",
        }
        self.emoji_re = re.compile(r"[\U0001F300-\U0001FAFF]")
        self.word_re = re.compile(r"[\w']+", re.UNICODE)

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", text or "").strip().lower()

    def extract_patterns(self, message: str) -> ConversationPattern:
        normalized = self._normalize(message)
        words = self.word_re.findall(normalized)

        greeting_words = []
        for phrase in self.greeting_phrases:
            if normalized.startswith(phrase):
                greeting_words.append(phrase)

        question_structures = []
        if "?" in (message or ""):
            question_structures.append("question_mark")
        for word in words:
            if word in self.question_words:
                question_structures.append(word)

        emotional_words = []
        for word in words:
            if word in self.positive_words:
                emotional_words.append(f"positive:{word}")
            elif word in self.negative_words:
                emotional_words.append(f"negative:{word}")

        sentence_starters = []
        for segment in re.split(r"[.!?\n]+", normalized):
            segment = segment.strip()
            if not segment:
                continue
            starter_words = self.word_re.findall(segment)[:2]
            if starter_words:
                sentence_starters.append(" ".join(starter_words))

        emoji_count = len(self.emoji_re.findall(message or ""))

        return ConversationPattern(
            greeting_words=greeting_words,
            question_structures=list(dict.fromkeys(question_structures)),
            emotional_words=list(dict.fromkeys(emotional_words)),
            sentence_starters=list(dict.fromkeys(sentence_starters)),
            message_length=len(message or ""),
            emoji_count=emoji_count,
        )

    def calculate_similarity(
        self, pattern_a: ConversationPattern, pattern_b: ConversationPattern
    ) -> float:
        def _jaccard(items_a: List[str], items_b: List[str]) -> float:
            set_a = set(items_a or [])
            set_b = set(items_b or [])
            if not set_a and not set_b:
                return 0.0
            return len(set_a & set_b) / len(set_a | set_b)

        greeting_sim = _jaccard(pattern_a.greeting_words, pattern_b.greeting_words)
        question_sim = _jaccard(
            pattern_a.question_structures, pattern_b.question_structures
        )
        emotion_sim = _jaccard(pattern_a.emotional_words, pattern_b.emotional_words)
        starter_sim = _jaccard(
            pattern_a.sentence_starters, pattern_b.sentence_starters
        )

        length_a = pattern_a.message_length or 0
        length_b = pattern_b.message_length or 0
        length_sim = 1.0
        if max(length_a, length_b) > 0:
            length_sim = 1.0 - (abs(length_a - length_b) / max(length_a, length_b))

        emoji_a = pattern_a.emoji_count or 0
        emoji_b = pattern_b.emoji_count or 0
        emoji_sim = 1.0
        if max(emoji_a, emoji_b) > 0:
            emoji_sim = 1.0 - (abs(emoji_a - emoji_b) / max(emoji_a, emoji_b))

        return (
            greeting_sim * 0.2
            + question_sim * 0.2
            + emotion_sim * 0.2
            + starter_sim * 0.2
            + length_sim * 0.1
            + emoji_sim * 0.1
        )


class ConversationMemory:
    def __init__(
        self,
        redis_client: Optional[Any] = None,
        pattern_extractor: Optional[PatternExtractor] = None,
        max_patterns_per_patient: int = 50,
        pattern_expiry_days: int = 30,
    ):
        from app.core.redis_manager import get_sync_redis_client as get_sync_redis

        self.redis = redis_client or get_sync_redis()
        self.pattern_extractor = pattern_extractor or PatternExtractor()
        self.max_patterns_per_patient = max_patterns_per_patient
        self.pattern_expiry_days = pattern_expiry_days

    async def store_message_pattern(self, patient_id: UUID, message: str) -> None:
        """
        Store message pattern for a patient.

        Args:
            patient_id: Patient UUID
            message: Message text to analyze and store
        """
        try:
            # Extract pattern from message
            pattern = self.pattern_extractor.extract_patterns(message)

            # Store pattern in Redis list
            key = f"msg_patterns:{patient_id}"
            pattern_data = json.dumps(pattern.to_dict())

            # Add to list (most recent first)
            self.redis.lpush(key, pattern_data)

            # Trim to keep only recent patterns
            self.redis.ltrim(key, 0, self.max_patterns_per_patient - 1)

            # Set expiration
            self.redis.expire(key, self.pattern_expiry_days * 24 * 3600)

            logger.debug(f"Stored message pattern for patient {patient_id}")

        except Exception as e:
            logger.error(f"Failed to store message pattern: {e}")
            # Don't raise - this is not critical for flow operation

    async def update_last_pattern_engagement(
        self, patient_id: UUID, score: float
    ) -> None:
        """
        Update the engagement score of the last stored message pattern.

        Args:
            patient_id: Patient UUID
            score: Engagement score (0.0 to 1.0)
        """
        try:
            key = f"msg_patterns:{patient_id}"

            # Get the last pattern (index 0)
            last_pattern_data = self.redis.lindex(key, 0)

            if last_pattern_data:
                pattern_dict = json.loads(last_pattern_data)
                pattern = ConversationPattern.from_dict(pattern_dict)

                # Update score
                pattern.engagement_score = score

                # Update in Redis
                self.redis.lset(key, 0, json.dumps(pattern.to_dict()))
                logger.debug(
                    f"Updated engagement score to {score} for patient {patient_id}"
                )

        except Exception as e:
            logger.error(f"Failed to update engagement score: {e}")

    async def get_recent_patterns(
        self, patient_id: UUID, limit: int = 10
    ) -> List[ConversationPattern]:
        """
        Get recent message patterns for a patient.

        Args:
            patient_id: Patient UUID
            limit: Maximum number of patterns to return

        Returns:
            List of recent conversation patterns
        """
        try:
            key = f"msg_patterns:{patient_id}"
            pattern_data_list = self.redis.lrange(key, 0, limit - 1)

            patterns = []
            for pattern_data in pattern_data_list:
                try:
                    pattern_dict = json.loads(pattern_data)
                    pattern = ConversationPattern.from_dict(pattern_dict)
                    patterns.append(pattern)
                except Exception as e:
                    logger.warning(f"Failed to parse pattern data: {e}")
                    continue

            logger.debug(f"Retrieved {len(patterns)} patterns for patient {patient_id}")
            return patterns

        except Exception as e:
            logger.error(f"Failed to get recent patterns: {e}")
            return []

    async def check_message_repetition(
        self, patient_id: UUID, new_message: str, similarity_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Check if a new message is too similar to recent messages.

        Args:
            patient_id: Patient UUID
            new_message: New message to check
            similarity_threshold: Similarity threshold (0.0-1.0)

        Returns:
            Dict with repetition analysis results
        """
        try:
            # Extract pattern from new message
            new_pattern = self.pattern_extractor.extract_patterns(new_message)

            # Get recent patterns
            recent_patterns = await self.get_recent_patterns(patient_id, limit=5)

            if not recent_patterns:
                return {
                    "is_repetitive": False,
                    "max_similarity": 0.0,
                    "similar_patterns": [],
                    "recommendation": "proceed",
                }

            # Calculate similarities
            similarities = []
            similar_patterns = []

            for pattern in recent_patterns:
                similarity = self.pattern_extractor.calculate_similarity(
                    new_pattern, pattern
                )
                similarities.append(similarity)

                if similarity >= similarity_threshold:
                    similar_patterns.append(
                        {
                            "similarity": similarity,
                            "pattern": pattern.to_dict(),
                            "age_hours": (
                                now_sao_paulo() - pattern.timestamp
                            ).total_seconds()
                            / 3600,
                        }
                    )

            max_similarity = max(similarities) if similarities else 0.0
            is_repetitive = max_similarity >= similarity_threshold

            # Generate recommendation
            recommendation = "proceed"
            if is_repetitive:
                if max_similarity >= 0.9:
                    recommendation = "regenerate"  # Very similar, should regenerate
                elif max_similarity >= 0.8:
                    recommendation = "modify"  # Somewhat similar, should modify
                else:
                    recommendation = (
                        "caution"  # Moderately similar, proceed with caution
                    )

            return {
                "is_repetitive": is_repetitive,
                "max_similarity": max_similarity,
                "similar_patterns": similar_patterns,
                "recommendation": recommendation,
                "analysis": {
                    "pattern_count": len(recent_patterns),
                    "avg_similarity": sum(similarities) / len(similarities)
                    if similarities
                    else 0.0,
                    "threshold_used": similarity_threshold,
                },
            }

        except Exception as e:
            logger.error(f"Failed to check message repetition: {e}")
            return {
                "is_repetitive": False,
                "max_similarity": 0.0,
                "similar_patterns": [],
                "recommendation": "proceed",
                "error": str(e),
            }

    async def get_communication_preferences(self, patient_id: UUID) -> Dict[str, Any]:
        """
        Get patient's communication preferences based on pattern history.

        Args:
            patient_id: Patient UUID

        Returns:
            Dict with communication preferences
        """
        try:
            patterns = await self.get_recent_patterns(patient_id, limit=20)

            if not patterns:
                return self._get_default_preferences()

            # Analyze patterns to determine preferences
            preferences = {
                "formality_level": self._analyze_formality(patterns),
                "emoji_usage": self._analyze_emoji_usage(patterns),
                "preferred_greetings": self._analyze_preferred_greetings(patterns),
                "question_style": self._analyze_question_style(patterns),
                "emotional_tone": self._analyze_emotional_tone(patterns),
                "message_length_preference": self._analyze_message_length(patterns),
                "pattern_count": len(patterns),
                "last_updated": now_sao_paulo().isoformat(),
            }

            # Cache preferences
            pref_key = f"comm_prefs:{patient_id}"
            self.redis.setex(
                pref_key,
                7 * 24 * 3600,  # Cache for 7 days
                json.dumps(preferences),
            )

            return preferences

        except Exception as e:
            logger.error(f"Failed to get communication preferences: {e}")
            return self._get_default_preferences()

    def _get_default_preferences(self) -> Dict[str, Any]:
        """Get default communication preferences."""
        return {
            "formality_level": "casual",
            "emoji_usage": True,
            "preferred_greetings": ["oi", "olá"],
            "question_style": "conversational",
            "emotional_tone": "supportive",
            "message_length_preference": "moderate",
            "pattern_count": 0,
            "last_updated": now_sao_paulo().isoformat(),
        }

    def _analyze_formality(self, patterns: List[ConversationPattern]) -> str:
        """Analyze formality level from patterns."""
        formal_indicators = ["você", "senhor", "senhora"]
        informal_indicators = ["tu", "vc", "voce"]

        formal_count = 0
        informal_count = 0

        for pattern in patterns:
            for starter in pattern.sentence_starters:
                if any(indicator in starter for indicator in formal_indicators):
                    formal_count += 1
                if any(indicator in starter for indicator in informal_indicators):
                    informal_count += 1

        if formal_count > informal_count * 1.5:
            return "formal"
        elif informal_count > formal_count:
            return "informal"
        else:
            return "casual"

    def _analyze_emoji_usage(self, patterns: List[ConversationPattern]) -> bool:
        """Analyze emoji usage preference."""
        total_messages = len(patterns)
        messages_with_emojis = sum(1 for p in patterns if p.emoji_count > 0)

        return (
            messages_with_emojis / total_messages > 0.3 if total_messages > 0 else True
        )

    def _analyze_preferred_greetings(
        self, patterns: List[ConversationPattern]
    ) -> List[str]:
        """Analyze preferred greeting words."""
        greeting_counts = {}

        for pattern in patterns:
            for greeting in pattern.greeting_words:
                greeting_counts[greeting] = greeting_counts.get(greeting, 0) + 1

        # Return top 3 most used greetings
        sorted_greetings = sorted(
            greeting_counts.items(), key=lambda x: x[1], reverse=True
        )
        return [greeting for greeting, _ in sorted_greetings[:3]]

    def _analyze_question_style(self, patterns: List[ConversationPattern]) -> str:
        """Analyze preferred question style."""
        direct_patterns = ["como está", "que tal"]
        conversational_patterns = ["me conta", "gostaria de saber"]

        direct_count = 0
        conversational_count = 0

        for pattern in patterns:
            for structure in pattern.question_structures:
                if any(dp in structure for dp in direct_patterns):
                    direct_count += 1
                if any(cp in structure for cp in conversational_patterns):
                    conversational_count += 1

        if direct_count > conversational_count:
            return "direct"
        elif conversational_count > 0:
            return "conversational"
        else:
            return "supportive"

    def _analyze_emotional_tone(self, patterns: List[ConversationPattern]) -> str:
        """Analyze preferred emotional tone."""
        positive_count = sum(
            1
            for p in patterns
            for emo in p.emotional_words
            if emo.startswith("positive:")
        )

        negative_count = sum(
            1
            for p in patterns
            for emo in p.emotional_words
            if emo.startswith("negative:")
        )

        if positive_count > negative_count * 2:
            return "upbeat"
        elif negative_count > positive_count:
            return "gentle"
        else:
            return "supportive"

    def _analyze_message_length(self, patterns: List[ConversationPattern]) -> str:
        """Analyze preferred message length."""
        if not patterns:
            return "moderate"

        avg_length = sum(p.message_length for p in patterns) / len(patterns)

        if avg_length < 50:
            return "brief"
        elif avg_length > 150:
            return "detailed"
        else:
            return "moderate"

    async def clear_patient_patterns(self, patient_id: UUID) -> bool:
        """
        Clear all stored patterns for a patient.

        Args:
            patient_id: Patient UUID

        Returns:
            True if successful, False otherwise
        """
        try:
            pattern_key = f"msg_patterns:{patient_id}"
            pref_key = f"comm_prefs:{patient_id}"

            deleted_count = self.redis.delete(pattern_key, pref_key)
            logger.info(f"Cleared {deleted_count} keys for patient {patient_id}")
            return deleted_count > 0

        except Exception as e:
            logger.error(f"Failed to clear patient patterns: {e}")
            return False

    async def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get conversation memory system statistics.

        Returns:
            Dict with memory system stats
        """
        try:
            # Get all pattern keys (non-blocking scan)
            pattern_keys = list(self.redis.scan_iter(match="msg_patterns:*", count=100))
            pref_keys = list(self.redis.scan_iter(match="comm_prefs:*", count=100))

            # Calculate total patterns
            total_patterns = 0
            for key in pattern_keys:
                total_patterns += self.redis.llen(key)

            return {
                "total_patients": len(pattern_keys),
                "total_patterns": total_patterns,
                "cached_preferences": len(pref_keys),
                "redis_memory_usage": self.redis.memory_usage("msg_patterns:*")
                if pattern_keys
                else 0,
                "avg_patterns_per_patient": total_patterns / len(pattern_keys)
                if pattern_keys
                else 0,
                "timestamp": now_sao_paulo().isoformat(),
            }

        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {"error": str(e), "timestamp": now_sao_paulo().isoformat()}

    async def health_check(self) -> bool:
        """
        Check if Redis connection is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            self.redis.ping()
            return True
        except Exception as e:
            logger.error(f"Conversation memory health check failed: {e}")
            return False


# Global conversation memory instance
_conversation_memory: Optional[ConversationMemory] = None


def get_conversation_memory() -> ConversationMemory:
    """
    Get global conversation memory instance.

    Returns:
        ConversationMemory instance
    """
    global _conversation_memory
    if _conversation_memory is None:
        _conversation_memory = ConversationMemory()
    return _conversation_memory

