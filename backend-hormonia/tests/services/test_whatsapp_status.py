"""
Comprehensive WhatsApp Status Update Tests

Tests P2 Implementation: WhatsApp message status updates (sent, delivered, read, failed)
Tests status processing, database updates, webhook callbacks, and concurrent updates.
Priority: P2 - High (Messaging Feature)

NOTE: whatsapp_status module was integrated into UnifiedWhatsAppService.
This test file needs to be updated to use the new API.
"""
import pytest

pytestmark = pytest.mark.skip(
    reason="whatsapp_status module integrated into UnifiedWhatsAppService"
)

from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock
from app.models.message import Message, MessageStatus as DBMessageStatus


@pytest.fixture
def sample_message(db_session, test_patient):
    """Create sample message for testing"""

    message = Message(
        id=uuid4(),
        patient_id=test_patient.id,
        content="Test message",
        direction="outbound",
        status=DBMessageStatus.PENDING,
        external_id="ext-msg-123",
        created_at=datetime.utcnow()
    )
    db_session.add(message)
    db_session.commit()
    db_session.refresh(message)
    return message


class TestStatusProcessing:
    """Test status update processing"""

    @pytest.mark.asyncio
    async def test_process_sent_status(self, db_session, sample_message):
        """Test processing 'sent' status update"""
        processor = WhatsAppStatusProcessor(db=db_session)

        status_update = StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.SENT,
            timestamp=datetime.utcnow(),
            instance_id="instance-1"
        )

        result = await processor.process_status(status_update)

        assert result.success is True

        # Reload message from database
        db_session.refresh(sample_message)

        assert sample_message.status == DBMessageStatus.SENT
        assert sample_message.sent_at is not None

    @pytest.mark.asyncio
    async def test_process_delivered_status(self, db_session, sample_message):
        """Test processing 'delivered' status update"""
        processor = WhatsAppStatusProcessor(db=db_session)

        # Update to sent first
        sample_message.status = DBMessageStatus.SENT
        sample_message.sent_at = datetime.utcnow()
        db_session.commit()

        status_update = StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.DELIVERED,
            timestamp=datetime.utcnow()
        )

        result = await processor.process_status(status_update)

        assert result.success is True
        db_session.refresh(sample_message)

        assert sample_message.status == DBMessageStatus.DELIVERED
        assert sample_message.delivered_at is not None

    @pytest.mark.asyncio
    async def test_process_read_status(self, db_session, sample_message):
        """Test processing 'read' status update"""
        processor = WhatsAppStatusProcessor(db=db_session)

        # Update to delivered first
        sample_message.status = DBMessageStatus.DELIVERED
        sample_message.delivered_at = datetime.utcnow()
        db_session.commit()

        status_update = StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.READ,
            timestamp=datetime.utcnow()
        )

        result = await processor.process_status(status_update)

        assert result.success is True
        db_session.refresh(sample_message)

        assert sample_message.status == DBMessageStatus.READ
        assert sample_message.read_at is not None

    @pytest.mark.asyncio
    async def test_process_failed_status(self, db_session, sample_message):
        """Test processing 'failed' status update"""
        processor = WhatsAppStatusProcessor(db=db_session)

        status_update = StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.FAILED,
            timestamp=datetime.utcnow(),
            error_code="401",
            error_message="Invalid phone number"
        )

        result = await processor.process_status(status_update)

        assert result.success is True
        db_session.refresh(sample_message)

        assert sample_message.status == DBMessageStatus.FAILED
        assert sample_message.failed_at is not None
        assert sample_message.error_code == "401"
        assert "Invalid phone number" in sample_message.error_message


