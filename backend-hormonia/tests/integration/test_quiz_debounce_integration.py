"""
Integration tests for Quiz Response Debouncing

Tests end-to-end debouncing behavior through webhook processing.
HIGH-005 Fix validation.
"""
import pytest
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.webhook_processor import WebhookProcessor
from app.models.patient import Patient
from app.models.message import Message, MessageType, MessageDirection
from app.services.quiz_response_debounce import get_quiz_debouncer


@pytest.fixture
def db_session(mocker):
    """Mock database session."""
    return mocker.MagicMock()


@pytest.fixture
def patient():
    """Create test patient."""
    patient = Patient(
        id=uuid4(),
        name="Test Patient",
        phone="+5511987654321",
        email="test@example.com"
    )
    return patient


@pytest.fixture
def quiz_session():
    """Create test quiz session."""
    session = MagicMock()
    session.id = uuid4()
    session.current_question = "question_001"
    session.current_question_index = 0
    return session


@pytest.fixture
def message(patient):
    """Create test message."""
    msg = Message(
        id=uuid4(),
        patient_id=patient.id,
        direction=MessageDirection.INBOUND,
        type=MessageType.TEXT,
        content="Test response",
        whatsapp_id="test_whatsapp_id_123",
        timestamp=datetime.utcnow()
    )
    return msg


@pytest.fixture
def webhook_processor(db_session):
    """Create webhook processor instance."""
    return WebhookProcessor(db=db_session)


@pytest.mark.asyncio
async def test_first_quiz_response_processed(
    webhook_processor,
    patient,
    message,
    quiz_session,
    mocker
):
    """Test that first quiz response is processed normally."""
    # Mock services
    mock_quiz_service = mocker.patch(
        'app.services.webhook_processor.ConversationalQuizService'
    )
    mock_quiz_service_instance = mock_quiz_service.return_value
    mock_quiz_service_instance.process_quiz_response = AsyncMock(
        return_value={
            "success": True,
            "action": "next_question"
        }
    )

    # Mock debouncer to allow first response
    with patch('app.services.quiz_response_debounce.get_async_redis') as mock_redis_func:
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)  # Not debounced
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis_func.return_value = mock_redis

        # Process quiz message
        await webhook_processor._handle_quiz_message(
            patient=patient,
            message=message,
            quiz_session=quiz_session
        )

        # Verify quiz service was called
        mock_quiz_service_instance.process_quiz_response.assert_called_once()


@pytest.mark.asyncio
async def test_duplicate_quiz_response_debounced(
    webhook_processor,
    patient,
    message,
    quiz_session,
    mocker
):
    """Test that duplicate quiz response within 3s is debounced."""
    # Mock services
    mock_quiz_service = mocker.patch(
        'app.services.webhook_processor.ConversationalQuizService'
    )
    mock_quiz_service_instance = mock_quiz_service.return_value
    mock_quiz_service_instance.process_quiz_response = AsyncMock()

    # Mock debouncer to reject duplicate
    with patch('app.services.quiz_response_debounce.get_async_redis') as mock_redis_func:
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)  # Debounced
        mock_redis.incr = AsyncMock(return_value=2)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis_func.return_value = mock_redis

        # Process duplicate quiz message
        await webhook_processor._handle_quiz_message(
            patient=patient,
            message=message,
            quiz_session=quiz_session
        )

        # Verify quiz service was NOT called (debounced)
        mock_quiz_service_instance.process_quiz_response.assert_not_called()


@pytest.mark.asyncio
async def test_clarification_clears_debounce(
    webhook_processor,
    patient,
    message,
    quiz_session,
    mocker
):
    """Test that clarification request clears debounce."""
    # Mock services
    mock_quiz_service = mocker.patch(
        'app.services.webhook_processor.ConversationalQuizService'
    )
    mock_quiz_service_instance = mock_quiz_service.return_value
    mock_quiz_service_instance.process_quiz_response = AsyncMock(
        return_value={
            "success": True,
            "action": "request_clarification"
        }
    )

    mock_redis_delete = AsyncMock(return_value=1)

    with patch('app.services.quiz_response_debounce.get_async_redis') as mock_redis_func:
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.delete = mock_redis_delete
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis_func.return_value = mock_redis

        # Process quiz message that requests clarification
        await webhook_processor._handle_quiz_message(
            patient=patient,
            message=message,
            quiz_session=quiz_session
        )

        # Verify debounce was cleared (delete called)
        mock_redis_delete.assert_called_once()


