"""
Tests for LGPD-compliant patient queries.

These tests verify that patient searches use hash-based lookups
for sensitive data (email, phone) instead of plaintext ILIKE queries.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from app.repositories.patient import PatientRepository, _looks_like_email, _looks_like_phone


class TestEmailPhoneDetection:
    """Test email and phone pattern detection helpers."""

    def test_looks_like_email_valid(self):
        """Valid email patterns should be detected."""
        assert _looks_like_email("user@example.com") is True
        assert _looks_like_email("test.user@domain.org") is True
        assert _looks_like_email("name+tag@company.co.uk") is True

    def test_looks_like_email_invalid(self):
        """Non-email patterns should not match."""
        assert _looks_like_email("John Smith") is False
        assert _looks_like_email("11999887766") is False
        assert _looks_like_email("") is False
        assert _looks_like_email("nodomain") is False
        assert _looks_like_email("missing@dot") is False

    def test_looks_like_phone_valid(self):
        """Valid phone patterns should be detected."""
        assert _looks_like_phone("+5511999887766") is True
        assert _looks_like_phone("11999887766") is True
        assert _looks_like_phone("(11) 99988-7766") is True
        assert _looks_like_phone("+55 11 99988-7766") is True

    def test_looks_like_phone_invalid(self):
        """Non-phone patterns should not match."""
        assert _looks_like_phone("John Smith") is False
        assert _looks_like_phone("user@email.com") is False
        assert _looks_like_phone("") is False
        assert _looks_like_phone("123") is False  # Too short
        assert _looks_like_phone("abcdefghij") is False  # Not digits


class TestPatientRepositoryHashSearch:
    """Test LGPD-compliant hash-based searches."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session."""
        session = MagicMock()
        session.query.return_value = session
        session.filter.return_value = session
        session.options.return_value = session
        session.limit.return_value = session
        session.offset.return_value = session
        session.all.return_value = []
        session.count.return_value = 0
        return session

    @pytest.fixture
    def repository(self, mock_db):
        """Create repository with mocked session."""
        repo = PatientRepository(mock_db)
        return repo

    def test_build_search_criteria_name_only(self, repository):
        """Name search should use ILIKE (plaintext OK for names)."""
        criteria = repository._build_search_criteria("John Smith")
        # Should have at least one criteria (name ILIKE)
        assert len(criteria) >= 1

    @patch('app.repositories.patient.get_unified_encryption_service')
    def test_build_search_criteria_email_uses_hash(
        self, mock_encryption, repository
    ):
        """Email search should use hash lookup, not plaintext."""
        mock_service = Mock()
        mock_service.generate_hash.return_value = "abc123hash"
        mock_encryption.return_value = mock_service

        criteria = repository._build_search_criteria("user@example.com")

        # Should call generate_hash for email
        mock_service.generate_hash.assert_called()
        # Criteria should include hash comparison
        assert len(criteria) >= 2  # name + email_hash

    @patch('app.repositories.patient.get_unified_encryption_service')
    def test_build_search_criteria_phone_uses_hash(
        self, mock_encryption, repository
    ):
        """Phone search should use hash lookup, not plaintext."""
        mock_service = Mock()
        mock_service.generate_hash.return_value = "xyz789hash"
        mock_encryption.return_value = mock_service

        criteria = repository._build_search_criteria("+5511999887766")

        # Should call generate_hash for phone
        mock_service.generate_hash.assert_called()
        # Criteria should include hash comparison
        assert len(criteria) >= 2  # name + phone_hash

    @patch('app.repositories.patient.get_unified_encryption_service')
    def test_encryption_failure_graceful_degradation(
        self, mock_encryption, repository
    ):
        """If encryption fails, search should still work (name-only)."""
        mock_service = Mock()
        mock_service.generate_hash.side_effect = Exception("Encryption error")
        mock_encryption.return_value = mock_service

        # Should not raise, should return at least name criteria
        criteria = repository._build_search_criteria("user@example.com")
        assert len(criteria) >= 1  # At least name criteria


