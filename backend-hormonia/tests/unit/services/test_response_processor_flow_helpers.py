from uuid import uuid4

from app.services.ai import ConcernLevel
from app.services.response_processor.flow_helpers import FlowHelpers
from app.services.response_processor.models import ResponseType, StructuredResponse


def _build_structured_response(*, medical_concerns: list[str], severity_score: int = 0) -> StructuredResponse:
    return StructuredResponse(
        patient_id=uuid4(),
        original_message="Teste",
        response_type=ResponseType.TEXT,
        extracted_data={},
        sentiment_analysis={"sentiment": "neutral", "confidence": 0.5},
        medical_concerns=medical_concerns,
        concern_level=ConcernLevel.LOW,
        requires_attention=False,
        severity_score=severity_score,
        confidence_score=0.8,
    )


def test_check_escalation_required_returns_bool_with_medical_concerns() -> None:
    structured_response = _build_structured_response(
        medical_concerns=["nausea", "fatigue"],
        severity_score=3,
    )

    result = FlowHelpers.check_escalation_required(structured_response)

    assert isinstance(result, bool)
    assert result is True
