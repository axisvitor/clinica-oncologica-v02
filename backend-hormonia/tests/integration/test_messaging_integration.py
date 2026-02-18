"""
Integration Test: WhatsApp Messaging Integration

Tests the messaging system integration including:
- Message scheduling
- WhatsApp delivery
- Message templates
- Retry logic
"""

import pytest
from datetime import datetime, timezone
from uuid import UUID

from app.models.message import Message, MessageType, MessageStatus
from app.models.patient import Patient
from app.domain.messaging.core import MessageService


from app.utils.timezone import now_sao_paulo
@pytest.mark.integration
class TestMessagingIntegration:
    """Test WhatsApp messaging integration."""

    def test_message_creation_and_scheduling(
        self,
        real_db_session,
        sample_patient_data,
        cleanup_patients,
    ):
        """Test message creation and scheduling."""
        # Arrange - Create patient first
        valid_doctor_id = UUID("28844c5c-6bb8-484f-9502-b6a22c466745")

        patient = Patient(
            name=sample_patient_data["name"],
            doctor_id=valid_doctor_id,
        )
        patient.set_phone(sample_patient_data["phone"])

        real_db_session.add(patient)
        real_db_session.commit()
        cleanup_patients.track(patient.id)

        # Create message service
        message_service = MessageService(real_db_session)

        # Act - Schedule message
        message = message_service.schedule_message(
            patient_id=patient.id,
            content="Test welcome message",
            scheduled_for=now_sao_paulo(),
            message_type=MessageType.TEXT,
            message_metadata={"test": True},
        )

        # Assert
        assert message is not None
        assert message.id is not None
        assert message.patient_id == patient.id
        assert message.status == MessageStatus.PENDING
        assert message.content == "Test welcome message"

        # Verify persisted
        db_message = (
            real_db_session.query(Message)
            .filter(Message.id == message.id)
            .first()
        )
        assert db_message is not None
        assert db_message.message_metadata.get("test") is True

    def test_message_status_updates(
        self,
        real_db_session,
        sample_patient_data,
        cleanup_patients,
    ):
        """Test message status transitions."""
        # Arrange - Create patient and message
        valid_doctor_id = UUID("28844c5c-6bb8-484f-9502-b6a22c466745")

        patient = Patient(
            name=sample_patient_data["name"],
            doctor_id=valid_doctor_id,
        )
        patient.set_phone(sample_patient_data["phone"])

        real_db_session.add(patient)
        real_db_session.commit()
        cleanup_patients.track(patient.id)

        message_service = MessageService(real_db_session)

        message = message_service.schedule_message(
            patient_id=patient.id,
            content="Status test message",
            scheduled_for=now_sao_paulo(),
            message_type=MessageType.TEXT,
        )

        assert message.status == MessageStatus.PENDING

        # Act - Update to sent
        message_service.mark_as_sent(message.id, external_id="test_external_123")

        # Assert
        updated_message = (
            real_db_session.query(Message)
            .filter(Message.id == message.id)
            .first()
        )
        assert updated_message.status == MessageStatus.SENT
        assert updated_message.external_id == "test_external_123"
        assert updated_message.sent_at is not None

    def test_message_patient_relationship(
        self,
        real_db_session,
        sample_patient_data,
        cleanup_patients,
    ):
        """Test message-patient relationship and lazy loading."""
        # Arrange
        valid_doctor_id = UUID("28844c5c-6bb8-484f-9502-b6a22c466745")

        patient = Patient(
            name=sample_patient_data["name"],
            doctor_id=valid_doctor_id,
        )
        patient.set_phone(sample_patient_data["phone"])

        real_db_session.add(patient)
        real_db_session.commit()
        cleanup_patients.track(patient.id)

        message_service = MessageService(real_db_session)

        # Create message
        message = message_service.schedule_message(
            patient_id=patient.id,
            content="Relationship test",
            scheduled_for=now_sao_paulo(),
            message_type=MessageType.TEXT,
        )

        # Act - Access patient via relationship
        message_patient = message.patient

        # Assert
        assert message_patient is not None
        assert message_patient.id == patient.id
        assert message_patient.name == patient.name

    def test_message_cascade_deletion_with_patient(
        self,
        real_db_session,
        sample_patient_data,
    ):
        """Test messages are cascade deleted when patient is deleted."""
        # Arrange
        valid_doctor_id = UUID("28844c5c-6bb8-484f-9502-b6a22c466745")

        patient = Patient(
            name=sample_patient_data["name"],
            doctor_id=valid_doctor_id,
        )
        patient.set_phone(sample_patient_data["phone"])

        real_db_session.add(patient)
        real_db_session.commit()

        message_service = MessageService(real_db_session)

        # Create messages
        message1 = message_service.schedule_message(
            patient_id=patient.id,
            content="Message 1",
            scheduled_for=now_sao_paulo(),
            message_type=MessageType.TEXT,
        )

        message2 = message_service.schedule_message(
            patient_id=patient.id,
            content="Message 2",
            scheduled_for=now_sao_paulo(),
            message_type=MessageType.TEXT,
        )

        message1_id = message1.id
        message2_id = message2.id
        patient_id = patient.id

        # Act - Delete patient
        real_db_session.delete(patient)
        real_db_session.commit()

        # Assert - Messages should be cascade deleted
        remaining_messages = (
            real_db_session.query(Message)
            .filter(Message.patient_id == patient_id)
            .all()
        )
        assert len(remaining_messages) == 0, "Messages should be cascade deleted"

    def test_message_metadata_jsonb_operations(
        self,
        real_db_session,
        sample_patient_data,
        cleanup_patients,
    ):
        """Test JSONB metadata operations on messages."""
        # Arrange
        valid_doctor_id = UUID("28844c5c-6bb8-484f-9502-b6a22c466745")

        patient = Patient(
            name=sample_patient_data["name"],
            doctor_id=valid_doctor_id,
        )
        patient.set_phone(sample_patient_data["phone"])

        real_db_session.add(patient)
        real_db_session.commit()
        cleanup_patients.track(patient.id)

        message_service = MessageService(real_db_session)

        # Create message with complex metadata
        metadata = {
            "message_type": "welcome",
            "template_version": "v2.0",
            "variables": {
                "patient_name": patient.name,
                "clinic_name": "Test Clinic",
            },
            "tags": ["onboarding", "automated"],
        }

        message = message_service.schedule_message(
            patient_id=patient.id,
            content="Metadata test",
            scheduled_for=now_sao_paulo(),
            message_type=MessageType.TEXT,
            message_metadata=metadata,
        )

        # Assert - Metadata is properly stored and retrieved
        db_message = (
            real_db_session.query(Message)
            .filter(Message.id == message.id)
            .first()
        )

        assert db_message.message_metadata is not None
        assert db_message.message_metadata["message_type"] == "welcome"
        assert db_message.message_metadata["template_version"] == "v2.0"
        assert "patient_name" in db_message.message_metadata["variables"]
        assert "onboarding" in db_message.message_metadata["tags"]

    def test_pending_messages_query(
        self,
        real_db_session,
        sample_patient_data,
        cleanup_patients,
    ):
        """Test querying pending messages for retry logic."""
        # Arrange
        valid_doctor_id = UUID("28844c5c-6bb8-484f-9502-b6a22c466745")

        patient = Patient(
            name=sample_patient_data["name"],
            doctor_id=valid_doctor_id,
        )
        patient.set_phone(sample_patient_data["phone"])

        real_db_session.add(patient)
        real_db_session.commit()
        cleanup_patients.track(patient.id)

        message_service = MessageService(real_db_session)

        # Create pending and sent messages
        pending_msg = message_service.schedule_message(
            patient_id=patient.id,
            content="Pending message",
            scheduled_for=now_sao_paulo(),
            message_type=MessageType.TEXT,
        )

        sent_msg = message_service.schedule_message(
            patient_id=patient.id,
            content="Sent message",
            scheduled_for=now_sao_paulo(),
            message_type=MessageType.TEXT,
        )
        message_service.mark_as_sent(sent_msg.id, "external_123")

        # Act - Query pending messages
        pending_messages = (
            real_db_session.query(Message)
            .filter(
                Message.patient_id == patient.id,
                Message.status == MessageStatus.PENDING,
            )
            .all()
        )

        # Assert
        assert len(pending_messages) == 1
        assert pending_messages[0].id == pending_msg.id
        assert pending_messages[0].content == "Pending message"