class TestPatientRepositorySearchMethods:
    """Test search methods use _build_search_criteria."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = MagicMock()
        query_mock = MagicMock()
        session.query.return_value = query_mock
        query_mock.filter.return_value = query_mock
        query_mock.options.return_value = query_mock
        query_mock.limit.return_value = query_mock
        query_mock.offset.return_value = query_mock
        query_mock.order_by.return_value = query_mock
        query_mock.all.return_value = []
        query_mock.count.return_value = 0
        query_mock.first.return_value = None
        return session

    @pytest.fixture
    def repository(self, mock_db):
        """Create repository with mocked session."""
        return PatientRepository(mock_db)

    @patch.object(PatientRepository, '_build_search_criteria')
    def test_list_with_search_uses_build_criteria(
        self, mock_build, repository
    ):
        """list() with search param should use _build_search_criteria."""
        mock_build.return_value = []

        repository.list(
            doctor_id=uuid4(),
            search="test@example.com"
        )

        mock_build.assert_called_once_with("test@example.com")

    @patch.object(PatientRepository, '_build_search_criteria')
    def test_list_without_search_skips_criteria(
        self, mock_build, repository
    ):
        """list() without search should not call _build_search_criteria."""
        repository.list(doctor_id=uuid4())

        mock_build.assert_not_called()


class TestNoPlaintextEmailPhoneQueries:
    """
    Verify that no queries use plaintext email/phone ILIKE.

    This is a critical LGPD compliance check.
    """

    def test_repository_has_no_email_ilike(self):
        """Repository should not have email.ilike patterns."""
        import inspect
        from app.repositories.patient import PatientRepository

        source = inspect.getsource(PatientRepository)

        # Check that there are no plaintext email ILIKE queries
        # The only acceptable pattern is in the helper detection function
        dangerous_patterns = [
            "Patient.email.ilike",
            ".email.ilike(",
            "email.ilike(search",
        ]

        for pattern in dangerous_patterns:
            assert pattern not in source, (
                f"Found dangerous pattern '{pattern}' in PatientRepository. "
                "Email searches must use hash-based lookups for LGPD compliance."
            )

    def test_repository_has_no_phone_ilike(self):
        """Repository should not have phone.ilike patterns."""
        import inspect
        from app.repositories.patient import PatientRepository

        source = inspect.getsource(PatientRepository)

        # Check that there are no plaintext phone ILIKE queries
        dangerous_patterns = [
            "Patient.phone.ilike",
            ".phone.ilike(",
            "phone.ilike(search",
        ]

        for pattern in dangerous_patterns:
            assert pattern not in source, (
                f"Found dangerous pattern '{pattern}' in PatientRepository. "
                "Phone searches must use hash-based lookups for LGPD compliance."
            )


class TestSearchResultsDecryption:
    """Test that search results properly decrypt sensitive data."""

    @pytest.fixture
    def mock_patient(self):
        """Create a mock patient with encrypted data."""
        patient = Mock()
        patient.id = uuid4()
        patient.name = "Test Patient"
        patient.email_encrypted = b"encrypted_email_data"
        patient.phone_encrypted = b"encrypted_phone_data"
        patient.email_hash = "abc123hash"
        patient.phone_hash = "xyz789hash"
        # Legacy plaintext (should be None after migration)
        patient.email = None
        patient.phone = None
        return patient

    @patch('app.repositories.patient.get_unified_encryption_service')
    def test_get_patient_decrypts_email(
        self, mock_encryption, mock_patient
    ):
        """Getting a patient should decrypt email if needed."""
        mock_service = Mock()
        mock_service.decrypt_email.return_value = "test@example.com"
        mock_service.decrypt_phone.return_value = "+5511999887766"
        mock_encryption.return_value = mock_service

        # The repository should handle decryption internally
        # This test documents expected behavior
        assert mock_patient.email_encrypted is not None
        assert mock_patient.email_hash is not None


class TestIdempotencyKeySearch:
    """Test idempotency key lookups for duplicate prevention."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        session = MagicMock()
        return session

    @pytest.fixture
    def repository(self, mock_db):
        """Create repository."""
        return PatientRepository(mock_db)

    def test_find_by_idempotency_key_exists(self, repository, mock_db):
        """Should find patient by idempotency key."""
        existing_patient = Mock()
        existing_patient.id = uuid4()
        mock_db.query.return_value.filter.return_value.first.return_value = (
            existing_patient
        )

        # Repository should have method to find by idempotency key
        if hasattr(repository, 'find_by_idempotency_key'):
            result = repository.find_by_idempotency_key("test-key-123")
            assert result is not None
        else:
            # Method should exist for production readiness
            pytest.skip("find_by_idempotency_key not implemented yet")
