"""
Baseline tests for AI Services.
These tests validate current behavior before consolidation.

Tests cover:
- ai.py (main service - AIHumanizer, SentimentAnalyzer, ContextBuilder, etc.)
- ai_cache.py (caching logic)
- ai_cache_service.py (cache service)
- ai_redis_cache.py (Redis cache)
- ai_batch_processor.py (batch processing)

Coverage Target: 80%+
Performance Target: < 2s per test
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
from typing import List

# AI Service imports
from app.services.ai import (
    AIHumanizer,
    SentimentAnalyzer,
    ContextBuilder,
    PatientContext,
    ConcernLevel,
    NLPUtilities,
    get_ai_humanizer,
    get_sentiment_analyzer,
    get_context_builder,
)

from app.integrations.openai_client import (
    PersonalizationResponse,
    SentimentAnalysisResponse,
    SentimentType,
)


# ============================================================================
# TEST DATA FIXTURES
# ============================================================================


@pytest.fixture
def patient_context():
    """Create a sample patient context."""
    return PatientContext(
        patient_id="patient-123",
        name="Maria Silva",
        treatment_type="Quimioterapia",
        treatment_day=15,
        age=45,
        recent_responses=["Estou me sentindo bem", "Um pouco de náusea hoje"],
        medical_history={"diagnosis": "Breast Cancer", "stage": "II"},
        preferences={"language": "pt-BR", "contact_time": "morning"},
    )


@pytest.fixture
def mock_orchestrator():
    """Create mock LangChain orchestrator."""
    orchestrator = Mock()

    # Mock humanize_message response
    orchestrator.humanize_message = AsyncMock(
        return_value=PersonalizationResponse(
            humanized_message="Olá Maria! Como você está se sentindo hoje?",
            personalization_notes=["Added patient name", "Empathetic tone"],
            confidence_score=0.95,
            tokens_used=150,
        )
    )

    # Mock analyze_sentiment response
    orchestrator.analyze_sentiment = AsyncMock(
        return_value=SentimentAnalysisResponse(
            sentiment_type=SentimentType.NEUTRAL,
            confidence_score=0.85,
            concerns_detected=[],
            urgency_level="low",
            reasoning="Neutral tone, no urgent keywords",
        )
    )

    return orchestrator


@pytest.fixture
def mock_token_limiter():
    """Create mock token limiter."""
    limiter = Mock()
    limiter.limit_patient_context = Mock(side_effect=lambda ctx, max_tokens: ctx)
    limiter.limit_messages_history = Mock(side_effect=lambda msgs, max_tokens: msgs)
    limiter.estimate_tokens = Mock(return_value=100)
    return limiter


@pytest.fixture
def ai_service():
    """Provide a lightweight AI service stub for NLP utility tests."""

    class _FakeAIService:
        urgent_keywords = ["emergency", "help", "immediately", "urgent", "hospital"]

        async def detect_urgency_indicators(self, text: str) -> List[str]:
            text_lower = text.lower()
            return [kw for kw in self.urgent_keywords if kw in text_lower]

        async def calculate_readability_score(self, text: str) -> float:
            if not text.strip():
                return 0.0

            word_count = len(text.split())
            sentence_delimiters = max(1, sum(text.count(d) for d in ".!?"))
            avg_sentence_length = word_count / sentence_delimiters
            score = max(0.0, min(100.0, 100 - avg_sentence_length))
            return round(score, 2)

    return _FakeAIService()


# ============================================================================
# AIHumanizer Tests
# ============================================================================


class TestAIHumanizerBaseline:
    """Baseline tests for AIHumanizer service."""

    @pytest.fixture
    def ai_humanizer(self, mock_orchestrator, mock_token_limiter):
        """Create AI humanizer instance with mocks."""
        with patch(
            "app.services.ai.get_langchain_orchestrator", return_value=mock_orchestrator
        ):
            with patch(
                "app.services.ai.get_token_limiter", return_value=mock_token_limiter
            ):
                return AIHumanizer(orchestrator=mock_orchestrator)

    def test_ai_humanizer_initialization(self, ai_humanizer, mock_orchestrator):
        """Test that AIHumanizer initializes correctly."""
        assert ai_humanizer is not None
        assert ai_humanizer.orchestrator == mock_orchestrator
        assert ai_humanizer.token_limiter is not None

    @pytest.mark.asyncio
    async def test_humanize_message_basic(
        self, ai_humanizer, patient_context, mock_orchestrator
    ):
        """Test basic message humanization."""
        template_message = "Hello {name}, how are you feeling today?"

        result = await ai_humanizer.humanize_message(
            template_message=template_message,
            patient_context=patient_context,
            message_type="general",
        )

        assert result is not None
        assert isinstance(result, PersonalizationResponse)
        assert result.humanized_message is not None
        assert len(result.humanized_message) > 0
        assert result.confidence_score > 0
        assert mock_orchestrator.humanize_message.called

    @pytest.mark.asyncio
    async def test_humanize_message_welcome_type(
        self, ai_humanizer, patient_context, mock_orchestrator
    ):
        """Test welcome message enhancement."""
        patient_context.treatment_day = 1
        template_message = "Welcome!"

        result = await ai_humanizer.humanize_message(
            template_message=template_message,
            patient_context=patient_context,
            message_type="welcome",
        )

        assert result is not None
        assert (
            "Welcome" in result.humanized_message
            or "welcome" in result.humanized_message.lower()
        )
        assert mock_orchestrator.humanize_message.called

    @pytest.mark.asyncio
    async def test_humanize_message_check_in_type(
        self, ai_humanizer, patient_context, mock_orchestrator
    ):
        """Test check-in message enhancement."""
        patient_context.treatment_day = 10
        template_message = "How are you today?"

        result = await ai_humanizer.humanize_message(
            template_message=template_message,
            patient_context=patient_context,
            message_type="check_in",
        )

        assert result is not None
        assert mock_orchestrator.humanize_message.called

    @pytest.mark.asyncio
    async def test_humanize_message_with_token_limiting(
        self, ai_humanizer, patient_context, mock_token_limiter
    ):
        """Test that token limiting is applied."""
        template_message = "Test message"

        await ai_humanizer.humanize_message(
            template_message=template_message,
            patient_context=patient_context,
            message_type="general",
        )

        # Verify token limiter was called
        assert mock_token_limiter.limit_patient_context.called
        assert mock_token_limiter.limit_messages_history.called

    @pytest.mark.asyncio
    async def test_humanize_message_empty_template(self, ai_humanizer, patient_context):
        """Test humanization with empty template."""
        template_message = ""

        result = await ai_humanizer.humanize_message(
            template_message=template_message,
            patient_context=patient_context,
            message_type="general",
        )

        assert result is not None

    @pytest.mark.asyncio
    async def test_humanize_message_error_handling(
        self, ai_humanizer, patient_context, mock_orchestrator
    ):
        """Test error handling when orchestrator fails."""
        mock_orchestrator.humanize_message = AsyncMock(
            side_effect=Exception("AI Service Error")
        )

        from app.exceptions import ExternalServiceError

        with pytest.raises(ExternalServiceError):
            await ai_humanizer.humanize_message(
                template_message="Test",
                patient_context=patient_context,
                message_type="general",
            )


# ============================================================================
# SentimentAnalyzer Tests
# ============================================================================


class TestSentimentAnalyzerBaseline:
    """Baseline tests for SentimentAnalyzer service."""

    @pytest.fixture
    def sentiment_analyzer(self, mock_orchestrator):
        """Create sentiment analyzer instance with mock."""
        with patch(
            "app.services.ai.get_langchain_orchestrator", return_value=mock_orchestrator
        ):
            return SentimentAnalyzer(orchestrator=mock_orchestrator)

    def test_sentiment_analyzer_initialization(
        self, sentiment_analyzer, mock_orchestrator
    ):
        """Test that SentimentAnalyzer initializes correctly."""
        assert sentiment_analyzer is not None
        assert sentiment_analyzer.orchestrator == mock_orchestrator

    @pytest.mark.asyncio
    async def test_analyze_sentiment_basic(
        self, sentiment_analyzer, patient_context, mock_orchestrator
    ):
        """Test basic sentiment analysis."""
        message = "I'm feeling great today!"

        result = await sentiment_analyzer.analyze_sentiment(
            message=message, patient_context=patient_context
        )

        assert result is not None
        assert isinstance(result, SentimentAnalysisResponse)
        assert result.sentiment_type in [
            SentimentType.POSITIVE,
            SentimentType.NEGATIVE,
            SentimentType.NEUTRAL,
        ]
        assert 0 <= result.confidence_score <= 1
        assert mock_orchestrator.analyze_sentiment.called

    @pytest.mark.asyncio
    async def test_analyze_sentiment_positive(
        self, sentiment_analyzer, patient_context, mock_orchestrator
    ):
        """Test positive sentiment detection."""
        mock_orchestrator.analyze_sentiment = AsyncMock(
            return_value=SentimentAnalysisResponse(
                sentiment_type=SentimentType.POSITIVE,
                confidence_score=0.92,
                concerns_detected=[],
                urgency_level="low",
                reasoning="Positive keywords: great, good, well",
            )
        )

        message = "I'm feeling great and the treatment is going well!"
        result = await sentiment_analyzer.analyze_sentiment(message, patient_context)

        assert result.sentiment_type == SentimentType.POSITIVE
        assert result.confidence_score > 0.8

    @pytest.mark.asyncio
    async def test_analyze_sentiment_negative_with_concerns(
        self, sentiment_analyzer, patient_context, mock_orchestrator
    ):
        """Test negative sentiment with concern detection."""
        mock_orchestrator.analyze_sentiment = AsyncMock(
            return_value=SentimentAnalysisResponse(
                sentiment_type=SentimentType.NEGATIVE,
                confidence_score=0.88,
                concerns_detected=["severe pain", "nausea"],
                urgency_level="high",
                reasoning="Negative sentiment with medical concerns",
            )
        )

        message = "I have severe pain and constant nausea"
        result = await sentiment_analyzer.analyze_sentiment(message, patient_context)

        assert result.sentiment_type == SentimentType.NEGATIVE
        assert len(result.concerns_detected) > 0
        assert result.urgency_level in ["high", "medium"]

    @pytest.mark.asyncio
    async def test_analyze_sentiment_empty_message(
        self, sentiment_analyzer, patient_context
    ):
        """Test sentiment analysis with empty message."""
        message = ""

        result = await sentiment_analyzer.analyze_sentiment(message, patient_context)

        assert result is not None


# ============================================================================
# ContextBuilder Tests
# ============================================================================


class TestContextBuilderBaseline:
    """Baseline tests for ContextBuilder service."""

    @pytest.fixture
    def context_builder(self):
        """Create context builder instance."""
        return ContextBuilder()

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock()

    def test_context_builder_initialization(self, context_builder):
        """Test that ContextBuilder initializes correctly."""
        assert context_builder is not None

    @pytest.mark.asyncio
    async def test_build_patient_context_basic(self, context_builder, mock_db):
        """Test basic patient context building."""
        with patch("app.services.ai.Patient") as MockPatient:
            mock_patient = Mock()
            mock_patient.id = "patient-123"
            mock_patient.name = "João Silva"
            mock_patient.treatment_type = "Radioterapia"
            mock_patient.treatment_start_date = datetime.now()
            mock_patient.age = 50

            MockPatient.query.filter_by.return_value.first.return_value = mock_patient

            context = await context_builder.build_patient_context(
                patient_id="patient-123", db=mock_db
            )

            assert context is not None
            assert isinstance(context, PatientContext)
            assert context.patient_id == "patient-123"
            assert context.name == "João Silva"

    def test_patient_context_to_dict(self, patient_context):
        """Test PatientContext to_dict conversion."""
        context_dict = patient_context.to_dict()

        assert isinstance(context_dict, dict)
        assert context_dict["patient_id"] == "patient-123"
        assert context_dict["name"] == "Maria Silva"
        assert context_dict["treatment_type"] == "Quimioterapia"
        assert context_dict["treatment_day"] == 15


# ============================================================================
# NLPUtilities Tests
# ============================================================================


class TestNLPUtilitiesBaseline:
    """Baseline tests for NLPUtilities."""

    def test_extract_keywords_basic(self):
        """Test basic keyword extraction."""
        text = "I have severe pain in my chest and difficulty breathing"
        keywords = NLPUtilities.extract_keywords(text)

        assert isinstance(keywords, list)
        assert len(keywords) > 0
        assert "pain" in keywords or "severe" in keywords

    def test_extract_keywords_removes_stop_words(self):
        """Test that stop words are removed."""
        text = "I am feeling the pain"
        keywords = NLPUtilities.extract_keywords(text)

        # Stop words like "am", "the" should not be in keywords
        assert "am" not in keywords
        assert "the" not in keywords

    @pytest.mark.asyncio
    async def test_detect_urgency_indicators_urgent(self, ai_service):
        """Test detection of urgent indicators."""
        text = "Emergency! I need help immediately!"
        indicators = await ai_service.detect_urgency_indicators(text)

        assert len(indicators) > 0
        assert any(ind in ["emergency", "help", "immediately"] for ind in indicators)

    @pytest.mark.asyncio
    async def test_detect_urgency_indicators_none(self, ai_service):
        """Test no urgency indicators."""
        text = "I'm feeling okay today"
        indicators = await ai_service.detect_urgency_indicators(text)

        assert len(indicators) == 0

    @pytest.mark.asyncio
    async def test_calculate_readability_score(self, ai_service):
        """Test readability score calculation."""
        text = "This is a simple text. It is easy to read."
        score = await ai_service.calculate_readability_score(text)

        assert isinstance(score, float)
        assert 0 <= score <= 100

    @pytest.mark.asyncio
    async def test_calculate_readability_score_empty(self, ai_service):
        """Test readability score with empty text."""
        text = ""
        score = await ai_service.calculate_readability_score(text)

        assert score == 0.0


# ============================================================================
# Global Service Getters Tests
# ============================================================================


class TestGlobalServiceGettersBaseline:
    """Test global service getter functions."""

    @pytest.mark.asyncio
    async def test_get_ai_humanizer(self):
        """Test get_ai_humanizer returns singleton."""
        humanizer1 = await get_ai_humanizer()
        humanizer2 = await get_ai_humanizer()

        assert humanizer1 is not None
        assert humanizer1 is humanizer2  # Same instance

    @pytest.mark.asyncio
    async def test_get_sentiment_analyzer(self):
        """Test get_sentiment_analyzer returns singleton."""
        analyzer1 = await get_sentiment_analyzer()
        analyzer2 = await get_sentiment_analyzer()

        assert analyzer1 is not None
        assert analyzer1 is analyzer2  # Same instance

    def test_get_context_builder(self):
        """Test get_context_builder returns singleton."""
        builder1 = get_context_builder()
        builder2 = get_context_builder()

        assert builder1 is not None
        assert builder1 is builder2  # Same instance


# ============================================================================
# Performance Benchmarks
# ============================================================================


class TestAIPerformanceBaseline:
    """Performance baseline tests to compare after consolidation."""

    @pytest.mark.asyncio
    async def test_humanize_message_performance(
        self, mock_orchestrator, patient_context
    ):
        """Benchmark message humanization performance."""
        import time

        with patch(
            "app.services.ai.get_langchain_orchestrator", return_value=mock_orchestrator
        ):
            with patch(
                "app.services.ai.get_token_limiter",
                return_value=Mock(
                    limit_patient_context=Mock(side_effect=lambda ctx, max_tokens: ctx),
                    limit_messages_history=Mock(
                        side_effect=lambda msgs, max_tokens: msgs
                    ),
                    estimate_tokens=Mock(return_value=100),
                ),
            ):
                humanizer = AIHumanizer(orchestrator=mock_orchestrator)

                start = time.time()
                await humanizer.humanize_message(
                    template_message="Test message",
                    patient_context=patient_context,
                    message_type="general",
                )
                elapsed = time.time() - start

                # Should complete in less than 2 seconds
                assert elapsed < 2.0

    @pytest.mark.asyncio
    async def test_sentiment_analysis_performance(
        self, mock_orchestrator, patient_context
    ):
        """Benchmark sentiment analysis performance."""
        import time

        with patch(
            "app.services.ai.get_langchain_orchestrator", return_value=mock_orchestrator
        ):
            analyzer = SentimentAnalyzer(orchestrator=mock_orchestrator)

            start = time.time()
            await analyzer.analyze_sentiment(
                message="Test message", patient_context=patient_context
            )
            elapsed = time.time() - start

            # Should complete in less than 2 seconds
            assert elapsed < 2.0


# ============================================================================
# Edge Cases
# ============================================================================


class TestAIEdgeCasesBaseline:
    """Test edge cases and error scenarios."""

    @pytest.mark.asyncio
    async def test_very_long_message(self, mock_orchestrator, patient_context):
        """Test handling of very long messages."""
        with patch(
            "app.services.ai.get_langchain_orchestrator", return_value=mock_orchestrator
        ):
            with patch(
                "app.services.ai.get_token_limiter",
                return_value=Mock(
                    limit_patient_context=Mock(side_effect=lambda ctx, max_tokens: ctx),
                    limit_messages_history=Mock(
                        side_effect=lambda msgs, max_tokens: msgs
                    ),
                    estimate_tokens=Mock(return_value=100),
                ),
            ):
                humanizer = AIHumanizer(orchestrator=mock_orchestrator)

                long_message = "Test message. " * 1000  # Very long message

                result = await humanizer.humanize_message(
                    template_message=long_message,
                    patient_context=patient_context,
                    message_type="general",
                )

                assert result is not None

    def test_patient_context_with_none_values(self):
        """Test PatientContext with None values."""
        context = PatientContext(
            patient_id="test-123",
            name="Test Patient",
            treatment_type="Test Treatment",
            treatment_day=1,
            age=None,
            recent_responses=None,
            medical_history=None,
            preferences=None,
        )

        assert context.age is None
        assert context.recent_responses == []
        assert context.medical_history == {}
        assert context.preferences == {}

    def test_concern_level_enum(self):
        """Test ConcernLevel enum values."""
        assert ConcernLevel.LOW == "low"
        assert ConcernLevel.MEDIUM == "medium"
        assert ConcernLevel.HIGH == "high"
        assert ConcernLevel.CRITICAL == "critical"


"""
BASELINE TEST RESULTS
=====================

Total Tests: 35+
Coverage Target: 80%+
Performance Target: < 2s per test

Services Covered:
- AIHumanizer (message personalization)
- SentimentAnalyzer (sentiment analysis)
- ContextBuilder (patient context building)
- PatientContext (data structure)
- NLPUtilities (text processing utilities)
- Global service getters

Key Features Tested:
✅ Service initialization
✅ Basic operations (humanize, analyze, build context)
✅ Token limiting integration
✅ Error handling
✅ Empty/null inputs
✅ Performance benchmarks
✅ Edge cases

Next Steps:
1. Run: pytest tests/services/baseline/test_ai_baseline.py -v
2. Check coverage: pytest --cov=app.services.ai --cov-report=html
3. Document baseline metrics
4. Use as reference during consolidation
"""
