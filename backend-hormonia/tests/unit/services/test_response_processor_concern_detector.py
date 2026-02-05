import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from app.services.response_processor.extractors import DataExtractor
from app.services.response_processor.models import (
    ResponseProcessorConfig,
    InboundMessage,
    ResponseType,
)
from app.services.analytics.data_extraction.models import (
    MedicalConcern,
    MedicalConcernType,
)
from app.services.ai import ConcernLevel


def _build_sentiment_response():
    response = MagicMock()
    # Sentiment should have a .value attribute like an enum
    sentiment_mock = MagicMock()
    sentiment_mock.value = "neutral"
    response.sentiment = sentiment_mock
    response.confidence = 0.6
    response.key_phrases = []
    response.emotional_indicators = []
    response.medical_concerns = []
    return response


def _build_patient():
    patient = MagicMock()
    patient.name = "Test Patient"
    patient.treatment_type = "general"
    patient.age = 45
    patient.preferences = {}
    patient.medical_history = {}
    return patient


@pytest.mark.asyncio
async def test_extract_structured_data_merges_concern_detector_ai():
    config = ResponseProcessorConfig(
        enable_ai_processing=True,
        enable_sentiment_analysis=True,
    )
    with patch(
        "app.services.response_processor.extractors.get_langchain_orchestrator"
    ) as mock_orchestrator:
        mock_orchestrator.return_value = MagicMock()
        extractor = DataExtractor(MagicMock(), config)

    extractor.patient_repo = MagicMock()
    extractor.patient_repo.get.return_value = _build_patient()
    extractor.message_repo = MagicMock()
    extractor.message_repo.get_conversation_history.return_value = []
    extractor.context_builder = MagicMock()
    extractor.context_builder.build_patient_context = AsyncMock(
        return_value=MagicMock()
    )
    extractor.sentiment_analyzer = MagicMock()
    extractor.sentiment_analyzer.analyze_sentiment = AsyncMock(
        return_value=(_build_sentiment_response(), ConcernLevel.LOW)
    )
    extractor.concern_detector = MagicMock()
    extractor.concern_detector.detect_medical_concerns = AsyncMock(
        return_value=[
            MedicalConcern(
                concern_type=MedicalConcernType.EMERGENCY,
                description="severe bleeding",
                severity=ConcernLevel.HIGH,
                keywords=["bleeding"],
                confidence=0.9,
                requires_immediate_attention=True,
                severity_score=8,
            )
        ]
    )
    extractor.concern_detector.detect_concerns_by_patterns = MagicMock(
        return_value=[]
    )
    extractor._concern_detector_ai_available = True

    inbound = InboundMessage(
        patient_phone="5511999999999",
        content="no symptoms",
        whatsapp_id="wamid.1",
    )

    with patch(
        "app.core.redis_manager.get_sync_redis_client",
        return_value=None,
    ):
        result = await extractor.extract_structured_data(
            uuid4(), inbound, ResponseType.TEXT, None
        )

    assert "severe bleeding" in result.medical_concerns
    assert result.severity_score >= 8
    assert result.extracted_data["concern_detector_severity_score"] == 8


@pytest.mark.asyncio
async def test_extract_structured_data_uses_pattern_detector_when_ai_disabled():
    config = ResponseProcessorConfig(
        enable_ai_processing=False,
        enable_sentiment_analysis=False,
    )
    with patch(
        "app.services.response_processor.extractors.get_langchain_orchestrator"
    ) as mock_orchestrator:
        mock_orchestrator.return_value = MagicMock()
        extractor = DataExtractor(MagicMock(), config)

    extractor.concern_detector = MagicMock()
    extractor.concern_detector.detect_concerns_by_patterns = MagicMock(
        return_value=[
            MedicalConcern(
                concern_type=MedicalConcernType.EMERGENCY,
                description="breathing difficulty",
                severity=ConcernLevel.CRITICAL,
                keywords=["falta de ar"],
                confidence=0.9,
                requires_immediate_attention=True,
                severity_score=10,
            )
        ]
    )
    extractor._concern_detector_ai_available = False

    inbound = InboundMessage(
        patient_phone="5511888888888",
        content="falta de ar",
        whatsapp_id="wamid.2",
    )

    result = await extractor.extract_structured_data(
        uuid4(), inbound, ResponseType.TEXT, None
    )

    assert "breathing difficulty" in result.medical_concerns
    assert result.severity_score >= 10
    assert result.extracted_data["concern_detector_severity_score"] == 10


@pytest.mark.asyncio
async def test_extract_structured_data_falls_back_when_detector_fails():
    config = ResponseProcessorConfig(
        enable_ai_processing=True,
        enable_sentiment_analysis=True,
    )
    with patch(
        "app.services.response_processor.extractors.get_langchain_orchestrator"
    ) as mock_orchestrator:
        mock_orchestrator.return_value = MagicMock()
        extractor = DataExtractor(MagicMock(), config)

    extractor.patient_repo = MagicMock()
    extractor.patient_repo.get.return_value = _build_patient()
    extractor.message_repo = MagicMock()
    extractor.message_repo.get_conversation_history.return_value = []
    extractor.context_builder = MagicMock()
    extractor.context_builder.build_patient_context = AsyncMock(
        return_value=MagicMock()
    )
    extractor.sentiment_analyzer = MagicMock()
    extractor.sentiment_analyzer.analyze_sentiment = AsyncMock(
        return_value=(_build_sentiment_response(), ConcernLevel.LOW)
    )
    extractor.concern_detector = MagicMock()
    extractor.concern_detector.detect_medical_concerns = AsyncMock(
        side_effect=Exception("detector error")
    )
    extractor.concern_detector.detect_concerns_by_patterns = MagicMock(
        return_value=[
            MedicalConcern(
                concern_type=MedicalConcernType.EMERGENCY,
                description="chest pain",
                severity=ConcernLevel.HIGH,
                keywords=["dor no peito"],
                confidence=0.8,
                requires_immediate_attention=True,
                severity_score=9,
            )
        ]
    )
    extractor._concern_detector_ai_available = True

    inbound = InboundMessage(
        patient_phone="5511777777777",
        content="dor no peito",
        whatsapp_id="wamid.3",
    )

    with patch(
        "app.core.redis_manager.get_sync_redis_client",
        return_value=None,
    ):
        result = await extractor.extract_structured_data(
            uuid4(), inbound, ResponseType.TEXT, None
        )

    assert "chest pain" in result.medical_concerns
    assert result.severity_score >= 9
