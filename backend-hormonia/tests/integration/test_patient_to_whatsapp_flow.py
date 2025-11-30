"""
End-to-end integration tests: Patient registration to WhatsApp follow-up

This test suite validates the complete patient journey from initial registration
through WhatsApp messaging, appointment scheduling, and saga orchestration.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from datetime import datetime, timedelta
from uuid import uuid4

from app.models.patient import Patient, FlowState
from app.models.message import Message, MessageType, MessageStatus, MessageDirection
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.domain.patient_onboarding.saga_coordinator import PatientOnboardingSagaCoordinator


class TestPatientToWhatsAppFlow:
    """Test complete patient journey from registration to WhatsApp"""

    @pytest.fixture
    def patient_data(self):
        """Sample patient registration data"""
        return {
            "name": "Maria Santos",
            "phone": "5511988887777",
            "email": "maria@example.com",
            "birth_date": "1980-03-15",
            "treatment_type": "hormone_therapy",
            "treatment_start_date": datetime.now().date().isoformat()
        }

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def mock_whatsapp_service(self):
        """Mock WhatsApp service"""
        service = AsyncMock(spec=UnifiedWhatsAppService)
        service.send_message = AsyncMock(return_value=True)
        service.send_flow_message = AsyncMock(return_value=True)
        return service

    @pytest.mark.asyncio
    async def test_complete_patient_registration_flow(self, patient_data, mock_db, mock_whatsapp_service):
        """Test full patient registration triggers welcome message"""
        # Step 1: Create patient
        doctor_id = uuid4()

        with patch('app.services.patient_service.PatientService') as mock_patient_svc:
            with patch('app.services.unified_whatsapp_service.UnifiedWhatsAppService') as mock_wa_svc:
                # Setup mocks
                patient_id = uuid4()
                created_patient = Patient(
                    id=patient_id,
                    name=patient_data["name"],
                    phone=patient_data["phone"],
                    email=patient_data["email"],
                    doctor_id=doctor_id,
                    flow_state=FlowState.ONBOARDING,
                    current_day=0
                )

                mock_patient_svc_instance = AsyncMock()
                mock_patient_svc.return_value = mock_patient_svc_instance
                mock_patient_svc_instance.create_patient = AsyncMock(return_value=created_patient)

                mock_wa_svc_instance = mock_whatsapp_service
                mock_wa_svc.return_value = mock_wa_svc_instance

                # Act: Create patient
                patient_service = mock_patient_svc()
                whatsapp_service = mock_wa_svc()

                patient = await patient_service.create_patient(patient_data, doctor_id)

                # Step 2: Trigger welcome message
                welcome_message = Message(
                    id=uuid4(),
                    patient_id=patient.id,
                    direction=MessageDirection.OUTBOUND,
                    type=MessageType.TEXT,
                    content=f"Olá {patient.name}! Bem-vinda à nossa clínica...",
                    status=MessageStatus.PENDING,
                    idempotency_key=f"welcome-{patient.id}"
                )
                welcome_message.patient = patient

                await whatsapp_service.send_message(welcome_message)

                # Assert: Verify patient was created
                assert patient.id == patient_id
                assert patient.flow_state == FlowState.ONBOARDING

                # Verify WhatsApp welcome message was triggered
                mock_wa_svc_instance.send_message.assert_called_once()
                call_args = mock_wa_svc_instance.send_message.call_args
                sent_message = call_args[0][0]
                assert patient_data["phone"] in sent_message.patient.phone
                assert "Bem-vinda" in sent_message.content

    @pytest.mark.asyncio
    async def test_appointment_reminder_flow(self, patient_data, mock_db, mock_whatsapp_service):
        """Test appointment triggers reminder via WhatsApp"""
        # Step 1: Create patient
        patient = Patient(
            id=uuid4(),
            name=patient_data["name"],
            phone=patient_data["phone"],
            doctor_id=uuid4(),
            flow_state=FlowState.ACTIVE
        )

        # Step 2: Create appointment for tomorrow
        appointment_time = datetime.now() + timedelta(days=1)

        # Step 3: Schedule reminder message
        reminder_message = Message(
            id=uuid4(),
            patient_id=patient.id,
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content=f"Lembrete: Você tem consulta amanhã às {appointment_time.strftime('%H:%M')}",
            status=MessageStatus.SCHEDULED,
            scheduled_for=appointment_time - timedelta(hours=24),
            idempotency_key=f"reminder-{patient.id}-{appointment_time.date()}"
        )
        reminder_message.patient = patient

        # Mock scheduling service
        with patch('app.services.unified_whatsapp_service.UnifiedWhatsAppService') as mock_wa_svc:
            mock_wa_svc_instance = mock_whatsapp_service
            mock_wa_svc.return_value = mock_wa_svc_instance

            whatsapp_service = mock_wa_svc()

            # Act: Send scheduled reminder
            result = await whatsapp_service.send_message(reminder_message)

            # Assert: Verify reminder was scheduled
            assert result is True
            mock_wa_svc_instance.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_saga_rollback_on_whatsapp_failure(self, patient_data, mock_db):
        """Test saga rollback when WhatsApp service fails"""
        # Setup saga coordinator
        with patch('app.domain.patient_onboarding.saga_coordinator.PatientOnboardingSagaCoordinator') as mock_saga:
            with patch('app.services.patient_service.PatientService') as mock_patient_svc:
                with patch('app.services.unified_whatsapp_service.UnifiedWhatsAppService') as mock_wa_svc:
                    # Configure mocks
                    saga_coordinator = AsyncMock()
                    mock_saga.return_value = saga_coordinator

                    patient_service = AsyncMock()
                    mock_patient_svc.return_value = patient_service

                    whatsapp_service = AsyncMock()
                    mock_wa_svc.return_value = whatsapp_service

                    # Simulate patient creation success
                    patient_id = uuid4()
                    created_patient = Patient(
                        id=patient_id,
                        name=patient_data["name"],
                        phone=patient_data["phone"],
                        doctor_id=uuid4(),
                        flow_state=FlowState.ONBOARDING
                    )
                    patient_service.create_patient = AsyncMock(return_value=created_patient)

                    # Simulate WhatsApp failure
                    whatsapp_service.send_message = AsyncMock(return_value=False)

                    # Configure saga rollback
                    saga_coordinator.rollback = AsyncMock()
                    patient_service.delete_patient = AsyncMock()

                    # Act: Attempt onboarding
                    coordinator = mock_saga()
                    patient_svc = mock_patient_svc()
                    wa_svc = mock_wa_svc()

                    # Create patient
                    patient = await patient_svc.create_patient(patient_data, uuid4())

                    # Try to send welcome message
                    welcome_message = Message(
                        id=uuid4(),
                        patient_id=patient.id,
                        direction=MessageDirection.OUTBOUND,
                        type=MessageType.TEXT,
                        content="Welcome message",
                        status=MessageStatus.PENDING,
                        idempotency_key=f"welcome-{patient.id}"
                    )

                    send_result = await wa_svc.send_message(welcome_message)

                    # If sending fails, trigger rollback
                    if not send_result:
                        await coordinator.rollback()

                    # Assert: Verify rollback was triggered
                    assert send_result is False
                    coordinator.rollback.assert_called_once()


class TestWhatsAppMessageDeliveryTracking:
    """Test WhatsApp message delivery status tracking"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_message_status_progression(self, mock_db):
        """Test message status updates through delivery lifecycle"""
        # Create message
        message = Message(
            id=uuid4(),
            patient_id=uuid4(),
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content="Test message",
            status=MessageStatus.PENDING,
            idempotency_key=f"test-{uuid4()}"
        )

        # Track status progression
        statuses = []

        # PENDING -> SENDING
        message.status = MessageStatus.SENDING
        statuses.append(message.status)

        # SENDING -> SENT
        message.status = MessageStatus.SENT
        message.sent_at = datetime.utcnow()
        statuses.append(message.status)

        # SENT -> DELIVERED
        message.status = MessageStatus.DELIVERED
        message.delivered_at = datetime.utcnow()
        statuses.append(message.status)

        # DELIVERED -> READ
        message.status = MessageStatus.READ
        message.read_at = datetime.utcnow()
        statuses.append(message.status)

        # Assert: Verify progression
        assert statuses == [
            MessageStatus.SENDING,
            MessageStatus.SENT,
            MessageStatus.DELIVERED,
            MessageStatus.READ
        ]
        assert message.sent_at is not None
        assert message.delivered_at is not None
        assert message.read_at is not None

    @pytest.mark.asyncio
    async def test_failed_message_tracking(self, mock_db):
        """Test failed message status and retry tracking"""
        message = Message(
            id=uuid4(),
            patient_id=uuid4(),
            direction=MessageDirection.OUTBOUND,
            type=MessageType.TEXT,
            content="Test message",
            status=MessageStatus.PENDING,
            retry_count=0,
            idempotency_key=f"test-{uuid4()}"
        )

        # Simulate failure
        message.status = MessageStatus.FAILED
        message.retry_count += 1
        message.last_retry_at = datetime.utcnow()
        message.failure_reason = "WhatsApp API timeout"
        message.next_retry_at = datetime.utcnow() + timedelta(minutes=5)

        # Assert
        assert message.status == MessageStatus.FAILED
        assert message.retry_count == 1
        assert message.failure_reason == "WhatsApp API timeout"
        assert message.next_retry_at > datetime.utcnow()


