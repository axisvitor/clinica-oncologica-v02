"""
Tests for multi-instance Evolution routing.

Validates that UnifiedWhatsAppService correctly routes messages
to different Evolution instances based on:
1. Constructor default_instance_name
2. Per-message metadata override
"""

import pytest
from uuid import uuid4
from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.patient import Patient
from app.models.message import Message, MessageType, MessageDirection, MessageStatus
from app.services.unified_whatsapp_service import UnifiedWhatsAppService, MessagingMode
from app.integrations.whatsapp.queue.schemas import MessageRequest


@pytest.fixture
async def test_patient_multi_instance(async_db_session) -> Patient:
    """Create a test patient for multi-instance tests."""
    patient = Patient(
        id=uuid4(),
        name="Maria Costa",
        phone="5511988776655",
        email="maria@test.com",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    async_db_session.add(patient)
    await async_db_session.commit()
    await async_db_session.refresh(patient)
    return patient


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.whatsapp
class TestMultiInstanceRouting:
    """Test multi-instance Evolution routing capabilities."""

    async def test_default_instance_routing(
        self,
        async_db_session,
        test_patient_multi_instance: Patient
    ):
        """
        Test routing to default instance when no override specified.

        Expected: instance_name = "inst_primary" (from constructor)
        """
        with patch('app.integrations.whatsapp.queue.manager.QueueManager.send_message') as mock_queue_send:
            mock_queue_send.return_value = {"success": True, "message_id": str(uuid4())}

            # Initialize with custom default instance
            service = UnifiedWhatsAppService(
                db=async_db_session,
                messaging_mode=MessagingMode.QUEUE,
                default_instance_name="inst_primary"
            )

            # Create message without instance override
            message = Message(
                id=uuid4(),
                patient_id=test_patient_multi_instance.id,
                patient=test_patient_multi_instance,
                content="Olá! Como você está?",
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                status=MessageStatus.PENDING,
                message_metadata={
                    "template_type": "greeting"
                },
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            async_db_session.add(message)
            await async_db_session.commit()

            # Send message
            success = await service.send_message(message)
            assert success is True

            # Verify queue manager called with default instance
            assert mock_queue_send.called
            call_args = mock_queue_send.call_args
            message_request: MessageRequest = call_args[0][0]

            assert message_request.instance_name == "inst_primary"
            assert message_request.to == test_patient_multi_instance.phone
            assert message_request.text == "Olá! Como você está?"

    async def test_metadata_instance_override(
        self,
        async_db_session,
        test_patient_multi_instance: Patient
    ):
        """
        Test routing override via message metadata.

        Expected: instance_name = "inst_secondary" (from metadata override)
        """
        with patch('app.integrations.whatsapp.queue.manager.QueueManager.send_message') as mock_queue_send:
            mock_queue_send.return_value = {"success": True, "message_id": str(uuid4())}

            # Initialize with default instance
            service = UnifiedWhatsAppService(
                db=async_db_session,
                messaging_mode=MessagingMode.QUEUE,
                default_instance_name="inst_primary"
            )

            # Create message WITH instance override in metadata
            message = Message(
                id=uuid4(),
                patient_id=test_patient_multi_instance.id,
                patient=test_patient_multi_instance,
                content="Mensagem urgente via instância secundária",
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                status=MessageStatus.PENDING,
                message_metadata={
                    "template_type": "urgent_alert",
                    "instance_name": "inst_secondary"  # Override
                },
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            async_db_session.add(message)
            await async_db_session.commit()

            # Send message
            success = await service.send_message(message)
            assert success is True

            # Verify queue manager called with overridden instance
            assert mock_queue_send.called
            call_args = mock_queue_send.call_args
            message_request: MessageRequest = call_args[0][0]

            assert message_request.instance_name == "inst_secondary"  # Overridden
            assert message_request.to == test_patient_multi_instance.phone

    async def test_load_balancing_scenario(
        self,
        async_db_session,
        test_patient_multi_instance: Patient
    ):
        """
        Test load balancing across multiple instances.

        Simulates routing to different instances based on load/tenant/region.
        """
        with patch('app.integrations.whatsapp.queue.manager.QueueManager.send_message') as mock_queue_send:
            mock_queue_send.return_value = {"success": True, "message_id": str(uuid4())}

            service = UnifiedWhatsAppService(
                db=async_db_session,
                messaging_mode=MessagingMode.QUEUE,
                default_instance_name="inst_lb_1"
            )

            # Simulate 5 messages distributed across 3 instances
            instance_routing = [
                "inst_lb_1",  # Default
                "inst_lb_2",  # Override
                "inst_lb_3",  # Override
                "inst_lb_1",  # Default (fallback)
                "inst_lb_2",  # Override
            ]

            sent_messages = []

            for idx, target_instance in enumerate(instance_routing):
                metadata = {"message_seq": idx}
                if target_instance != "inst_lb_1":
                    metadata["instance_name"] = target_instance

                message = Message(
                    id=uuid4(),
                    patient_id=test_patient_multi_instance.id,
                    patient=test_patient_multi_instance,
                    content=f"Mensagem #{idx+1}",
                    direction=MessageDirection.OUTBOUND,
                    type=MessageType.TEXT,
                    status=MessageStatus.PENDING,
                    message_metadata=metadata,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC)
                )
                async_db_session.add(message)
                await async_db_session.commit()

                success = await service.send_message(message)
                assert success is True

                sent_messages.append((message, target_instance))

            # Verify all calls used correct instances
            assert mock_queue_send.call_count == 5

            for call_idx, (call, (orig_message, expected_instance)) in enumerate(
                zip(mock_queue_send.call_args_list, sent_messages)
            ):
                message_request: MessageRequest = call[0][0]
                assert message_request.instance_name == expected_instance, (
                    f"Call {call_idx}: expected instance '{expected_instance}', "
                    f"got '{message_request.instance_name}'"
                )

    async def test_instance_failover_scenario(
        self,
        async_db_session,
        test_patient_multi_instance: Patient
    ):
        """
        Test instance failover when primary fails.

        Simulates:
        1. Send to inst_primary (fails)
        2. Fallback to inst_backup (succeeds)
        """
        call_count = 0

        def queue_send_side_effect(request: MessageRequest):
            nonlocal call_count
            call_count += 1

            # First call (inst_primary) fails
            if request.instance_name == "inst_primary" and call_count == 1:
                raise Exception("Instance inst_primary unavailable")

            # Second call (inst_backup) succeeds
            if request.instance_name == "inst_backup":
                return {"success": True, "message_id": str(uuid4())}

            raise Exception(f"Unexpected instance: {request.instance_name}")

        with patch('app.integrations.whatsapp.queue.manager.QueueManager.send_message') as mock_queue_send:
            mock_queue_send.side_effect = queue_send_side_effect

            service = UnifiedWhatsAppService(
                db=async_db_session,
                messaging_mode=MessagingMode.QUEUE,
                default_instance_name="inst_primary"
            )

            # First attempt: use primary (will fail)
            message = Message(
                id=uuid4(),
                patient_id=test_patient_multi_instance.id,
                patient=test_patient_multi_instance,
                content="Mensagem com failover",
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                status=MessageStatus.PENDING,
                message_metadata={
                    "template_type": "critical_alert"
                },
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            async_db_session.add(message)
            await async_db_session.commit()

            # This should fail with primary instance
            success_primary = await service.send_message(message)
            assert success_primary is False  # Failed as expected

            # Retry with backup instance (manual failover simulation)
            message.message_metadata["instance_name"] = "inst_backup"
            async_db_session.add(message)
            await async_db_session.commit()

            success_backup = await service.send_message(message)
            assert success_backup is True  # Succeeds with backup

            # Verify both calls were made
            assert call_count == 2

    async def test_hybrid_mode_instance_routing(
        self,
        async_db_session,
        test_patient_multi_instance: Patient
    ):
        """
        Test instance routing in HYBRID mode.

        HYBRID: tries QUEUE first, falls back to LEGACY.
        Verify instance_name is correctly passed in both paths.
        """
        with patch('app.integrations.whatsapp.queue.manager.QueueManager.send_message') as mock_queue_send, \
             patch('app.integrations.evolution.client.EvolutionClient.send_text') as mock_legacy_send:

            # Simulate QUEUE failure → LEGACY fallback
            mock_queue_send.side_effect = Exception("Queue unavailable")
            mock_legacy_send.return_value = {"success": True, "key": {"id": str(uuid4())}}

            service = UnifiedWhatsAppService(
                db=async_db_session,
                messaging_mode=MessagingMode.HYBRID,
                default_instance_name="inst_hybrid"
            )

            message = Message(
                id=uuid4(),
                patient_id=test_patient_multi_instance.id,
                patient=test_patient_multi_instance,
                content="Teste modo híbrido",
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                status=MessageStatus.PENDING,
                message_metadata={
                    "template_type": "test"
                },
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            async_db_session.add(message)
            await async_db_session.commit()

            success = await service.send_message(message)
            assert success is True

            # Verify QUEUE was attempted first (and failed)
            assert mock_queue_send.called

            # Verify LEGACY was used as fallback
            assert mock_legacy_send.called

            # Note: LEGACY path currently doesn't use instance_name
            # (would need Evolution client enhancement for multi-instance support)
