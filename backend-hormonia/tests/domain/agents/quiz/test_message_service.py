from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.domain.agents.quiz.message_service import QuizMessageService
from app.models.message import MessageStatus


@pytest.mark.asyncio
async def test_create_and_send_text_persists_and_normalizes_none_delivery():
    db_session = MagicMock()
    message_sender = MagicMock()
    message_sender.send_message = AsyncMock(return_value=None)
    service = QuizMessageService(db_session=db_session, message_sender=message_sender)

    patient_id = uuid4()
    message, delivery_success = await service.create_and_send_text(
        patient_id=patient_id,
        content="Olá",
        message_metadata={"source": "test"},
    )

    db_session.add.assert_called_once_with(message)
    db_session.commit.assert_called_once()
    db_session.refresh.assert_called_once_with(message)
    message_sender.send_message.assert_awaited_once_with(message)

    assert message.patient_id == patient_id
    assert message.content == "Olá"
    assert message.status == MessageStatus.PENDING
    assert message.message_metadata == {"source": "test"}
    assert delivery_success is True


@pytest.mark.asyncio
async def test_create_and_send_text_returns_false_for_failed_delivery():
    db_session = MagicMock()
    message_sender = MagicMock()
    message_sender.send_message = AsyncMock(return_value=False)
    service = QuizMessageService(db_session=db_session, message_sender=message_sender)

    _, delivery_success = await service.create_and_send_text(
        patient_id=uuid4(),
        content="Teste",
        message_metadata={},
    )

    assert delivery_success is False


@pytest.mark.asyncio
async def test_create_and_send_text_rolls_back_when_commit_fails():
    db_session = MagicMock()
    db_session.commit.side_effect = RuntimeError("db unavailable")
    message_sender = MagicMock()
    message_sender.send_message = AsyncMock()
    service = QuizMessageService(db_session=db_session, message_sender=message_sender)

    with pytest.raises(RuntimeError, match="db unavailable"):
        await service.create_and_send_text(
            patient_id=uuid4(),
            content="Falha",
            message_metadata={},
        )

    db_session.rollback.assert_called_once()
    message_sender.send_message.assert_not_awaited()
