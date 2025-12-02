"""
Unit tests for PatientOnboardingService - Happy Path Scenarios.

This test suite covers successful patient onboarding flows including:
- Direct creation without Saga
- Saga-based creation
- Welcome message sending
- Flow initialization
- Cache invalidation
- WebSocket event publishing

Coverage Impact: +2%
Priority: P0 - Critical Business Path
"""

import pytest
from datetime import datetime
from uuid import uuid4
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from app.domain.patient.onboarding.coordinator import PatientOnboardingService
from app.schemas.patient import PatientCreate
from app.models.patient import Patient, FlowState
from app.models.user import User
from app.models.message import MessageType


class TestPatientOnboardingHappyPath:
    """Test successful patient onboarding scenarios."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create all mocked dependencies for onboarding service."""
        db = Mock()
        integrity_service = Mock()
        flow_service = Mock()
        message_service = Mock()
        whatsapp_service = Mock()
        saga_orchestrator = None

        # Setup async methods
        integrity_service.validate_patient_data = AsyncMock()
        integrity_service.generate_patient_hash = Mock(return_value="test_hash_123")
        flow_service.initialize_default_flow = AsyncMock()
        message_service.schedule_message = Mock()
        whatsapp_service.send_message = AsyncMock(return_value=True)

        return {
            "db": db,
            "integrity_service": integrity_service,
            "flow_service": flow_service,
            "message_service": message_service,
            "whatsapp_service": whatsapp_service,
            "saga_orchestrator": saga_orchestrator,
        }

    @pytest.fixture
    def onboarding_service(self, mock_dependencies):
        """Create PatientOnboardingService instance with mocked dependencies."""
        return PatientOnboardingService(**mock_dependencies)

    @pytest.fixture
    def valid_patient_data(self):
        """Valid patient creation data."""
        return PatientCreate(
            name="João Silva",
            email="joao.silva@example.com",
            phone="+5511999887766",
            birth_date=datetime(1980, 5, 15),
            treatment_type="Quimioterapia",
            cpf="12345678900",
            metadata={"source": "manual_registration"}
        )

    @pytest.fixture
    def test_doctor_id(self):
        """Test doctor UUID."""
        return uuid4()

    @pytest.fixture
    def test_user(self):
        """Test user object."""
        return User(
            id=uuid4(),
            email="doctor@example.com",
            full_name="Dr. Test"
        )

    @pytest.mark.asyncio
    async def test_create_patient_direct_success(
        self,
        onboarding_service,
        valid_patient_data,
        test_doctor_id,
        test_user,
        mock_dependencies
    ):
        """
        Test successful patient creation without Saga.

        This is the most common path when Saga is disabled or not available.
        """
        # Arrange
        expected_patient = Patient(
            id=uuid4(),
            name=valid_patient_data.name,
            email=valid_patient_data.email,
            phone=valid_patient_data.phone,
            doctor_id=test_doctor_id,
            flow_state=FlowState.NOT_STARTED,
        )

        # Mock repository creation
        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.create = Mock(return_value=expected_patient)
            mock_repo_class.return_value = mock_repo

            # Mock cache manager
            with patch("app.services.patient.onboarding_service.get_cache_manager") as mock_cache:
                mock_cache_manager = Mock()
                mock_cache.return_value = mock_cache_manager

                # Mock WebSocket events
                with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                    mock_ws.publish_patient_event = AsyncMock()

                    # Mock settings
                    with patch("app.services.patient.onboarding_service.settings") as mock_settings:
                        mock_settings.ENABLE_WHATSAPP_ON_REGISTRATION = False

                        # Act
                        result = await onboarding_service.create_patient(
                            patient_data=valid_patient_data,
                            doctor_id=test_doctor_id,
                            current_user=test_user
                        )

        # Assert
        assert result is not None
        assert result.id == expected_patient.id
        assert result.name == valid_patient_data.name
        assert result.email == valid_patient_data.email

        # Verify validation was called
        mock_dependencies["integrity_service"].validate_patient_data.assert_called_once()

        # Verify patient was created
        mock_repo.create.assert_called_once()
        created_data = mock_repo.create.call_args[0][0]
        assert created_data["doctor_id"] == test_doctor_id
        assert "patient_data" in created_data
        assert created_data["patient_data"]["integrity_hash"] == "test_hash_123"

        # Verify cache invalidation
        mock_cache_manager.invalidate_pattern.assert_called_once()

        # Verify WebSocket event published
        mock_ws.publish_patient_event.assert_called_once()

        # Verify flow initialization
        mock_dependencies["flow_service"].initialize_default_flow.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_patient_with_welcome_message(
        self,
        onboarding_service,
        valid_patient_data,
        test_doctor_id,
        test_user,
        mock_dependencies
    ):
        """
        Test patient creation with welcome message sending.

        Verifies that welcome messages are properly scheduled and sent
        when WhatsApp integration is enabled.
        """
        # Arrange
        patient = Patient(
            id=uuid4(),
            name=valid_patient_data.name,
            email=valid_patient_data.email,
            phone=valid_patient_data.phone,
            doctor_id=test_doctor_id,
            treatment_type=valid_patient_data.treatment_type,
        )

        scheduled_message = Mock()
        scheduled_message.id = uuid4()
        mock_dependencies["message_service"].schedule_message.return_value = scheduled_message

        # Mock all external dependencies
        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.create = Mock(return_value=patient)
            mock_repo_class.return_value = mock_repo

            with patch("app.services.patient.onboarding_service.get_cache_manager"):
                with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                    mock_ws.publish_patient_event = AsyncMock()

                    with patch("app.services.patient.onboarding_service.get_welcome_message") as mock_welcome:
                        mock_welcome.return_value = "Bem-vindo ao tratamento!"

                        with patch("app.services.patient.onboarding_service.settings") as mock_settings:
                            mock_settings.ENABLE_WHATSAPP_ON_REGISTRATION = True
                            mock_settings.WHATSAPP_WELCOME_MESSAGE_ENABLED = True
                            mock_settings.CLINIC_NAME = "Clínica Teste"
                            mock_settings.CLINIC_SUPPORT_PHONE = "+5511999999999"

                            # Act
                            result = await onboarding_service.create_patient(
                                patient_data=valid_patient_data,
                                doctor_id=test_doctor_id,
                                current_user=test_user
                            )

        # Assert
        assert result is not None

        # Verify message was scheduled
        mock_dependencies["message_service"].schedule_message.assert_called_once()
        schedule_call = mock_dependencies["message_service"].schedule_message.call_args
        assert schedule_call[1]["patient_id"] == patient.id
        assert schedule_call[1]["message_type"] == MessageType.TEXT
        assert "message_metadata" in schedule_call[1]

        # Verify message was sent via WhatsApp
        mock_dependencies["whatsapp_service"].send_message.assert_called_once_with(scheduled_message)

    @pytest.mark.asyncio
    async def test_create_patient_saga_success(
        self,
        mock_dependencies,
        valid_patient_data,
        test_doctor_id,
        test_user
    ):
        """
        Test successful patient creation using Saga pattern.

        Verifies that when Saga orchestrator is available and enabled,
        patient creation goes through the Saga workflow.
        """
        # Arrange
        expected_patient = Patient(
            id=uuid4(),
            name=valid_patient_data.name,
            email=valid_patient_data.email,
            phone=valid_patient_data.phone,
            doctor_id=test_doctor_id,
        )

        # Create saga orchestrator mock
        saga_orchestrator = Mock()
        saga_orchestrator.execute_patient_onboarding_saga = AsyncMock(return_value=expected_patient)
        mock_dependencies["saga_orchestrator"] = saga_orchestrator

        service = PatientOnboardingService(**mock_dependencies)

        with patch("app.services.patient.onboarding_service.settings") as mock_settings:
            mock_settings.ENABLE_SAGA_PATTERN = True

            # Act
            result = await service.create_patient(
                patient_data=valid_patient_data,
                doctor_id=test_doctor_id,
                current_user=test_user
            )

        # Assert
        assert result is not None
        assert result.id == expected_patient.id

        # Verify Saga was executed
        saga_orchestrator.execute_patient_onboarding_saga.assert_called_once_with(
            patient_data=valid_patient_data,
            doctor_id=test_doctor_id,
            current_user=test_user
        )

    @pytest.mark.asyncio
    async def test_create_patient_with_metadata(
        self,
        onboarding_service,
        test_doctor_id,
        test_user,
        mock_dependencies
    ):
        """
        Test patient creation with custom metadata.

        Verifies that custom metadata is properly stored in patient_data field
        along with the integrity hash.
        """
        # Arrange
        patient_data = PatientCreate(
            name="Maria Santos",
            email="maria@example.com",
            phone="+5511988776655",
            birth_date=datetime(1975, 3, 20),
            treatment_type="Radioterapia",
            cpf="98765432100",
            metadata={
                "source": "referral",
                "referral_doctor": "Dr. João",
                "insurance": "Unimed",
                "custom_field": "test_value"
            }
        )

        created_patient = Patient(
            id=uuid4(),
            name=patient_data.name,
            email=patient_data.email,
            phone=patient_data.phone,
            doctor_id=test_doctor_id,
        )

        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.create = Mock(return_value=created_patient)
            mock_repo_class.return_value = mock_repo

            with patch("app.services.patient.onboarding_service.get_cache_manager"):
                with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                    mock_ws.publish_patient_event = AsyncMock()

                    with patch("app.services.patient.onboarding_service.settings") as mock_settings:
                        mock_settings.ENABLE_WHATSAPP_ON_REGISTRATION = False

                        # Act
                        result = await onboarding_service.create_patient(
                            patient_data=patient_data,
                            doctor_id=test_doctor_id,
                            current_user=test_user
                        )

        # Assert
        assert result is not None

        # Verify metadata was included in patient_data
        mock_repo.create.assert_called_once()
        created_data = mock_repo.create.call_args[0][0]
        assert "patient_data" in created_data
        patient_metadata = created_data["patient_data"]

        # Verify original metadata is preserved
        assert patient_metadata.get("source") == "referral"
        assert patient_metadata.get("referral_doctor") == "Dr. João"
        assert patient_metadata.get("insurance") == "Unimed"
        assert patient_metadata.get("custom_field") == "test_value"

        # Verify integrity hash was added
        assert "integrity_hash" in patient_metadata
        assert patient_metadata["integrity_hash"] == "test_hash_123"

    @pytest.mark.asyncio
    async def test_flow_initialization_called(
        self,
        onboarding_service,
        valid_patient_data,
        test_doctor_id,
        test_user,
        mock_dependencies
    ):
        """
        Test that flow initialization is called after patient creation.

        Verifies the default flow is initialized for the new patient.
        """
        # Arrange
        patient = Patient(
            id=uuid4(),
            name=valid_patient_data.name,
            email=valid_patient_data.email,
            phone=valid_patient_data.phone,
            doctor_id=test_doctor_id,
        )

        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.create = Mock(return_value=patient)
            mock_repo_class.return_value = mock_repo

            with patch("app.services.patient.onboarding_service.get_cache_manager"):
                with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                    mock_ws.publish_patient_event = AsyncMock()

                    with patch("app.services.patient.onboarding_service.settings") as mock_settings:
                        mock_settings.ENABLE_WHATSAPP_ON_REGISTRATION = False

                        # Act
                        await onboarding_service.create_patient(
                            patient_data=valid_patient_data,
                            doctor_id=test_doctor_id,
                            current_user=test_user
                        )

        # Assert - verify flow initialization was called with correct parameters
        mock_dependencies["flow_service"].initialize_default_flow.assert_called_once_with(
            patient,
            test_user.id
        )

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_creation(
        self,
        onboarding_service,
        valid_patient_data,
        test_doctor_id,
        test_user
    ):
        """
        Test that patient list cache is invalidated after creation.

        Ensures cache consistency by invalidating relevant cache keys.
        """
        # Arrange
        patient = Patient(
            id=uuid4(),
            name=valid_patient_data.name,
            doctor_id=test_doctor_id,
        )

        with patch("app.services.patient.onboarding_service.PatientRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.create = Mock(return_value=patient)
            mock_repo_class.return_value = mock_repo

            with patch("app.services.patient.onboarding_service.get_cache_manager") as mock_cache:
                mock_cache_manager = Mock()
                mock_cache.return_value = mock_cache_manager

                with patch("app.services.patient.onboarding_service.websocket_events") as mock_ws:
                    mock_ws.publish_patient_event = AsyncMock()

                    with patch("app.services.patient.onboarding_service.settings") as mock_settings:
                        mock_settings.ENABLE_WHATSAPP_ON_REGISTRATION = False

                        # Act
                        await onboarding_service.create_patient(
                            patient_data=valid_patient_data,
                            doctor_id=test_doctor_id,
                            current_user=test_user
                        )

        # Assert - verify cache invalidation was called with correct pattern
        mock_cache_manager.invalidate_pattern.assert_called_once_with(
            f"patient_list:*:{test_doctor_id}*",
            namespace="cache"
        )
