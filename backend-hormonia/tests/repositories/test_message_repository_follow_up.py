from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models.message import Message, MessageDirection, MessageStatus, MessageType
from app.models.patient import Patient
from app.repositories.message import MessageRepository


from app.utils.timezone import now_sao_paulo
class TestMessageRepositoryFollowUp:
    def test_get_recent_follow_up_message_time_no_messages(self, db_session):
        patient = Patient(name="Test Patient")
        db_session.add(patient)
        db_session.commit()

        repo = MessageRepository(db_session)
        since = now_sao_paulo() - timedelta(hours=24)

        assert repo.get_recent_follow_up_message_time(patient.id, since) is None

    def test_get_recent_follow_up_message_time_skips_non_follow_up(self, db_session):
        patient = Patient(name="Test Patient")
        db_session.add(patient)
        db_session.commit()

        follow_up_time = now_sao_paulo() - timedelta(hours=1)
        follow_up_message = Message(
            patient_id=patient.id,
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content="Follow-up message",
            status=MessageStatus.PENDING,
            scheduled_for=follow_up_time,
            idempotency_key=f"followup-{uuid4()}",
            message_metadata={"follow_up_type": "empathetic_response"},
        )
        db_session.add(follow_up_message)
        db_session.commit()

        non_follow_up_message = Message(
            patient_id=patient.id,
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content="General message",
            status=MessageStatus.PENDING,
            scheduled_for=now_sao_paulo(),
            idempotency_key=f"nonfollowup-{uuid4()}",
            message_metadata={},
        )
        db_session.add(non_follow_up_message)
        db_session.commit()

        repo = MessageRepository(db_session)
        since = now_sao_paulo() - timedelta(hours=24)

        result = repo.get_recent_follow_up_message_time(patient.id, since)

        assert result is not None
        assert result == follow_up_time