@pytest.mark.asyncio
async def test_quiz_completion_clears_all_debounce(
    webhook_processor,
    patient,
    message,
    quiz_session,
    mocker
):
    """Test that quiz completion clears all debounce state."""
    # Mock services
    mock_quiz_service = mocker.patch(
        'app.services.webhook_processor.ConversationalQuizService'
    )
    mock_quiz_service_instance = mock_quiz_service.return_value
    mock_quiz_service_instance.process_quiz_response = AsyncMock(
        return_value={
            "success": True,
            "action": "quiz_completed"
        }
    )

    mock_scan = AsyncMock(return_value=(0, [
        b"quiz:debounce:session_id:q1",
        b"quiz:debounce:session_id:q2"
    ]))
    mock_delete = AsyncMock(return_value=2)

    with patch('app.services.quiz_response_debounce.get_async_redis') as mock_redis_func:
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.scan = mock_scan
        mock_redis.delete = mock_delete
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis_func.return_value = mock_redis

        # Process quiz message that completes quiz
        await webhook_processor._handle_quiz_message(
            patient=patient,
            message=message,
            quiz_session=quiz_session
        )

        # Verify scan was called to find all debounce keys
        mock_scan.assert_called_once()
        # Verify all keys were deleted
        mock_delete.assert_called_once()


@pytest.mark.asyncio
async def test_different_sessions_not_debounced(
    webhook_processor,
    patient,
    message,
    mocker
):
    """Test that responses from different sessions are not debounced."""
    # Create two different quiz sessions
    session1 = MagicMock()
    session1.id = uuid4()
    session1.current_question = "question_001"

    session2 = MagicMock()
    session2.id = uuid4()
    session2.current_question = "question_001"

    # Mock services
    mock_quiz_service = mocker.patch(
        'app.services.webhook_processor.ConversationalQuizService'
    )
    mock_quiz_service_instance = mock_quiz_service.return_value
    mock_quiz_service_instance.process_quiz_response = AsyncMock(
        return_value={"success": True, "action": "next_question"}
    )

    with patch('app.services.quiz_response_debounce.get_async_redis') as mock_redis_func:
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)  # Both allowed
        mock_redis.setex = AsyncMock(return_value=True)
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)
        mock_redis_func.return_value = mock_redis

        # Process message for session 1
        await webhook_processor._handle_quiz_message(
            patient=patient,
            message=message,
            quiz_session=session1
        )

        # Process message for session 2
        await webhook_processor._handle_quiz_message(
            patient=patient,
            message=message,
            quiz_session=session2
        )

        # Both should be processed
        assert mock_quiz_service_instance.process_quiz_response.call_count == 2


@pytest.mark.asyncio
async def test_debounce_metrics_tracking(quiz_session):
    """Test that debounce metrics are properly tracked."""
    with patch('app.services.quiz_response_debounce.get_async_redis') as mock_redis_func:
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"3")  # 3 debounced
        mock_redis.scan = AsyncMock(return_value=(0, [
            b"quiz:debounce:session_id:q1"
        ]))
        mock_redis.ttl = AsyncMock(return_value=2)
        mock_redis_func.return_value = mock_redis

        debouncer = get_quiz_debouncer()

        stats = await debouncer.get_debounce_stats(quiz_session.id)

        assert stats["total_debounced"] == 3
        assert stats["active_debounces"] == 1
        assert stats["debounce_window"] == 3


@pytest.mark.asyncio
async def test_redis_failure_allows_processing(
    webhook_processor,
    patient,
    message,
    quiz_session,
    mocker
):
    """Test that Redis failure doesn't block quiz processing."""
    # Mock services
    mock_quiz_service = mocker.patch(
        'app.services.webhook_processor.ConversationalQuizService'
    )
    mock_quiz_service_instance = mock_quiz_service.return_value
    mock_quiz_service_instance.process_quiz_response = AsyncMock(
        return_value={"success": True, "action": "next_question"}
    )

    # Simulate Redis failure
    with patch('app.services.quiz_response_debounce.get_async_redis') as mock_redis_func:
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(side_effect=Exception("Redis connection failed"))
        mock_redis_func.return_value = mock_redis

        # Process message - should succeed despite Redis error
        await webhook_processor._handle_quiz_message(
            patient=patient,
            message=message,
            quiz_session=quiz_session
        )

        # Verify quiz service was called (fail open behavior)
        mock_quiz_service_instance.process_quiz_response.assert_called_once()
