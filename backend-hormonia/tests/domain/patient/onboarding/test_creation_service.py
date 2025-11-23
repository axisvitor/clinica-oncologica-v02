"""
Test suite for CreationService.

Tests direct patient creation logic.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.domain.patient.onboarding.creation_service import CreationService
from app.models.patient import Patient
from app.schemas.patient import PatientCreate
from app.exceptions import ValidationError


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.commit = MagicMock()
    db.rollback = MagicMock()
    db.refresh = MagicMock()
    return db


@pytest.fixture
def mock_integrity_service():
    """Mock IntegrityService."""
    service = MagicMock()
    service.generate_patient_hash = MagicMock(return_value="test_hash_123")
    return service


@pytest.fixture
def mock_completion_service():
    """Mock CompletionService."""
    service = MagicMock()
    service.complete_partial_onboarding = AsyncMock()
    return service


@pytest.fixture
def mock_notification_service():
    """Mock NotificationService."""
    service = MagicMock()
    service.send_welcome_message = AsyncMock(return_value=True)
    service.publish_patient_created_event = AsyncMock(return_value=True)
    return service


@pytest.fixture
def mock_flow_service():
    """Mock FlowService."""
    service = MagicMock()
    service.initialize_default_flow = AsyncMock()
    return service


@pytest.fixture
def creation_service(
    mock_db,
    mock_integrity_service,
    mock_completion_service,
    mock_notification_service,
    mock_flow_service,
    sync_executor,
):
    """Create CreationService instance."""
    return CreationService(
        db=mock_db,
        integrity_service=mock_integrity_service,
        completion_service=mock_completion_service,
        notification_service=mock_notification_service,
        flow_service=mock_flow_service,
        executor=sync_executor,
    )


@pytest.fixture
def patient_data():
    """Sample patient data."""
    return PatientCreate(
        name="João Silva",
        phone="+5511999999999",
        email="joao@example.com",
        cpf="12345678909",
        birth_date="1990-01-01",
        treatment_type="quimioterapia",
    )


@pytest.fixture
def sample_patient():
    """Sample patient object."""
    patient_id = uuid4()
    patient = Patient(
        id=patient_id,
        name="João Silva",
        phone="+5511999999999",
        email="joao@example.com",
        doctor_id=uuid4(),
    )
    return patient


class TestCreationServiceCreate:
    """Test patient creation logic."""

    @pytest.mark.asyncio
    async def test_create_patient_direct_success(
        self, creation_service, patient_data, sample_patient, mock_integrity_service
    ):
        """
        GIVEN: Valid patient data
        WHEN: create_patient_direct is called
        THEN: Patient is created successfully
        """
        # Setup
        doctor_id = uuid4()

        # Mock repository
        with patch("app.domain.patient.onboarding.creation_service.PatientRepository") as mock_repo:
            mock_repo.return_value.create.return_value = sample_patient

            # Mock executor
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(
                    return_value=sample_patient
                )

                # Execute
                result = await creation_service.create_patient_direct(
                    patient_data, doctor_id
                )

        # Assert
        assert result == sample_patient
        mock_integrity_service.generate_patient_hash.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_patient_direct_invalidates_cache(
        self, creation_service, patient_data, sample_patient
    ):
        """
        GIVEN: Patient creation
        WHEN: create_patient_direct is called
        THEN: Cache is invalidated
        """
        # Setup
        doctor_id = uuid4()

        # Mock repository
        with patch("app.domain.patient.onboarding.creation_service.PatientRepository") as mock_repo:
            mock_repo.return_value.create.return_value = sample_patient

            # Mock cache manager
            with patch("app.domain.patient.onboarding.creation_service.get_cache_manager") as mock_cache:
                mock_cache_manager = MagicMock()
                mock_cache.return_value = mock_cache_manager

                # Mock executor
                with patch("asyncio.get_event_loop") as mock_loop:
                    mock_loop.return_value.run_in_executor = AsyncMock(
                        return_value=sample_patient
                    )

                    # Execute
                    await creation_service.create_patient_direct(patient_data, doctor_id)

        # Assert
        mock_cache_manager.invalidate_pattern.assert_called_once()


class TestCreationServiceNotifications:
    """Test notification delivery."""

    @pytest.mark.asyncio
    async def test_sends_welcome_message(
        self, creation_service, patient_data, sample_patient, mock_notification_service
    ):
        """
        GIVEN: Patient creation
        WHEN: create_patient_direct is called
        THEN: Welcome message is sent
        """
        # Setup
        doctor_id = uuid4()

        # Mock repository
        with patch("app.domain.patient.onboarding.creation_service.PatientRepository") as mock_repo:
            mock_repo.return_value.create.return_value = sample_patient

            # Mock executor
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(
                    return_value=sample_patient
                )

                # Execute
                await creation_service.create_patient_direct(patient_data, doctor_id)

        # Assert
        mock_notification_service.send_welcome_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_publishes_creation_event(
        self, creation_service, patient_data, sample_patient, mock_notification_service
    ):
        """
        GIVEN: Patient creation
        WHEN: create_patient_direct is called
        THEN: WebSocket event is published
        """
        # Setup
        doctor_id = uuid4()

        # Mock repository
        with patch("app.domain.patient.onboarding.creation_service.PatientRepository") as mock_repo:
            mock_repo.return_value.create.return_value = sample_patient

            # Mock executor
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(
                    return_value=sample_patient
                )

                # Execute
                await creation_service.create_patient_direct(patient_data, doctor_id)

        # Assert
        mock_notification_service.publish_patient_created_event.assert_called_once()


class TestCreationServiceFlow:
    """Test flow initialization."""

    @pytest.mark.asyncio
    async def test_initializes_flow(
        self, creation_service, patient_data, sample_patient, mock_flow_service
    ):
        """
        GIVEN: Patient creation with flow service
        WHEN: create_patient_direct is called
        THEN: Flow is initialized
        """
        # Setup
        doctor_id = uuid4()

        # Mock repository
        with patch("app.domain.patient.onboarding.creation_service.PatientRepository") as mock_repo:
            mock_repo.return_value.create.return_value = sample_patient

            # Mock executor
            with patch("asyncio.get_event_loop") as mock_loop:
                mock_loop.return_value.run_in_executor = AsyncMock(
                    return_value=sample_patient
                )

                # Execute
                await creation_service.create_patient_direct(patient_data, doctor_id)

        # Assert
        mock_flow_service.initialize_default_flow.assert_called_once()
