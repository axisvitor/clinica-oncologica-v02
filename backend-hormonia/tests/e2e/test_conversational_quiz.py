"""
End-to-end tests for conversational quiz flow.

Tests the complete flow:
1. Template seeding → Session start
2. Intro/question sent via UnifiedWhatsAppService
3. Evolution webhook inbound → response processing
4. QuizResponse persisted, session advanced/completed
5. WebSocket events published
6. Next question enqueued/sent
"""

import pytest
import asyncio
from uuid import UUID, uuid4
from datetime import datetime, UTC
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient
from app.models.quiz import QuizTemplate, QuizSession, QuizResponse
from app.models.message import Message, MessageDirection, MessageStatus, MessageType
from app.services.quiz import QuizSessionService, QuizResponseService
from app.services.quiz_flow_integration import ConversationalQuizService
from app.services.webhook_processor import WebhookProcessor
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.core.redis_unified import get_async_redis


@pytest.fixture
async def test_patient(async_db_session: AsyncSession) -> Patient:
    """Create a test patient."""
    patient = Patient(
        id=uuid4(),
        name="João Silva",
        phone="5511999887766",
        email="joao@test.com",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    async_db_session.add(patient)
    await async_db_session.commit()
    await async_db_session.refresh(patient)
    return patient


@pytest.fixture
async def test_quiz_template(async_db_session: AsyncSession) -> QuizTemplate:
    """Create a test quiz template with 3 questions."""
    template = QuizTemplate(
        id=uuid4(),
        name="Avaliação de Efeitos Colaterais",
        version="1.0",
        is_active=True,
        questions=[
            {
                "id": "q1",
                "question": "Como você está se sentindo hoje?",
                "type": "single_choice",
                "options": ["Muito bem", "Bem", "Regular", "Mal", "Muito mal"],
                "required": True
            },
            {
                "id": "q2",
                "question": "Você teve náuseas nos últimos dias?",
                "type": "yes_no",
                "required": True
            },
            {
                "id": "q3",
                "question": "De 0 a 10, qual seu nível de dor?",
                "type": "scale",
                "min": 0,
                "max": 10,
                "required": True
            }
        ],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    async_db_session.add(template)
    await async_db_session.commit()
    await async_db_session.refresh(template)
    return template


@pytest.fixture
def mock_evolution_webhook_payload() -> Dict[str, Any]:
    """Generate realistic Evolution API webhook payload."""
    def _generate(phone: str, message_text: str, whatsapp_id: str = None) -> Dict[str, Any]:
        return {
            "event": "messages.upsert",
            "instance": "default",
            "data": {
                "key": {
                    "remoteJid": f"{phone}@s.whatsapp.net",
                    "fromMe": False,
                    "id": whatsapp_id or f"3EB0{uuid4().hex[:16].upper()}"
                },
                "pushName": "João Silva",
                "message": {
                    "extendedTextMessage": {
                        "text": message_text
                    }
                },
                "messageType": "extendedTextMessage",
                "messageTimestamp": int(datetime.now(UTC).timestamp()),
                "status": "RECEIVED"
            },
            "destination": "5511999887766",
            "date_time": datetime.now(UTC).isoformat(),
            "sender": phone,
            "server_url": "https://evolution.example.com",
            "apikey": "test_api_key"
        }
    return _generate


@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.whatsapp
@pytest.mark.database
class TestConversationalQuizE2E:
    """End-to-end tests for conversational quiz flow."""

    async def test_complete_quiz_flow(
        self,
        async_db_session: AsyncSession,
        test_patient: Patient,
        test_quiz_template: QuizTemplate,
        mock_evolution_webhook_payload
    ):
        """
        Test complete quiz flow from start to completion.

        Flow:
        1. Start quiz session
        2. Send intro + first question
        3. Simulate webhook with answer #1
        4. Verify response persisted + session advanced + question #2 sent
        5. Simulate webhook with answer #2
        6. Verify response persisted + session advanced + question #3 sent
        7. Simulate webhook with answer #3
        8. Verify response persisted + session completed + completion message sent
        """
        # Mock external dependencies
        with patch('app.services.unified_whatsapp_service.UnifiedWhatsAppService.send_message') as mock_send, \
             patch('app.services.websocket_events.websocket_events.publish_event') as mock_ws_publish, \
             patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):

            mock_send.return_value = True  # Simulate successful send

            # Step 1: Start quiz session
            session_service = QuizSessionService(async_db_session)
            session = await session_service.start_quiz_session(
                patient_id=test_patient.id,
                quiz_template_id=test_quiz_template.id
            )

            assert session is not None
            assert session.quiz_template_id == test_quiz_template.id
            assert session.patient_id == test_patient.id
            assert session.current_question_index == 0
            assert session.is_completed is False

            # Step 2: Verify intro message sent
            quiz_service = ConversationalQuizService(async_db_session)
            await quiz_service.send_quiz_introduction(test_patient.id, session.id)

            # Verify send was called (intro message)
            assert mock_send.call_count >= 1

            # Step 3: Simulate first answer via webhook
            webhook_processor = WebhookProcessor(async_db_session)

            # Answer Q1: "Bem"
            webhook_payload_q1 = mock_evolution_webhook_payload(
                phone=test_patient.phone,
                message_text="Bem",
                whatsapp_id=f"WA_Q1_{uuid4().hex[:8]}"
            )

            message_id_q1 = await webhook_processor.process_message_webhook(webhook_payload_q1)
            assert message_id_q1 is not None

            # Verify response persisted
            result = await async_db_session.execute(
                select(QuizResponse).where(
                    QuizResponse.session_id == session.id,
                    QuizResponse.question_id == "q1"
                )
            )
            response_q1 = result.scalar_one_or_none()
            assert response_q1 is not None
            assert response_q1.response_value == "Bem"

            # Verify session advanced
            await async_db_session.refresh(session)
            assert session.current_question_index == 1
            assert session.is_completed is False

            # Step 4: Answer Q2: "Sim"
            webhook_payload_q2 = mock_evolution_webhook_payload(
                phone=test_patient.phone,
                message_text="Sim",
                whatsapp_id=f"WA_Q2_{uuid4().hex[:8]}"
            )

            message_id_q2 = await webhook_processor.process_message_webhook(webhook_payload_q2)
            assert message_id_q2 is not None

            # Verify response persisted
            result = await async_db_session.execute(
                select(QuizResponse).where(
                    QuizResponse.session_id == session.id,
                    QuizResponse.question_id == "q2"
                )
            )
            response_q2 = result.scalar_one_or_none()
            assert response_q2 is not None
            assert response_q2.response_value is True  # Normalized yes/no

            # Verify session advanced
            await async_db_session.refresh(session)
            assert session.current_question_index == 2
            assert session.is_completed is False

            # Step 5: Answer Q3: "7"
            webhook_payload_q3 = mock_evolution_webhook_payload(
                phone=test_patient.phone,
                message_text="7",
                whatsapp_id=f"WA_Q3_{uuid4().hex[:8]}"
            )

            message_id_q3 = await webhook_processor.process_message_webhook(webhook_payload_q3)
            assert message_id_q3 is not None

            # Verify response persisted
            result = await async_db_session.execute(
                select(QuizResponse).where(
                    QuizResponse.session_id == session.id,
                    QuizResponse.question_id == "q3"
                )
            )
            response_q3 = result.scalar_one_or_none()
            assert response_q3 is not None
            assert response_q3.response_value == 7  # Numeric scale

            # Verify session completed
            await async_db_session.refresh(session)
            assert session.is_completed is True
            assert session.completed_at is not None

            # Verify completion message sent (intro + q1 + q2 + q3 + completion)
            assert mock_send.call_count >= 5

            # Verify WebSocket events published
            assert mock_ws_publish.call_count >= 3  # At least 3 QUIZ_RESPONSE_SUBMITTED events

    async def test_quiz_idempotency_redis_path(
        self,
        async_db_session: AsyncSession,
        test_patient: Patient,
        test_quiz_template: QuizTemplate,
        mock_evolution_webhook_payload
    ):
        """
        Test idempotency via Redis fast path.

        Duplicate webhook with same whatsapp_id should:
        1. Be detected via Redis
        2. Return existing message_id
        3. Not create duplicate QuizResponse
        """
        with patch('app.services.unified_whatsapp_service.UnifiedWhatsAppService.send_message') as mock_send, \
             patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):

            mock_send.return_value = True

            # Start session
            session_service = QuizSessionService(async_db_session)
            session = await session_service.start_quiz_session(
                patient_id=test_patient.id,
                quiz_template_id=test_quiz_template.id
            )

            # Send intro
            quiz_service = ConversationalQuizService(async_db_session)
            await quiz_service.send_quiz_introduction(test_patient.id, session.id)

            webhook_processor = WebhookProcessor(async_db_session)

            # First webhook
            whatsapp_id = f"WA_DUPLICATE_{uuid4().hex[:8]}"
            webhook_payload = mock_evolution_webhook_payload(
                phone=test_patient.phone,
                message_text="Bem",
                whatsapp_id=whatsapp_id
            )

            message_id_1 = await webhook_processor.process_message_webhook(webhook_payload)
            assert message_id_1 is not None

            # Verify response created
            result = await async_db_session.execute(
                select(QuizResponse).where(QuizResponse.session_id == session.id)
            )
            responses_before = result.scalars().all()
            assert len(responses_before) == 1

            # Duplicate webhook (same whatsapp_id)
            message_id_2 = await webhook_processor.process_message_webhook(webhook_payload)
            assert message_id_2 == message_id_1  # Same message ID returned

            # Verify no duplicate response
            result = await async_db_session.execute(
                select(QuizResponse).where(QuizResponse.session_id == session.id)
            )
            responses_after = result.scalars().all()
            assert len(responses_after) == 1  # Still only one response

    async def test_quiz_idempotency_db_fallback(
        self,
        async_db_session: AsyncSession,
        test_patient: Patient,
        test_quiz_template: QuizTemplate,
        mock_evolution_webhook_payload
    ):
        """
        Test idempotency via DB fallback when Redis unavailable.

        Simulates Redis failure and verifies DB-based deduplication.
        """
        with patch('app.services.unified_whatsapp_service.UnifiedWhatsAppService.send_message') as mock_send, \
             patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True), \
             patch('app.core.redis_unified.get_async_redis') as mock_redis:

            # Simulate Redis failure
            mock_redis_client = AsyncMock()
            mock_redis_client.exists.side_effect = Exception("Redis connection failed")
            mock_redis_client.get.side_effect = Exception("Redis connection failed")
            mock_redis_client.setex.side_effect = Exception("Redis connection failed")
            mock_redis.return_value = mock_redis_client

            mock_send.return_value = True

            # Start session
            session_service = QuizSessionService(async_db_session)
            session = await session_service.start_quiz_session(
                patient_id=test_patient.id,
                quiz_template_id=test_quiz_template.id
            )

            # Send intro
            quiz_service = ConversationalQuizService(async_db_session)
            await quiz_service.send_quiz_introduction(test_patient.id, session.id)

            webhook_processor = WebhookProcessor(async_db_session)

            # First webhook
            whatsapp_id = f"WA_DB_FALLBACK_{uuid4().hex[:8]}"
            webhook_payload = mock_evolution_webhook_payload(
                phone=test_patient.phone,
                message_text="Regular",
                whatsapp_id=whatsapp_id
            )

            # First call should create message (Redis fails, DB insert succeeds)
            message_id_1 = await webhook_processor.process_message_webhook(webhook_payload)
            assert message_id_1 is not None

            # Verify message in DB
            result = await async_db_session.execute(
                select(Message).where(Message.whatsapp_id == whatsapp_id)
            )
            message_db = result.scalar_one_or_none()
            assert message_db is not None

            # Duplicate webhook (Redis still fails, DB detects duplicate)
            message_id_2 = await webhook_processor.process_message_webhook(webhook_payload)
            assert message_id_2 == message_id_1  # DB fallback returns existing message

            # Verify still only one message
            result = await async_db_session.execute(
                select(Message).where(Message.whatsapp_id == whatsapp_id)
            )
            messages = result.scalars().all()
            assert len(messages) == 1

    async def test_quiz_invalid_response_clarification(
        self,
        async_db_session: AsyncSession,
        test_patient: Patient,
        test_quiz_template: QuizTemplate,
        mock_evolution_webhook_payload
    ):
        """
        Test clarification message when invalid response provided.

        E.g., answering "banana" to a yes/no question.
        """
        with patch('app.services.unified_whatsapp_service.UnifiedWhatsAppService.send_message') as mock_send, \
             patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):

            mock_send.return_value = True

            # Start session
            session_service = QuizSessionService(async_db_session)
            session = await session_service.start_quiz_session(
                patient_id=test_patient.id,
                quiz_template_id=test_quiz_template.id
            )

            # Send intro + first question
            quiz_service = ConversationalQuizService(async_db_session)
            await quiz_service.send_quiz_introduction(test_patient.id, session.id)

            # Advance to Q2 (yes/no question)
            await session_service.advance_question(session.id)

            webhook_processor = WebhookProcessor(async_db_session)

            # Invalid answer to yes/no question
            webhook_payload = mock_evolution_webhook_payload(
                phone=test_patient.phone,
                message_text="banana",  # Invalid for yes/no
                whatsapp_id=f"WA_INVALID_{uuid4().hex[:8]}"
            )

            message_id = await webhook_processor.process_message_webhook(webhook_payload)
            assert message_id is not None

            # Verify no response persisted (validation failed)
            result = await async_db_session.execute(
                select(QuizResponse).where(
                    QuizResponse.session_id == session.id,
                    QuizResponse.question_id == "q2"
                )
            )
            response = result.scalar_one_or_none()
            assert response is None  # No response created due to validation error

            # Verify clarification message sent
            # Should have: intro + q1 + advance to q2 + clarification
            assert mock_send.call_count >= 3

    async def test_quiz_session_concurrent_start_protection(
        self,
        async_db_session: AsyncSession,
        test_patient: Patient,
        test_quiz_template: QuizTemplate
    ):
        """
        Test race condition protection when starting duplicate sessions.

        Uses SELECT FOR UPDATE NOWAIT + partial unique index.
        """
        session_service = QuizSessionService(async_db_session)

        # Start first session
        session_1 = await session_service.start_quiz_session(
            patient_id=test_patient.id,
            quiz_template_id=test_quiz_template.id
        )
        assert session_1 is not None

        # Attempt to start duplicate session (should fail)
        with pytest.raises(Exception):  # Should raise IntegrityError or LockError
            await session_service.start_quiz_session(
                patient_id=test_patient.id,
                quiz_template_id=test_quiz_template.id
            )

    async def test_quiz_websocket_events_published(
        self,
        async_db_session: AsyncSession,
        test_patient: Patient,
        test_quiz_template: QuizTemplate,
        mock_evolution_webhook_payload
    ):
        """
        Test WebSocket events are published at key points.

        Events expected:
        - QUIZ_RESPONSE_SUBMITTED (each answer)
        - QUIZ_COMPLETED (session completion)
        """
        with patch('app.services.unified_whatsapp_service.UnifiedWhatsAppService.send_message') as mock_send, \
             patch('app.services.websocket_events.websocket_events.publish_event') as mock_ws_publish, \
             patch('app.api.v1.webhooks.validate_webhook_signature', return_value=True):

            mock_send.return_value = True

            # Start session
            session_service = QuizSessionService(async_db_session)
            session = await session_service.start_quiz_session(
                patient_id=test_patient.id,
                quiz_template_id=test_quiz_template.id
            )

            # Send intro
            quiz_service = ConversationalQuizService(async_db_session)
            await quiz_service.send_quiz_introduction(test_patient.id, session.id)

            webhook_processor = WebhookProcessor(async_db_session)

            # Answer all 3 questions
            for idx, (q_id, answer) in enumerate([("q1", "Bem"), ("q2", "Sim"), ("q3", "5")]):
                webhook_payload = mock_evolution_webhook_payload(
                    phone=test_patient.phone,
                    message_text=answer,
                    whatsapp_id=f"WA_Q{idx+1}_{uuid4().hex[:8]}"
                )
                await webhook_processor.process_message_webhook(webhook_payload)

            # Verify WebSocket events
            ws_calls = [call.args[0] for call in mock_ws_publish.call_args_list]

            # Should have at least 3 QUIZ_RESPONSE_SUBMITTED and 1 QUIZ_COMPLETED
            response_events = [e for e in ws_calls if 'RESPONSE' in str(e)]
            assert len(response_events) >= 3

            completion_events = [e for e in ws_calls if 'COMPLETED' in str(e)]
            assert len(completion_events) >= 1
