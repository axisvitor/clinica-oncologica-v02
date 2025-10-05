"""
Conversation memory system using Redis for pattern tracking and anti-repetition.
Stores and analyzes conversation patterns to avoid repetitive messaging.
"""
import json
import re
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from uuid import UUID
from redis import Redis

from app.config import settings
from app.core.redis_unified import get_sync_redis

logger = logging.getLogger(__name__)


class ConversationPattern:
    """Represents a conversation pattern extracted from messages."""
    
    def __init__(self, 
                 greeting_words: List[str] = None,
                 question_structures: List[str] = None,
                 emotional_words: List[str] = None,
                 sentence_starters: List[str] = None,
                 message_length: int = 0,
                 emoji_count: int = 0,
                 timestamp: datetime = None):
        self.greeting_words = greeting_words or []
        self.question_structures = question_structures or []
        self.emotional_words = emotional_words or []
        self.sentence_starters = sentence_starters or []
        self.message_length = message_length
        self.emoji_count = emoji_count
        self.timestamp = timestamp or datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert pattern to dictionary for storage."""
        return {
            "greeting_words": self.greeting_words,
            "question_structures": self.question_structures,
            "emotional_words": self.emotional_words,
            "sentence_starters": self.sentence_starters,
            "message_length": self.message_length,
            "emoji_count": self.emoji_count,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationPattern':
        """Create pattern from dictionary."""
        return cls(
            greeting_words=data.get("greeting_words", []),
            question_structures=data.get("question_structures", []),
            emotional_words=data.get("emotional_words", []),
            sentence_starters=data.get("sentence_starters", []),
            message_length=data.get("message_length", 0),
            emoji_count=data.get("emoji_count", 0),
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.utcnow().isoformat()))
        )


class PatternExtractor:
    """Extracts linguistic patterns from messages."""
    
    # Portuguese greeting words
    GREETING_WORDS = {
        "oi", "olá", "ola", "hey", "e aí", "eai", "tudo bem", "como vai", 
        "bom dia", "boa tarde", "boa noite", "salve", "fala", "beleza"
    }
    
    # Emotional indicators
    EMOTIONAL_WORDS = {
        "positive": {
            "bem", "ótimo", "otimo", "excelente", "maravilhoso", "feliz", 
            "alegre", "animada", "contente", "satisfeita", "melhor", "bom"
        },
        "negative": {
            "mal", "ruim", "péssimo", "pessimo", "triste", "preocupada", 
            "ansiosa", "nervosa", "cansada", "estressada", "pior", "difícil"
        },
        "neutral": {
            "normal", "ok", "tranquilo", "comum", "igual", "mesmo", "assim"
        }
    }
    
    # Question patterns
    QUESTION_PATTERNS = [
        r"como (você |tu )?está",
        r"como (você |tu )?se sente",
        r"como (foi|tem sido|está sendo)",
        r"que tal",
        r"me conta",
        r"pode me dizer",
        r"gostaria de saber"
    ]
    
    def extract_patterns(self, message: str) -> ConversationPattern:
        """
        Extract linguistic patterns from a message.
        
        Args:
            message: Message text to analyze
            
        Returns:
            ConversationPattern with extracted patterns
        """
        message_lower = message.lower()
        
        # Extract greeting words
        greeting_words = [word for word in self.GREETING_WORDS 
                         if word in message_lower]
        
        # Extract question structures
        question_structures = []
        for pattern in self.QUESTION_PATTERNS:
            if re.search(pattern, message_lower):
                question_structures.append(pattern)
        
        # Extract emotional words
        emotional_words = []
        for category, words in self.EMOTIONAL_WORDS.items():
            found_words = [word for word in words if word in message_lower]
            if found_words:
                emotional_words.extend([f"{category}:{word}" for word in found_words])
        
        # Extract sentence starters (first 3 words)
        words = message_lower.split()
        sentence_starters = words[:3] if len(words) >= 3 else words
        
        # Count emojis (using a more comprehensive emoji pattern)
        emoji_pattern = r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002600-\U000027BF\U0001F900-\U0001F9FF]'
        emoji_count = len(re.findall(emoji_pattern, message))
        
        return ConversationPattern(
            greeting_words=greeting_words,
            question_structures=question_structures,
            emotional_words=emotional_words,
            sentence_starters=sentence_starters,
            message_length=len(message),
            emoji_count=emoji_count
        )
    
    def calculate_similarity(self, pattern1: ConversationPattern, pattern2: ConversationPattern) -> float:
        """
        Calculate similarity between two conversation patterns.
        
        Args:
            pattern1: First pattern
            pattern2: Second pattern
            
        Returns:
            Similarity score between 0.0 and 1.0
        """
        similarity_scores = []
        
        # Greeting words similarity
        greeting_sim = self._calculate_list_similarity(
            pattern1.greeting_words, pattern2.greeting_words
        )
        similarity_scores.append(greeting_sim * 0.3)  # 30% weight
        
        # Question structures similarity
        question_sim = self._calculate_list_similarity(
            pattern1.question_structures, pattern2.question_structures
        )
        similarity_scores.append(question_sim * 0.3)  # 30% weight
        
        # Emotional words similarity
        emotional_sim = self._calculate_list_similarity(
            pattern1.emotional_words, pattern2.emotional_words
        )
        similarity_scores.append(emotional_sim * 0.2)  # 20% weight
        
        # Sentence starters similarity
        starters_sim = self._calculate_list_similarity(
            pattern1.sentence_starters, pattern2.sentence_starters
        )
        similarity_scores.append(starters_sim * 0.2)  # 20% weight
        
        return sum(similarity_scores)
    
    def _calculate_list_similarity(self, list1: List[str], list2: List[str]) -> float:
        """Calculate similarity between two lists of strings."""
        if not list1 and not list2:
            return 0.0
        if not list1 or not list2:
            return 0.0
        
        set1 = set(list1)
        set2 = set(list2)
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0


class ConversationMemory:
    """
    Redis-based conversation memory system for pattern tracking.
    Stores conversation patterns and provides anti-repetition functionality.
    """
    
    def __init__(self):
        """
        Initialize conversation memory with unified Redis client.

        Uses the unified RedisManager from app.core.redis_unified.
        """
        self.redis = self._create_redis_client()
        self.pattern_extractor = PatternExtractor()
        self.max_patterns_per_patient = 20  # Store last 20 message patterns
        self.pattern_expiry_days = 30  # Patterns expire after 30 days

        logger.info("ConversationMemory initialized with unified Redis backend")
    
    def _create_redis_client(self) -> Redis:
        """Create Redis client using unified RedisManager."""
        try:
            client = get_sync_redis()
            logger.info("Redis connection established via unified RedisManager")
            return client
        except Exception as e:
            logger.error(f"Failed to connect to Redis via unified manager: {e}")
            raise
    
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
    
    async def get_recent_patterns(self, patient_id: UUID, limit: int = 10) -> List[ConversationPattern]:
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
    
    async def check_message_repetition(self, patient_id: UUID, new_message: str, 
                                     similarity_threshold: float = 0.7) -> Dict[str, Any]:
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
                    "recommendation": "proceed"
                }
            
            # Calculate similarities
            similarities = []
            similar_patterns = []
            
            for pattern in recent_patterns:
                similarity = self.pattern_extractor.calculate_similarity(new_pattern, pattern)
                similarities.append(similarity)
                
                if similarity >= similarity_threshold:
                    similar_patterns.append({
                        "similarity": similarity,
                        "pattern": pattern.to_dict(),
                        "age_hours": (datetime.utcnow() - pattern.timestamp).total_seconds() / 3600
                    })
            
            max_similarity = max(similarities) if similarities else 0.0
            is_repetitive = max_similarity >= similarity_threshold
            
            # Generate recommendation
            recommendation = "proceed"
            if is_repetitive:
                if max_similarity >= 0.9:
                    recommendation = "regenerate"  # Very similar, should regenerate
                elif max_similarity >= 0.8:
                    recommendation = "modify"     # Somewhat similar, should modify
                else:
                    recommendation = "caution"    # Moderately similar, proceed with caution
            
            return {
                "is_repetitive": is_repetitive,
                "max_similarity": max_similarity,
                "similar_patterns": similar_patterns,
                "recommendation": recommendation,
                "analysis": {
                    "pattern_count": len(recent_patterns),
                    "avg_similarity": sum(similarities) / len(similarities) if similarities else 0.0,
                    "threshold_used": similarity_threshold
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to check message repetition: {e}")
            return {
                "is_repetitive": False,
                "max_similarity": 0.0,
                "similar_patterns": [],
                "recommendation": "proceed",
                "error": str(e)
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
                "last_updated": datetime.utcnow().isoformat()
            }
            
            # Cache preferences
            pref_key = f"comm_prefs:{patient_id}"
            self.redis.setex(
                pref_key, 
                7 * 24 * 3600,  # Cache for 7 days
                json.dumps(preferences)
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
            "last_updated": datetime.utcnow().isoformat()
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
        
        return messages_with_emojis / total_messages > 0.3 if total_messages > 0 else True
    
    def _analyze_preferred_greetings(self, patterns: List[ConversationPattern]) -> List[str]:
        """Analyze preferred greeting words."""
        greeting_counts = {}
        
        for pattern in patterns:
            for greeting in pattern.greeting_words:
                greeting_counts[greeting] = greeting_counts.get(greeting, 0) + 1
        
        # Return top 3 most used greetings
        sorted_greetings = sorted(greeting_counts.items(), key=lambda x: x[1], reverse=True)
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
        positive_count = sum(1 for p in patterns 
                           for emo in p.emotional_words 
                           if emo.startswith("positive:"))
        
        negative_count = sum(1 for p in patterns 
                           for emo in p.emotional_words 
                           if emo.startswith("negative:"))
        
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
            # Get all pattern keys
            pattern_keys = self.redis.keys("msg_patterns:*")
            pref_keys = self.redis.keys("comm_prefs:*")
            
            # Calculate total patterns
            total_patterns = 0
            for key in pattern_keys:
                total_patterns += self.redis.llen(key)
            
            return {
                "total_patients": len(pattern_keys),
                "total_patterns": total_patterns,
                "cached_preferences": len(pref_keys),
                "redis_memory_usage": self.redis.memory_usage("msg_patterns:*") if pattern_keys else 0,
                "avg_patterns_per_patient": total_patterns / len(pattern_keys) if pattern_keys else 0,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
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


async def test_conversation_memory():
    """Test conversation memory system functionality."""
    try:
        memory = get_conversation_memory()
        
        # Test health check
        if not await memory.health_check():
            logger.error("Conversation memory health check failed")
            return False
        
        # Test pattern storage and retrieval
        test_patient_id = UUID("12345678-1234-5678-9012-123456789012")
        test_messages = [
            "Oi Maria, como você está se sentindo hoje?",
            "Olá Maria, tudo bem por aí?",
            "Hey Maria, me conta como foi seu dia!"
        ]
        
        # Store patterns
        for message in test_messages:
            await memory.store_message_pattern(test_patient_id, message)
        
        # Check repetition
        new_message = "Oi Maria, como você está hoje?"
        repetition_check = await memory.check_message_repetition(test_patient_id, new_message)
        
        logger.info(f"Repetition check result: {repetition_check}")
        
        # Get preferences
        preferences = await memory.get_communication_preferences(test_patient_id)
        logger.info(f"Communication preferences: {preferences}")
        
        # Clean up test data
        await memory.clear_patient_patterns(test_patient_id)
        
        logger.info("Conversation memory test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Conversation memory test failed: {e}")
        return False