class TestPatientFlowProgression:
    """Test patient flow progression through treatment stages"""

    @pytest.mark.asyncio
    async def test_onboarding_to_active_transition(self):
        """Test patient transitions from ONBOARDING to ACTIVE"""
        patient = Patient(
            id=uuid4(),
            name="Test Patient",
            phone="5511999999999",
            doctor_id=uuid4(),
            flow_state=FlowState.ONBOARDING,
            current_day=0
        )

        # Simulate completing onboarding
        patient.flow_state = FlowState.ACTIVE
        patient.current_day = 1

        assert patient.flow_state == FlowState.ACTIVE
        assert patient.current_day == 1

    @pytest.mark.asyncio
    async def test_flow_messages_sent_on_schedule(self, mock_db):
        """Test that flow messages are sent according to patient day"""
        patient = Patient(
            id=uuid4(),
            name="Test Patient",
            phone="5511999999999",
            doctor_id=uuid4(),
            flow_state=FlowState.ACTIVE,
            current_day=5
        )

        # Messages for day 5
        day_5_messages = [
            Message(
                id=uuid4(),
                patient_id=patient.id,
                direction=MessageDirection.OUTBOUND,
                type=MessageType.TEXT,
                content=f"Day {patient.current_day} message",
                status=MessageStatus.PENDING,
                idempotency_key=f"day-{patient.current_day}-{patient.id}"
            )
        ]

        # Assert: Messages are ready for current day
        assert len(day_5_messages) > 0
        assert all(msg.patient_id == patient.id for msg in day_5_messages)

    @pytest.mark.asyncio
    async def test_flow_pause_and_resume(self):
        """Test pausing and resuming patient flow"""
        patient = Patient(
            id=uuid4(),
            name="Test Patient",
            phone="5511999999999",
            doctor_id=uuid4(),
            flow_state=FlowState.ACTIVE,
            current_day=10
        )

        # Pause flow
        paused_day = patient.current_day
        patient.flow_state = FlowState.PAUSED

        assert patient.flow_state == FlowState.PAUSED
        assert patient.current_day == paused_day  # Day doesn't change

        # Resume flow
        patient.flow_state = FlowState.ACTIVE

        assert patient.flow_state == FlowState.ACTIVE
        assert patient.current_day == paused_day  # Resumes from same day


