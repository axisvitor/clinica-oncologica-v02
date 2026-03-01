from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.domain.agents.quiz.session_coordinator import SessionCoordinator


def _response(question_id: str, value: str, order: int):
    timestamp = datetime(2025, 1, order, 12, 0, tzinfo=timezone.utc)
    return SimpleNamespace(
        question_id=question_id,
        question_text=f"Pergunta {question_id}",
        response_type="open_text",
        response_value=value,
        response_metadata={"confidence": 0.9},
        responded_at=timestamp,
    )


@pytest.mark.asyncio
async def test_get_session_responses_uses_response_service_and_respects_limit():
    quiz_response_service = MagicMock()
    quiz_response_service.get_session_responses.return_value = [
        _response("q1", "a1", 1),
        _response("q2", "a2", 2),
        _response("q3", "a3", 3),
    ]

    coordinator = SessionCoordinator(
        db_session=MagicMock(),
        quiz_template_service=MagicMock(),
        quiz_session_service=MagicMock(),
        quiz_response_service=quiz_response_service,
        patient_repo=MagicMock(),
        agent_id="agent-test",
    )

    payloads = await coordinator.get_session_responses(uuid4(), limit=2)

    assert [payload["question_id"] for payload in payloads] == ["q2", "q3"]
    assert payloads[-1]["processed_value"] == "a3"
    quiz_response_service.get_session_responses.assert_called_once()