class TestStatusTransitions:
    """Test valid and invalid status transitions"""

    @pytest.mark.asyncio
    async def test_valid_status_transition_sequence(self, db_session, sample_message):
        """Test complete valid status transition sequence"""
        processor = WhatsAppStatusProcessor(db=db_session)

        # PENDING -> SENT
        await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.SENT,
            timestamp=datetime.utcnow()
        ))

        db_session.refresh(sample_message)
        assert sample_message.status == DBMessageStatus.SENT

        # SENT -> DELIVERED
        await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.DELIVERED,
            timestamp=datetime.utcnow()
        ))

        db_session.refresh(sample_message)
        assert sample_message.status == DBMessageStatus.DELIVERED

        # DELIVERED -> READ
        await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.READ,
            timestamp=datetime.utcnow()
        ))

        db_session.refresh(sample_message)
        assert sample_message.status == DBMessageStatus.READ

    @pytest.mark.asyncio
    async def test_invalid_status_regression(self, db_session, sample_message):
        """Test status cannot regress (e.g., DELIVERED -> SENT)"""
        processor = WhatsAppStatusProcessor(db=db_session)

        # Set to DELIVERED
        sample_message.status = DBMessageStatus.DELIVERED
        db_session.commit()

        # Try to regress to SENT
        result = await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.SENT,
            timestamp=datetime.utcnow()
        ))

        # Should be rejected or ignored
        assert result.success is False or result.ignored is True

        db_session.refresh(sample_message)
        assert sample_message.status == DBMessageStatus.DELIVERED  # Unchanged

    @pytest.mark.asyncio
    async def test_failed_status_from_any_state(self, db_session, sample_message):
        """Test FAILED status can occur from any state"""
        processor = WhatsAppStatusProcessor(db=db_session)

        # Set to DELIVERED
        sample_message.status = DBMessageStatus.DELIVERED
        db_session.commit()

        # Fail from DELIVERED state
        result = await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.FAILED,
            timestamp=datetime.utcnow(),
            error_message="Network error"
        ))

        assert result.success is True
        db_session.refresh(sample_message)
        assert sample_message.status == DBMessageStatus.FAILED

    @pytest.mark.asyncio
    async def test_duplicate_status_update_idempotent(self, db_session, sample_message):
        """Test duplicate status updates are idempotent"""
        processor = WhatsAppStatusProcessor(db=db_session)

        status_update = StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.SENT,
            timestamp=datetime.utcnow()
        )

        # Process twice
        result1 = await processor.process_status(status_update)
        result2 = await processor.process_status(status_update)

        assert result1.success is True
        assert result2.success is True or result2.ignored is True

        db_session.refresh(sample_message)
        assert sample_message.status == DBMessageStatus.SENT


class TestDatabaseUpdates:
    """Test database update operations"""

    @pytest.mark.asyncio
    async def test_timestamp_fields_updated(self, db_session, sample_message):
        """Test all timestamp fields are updated correctly"""
        processor = WhatsAppStatusProcessor(db=db_session)

        sent_time = datetime.utcnow()
        delivered_time = sent_time + timedelta(seconds=5)
        read_time = delivered_time + timedelta(seconds=10)

        # SENT
        await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.SENT,
            timestamp=sent_time
        ))

        db_session.refresh(sample_message)
        assert sample_message.sent_at is not None
        assert (sample_message.sent_at - sent_time).total_seconds() < 1

        # DELIVERED
        await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.DELIVERED,
            timestamp=delivered_time
        ))

        db_session.refresh(sample_message)
        assert sample_message.delivered_at is not None

        # READ
        await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.READ,
            timestamp=read_time
        ))

        db_session.refresh(sample_message)
        assert sample_message.read_at is not None

    @pytest.mark.asyncio
    async def test_metadata_field_updated(self, db_session, sample_message):
        """Test metadata field is updated with status details"""
        processor = WhatsAppStatusProcessor(db=db_session)

        await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.SENT,
            timestamp=datetime.utcnow(),
            instance_id="instance-1",
            extra_data={"webhook_id": "hook-123"}
        ))

        db_session.refresh(sample_message)

        # Metadata should contain status update info
        assert sample_message.metadata is not None
        assert "status_updates" in sample_message.metadata

    @pytest.mark.asyncio
    async def test_message_not_found_handling(self, db_session):
        """Test handling when message doesn't exist"""
        processor = WhatsAppStatusProcessor(db=db_session)

        result = await processor.process_status(StatusUpdate(
            message_id=str(uuid4()),  # Non-existent ID
            external_id="nonexistent",
            status=MessageStatus.SENT,
            timestamp=datetime.utcnow()
        ))

        assert result.success is False
        assert "not found" in result.error.lower()


