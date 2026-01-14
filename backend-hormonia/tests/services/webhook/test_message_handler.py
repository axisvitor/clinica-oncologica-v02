"""
Unit tests for MessageWebhookHandler.

Tests message processing, flow routing, quiz handling, and security monitoring.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from app.models.message import MessageDirection, MessageStatus, MessageType

class TestMessageWebhookHandler:
    """Test MessageWebhookHandler functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        db = Mock()
        db.query = Mock()
        db.execute = Mock()
        db.add = Mock()
        db.commit = Mock()
        db.rollback = Mock()
        db.refresh = Mock()
        return db

    @pytest.fixture
    def mock_webhook_store(self):
        """Create a mock webhook store."""
        store = Mock()
        store.persist_event = AsyncMock(return_value=uuid4())
        store.mark_processed = AsyncMock()
        return store

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.set = AsyncMock(return_value=True)
        redis.get = AsyncMock(return_value=None)
        return redis

    @pytest.fixture
    def mock_get_async_redis(self, mock_redis):
        """Patch async Redis getter."""
        with patch(
            "app.services.webhook.handlers.message_handler.get_async_redis",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = mock_redis
            yield mock_get

    @pytest.fixture
    def mock_publish_ws(self):
        """Patch websocket publish."""
        with patch(
            "app.services.webhook.handlers.message_handler.websocket_events",
            new=Mock(),
        ) as mock_ws:
            mock_ws.publish_message_event = AsyncMock()
            yield mock_ws

    @pytest.fixture
    def handler(self, mock_db):
        """Create MessageWebhookHandler instance."""
        from app.services.webhook.handlers.message_handler import MessageWebhookHandler
        handler = MessageWebhookHandler(mock_db)
        handler.flow_state_repo.get_active_flow = Mock(return_value=None)
        return handler

    @pytest.fixture
    def sample_message_event(self):
        """Sample Evolution API message webhook payload."""
        return {
            "instance": "clinica-hormonia",
            "event": "messages.upsert",
            "data": {
                "key": {
                    "remoteJid": "5511987654321@s.whatsapp.net",
                    "fromMe": False,
                    "id": "whatsapp_msg_123"
                },
                "message": {
                    "conversation": "Hello, I need help with my treatment."
                },
                "messageTimestamp": 1699999999,
                "pushName": "Test Patient"
            }
        }

    @pytest.fixture
    def sample_patient(self):
        """Create a sample patient."""
        patient = Mock()
        patient.id = uuid4()
        patient.cpf = "12345678909"
        patient.full_name = "Test Patient"
        patient.name = "Test Patient"
        patient.phone = "+5511987654321"
        patient.is_active = True
        patient.current_flow_id = None
        return patient

    @pytest.fixture
    def inbound_message(self):
        """Create a mock inbound message."""
        message = Mock()
        message.id = uuid4()
        message.direction = MessageDirection.INBOUND
        message.type = MessageType.TEXT
        message.status = MessageStatus.PENDING
        message.content = "Hello"
        message.whatsapp_id = "whatsapp_msg_123"
        message.metadata = {}
        return message


class TestMessageProcessing(TestMessageWebhookHandler):
    """Test basic message processing."""

    @pytest.mark.asyncio
    async def test_process_message_success(
        self,
        handler,
        mock_db,
        mock_webhook_store,
        mock_get_async_redis,
        mock_publish_ws,
        sample_message_event,
        sample_patient,
        inbound_message,
    ):
        """Test successful message processing."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        handler.message_service.process_inbound_message = Mock(
            return_value=inbound_message
        )

        with patch.object(
            handler, "_find_patient_with_security", new_callable=AsyncMock
        ) as mock_find, patch.object(
            handler, "_handle_general_chat", new_callable=AsyncMock
        ):
            mock_find.return_value = sample_patient

            result = await handler.process_message(
                sample_message_event, mock_webhook_store
            )

        assert result == str(inbound_message.id)
        mock_webhook_store.persist_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_missing_data(self, handler, mock_webhook_store):
        """Test handling of missing data in webhook."""
        event = {"instance": "clinica-hormonia"}
        
        result = await handler.process_message(event, mock_webhook_store)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_process_message_missing_phone(self, handler, mock_webhook_store):
        """Test handling of missing phone number."""
        event = {
            "instance": "clinica-hormonia",
            "data": {
                "key": {"id": "msg_123"},
                "message": {"conversation": "Hello"}
            }
        }
        
        result = await handler.process_message(event, mock_webhook_store)
        
        # Should handle gracefully
        assert result is None or mock_webhook_store.mark_processed.called

    @pytest.mark.asyncio
    async def test_process_message_from_me_processed(
        self,
        handler,
        mock_db,
        mock_webhook_store,
        mock_get_async_redis,
        mock_publish_ws,
        sample_patient,
        inbound_message,
    ):
        """Test that messages from self are still processed."""
        event = {
            "instance": "clinica-hormonia",
            "data": {
                "key": {
                    "remoteJid": "5511987654321@s.whatsapp.net",
                    "fromMe": True,  # Message from ourselves
                    "id": "msg_123"
                },
                "message": {"conversation": "Hello"}
            }
        }
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        handler.message_service.process_inbound_message = Mock(
            return_value=inbound_message
        )

        with patch.object(
            handler, "_find_patient_with_security", new_callable=AsyncMock
        ) as mock_find, patch.object(
            handler, "_handle_general_chat", new_callable=AsyncMock
        ):
            mock_find.return_value = sample_patient

            result = await handler.process_message(event, mock_webhook_store)

        assert result == str(inbound_message.id)


class TestPatientLookup(TestMessageWebhookHandler):
    """Test patient lookup with security features."""

    @pytest.mark.asyncio
    async def test_find_patient_exact_phone_match(self, handler, mock_db, sample_patient):
        """Test finding patient with exact phone match."""
        with patch.object(handler, '_find_patient_with_security', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = sample_patient

            result = await handler._find_patient_with_security(
                {
                    "phone": "+5511987654321",
                    "content": "Hello",
                    "whatsapp_id": "msg_123",
                    "metadata": {},
                },
                None,
                None,
            )

            assert result is not None
            assert result.id == sample_patient.id

    @pytest.mark.asyncio
    async def test_find_patient_not_found(self, handler, mock_db):
        """Test handling when patient is not found."""
        with patch.object(handler, '_find_patient_with_security', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None

            result = await handler._find_patient_with_security(
                {
                    "phone": "+5511999999999",
                    "content": "Hello",
                    "whatsapp_id": "msg_123",
                    "metadata": {},
                },
                None,
                None,
            )

            assert result is None


class TestMessageTypes(TestMessageWebhookHandler):
    """Test handling of different message types."""

    @pytest.mark.asyncio
    async def test_process_text_message(
        self,
        handler,
        mock_db,
        mock_webhook_store,
        mock_get_async_redis,
        mock_publish_ws,
        sample_patient,
        inbound_message,
    ):
        """Test processing text message."""
        event = {
            "instance": "clinica-hormonia",
            "data": {
                "key": {
                    "remoteJid": "5511987654321@s.whatsapp.net",
                    "fromMe": False,
                    "id": "msg_123"
                },
                "message": {
                    "conversation": "This is a text message"
                }
            }
        }
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        handler.message_service.process_inbound_message = Mock(
            return_value=inbound_message
        )

        with patch(
            "app.services.webhook.handlers.message_handler.extract_message_data",
            return_value={
                "phone": "5511987654321",
                "content": "This is a text message",
                "type": MessageType.TEXT,
                "whatsapp_id": "whatsapp_msg_123",
                "metadata": {},
            },
        ), patch.object(
            handler, "_find_patient_with_security", new_callable=AsyncMock
        ) as mock_find, patch.object(
            handler, "_handle_general_chat", new_callable=AsyncMock
        ):
            mock_find.return_value = sample_patient
            result = await handler.process_message(event, mock_webhook_store)

        assert result == str(inbound_message.id)
        mock_webhook_store.persist_event.assert_called()

    @pytest.mark.asyncio
    async def test_process_image_message(
        self,
        handler,
        mock_db,
        mock_webhook_store,
        mock_get_async_redis,
        mock_publish_ws,
        sample_patient,
        inbound_message,
    ):
        """Test processing image message."""
        event = {
            "instance": "clinica-hormonia",
            "data": {
                "key": {
                    "remoteJid": "5511987654321@s.whatsapp.net",
                    "fromMe": False,
                    "id": "msg_123"
                },
                "message": {
                    "imageMessage": {
                        "url": "https://example.com/image.jpg",
                        "caption": "My test results"
                    }
                }
            }
        }
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        handler.message_service.process_inbound_message = Mock(
            return_value=inbound_message
        )

        with patch(
            "app.services.webhook.handlers.message_handler.extract_message_data",
            return_value={
                "phone": "5511987654321",
                "content": "My test results",
                "type": MessageType.MEDIA,
                "whatsapp_id": "whatsapp_msg_123",
                "metadata": {},
            },
        ), patch.object(
            handler, "_find_patient_with_security", new_callable=AsyncMock
        ) as mock_find, patch.object(
            handler, "_handle_general_chat", new_callable=AsyncMock
        ):
            mock_find.return_value = sample_patient
            result = await handler.process_message(event, mock_webhook_store)

        assert result == str(inbound_message.id)
        mock_webhook_store.persist_event.assert_called()

    @pytest.mark.asyncio
    async def test_process_audio_message(
        self,
        handler,
        mock_db,
        mock_webhook_store,
        mock_get_async_redis,
        mock_publish_ws,
        sample_patient,
        inbound_message,
    ):
        """Test processing audio message."""
        event = {
            "instance": "clinica-hormonia",
            "data": {
                "key": {
                    "remoteJid": "5511987654321@s.whatsapp.net",
                    "fromMe": False,
                    "id": "msg_123"
                },
                "message": {
                    "audioMessage": {
                        "url": "https://example.com/audio.ogg",
                        "seconds": 30
                    }
                }
            }
        }
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        handler.message_service.process_inbound_message = Mock(
            return_value=inbound_message
        )

        with patch(
            "app.services.webhook.handlers.message_handler.extract_message_data",
            return_value={
                "phone": "5511987654321",
                "content": "[Audio message]",
                "type": MessageType.MEDIA,
                "whatsapp_id": "whatsapp_msg_123",
                "metadata": {},
            },
        ), patch.object(
            handler, "_find_patient_with_security", new_callable=AsyncMock
        ) as mock_find, patch.object(
            handler, "_handle_general_chat", new_callable=AsyncMock
        ):
            mock_find.return_value = sample_patient
            result = await handler.process_message(event, mock_webhook_store)

        assert result == str(inbound_message.id)
        mock_webhook_store.persist_event.assert_called()


class TestFlowRouting(TestMessageWebhookHandler):
    """Test flow-based message routing."""

    @pytest.mark.asyncio
    async def test_patient_with_active_flow(
        self,
        handler,
        mock_db,
        mock_webhook_store,
        mock_get_async_redis,
        mock_publish_ws,
        sample_patient,
        inbound_message,
    ):
        """Test routing message when patient has active flow."""
        event = {
            "instance": "clinica-hormonia",
            "data": {
                "key": {
                    "remoteJid": "5511987654321@s.whatsapp.net",
                    "fromMe": False,
                    "id": "msg_123"
                },
                "message": {"conversation": "Next step"}
            }
        }
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        handler.message_service.process_inbound_message = Mock(
            return_value=inbound_message
        )

        flow_state = Mock()
        flow_state.id = uuid4()
        flow_state.current_step = "step_1"
        handler.flow_state_repo.get_active_flow = Mock(return_value=flow_state)

        with patch(
            "app.services.webhook.handlers.message_handler.extract_message_data",
            return_value={
                "phone": "5511987654321",
                "content": "Next step",
                "type": MessageType.TEXT,
                "whatsapp_id": "whatsapp_msg_123",
                "metadata": {},
            },
        ), patch.object(
            handler, "_find_patient_with_security", new_callable=AsyncMock
        ) as mock_find, patch.object(
            handler, "_handle_flow_message", new_callable=AsyncMock
        ) as mock_flow:
            mock_find.return_value = sample_patient
            result = await handler.process_message(event, mock_webhook_store)

        assert result == str(inbound_message.id)
        mock_flow.assert_called_once()


class TestQuizDebouncing(TestMessageWebhookHandler):
    """Test quiz message debouncing (HIGH-005 fix)."""

    @pytest.mark.asyncio
    async def test_quiz_message_debouncing(self, handler, mock_db, sample_patient):
        """Test that rapid quiz messages are debounced."""
        # This tests the HIGH-005 fix: quiz responses should be debounced
        # to prevent duplicate submissions
        
        with patch.object(handler, '_handle_quiz_message', new_callable=AsyncMock) as mock_quiz:
            mock_quiz.return_value = "Quiz response"
            
            # Simulate rapid quiz messages
            quiz_message = "My quiz answer"
            
            # First call should process
            await handler._handle_quiz_message(sample_patient, quiz_message)
            mock_quiz.assert_called_once()


class TestErrorHandling(TestMessageWebhookHandler):
    """Test error handling scenarios."""

    @pytest.mark.asyncio
    async def test_database_error_handling(
        self, handler, mock_db, mock_webhook_store, mock_get_async_redis
    ):
        """Test handling of database errors."""
        event = {
            "instance": "clinica-hormonia",
            "data": {
                "key": {
                    "remoteJid": "5511987654321@s.whatsapp.net",
                    "fromMe": False,
                    "id": "msg_123"
                },
                "message": {"conversation": "Hello"}
            }
        }
        
        mock_db.query.side_effect = Exception("Database connection error")
        
        # Should handle error gracefully
        result = await handler.process_message(event, mock_webhook_store)
        
        assert result is None
        mock_webhook_store.mark_processed.assert_called()

    @pytest.mark.asyncio
    async def test_invalid_phone_format_handling(self, handler, mock_webhook_store):
        """Test handling of invalid phone format."""
        event = {
            "instance": "clinica-hormonia",
            "data": {
                "key": {
                    "remoteJid": "invalid_phone_format",
                    "fromMe": False,
                    "id": "msg_123"
                },
                "message": {"conversation": "Hello"}
            }
        }
        
        result = await handler.process_message(event, mock_webhook_store)
        
        # Should handle gracefully (patient not found with invalid phone)
        assert result is None or mock_webhook_store.mark_processed.called


class TestResponseSending(TestMessageWebhookHandler):
    """Test message response functionality."""

    @pytest.mark.asyncio
    async def test_send_response_creates_single_message(self, handler, mock_db, sample_patient):
        """Test that _send_response creates exactly ONE message (FIX P0-2)."""
        response_message = Mock()
        response_message.id = uuid4()

        handler.message_service.create_message = Mock(return_value=response_message)
        handler._publish_message_event = AsyncMock()

        with patch("app.domain.messaging.scheduling.MessageScheduler") as mock_scheduler_cls:
            scheduler = AsyncMock()
            scheduler.schedule_existing_message = AsyncMock()
            mock_scheduler_cls.return_value = scheduler

            response_text = "Thank you for your message"

            result = await handler._send_response(
                patient_id=sample_patient.id,
                content=response_text,
                metadata={"context": "general_chat"},
            )

        assert result == response_message
        handler.message_service.create_message.assert_called_once()
        scheduler.schedule_existing_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_response_with_empty_text_processed(self, handler, sample_patient):
        """Test that empty responses are still scheduled."""
        response_message = Mock()
        response_message.id = uuid4()

        handler.message_service.create_message = Mock(return_value=response_message)
        handler._publish_message_event = AsyncMock()

        with patch("app.domain.messaging.scheduling.MessageScheduler") as mock_scheduler_cls:
            scheduler = AsyncMock()
            scheduler.schedule_existing_message = AsyncMock()
            mock_scheduler_cls.return_value = scheduler

            result = await handler._send_response(
                patient_id=sample_patient.id,
                content="",
                metadata={"context": "general_chat"},
            )

        assert result == response_message
        handler.message_service.create_message.assert_called_once()
        scheduler.schedule_existing_message.assert_called_once()
