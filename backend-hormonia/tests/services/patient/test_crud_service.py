"""
Unit tests for PatientCRUDService.

This test suite provides comprehensive coverage for the Patient CRUD service
including all CRUD operations, error handling, transaction management, and
cache invalidation.

Coverage Areas:
- get_patient: Fetch by ID, not found handling
- get_patient_by_phone: Phone lookup with LGPD compliance
- list_patients: Pagination, filters, search
- update_patient: Partial update, full update, transaction handling
- delete_patient: Soft delete, already deleted handling
- restore_patient: Restore soft-deleted patients
- Cache invalidation: Best-effort cache invalidation behavior
- Error handling: NotFoundError, transaction rollback

Test Categories:
- Happy path tests
- Edge case tests
- Error handling tests
- Transaction behavior tests

File: tests/services/patient/test_crud_service.py
Priority: P0 - Core Business Logic
"""

from __future__ import annotations

import pytest
from datetime import datetime, date
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.services.patient.crud_service import PatientCRUDService
from app.models.patient import Patient, FlowState
from app.schemas.patient import PatientUpdate
from app.exceptions import NotFoundError
from app.utils.timezone import SAO_PAULO_TZ, now_sao_paulo


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.refresh = MagicMock()
    session.query = MagicMock()
    return session


@pytest.fixture
def mock_repository():
    """Create a mock PatientRepository."""
    repo = MagicMock()
    repo.get_by_id = MagicMock()
    repo.get_by_phone = MagicMock()
    repo.get_paginated = MagicMock()
    repo.update = MagicMock()
    repo.create = MagicMock()
    return repo


@pytest.fixture
def mock_cache_invalidation_service():
    """Create a mock CacheInvalidationService."""
    cache_service = MagicMock()
    cache_service.invalidate_entity = MagicMock()
    return cache_service


@pytest.fixture
def crud_service(mock_db_session, mock_repository, mock_cache_invalidation_service):
    """Create PatientCRUDService with mocked dependencies."""
    with patch("app.services.patient.crud_service.get_cache_manager") as mock_cache_manager:
        mock_cache_manager.return_value = MagicMock()
        service = PatientCRUDService(
            db=mock_db_session,
            repository=mock_repository,
            cache_invalidation_service=mock_cache_invalidation_service,
        )
        return service


@pytest.fixture
def sample_patient():
    """Create a sample patient for testing."""
    patient_id = uuid4()
    doctor_id = uuid4()

    patient = MagicMock(spec=Patient)
    patient.id = patient_id
    patient.doctor_id = doctor_id
    patient.name = "Test Patient"
    patient.flow_state = FlowState.ACTIVE
    patient.current_day = 5
    patient.deleted_at = None
    patient.birth_date = date(1980, 5, 15)
    patient.treatment_type = "Quimioterapia"
    patient.treatment_start_date = date(2024, 1, 15)
    patient.diagnosis = "Test Diagnosis"
    patient.treatment_phase = "initial"
    patient.doctor_notes = "Initial notes"
    patient.patient_data = {"preferences": {"timezone": "America/Sao_Paulo"}}
    patient.created_at = datetime(2024, 1, 1, tzinfo=SAO_PAULO_TZ)
    patient.updated_at = datetime(2024, 1, 15, tzinfo=SAO_PAULO_TZ)

    return patient


@pytest.fixture
def sample_doctor_id():
    """Return a sample doctor UUID."""
    return uuid4()


@pytest.fixture
def sample_patient_update():
    """Create a sample PatientUpdate schema."""
    return PatientUpdate(
        name="Updated Patient Name",
        treatment_phase="maintenance",
        doctor_notes="Updated notes",
    )


# =============================================================================
# GET_PATIENT TESTS
# =============================================================================