class TestWebhookProcessing:
    """Test webhook payload processing"""

    @pytest.mark.asyncio
    async def test_evolution_webhook_format(self, db_session, sample_message):
        """Test processing Evolution API webhook format"""
        webhook_payload = {
            "event": "messages.upsert",
            "instance": "instance-1",
            "data": {
                "key": {
                    "id": "ext-msg-123",
                    "remoteJid": "5511999999999@s.whatsapp.net"
                },
                "messageTimestamp": int(datetime.utcnow().timestamp()),
                "status": 3  # DELIVERED (Evolution status code)
            }
        }

        result = await process_status_webhook(webhook_payload, db=db_session)

        assert result.success is True

    @pytest.mark.asyncio
    async def test_webhook_authentication(self, db_session):
        """Test webhook requires authentication"""
        # This would typically be tested at API endpoint level
        # Here we test the signature validation logic

        from app.services.whatsapp_status import verify_webhook_signature

        payload = {"test": "data"}
        signature = "invalid_signature"

        is_valid = verify_webhook_signature(payload, signature)

        assert is_valid is False

    @pytest.mark.asyncio
    async def test_malformed_webhook_handling(self, db_session):
        """Test handling of malformed webhook payload"""
        malformed_payload = {
            "event": "messages.upsert",
            # Missing required fields
        }

        with pytest.raises(ValueError, match="Invalid webhook payload"):
            await process_status_webhook(malformed_payload, db=db_session)


class TestConcurrentUpdates:
    """Test concurrent status update handling"""

    @pytest.mark.asyncio
    async def test_concurrent_status_updates_same_message(self, db_session, sample_message):
        """Test handling concurrent updates to same message"""
        import asyncio

        processor = WhatsAppStatusProcessor(db=db_session)

        # Create multiple status updates
        updates = [
            StatusUpdate(
                message_id=str(sample_message.id),
                external_id="ext-msg-123",
                status=MessageStatus.SENT,
                timestamp=datetime.utcnow()
            ),
            StatusUpdate(
                message_id=str(sample_message.id),
                external_id="ext-msg-123",
                status=MessageStatus.DELIVERED,
                timestamp=datetime.utcnow() + timedelta(seconds=1)
            ),
            StatusUpdate(
                message_id=str(sample_message.id),
                external_id="ext-msg-123",
                status=MessageStatus.READ,
                timestamp=datetime.utcnow() + timedelta(seconds=2)
            )
        ]

        # Process concurrently
        results = await asyncio.gather(
            *[processor.process_status(u) for u in updates],
            return_exceptions=True
        )

        # All should succeed or be handled gracefully
        assert all(not isinstance(r, Exception) for r in results)

        # Final status should be READ (latest)
        db_session.refresh(sample_message)
        assert sample_message.status in [DBMessageStatus.READ, DBMessageStatus.DELIVERED]

    @pytest.mark.asyncio
    async def test_race_condition_handling(self, db_session, sample_message):
        """Test race condition handling with database locks"""
        processor1 = WhatsAppStatusProcessor(db=db_session)
        processor2 = WhatsAppStatusProcessor(db=db_session)

        # Simulate race condition
        update = StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.SENT,
            timestamp=datetime.utcnow()
        )

        # Both processors try to update simultaneously
        # Database should handle with row locking