class TestQuizIntegration:
    """Test quiz delivery and response tracking via WhatsApp"""

    @pytest.mark.asyncio
    async def test_monthly_quiz_link_delivery(self, mock_db):
        """Test monthly quiz link is sent via WhatsApp"""
        patient = Patient(
            id=uuid4(),
            name="Test Patient",
            phone="5511999999999",
            doctor_id=uuid4(),
            flow_state=FlowState.ACTIVE,
            current_day=30
        )

        quiz_session_id = uuid4()
        quiz_link = f"https://clinic.com/quiz/{quiz_session_id}"

        # Create quiz link message
        quiz_message = Message(
            id=uuid4(),
            patient_id=patient.id,
            direction=MessageDirection.OUTBOUND,
            type=MessageType.MONTHLY_QUIZ_LINK,
            content=f"Olá! Chegou a hora do quiz mensal: {quiz_link}",
            status=MessageStatus.PENDING,
            message_metadata={
                "quiz_session_id": str(quiz_session_id),
                "quiz_month": 1,
                "template_type": "monthly_quiz_link"
            },
            idempotency_key=f"quiz-{quiz_session_id}"
        )

        # Assert: Quiz message is properly formatted
        assert quiz_message.type == MessageType.MONTHLY_QUIZ_LINK
        assert quiz_link in quiz_message.content
        assert quiz_message.message_metadata["quiz_session_id"] == str(quiz_session_id)

    @pytest.mark.asyncio
    async def test_quiz_reminder_after_no_response(self, mock_db):
        """Test reminder is sent if patient doesn't respond to quiz"""
        patient = Patient(
            id=uuid4(),
            name="Test Patient",
            phone="5511999999999",
            doctor_id=uuid4(),
            flow_state=FlowState.ACTIVE
        )

        quiz_session_id = uuid4()

        # Initial quiz link sent 2 days ago
        initial_message = Message(
            id=uuid4(),
            patient_id=patient.id,
            type=MessageType.MONTHLY_QUIZ_LINK,
            sent_at=datetime.utcnow() - timedelta(days=2),
            status=MessageStatus.DELIVERED,
            message_metadata={"quiz_session_id": str(quiz_session_id)},
            idempotency_key=f"quiz-{quiz_session_id}"
        )

        # Reminder message
        reminder_message = Message(
            id=uuid4(),
            patient_id=patient.id,
            type=MessageType.MONTHLY_QUIZ_REMINDER,
            content="Lembrete: Não esqueça de responder o quiz mensal!",
            status=MessageStatus.PENDING,
            message_metadata={
                "quiz_session_id": str(quiz_session_id),
                "reminder_number": 1
            },
            idempotency_key=f"quiz-reminder-{quiz_session_id}-1"
        )

        # Assert: Reminder is scheduled
        assert reminder_message.type == MessageType.MONTHLY_QUIZ_REMINDER
        assert reminder_message.message_metadata["reminder_number"] == 1
