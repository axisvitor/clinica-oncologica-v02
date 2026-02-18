from unittest.mock import Mock
from uuid import uuid4

from app.domain.messaging.core.message_factory import MessageFactory, MessageTemplate
from app.models.message import MessageType


def _build_db_mock():
    db = Mock()
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    return db


def test_create_outbound_message_uses_canonical_message_fields():
    db = _build_db_mock()
    factory = MessageFactory(db)

    factory.create_outbound_message(
        patient_id=uuid4(),
        content="Mensagem teste",
        message_type=MessageType.TEXT,
        metadata={"channel": "whatsapp"},
        template_type=MessageTemplate.REMINDER,
    )

    created_message = db.add.call_args.args[0]
    assert created_message.type == MessageType.TEXT
    assert created_message.message_metadata["channel"] == "whatsapp"
    assert created_message.message_metadata["template_type"] == MessageTemplate.REMINDER.value


def test_create_outbound_message_accepts_compat_kwargs_without_invalid_fields():
    db = _build_db_mock()
    factory = MessageFactory(db)

    factory.create_outbound_message(
        patient_id=uuid4(),
        content="Compat test",
        message_type=MessageType.TEXT,
        metadata={"source": "adapter"},
        type=MessageType.IMAGE,
        message_metadata={"origin": "kwargs"},
    )

    created_message = db.add.call_args.args[0]
    assert created_message.type == MessageType.IMAGE
    assert created_message.message_metadata["source"] == "adapter"
    assert created_message.message_metadata["origin"] == "kwargs"