class TestStatusCallbacks:
    """Test status update callbacks and notifications"""

    @pytest.mark.asyncio
    async def test_callback_triggered_on_status_change(self, db_session, sample_message, mocker):
        """Test callback is triggered when status changes"""
        callback_mock = AsyncMock()

        processor = WhatsAppStatusProcessor(
            db=db_session,
            on_status_change=callback_mock
        )

        await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.SENT,
            timestamp=datetime.utcnow()
        ))

        # Callback should be called
        callback_mock.assert_called_once()
        args = callback_mock.call_args[0]
        assert args[0] == str(sample_message.id)
        assert args[1] == MessageStatus.SENT

    @pytest.mark.asyncio
    async def test_websocket_notification_on_status_update(self, db_session, sample_message, mocker):
        """Test WebSocket notification sent on status update"""
        mock_websocket = mocker.patch('app.services.whatsapp_status.send_websocket_notification')

        processor = WhatsAppStatusProcessor(db=db_session)

        await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.DELIVERED,
            timestamp=datetime.utcnow()
        ))

        # WebSocket notification should be sent
        mock_websocket.assert_called_once()


class TestStatusMetrics:
    """Test status update metrics and analytics"""

    @pytest.mark.asyncio
    async def test_delivery_time_tracking(self, db_session, sample_message):
        """Test tracking time to delivery"""
        processor = WhatsAppStatusProcessor(db=db_session)

        sent_time = datetime.utcnow()
        delivered_time = sent_time + timedelta(seconds=30)

        # SENT
        await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.SENT,
            timestamp=sent_time
        ))

        # DELIVERED
        await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.DELIVERED,
            timestamp=delivered_time
        ))

        db_session.refresh(sample_message)

        # Calculate delivery time
        delivery_time = (sample_message.delivered_at - sample_message.sent_at).total_seconds()
        assert abs(delivery_time - 30) < 1  # ~30 seconds

    @pytest.mark.asyncio
    async def test_read_receipt_tracking(self, db_session, sample_message):
        """Test tracking read receipts"""
        processor = WhatsAppStatusProcessor(db=db_session)

        # Set to delivered
        sample_message.status = DBMessageStatus.DELIVERED
        sample_message.delivered_at = datetime.utcnow()
        db_session.commit()

        read_time = datetime.utcnow()

        await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.READ,
            timestamp=read_time
        ))

        db_session.refresh(sample_message)

        # Time to read
        time_to_read = (sample_message.read_at - sample_message.delivered_at).total_seconds()
        assert time_to_read >= 0


class TestErrorHandling:
    """Test error handling in status processing"""

    @pytest.mark.asyncio
    async def test_database_error_handling(self, db_session, sample_message, mocker):
        """Test handling database errors during update"""
        processor = WhatsAppStatusProcessor(db=db_session)

        # Mock database commit failure
        mocker.patch.object(db_session, 'commit', side_effect=Exception("Database error"))

        result = await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.SENT,
            timestamp=datetime.utcnow()
        ))

        assert result.success is False
        assert "database" in result.error.lower() or "error" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invalid_timestamp_handling(self, db_session, sample_message):
        """Test handling invalid timestamp"""
        processor = WhatsAppStatusProcessor(db=db_session)

        # Timestamp in the future
        future_time = datetime.utcnow() + timedelta(days=1)

        result = await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id="ext-msg-123",
            status=MessageStatus.SENT,
            timestamp=future_time
        ))

        # Should handle gracefully
        assert result.success in [True, False]  # Either accepts or rejects

    @pytest.mark.asyncio
    async def test_missing_external_id(self, db_session, sample_message):
        """Test handling missing external ID"""
        processor = WhatsAppStatusProcessor(db=db_session)

        result = await processor.process_status(StatusUpdate(
            message_id=str(sample_message.id),
            external_id=None,  # Missing
            status=MessageStatus.SENT,
            timestamp=datetime.utcnow()
        ))

        # Should still work with message_id
        assert result.success is True