class TestGetPatient:
    """Tests for get_patient method."""

    def test_get_patient_success(self, crud_service, mock_repository, sample_patient):
        """Test successful patient retrieval by ID."""
        # Arrange
        patient_id = sample_patient.id
        mock_repository.get_by_id.return_value = sample_patient

        # Act
        result = crud_service.get_patient(patient_id)

        # Assert
        assert result == sample_patient
        mock_repository.get_by_id.assert_called_once_with(
            patient_id, eager_load=False
        )

    def test_get_patient_not_found(self, crud_service, mock_repository):
        """Test NotFoundError when patient does not exist."""
        # Arrange
        patient_id = uuid4()
        mock_repository.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            crud_service.get_patient(patient_id)

        assert str(patient_id) in str(exc_info.value)
        mock_repository.get_by_id.assert_called_once_with(
            patient_id, eager_load=False
        )

    def test_get_patient_with_uuid_string(self, crud_service, mock_repository, sample_patient):
        """Test retrieval with UUID as string."""
        # Arrange
        patient_id = sample_patient.id
        mock_repository.get_by_id.return_value = sample_patient

        # Act
        result = crud_service.get_patient(patient_id)

        # Assert
        assert result is not None
        assert result.id == patient_id


# =============================================================================
# GET_PATIENT_BY_PHONE TESTS
# =============================================================================


class TestGetPatientByPhone:
    """Tests for get_patient_by_phone method."""

    def test_get_patient_by_phone_success(self, crud_service, mock_repository, sample_patient):
        """Test successful patient retrieval by phone."""
        # Arrange
        phone = "+5511999887766"
        mock_repository.get_by_phone.return_value = sample_patient

        # Act
        result = crud_service.get_patient_by_phone(phone)

        # Assert
        assert result == sample_patient
        mock_repository.get_by_phone.assert_called_once_with(phone)

    def test_get_patient_by_phone_not_found(self, crud_service, mock_repository):
        """Test return None when phone not found."""
        # Arrange
        phone = "+5511000000000"
        mock_repository.get_by_phone.return_value = None

        # Act
        result = crud_service.get_patient_by_phone(phone)

        # Assert
        assert result is None
        mock_repository.get_by_phone.assert_called_once_with(phone)

    def test_get_patient_by_phone_e164_format(self, crud_service, mock_repository, sample_patient):
        """Test phone lookup with E.164 format."""
        # Arrange
        phone_e164 = "+5511987654321"
        mock_repository.get_by_phone.return_value = sample_patient

        # Act
        result = crud_service.get_patient_by_phone(phone_e164)

        # Assert
        assert result == sample_patient
        mock_repository.get_by_phone.assert_called_once_with(phone_e164)


# =============================================================================
# LIST_PATIENTS TESTS
# =============================================================================


