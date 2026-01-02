import pytest
from unittest.mock import MagicMock
from app.service_provider import ServiceProvider
from app.services.patient.crud_service import PatientCRUDService

def test_patient_service_initialization_success():
    """
    Verification test for PatientCRUDService initialization.
    """
    # Mock dependencies
    mock_db = MagicMock()
    mock_redis = MagicMock()
    
    # Initialize ServiceProvider
    provider = ServiceProvider(db=mock_db, redis_client=mock_redis)
    
    # Assert that accessing patient_service returns an instance of PatientCRUDService
    service = provider.patient_service
    assert isinstance(service, PatientCRUDService)
    assert service.db == mock_db