"""
Unit tests for alerts schema compatibility.

Tests the Alert model property mappings and repository methods
to ensure they work with the existing database schema.
"""
import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, MagicMock

# Import models directly to avoid circular imports
from app.models.alert import Alert, AlertSeverity, AlertStatus


class TestAlertModelSchemaCompatibility:
    """Test Alert model property mappings for schema compatibility."""
    
    def test_alert_type_column_mapping(self):
        """Test that alert_type maps to 'type' column."""
        # Check that the column is mapped correctly in the table definition
        assert hasattr(Alert.__table__.columns, 'type')
        assert Alert.__table__.columns['type'].name == 'type'
        
        # Test that we can set the attribute
        alert = Alert()
        alert.alert_type = "urgency"
        assert alert.alert_type == "urgency"
    
    def test_description_column_mapping(self):
        """Test that description maps to 'message' column."""
        # Check that the column is mapped correctly in the table definition
        assert hasattr(Alert.__table__.columns, 'message')
        assert Alert.__table__.columns['message'].name == 'message'
        
        # Test that we can set the attribute
        alert = Alert()
        alert.description = "Test alert message"
        assert alert.description == "Test alert message"
    
    def test_status_property_mapping_to_acknowledged_boolean(self):
        """Test that status property maps to acknowledged boolean."""
        alert = Alert()
        alert.acknowledged = False  # Initialize the field
        
        # Test setting status to acknowledged
        alert.status = "acknowledged"
        assert alert.acknowledged is True
        assert alert.status == "acknowledged"
        
        # Test setting status to pending
        alert.status = "pending"
        assert alert.acknowledged is False
        assert alert.status == "pending"
        
        # Test setting status to other values
        alert.status = "resolved"
        assert alert.acknowledged is False
        assert alert.status == "pending"  # Non-acknowledged status maps to pending
    
    def test_quiz_session_id_storage_in_jsonb_data_field(self):
        """Test quiz_session_id storage and retrieval from JSONB data field."""
        alert = Alert()
        alert.data = {}  # Initialize the data field
        test_uuid = uuid.uuid4()
        
        # Test setting quiz_session_id
        alert.quiz_session_id = test_uuid
        assert alert.data["quiz_session_id"] == str(test_uuid)
        assert alert.quiz_session_id == test_uuid
        
        # Test getting quiz_session_id
        retrieved_uuid = alert.quiz_session_id
        assert retrieved_uuid == test_uuid
        assert isinstance(retrieved_uuid, uuid.UUID)
    
    def test_quiz_session_id_none_handling(self):
        """Test quiz_session_id handling when None or not set."""
        alert = Alert()
        
        # Test when data is None
        alert.data = None
        assert alert.quiz_session_id is None
        
        # Test when data exists but no quiz_session_id
        alert.data = {"other_field": "value"}
        assert alert.quiz_session_id is None
        
        # Test setting to None
        alert.data = {}  # Initialize first
        alert.quiz_session_id = uuid.uuid4()
        alert.quiz_session_id = None
        assert "quiz_session_id" not in alert.data
        assert alert.quiz_session_id is None
    
    def test_quiz_session_id_invalid_uuid_handling(self):
        """Test quiz_session_id handling with invalid UUID in data."""
        alert = Alert()
        alert.data = {"quiz_session_id": "invalid-uuid"}
        
        # Should return None for invalid UUID
        assert alert.quiz_session_id is None
    
    def test_alert_model_initialization_with_schema_fields(self):
        """Test Alert model initialization with schema-compatible fields."""
        patient_id = uuid.uuid4()
        
        # Create alert without SQLAlchemy session
        alert = Alert()
        alert.patient_id = patient_id
        alert.alert_type = "symptom"
        alert.severity = AlertSeverity.HIGH
        alert.description = "Patient reported severe pain"
        alert.acknowledged = False
        alert.data = {"additional_info": "test"}
        
        assert alert.patient_id == patient_id
        assert alert.alert_type == "symptom"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.description == "Patient reported severe pain"
        assert alert.acknowledged is False
        assert alert.status == "pending"
        assert alert.data["additional_info"] == "test"


