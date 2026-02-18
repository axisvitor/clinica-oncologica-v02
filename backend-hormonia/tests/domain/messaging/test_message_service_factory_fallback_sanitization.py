from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.domain.messaging.core.message_service.factory import MessageFactory


def _build_db_mock():
    db = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    return db


def test_monthly_invitation_fallback_sanitizes_patient_name_and_link():
    db = _build_db_mock()
    factory = MessageFactory(db)
    factory._core_factory.create_monthly_quiz_link_message = Mock(
        side_effect=AttributeError("force fallback")
    )

    message = factory.create_monthly_quiz_invitation_message(
        patient_id=uuid4(),
        patient_name="<script>alert(1)</script>",
        link="javascript:alert(1)",
        expiry_hours=24,
        quiz_session_id="quiz-123",
    )

    assert "<script" not in message.content.lower()
    assert "javascript:" not in message.content.lower()


def test_quiz_question_fallback_sanitizes_question_content():
    db = _build_db_mock()
    factory = MessageFactory(db)

    question = SimpleNamespace(
        id=uuid4(),
        question_text="<script>alert(1)</script> Como você está hoje?",
        options=["<img src=x onerror=alert(1)>", "Bem"],
    )

    message = factory.create_quiz_question_message(
        patient_id=uuid4(),
        question=question,
        quiz_session_id="quiz-session-1",
        question_number=1,
        total_questions=5,
    )

    assert "<script" not in message.content.lower()
    assert "<img" not in message.content.lower()
    assert "&lt;img" in message.content.lower()