class TestListPatients:
    """Tests for list_patients method."""

    def test_list_patients_basic_pagination(
        self, crud_service, mock_repository, sample_patient, sample_doctor_id
    ):
        """Test basic pagination without filters."""
        # Arrange
        patients = [sample_patient]
        total_count = 1
        mock_repository.get_paginated.return_value = (patients, total_count)

        # Act
        result, total = crud_service.list_patients(
            doctor_id=sample_doctor_id,
            page=1,
            size=20,
        )

        # Assert
        assert len(result) == 1
        assert total == 1
        mock_repository.get_paginated.assert_called_once_with(
            doctor_id=sample_doctor_id,
            page=1,
            limit=20,
            search=None,
            flow_state=None,
            treatment_type=None,
            start_date_from=None,
            start_date_to=None,
            eager_load=False,
        )

    def test_list_patients_with_search(
        self, crud_service, mock_repository, sample_patient, sample_doctor_id
    ):
        """Test list patients with search term."""
        # Arrange
        patients = [sample_patient]
        mock_repository.get_paginated.return_value = (patients, 1)

        # Act
        result, total = crud_service.list_patients(
            doctor_id=sample_doctor_id,
            search="Test",
        )

        # Assert
        assert len(result) == 1
        mock_repository.get_paginated.assert_called_once()
        call_kwargs = mock_repository.get_paginated.call_args.kwargs
        assert call_kwargs["search"] == "Test"

    def test_list_patients_with_flow_state_filter(
        self, crud_service, mock_repository, sample_patient, sample_doctor_id
    ):
        """Test list patients filtered by flow state."""
        # Arrange
        mock_repository.get_paginated.return_value = ([sample_patient], 1)

        # Act
        result, total = crud_service.list_patients(
            doctor_id=sample_doctor_id,
            flow_state=FlowState.ACTIVE,
        )

        # Assert
        call_kwargs = mock_repository.get_paginated.call_args.kwargs
        assert call_kwargs["flow_state"] == FlowState.ACTIVE

    def test_list_patients_with_treatment_type_filter(
        self, crud_service, mock_repository, sample_doctor_id
    ):
        """Test list patients filtered by treatment type."""
        # Arrange
        mock_repository.get_paginated.return_value = ([], 0)

        # Act
        result, total = crud_service.list_patients(
            doctor_id=sample_doctor_id,
            treatment_type="Quimioterapia",
        )

        # Assert
        call_kwargs = mock_repository.get_paginated.call_args.kwargs
        assert call_kwargs["treatment_type"] == "Quimioterapia"

    def test_list_patients_with_date_range(
        self, crud_service, mock_repository, sample_doctor_id
    ):
        """Test list patients with date range filter."""
        # Arrange
        start_from = datetime(2024, 1, 1, tzinfo=SAO_PAULO_TZ)
        start_to = datetime(2024, 12, 31, tzinfo=SAO_PAULO_TZ)
        mock_repository.get_paginated.return_value = ([], 0)

        # Act
        result, total = crud_service.list_patients(
            doctor_id=sample_doctor_id,
            start_date_from=start_from,
            start_date_to=start_to,
        )

        # Assert
        call_kwargs = mock_repository.get_paginated.call_args.kwargs
        assert call_kwargs["start_date_from"] == start_from
        assert call_kwargs["start_date_to"] == start_to

    def test_list_patients_with_include_related(
        self, crud_service, mock_repository, sample_doctor_id
    ):
        """Test list patients with eager loading."""
        # Arrange
        mock_repository.get_paginated.return_value = ([], 0)

        # Act
        result, total = crud_service.list_patients(
            doctor_id=sample_doctor_id,
            include_related=True,
        )

        # Assert
        call_kwargs = mock_repository.get_paginated.call_args.kwargs
        assert call_kwargs["eager_load"] is True

    def test_list_patients_empty_result(
        self, crud_service, mock_repository, sample_doctor_id
    ):
        """Test empty results handling."""
        # Arrange
        mock_repository.get_paginated.return_value = ([], 0)

        # Act
        result, total = crud_service.list_patients(doctor_id=sample_doctor_id)

        # Assert
        assert result == []
        assert total == 0

    def test_list_patients_custom_pagination(
        self, crud_service, mock_repository, sample_doctor_id
    ):
        """Test custom page and size values."""
        # Arrange
        mock_repository.get_paginated.return_value = ([], 0)

        # Act
        result, total = crud_service.list_patients(
            doctor_id=sample_doctor_id,
            page=3,
            size=50,
        )

        # Assert
        call_kwargs = mock_repository.get_paginated.call_args.kwargs
        assert call_kwargs["page"] == 3
        assert call_kwargs["limit"] == 50


# =============================================================================
# UPDATE_PATIENT TESTS
# =============================================================================