class TestAlertRepositorySchemaCompatibility:
    """Test AlertRepository methods work with schema-compatible queries."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        return Mock()
    
    @pytest.fixture
    def alert_repository(self, mock_db_session):
        """Create AlertRepository with mock session."""
        # Import here to avoid circular imports
        from app.repositories.alert import AlertRepository
        return AlertRepository(mock_db_session)
    
    @pytest.fixture
    def sample_alerts(self):
        """Create sample alerts for testing."""
        alerts = []
        for i in range(3):
            alert = Alert(
                id=uuid.uuid4(),
                patient_id=uuid.uuid4(),
                alert_type=f"type_{i}",
                severity=AlertSeverity.MEDIUM,
                description=f"Alert {i}",
                acknowledged=(i % 2 == 0),  # Alternate acknowledged status
                data={"quiz_session_id": str(uuid.uuid4())} if i == 0 else {}
            )
            alerts.append(alert)
        return alerts
    
    def test_get_by_quiz_session_uses_jsonb_query(self, alert_repository, mock_db_session):
        """Test get_by_quiz_session method uses JSONB data field queries."""
        quiz_session_id = uuid.uuid4()
        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        
        alert_repository.get_by_quiz_session(quiz_session_id)
        
        # Verify query was called with correct filter
        mock_db_session.query.assert_called_once_with(Alert)
        mock_query.filter.assert_called_once()
        mock_query.order_by.assert_called_once()
        mock_query.all.assert_called_once()
    
    def test_get_by_status_uses_acknowledged_boolean_field(self, alert_repository, mock_db_session):
        """Test get_by_status method uses acknowledged boolean field."""
        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.all.return_value = []
        
        # Test acknowledged status
        alert_repository.get_by_status("acknowledged")
        mock_query.filter.assert_called()
        
        # Test pending status
        alert_repository.get_by_status("pending")
        mock_query.filter.assert_called()
    
    def test_get_unacknowledged_uses_boolean_field(self, alert_repository, mock_db_session):
        """Test get_unacknowledged method uses acknowledged boolean field."""
        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        alert_repository.get_unacknowledged()
        
        # Verify query structure
        mock_db_session.query.assert_called_once_with(Alert)
        mock_query.filter.assert_called_once()
        mock_query.order_by.assert_called_once()
    
    def test_count_unacknowledged_uses_boolean_field(self, alert_repository, mock_db_session):
        """Test count_unacknowledged method uses acknowledged boolean field."""
        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 5
        
        result = alert_repository.count_unacknowledged()
        
        assert result == 5
        mock_db_session.query.assert_called_once_with(Alert)
        mock_query.filter.assert_called_once()
        mock_query.count.assert_called_once()
    
    def test_get_critical_unacknowledged_uses_boolean_field(self, alert_repository, mock_db_session):
        """Test get_critical_unacknowledged uses acknowledged boolean field."""
        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        alert_repository.get_critical_unacknowledged()
        
        # Verify query structure
        mock_db_session.query.assert_called_once_with(Alert)
        mock_query.filter.assert_called_once()
        mock_query.order_by.assert_called_once()
    
    def test_bulk_update_status_maps_to_acknowledged_field(self, alert_repository, mock_db_session):
        """Test bulk_update_status maps status enum to acknowledged boolean field."""
        alert_ids = [uuid.uuid4(), uuid.uuid4()]
        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.update.return_value = 2
        
        result = alert_repository.bulk_update_status(
            alert_ids, 
            AlertStatus.ACKNOWLEDGED,
            acknowledged_by=uuid.uuid4()
        )
        
        assert result == 2
        mock_db_session.query.assert_called_once_with(Alert)
        mock_query.filter.assert_called_once()
        mock_query.update.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    def test_get_alerts_by_patient_and_status_maps_enum_to_boolean(self, alert_repository, mock_db_session):
        """Test get_alerts_by_patient_and_status maps status enum to acknowledged boolean."""
        patient_id = uuid.uuid4()
        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        
        # Test with ACKNOWLEDGED status
        alert_repository.get_alerts_by_patient_and_status(patient_id, AlertStatus.ACKNOWLEDGED)
        
        # Test with PENDING status
        alert_repository.get_alerts_by_patient_and_status(patient_id, AlertStatus.PENDING)
        
        # Verify queries were made
        assert mock_db_session.query.call_count == 2
        assert mock_query.filter.call_count == 2
    
    def test_get_alerts_summary_uses_acknowledged_field(self, alert_repository, mock_db_session):
        """Test get_alerts_summary uses acknowledged boolean field to derive status."""
        mock_query = Mock()
        mock_db_session.query.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        mock_query.all.return_value = [
            (True, AlertSeverity.HIGH, 2),   # acknowledged=True, severity=HIGH, count=2
            (False, AlertSeverity.MEDIUM, 3) # acknowledged=False, severity=MEDIUM, count=3
        ]
        
        result = alert_repository.get_alerts_summary()
        
        expected = {
            'by_status': {'acknowledged': 2, 'pending': 3},
            'by_severity': {'high': 2, 'medium': 3},
            'total': 5
        }
        
        assert result == expected
        mock_db_session.query.assert_called_once()
        mock_query.group_by.assert_called_once()
    
    def test_repository_error_handling(self, alert_repository, mock_db_session):
        """Test repository methods handle database errors properly."""
        from app.exceptions import DatabaseError
        
        quiz_session_id = uuid.uuid4()
        mock_db_session.query.side_effect = Exception("Database error")
        
        with pytest.raises(DatabaseError) as exc_info:
            alert_repository.get_by_quiz_session(quiz_session_id)
        
        assert "Failed to retrieve alerts by quiz session" in str(exc_info.value)
    
    def test_bulk_update_validation_error(self, alert_repository):
        """Test bulk_update_status raises ValidationError for empty alert_ids."""
        from app.exceptions import ValidationError
        
        with pytest.raises(ValidationError) as exc_info:
            alert_repository.bulk_update_status([], AlertStatus.ACKNOWLEDGED)
        
        assert "Alert IDs list cannot be empty" in str(exc_info.value)


class TestAlertSchemaCompatibilityIntegration:
    """Integration tests for Alert model and repository schema compatibility."""
    
    def test_alert_creation_with_schema_compatible_fields(self):
        """Test creating Alert with schema-compatible field mappings."""
        patient_id = uuid.uuid4()
        quiz_session_id = uuid.uuid4()
        
        alert = Alert(
            patient_id=patient_id,
            alert_type="quiz_response",  # Maps to 'type' column
            severity=AlertSeverity.CRITICAL,
            description="Critical quiz response detected",  # Maps to 'message' column
            acknowledged=False,  # Direct boolean field
            data={}
        )
        
        # Set quiz_session_id via property (stored in data JSONB)
        alert.quiz_session_id = quiz_session_id
        
        # Verify all mappings work correctly
        assert alert.patient_id == patient_id
        assert alert.alert_type == "quiz_response"
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.description == "Critical quiz response detected"
        assert alert.acknowledged is False
        assert alert.status == "pending"
        assert alert.quiz_session_id == quiz_session_id
        assert alert.data["quiz_session_id"] == str(quiz_session_id)
    
    def test_status_property_bidirectional_mapping(self):
        """Test that status property works bidirectionally with acknowledged field."""
        alert = Alert()
        
        # Test setting via status property
        alert.status = "acknowledged"
        assert alert.acknowledged is True
        
        # Test setting via acknowledged field directly
        alert.acknowledged = False
        assert alert.status == "pending"
        
        # Test round-trip
        alert.status = "acknowledged"
        assert alert.acknowledged is True
        assert alert.status == "acknowledged"
    
    def test_quiz_session_id_property_with_data_field_manipulation(self):
        """Test quiz_session_id property handles data field manipulation correctly."""
        alert = Alert()
        quiz_id_1 = uuid.uuid4()
        quiz_id_2 = uuid.uuid4()
        
        # Test initial setting
        alert.quiz_session_id = quiz_id_1
        assert alert.quiz_session_id == quiz_id_1
        assert alert.data["quiz_session_id"] == str(quiz_id_1)
        
        # Test updating
        alert.quiz_session_id = quiz_id_2
        assert alert.quiz_session_id == quiz_id_2
        assert alert.data["quiz_session_id"] == str(quiz_id_2)
        
        # Test clearing
        alert.quiz_session_id = None
        assert alert.quiz_session_id is None
        assert "quiz_session_id" not in alert.data
        
        # Test with existing data
        alert.data = {"other_field": "value"}
        alert.quiz_session_id = quiz_id_1
        assert alert.quiz_session_id == quiz_id_1
        assert alert.data["quiz_session_id"] == str(quiz_id_1)
        assert alert.data["other_field"] == "value"  # Other data preserved