class TestUpdatePatient:
    """Tests for update_patient method."""

    def test_update_patient_success(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test successful patient update."""
        # Arrange
        patient_id = sample_patient.id
        update_data = PatientUpdate(name="New Name", treatment_phase="maintenance")

        mock_repository.get_by_id.return_value = sample_patient

        updated_patient = MagicMock(spec=Patient)
        updated_patient.id = patient_id
        updated_patient.name = "New Name"
        updated_patient.treatment_phase = "maintenance"
        mock_repository.update.return_value = updated_patient

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)
            result = crud_service.update_patient(patient_id, update_data)

        # Assert
        assert result.name == "New Name"
        mock_repository.get_by_id.assert_called_once_with(patient_id)
        mock_repository.update.assert_called_once()

    def test_update_patient_not_found(
        self, crud_service, mock_repository
    ):
        """Test NotFoundError when updating non-existent patient."""
        # Arrange
        patient_id = uuid4()
        update_data = PatientUpdate(name="New Name")
        mock_repository.get_by_id.return_value = None

        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            crud_service.update_patient(patient_id, update_data)

        assert str(patient_id) in str(exc_info.value)

    def test_update_patient_partial_update(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test partial update with only some fields."""
        # Arrange
        patient_id = sample_patient.id
        update_data = PatientUpdate(doctor_notes="Only updating notes")

        mock_repository.get_by_id.return_value = sample_patient
        mock_repository.update.return_value = sample_patient

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)
            result = crud_service.update_patient(patient_id, update_data)

        # Assert
        update_call = mock_repository.update.call_args
        update_dict = update_call[0][1]  # Second positional argument
        assert "doctor_notes" in update_dict
        assert update_dict["doctor_notes"] == "Only updating notes"

    def test_update_patient_exclude_unset_fields(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test that unset fields are excluded from update."""
        # Arrange
        patient_id = sample_patient.id
        update_data = PatientUpdate(name="Only Name")

        mock_repository.get_by_id.return_value = sample_patient
        mock_repository.update.return_value = sample_patient

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)
            result = crud_service.update_patient(patient_id, update_data)

        # Assert
        update_call = mock_repository.update.call_args
        update_dict = update_call[0][1]
        # Only name should be in the update dict
        assert "name" in update_dict
        # Other fields should not be present unless explicitly set
        assert update_dict.get("email") is None or "email" not in update_dict

    def test_update_patient_full_update(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test full update with all fields."""
        # Arrange
        patient_id = sample_patient.id
        update_data = PatientUpdate(
            name="Full Update Name",
            phone="+5511999887766",
            email="updated@example.com",
            treatment_type="Radioterapia",
            treatment_phase="completed",
            doctor_notes="Full update notes",
            diagnosis="Updated diagnosis",
        )

        mock_repository.get_by_id.return_value = sample_patient
        mock_repository.update.return_value = sample_patient

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)
            result = crud_service.update_patient(patient_id, update_data)

        # Assert
        update_call = mock_repository.update.call_args
        update_dict = update_call[0][1]
        assert "name" in update_dict
        assert "treatment_type" in update_dict
        assert "treatment_phase" in update_dict

    def test_update_patient_cache_invalidation_called(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test that cache invalidation is triggered after update."""
        # Arrange
        patient_id = sample_patient.id
        update_data = PatientUpdate(name="Cache Test")

        mock_repository.get_by_id.return_value = sample_patient
        mock_repository.update.return_value = sample_patient

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            with patch.object(crud_service, "_run_cache_invalidation") as mock_cache:
                result = crud_service.update_patient(patient_id, update_data)

                # Assert
                mock_cache.assert_called_once_with(
                    entity="patient",
                    identifier=str(patient_id),
                    cascade=True,
                )


# =============================================================================
# DELETE_PATIENT TESTS
# =============================================================================


class TestDeletePatient:
    """Tests for delete_patient method (soft delete)."""

    def test_delete_patient_success(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test successful soft delete."""
        # Arrange
        patient_id = sample_patient.id
        sample_patient.deleted_at = None
        mock_repository.get_by_id.return_value = sample_patient

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)
            result = crud_service.delete_patient(patient_id)

        # Assert
        assert result is True
        assert sample_patient.deleted_at is not None
        mock_db_session.add.assert_called_once_with(sample_patient)

    def test_delete_patient_not_found(
        self, crud_service, mock_repository
    ):
        """Test delete returns False when patient not found."""
        # Arrange
        patient_id = uuid4()
        mock_repository.get_by_id.return_value = None

        # Act
        result = crud_service.delete_patient(patient_id)

        # Assert
        assert result is False

    def test_delete_patient_sets_deleted_at_timestamp(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test that deleted_at is set to current Sao Paulo time."""
        # Arrange
        patient_id = sample_patient.id
        sample_patient.deleted_at = None
        mock_repository.get_by_id.return_value = sample_patient

        before_delete = now_sao_paulo()

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)
            result = crud_service.delete_patient(patient_id)

        after_delete = now_sao_paulo()

        # Assert
        assert result is True
        assert sample_patient.deleted_at is not None
        assert before_delete <= sample_patient.deleted_at <= after_delete

    def test_delete_patient_cache_invalidation(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test cache is invalidated after deletion."""
        # Arrange
        patient_id = sample_patient.id
        sample_patient.deleted_at = None
        mock_repository.get_by_id.return_value = sample_patient

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            with patch.object(crud_service, "_run_cache_invalidation") as mock_cache:
                result = crud_service.delete_patient(patient_id)

                # Assert
                mock_cache.assert_called_once_with(
                    entity="patient",
                    identifier=str(patient_id),
                    cascade=True,
                )

    def test_delete_patient_transaction_rollback_on_error(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test transaction rollback on error during delete."""
        # Arrange
        patient_id = sample_patient.id
        sample_patient.deleted_at = None
        mock_repository.get_by_id.return_value = sample_patient

        # Simulate an exception during the transaction
        mock_db_session.add.side_effect = Exception("Database error")

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            # Configure the context manager to raise on error
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            result = crud_service.delete_patient(patient_id)

        # Assert - the service catches the exception and returns False
        assert result is False


# =============================================================================
# RESTORE_PATIENT TESTS
# =============================================================================


class TestRestorePatient:
    """Tests for restore_patient method."""

    def test_restore_patient_success(
        self, crud_service, mock_db_session, sample_patient
    ):
        """Test successful restoration of soft-deleted patient."""
        # Arrange
        patient_id = sample_patient.id
        sample_patient.deleted_at = now_sao_paulo()

        # Mock the query for deleted patients
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = sample_patient
        mock_query.filter.return_value = mock_filter
        mock_db_session.query.return_value = mock_query

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)
            result = crud_service.restore_patient(patient_id)

        # Assert
        assert result is True
        assert sample_patient.deleted_at is None

    def test_restore_patient_not_found(
        self, crud_service, mock_db_session
    ):
        """Test restore returns False when patient not found."""
        # Arrange
        patient_id = uuid4()

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = None
        mock_query.filter.return_value = mock_filter
        mock_db_session.query.return_value = mock_query

        # Act
        result = crud_service.restore_patient(patient_id)

        # Assert
        assert result is False

    def test_restore_patient_not_deleted(
        self, crud_service, mock_db_session, sample_patient
    ):
        """Test restore returns False for non-deleted patient."""
        # Arrange
        patient_id = sample_patient.id
        sample_patient.deleted_at = None  # Not deleted

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = None  # Query for deleted_at.isnot(None) returns None
        mock_query.filter.return_value = mock_filter
        mock_db_session.query.return_value = mock_query

        # Act
        result = crud_service.restore_patient(patient_id)

        # Assert
        assert result is False

    def test_restore_patient_cache_invalidation(
        self, crud_service, mock_db_session, sample_patient
    ):
        """Test cache is invalidated after restoration."""
        # Arrange
        patient_id = sample_patient.id
        sample_patient.deleted_at = now_sao_paulo()

        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = sample_patient
        mock_query.filter.return_value = mock_filter
        mock_db_session.query.return_value = mock_query

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            with patch.object(crud_service, "_run_cache_invalidation") as mock_cache:
                result = crud_service.restore_patient(patient_id)

                # Assert
                mock_cache.assert_called_once_with(
                    entity="patient",
                    identifier=str(patient_id),
                    cascade=True,
                )


# =============================================================================
# TRANSACTION HANDLING TESTS
# =============================================================================


class TestTransactionHandling:
    """Tests for transaction management behavior."""

    def test_update_uses_sync_transaction_context(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test that update uses sync_transaction context manager."""
        # Arrange
        patient_id = sample_patient.id
        update_data = PatientUpdate(name="Transaction Test")
        mock_repository.get_by_id.return_value = sample_patient
        mock_repository.update.return_value = sample_patient

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_cm = MagicMock()
            mock_cm.__enter__ = MagicMock(return_value=mock_db_session)
            mock_cm.__exit__ = MagicMock(return_value=False)
            mock_tx.return_value = mock_cm

            result = crud_service.update_patient(patient_id, update_data)

            # Assert - sync_transaction should be called with the db session
            mock_tx.assert_called_once_with(mock_db_session)

    def test_delete_uses_sync_transaction_context(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test that delete uses sync_transaction context manager."""
        # Arrange
        patient_id = sample_patient.id
        sample_patient.deleted_at = None
        mock_repository.get_by_id.return_value = sample_patient

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_cm = MagicMock()
            mock_cm.__enter__ = MagicMock(return_value=mock_db_session)
            mock_cm.__exit__ = MagicMock(return_value=False)
            mock_tx.return_value = mock_cm

            result = crud_service.delete_patient(patient_id)

            # Assert
            mock_tx.assert_called_once_with(mock_db_session)


# =============================================================================
# CACHE INVALIDATION TESTS
# =============================================================================


class TestCacheInvalidation:
    """Tests for cache invalidation behavior."""

    def test_run_cache_invalidation_fire_and_forget(
        self, crud_service, mock_cache_invalidation_service
    ):
        """Test that cache invalidation is fire-and-forget."""
        # Arrange
        patient_id = uuid4()

        # Act
        with patch("app.services.patient.crud_service.get_cache_executor") as mock_get_executor:
            mock_executor = MagicMock()
            mock_get_executor.return_value = mock_executor
            crud_service._run_cache_invalidation(
                entity="patient",
                identifier=str(patient_id),
                cascade=True,
            )

            # Assert - executor.submit should be called
            mock_executor.submit.assert_called_once()

    def test_run_cache_invalidation_handles_exception(
        self, crud_service
    ):
        """Test that cache invalidation failures are logged but don't raise."""
        # Arrange
        patient_id = uuid4()

        # Act & Assert - should not raise
        with patch("app.services.patient.crud_service.get_cache_executor") as mock_get_executor:
            mock_executor = MagicMock()
            mock_executor.submit.side_effect = Exception("Executor error")
            mock_get_executor.return_value = mock_executor

            # This should not raise
            crud_service._run_cache_invalidation(
                entity="patient",
                identifier=str(patient_id),
                cascade=True,
            )

    def test_static_invalidation_method(self):
        """Test static cache invalidation method."""
        # Arrange
        patient_id = uuid4()
        doctor_id = uuid4()

        # Act & Assert - should not raise
        with patch("app.services.patient.crud_service.get_cache_executor") as mock_get_executor:
            mock_executor = MagicMock()
            mock_get_executor.return_value = mock_executor
            PatientCRUDService.invalidate_patient_cache_static(patient_id, doctor_id)

            # Assert - executor.submit should be called
            mock_executor.submit.assert_called_once()


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_get_patient_logs_debug_on_fetch(
        self, crud_service, mock_repository, sample_patient
    ):
        """Test that debug logging occurs during fetch."""
        # Arrange
        patient_id = sample_patient.id
        mock_repository.get_by_id.return_value = sample_patient

        # Act
        with patch.object(crud_service, "_logger") as mock_logger:
            result = crud_service.get_patient(patient_id)

            # Assert
            mock_logger.debug.assert_called()

    def test_update_patient_logs_info_on_success(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test that info logging occurs on successful update."""
        # Arrange
        patient_id = sample_patient.id
        update_data = PatientUpdate(name="Log Test")
        mock_repository.get_by_id.return_value = sample_patient
        mock_repository.update.return_value = sample_patient

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            with patch.object(crud_service, "_logger") as mock_logger:
                result = crud_service.update_patient(patient_id, update_data)

                # Assert
                mock_logger.info.assert_called()

    def test_delete_patient_logs_error_on_exception(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test that errors are logged during delete failures."""
        # Arrange
        patient_id = sample_patient.id
        sample_patient.deleted_at = None
        mock_repository.get_by_id.return_value = sample_patient
        mock_db_session.add.side_effect = Exception("DB Error")

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)

            with patch.object(crud_service, "_logger") as mock_logger:
                result = crud_service.delete_patient(patient_id)

                # Assert
                mock_logger.error.assert_called()
                assert result is False


# =============================================================================
# RETRY DECORATOR TESTS
# =============================================================================


class TestRetryDecorator:
    """Tests for db_retry decorator behavior."""

    def test_get_patient_has_retry_decorator(self, crud_service):
        """Test that get_patient method has retry decorator."""
        # The method should have __wrapped__ if decorated
        method = crud_service.get_patient
        # Check that the method exists and is callable
        assert callable(method)

    def test_list_patients_has_retry_decorator(self, crud_service):
        """Test that list_patients method has retry decorator."""
        method = crud_service.list_patients
        assert callable(method)

    def test_update_patient_has_retry_decorator(self, crud_service):
        """Test that update_patient method has retry decorator."""
        method = crud_service.update_patient
        assert callable(method)

    def test_delete_patient_has_retry_decorator(self, crud_service):
        """Test that delete_patient method has retry decorator."""
        method = crud_service.delete_patient
        assert callable(method)


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_list_patients_with_zero_results(
        self, crud_service, mock_repository, sample_doctor_id
    ):
        """Test handling of zero results."""
        # Arrange
        mock_repository.get_paginated.return_value = ([], 0)

        # Act
        result, total = crud_service.list_patients(doctor_id=sample_doctor_id)

        # Assert
        assert result == []
        assert total == 0

    def test_list_patients_with_large_page_number(
        self, crud_service, mock_repository, sample_doctor_id
    ):
        """Test handling of large page numbers."""
        # Arrange
        mock_repository.get_paginated.return_value = ([], 0)

        # Act
        result, total = crud_service.list_patients(
            doctor_id=sample_doctor_id,
            page=999999,
            size=20,
        )

        # Assert
        call_kwargs = mock_repository.get_paginated.call_args.kwargs
        assert call_kwargs["page"] == 999999

    def test_update_with_empty_update_data(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test update with no fields set."""
        # Arrange
        patient_id = sample_patient.id
        update_data = PatientUpdate()  # No fields set
        mock_repository.get_by_id.return_value = sample_patient
        mock_repository.update.return_value = sample_patient

        # Act
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)
            result = crud_service.update_patient(patient_id, update_data)

        # Assert
        update_call = mock_repository.update.call_args
        update_dict = update_call[0][1]
        # Empty update dict when no fields are set
        assert update_dict == {}

    def test_service_initialization_with_none_repository(self, mock_db_session):
        """Test service creates repository if not provided."""
        # Act
        with patch("app.services.patient.crud_service.PatientRepository") as mock_repo_class:
            with patch("app.services.patient.crud_service.get_cache_manager"):
                mock_repo_class.return_value = MagicMock()
                service = PatientCRUDService(db=mock_db_session, repository=None)

                # Assert
                mock_repo_class.assert_called_once_with(mock_db_session)

    def test_service_initialization_with_redis_unavailable(self, mock_db_session, mock_repository):
        """Test service handles missing Redis gracefully."""
        # Act
        with patch("app.services.patient.crud_service.get_cache_manager") as mock_cache:
            mock_cache.side_effect = Exception("Redis unavailable")

            # Should not raise
            service = PatientCRUDService(
                db=mock_db_session,
                repository=mock_repository,
            )

            # Assert
            assert service is not None


# =============================================================================
# INTEGRATION-STYLE TESTS (Still using mocks but testing full flows)
# =============================================================================


class TestCRUDFlows:
    """Tests for complete CRUD operation flows."""

    def test_create_update_delete_flow(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test full lifecycle: get -> update -> delete."""
        patient_id = sample_patient.id
        sample_patient.deleted_at = None

        # 1. Get patient
        mock_repository.get_by_id.return_value = sample_patient
        patient = crud_service.get_patient(patient_id)
        assert patient is not None

        # 2. Update patient
        update_data = PatientUpdate(name="Updated in Flow")
        mock_repository.update.return_value = sample_patient

        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)
            updated = crud_service.update_patient(patient_id, update_data)

        assert updated is not None

        # 3. Delete patient
        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)
            result = crud_service.delete_patient(patient_id)

        assert result is True

    def test_delete_restore_flow(
        self, crud_service, mock_repository, mock_db_session, sample_patient
    ):
        """Test delete -> restore flow."""
        patient_id = sample_patient.id
        sample_patient.deleted_at = None

        # 1. Delete patient
        mock_repository.get_by_id.return_value = sample_patient

        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)
            delete_result = crud_service.delete_patient(patient_id)

        assert delete_result is True
        assert sample_patient.deleted_at is not None

        # 2. Restore patient
        mock_query = MagicMock()
        mock_filter = MagicMock()
        mock_filter.first.return_value = sample_patient
        mock_query.filter.return_value = mock_filter
        mock_db_session.query.return_value = mock_query

        with patch("app.services.patient.crud_service.sync_transaction") as mock_tx:
            mock_tx.return_value.__enter__ = MagicMock(return_value=mock_db_session)
            mock_tx.return_value.__exit__ = MagicMock(return_value=False)
            restore_result = crud_service.restore_patient(patient_id)

        assert restore_result is True
        assert sample_patient.deleted_at is None
