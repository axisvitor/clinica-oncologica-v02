"""
Tests for PatientFlowService template to FlowType mapping.
Verifies that the service correctly uses the configuration to map template names to FlowType enums.
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

from app.services.patient.flow_service import PatientFlowService
from app.services.flow_core import FlowType
from app.models.patient import Patient
from app.config.template_loader import FlowTypeConfig

@pytest.mark.asyncio
class TestFlowServiceMapping:
    
    async def test_initialize_default_flow_uses_config_mapping(self):
        """Test that initialize_default_flow uses config enum_value."""
        # Mock dependencies
        mock_db = Mock()
        mock_flow_engine = AsyncMock()
        mock_flow_engine.enroll_patient.return_value = Mock(started_at=Mock(isoformat=lambda: "2023-01-01"))
        
        service = PatientFlowService(db=mock_db, flow_engine=mock_flow_engine)
        
        # Mock patient
        patient = Mock(spec=Patient)
        patient.id = uuid4()
        patient.treatment_type = "hormone"
        patient.patient_data = {}
        
        # Mock template loader
        with patch("app.services.patient.flow_service.get_template_loader") as mock_get_loader:
            mock_loader = mock_get_loader.return_value
            
            # Mock get_template_for_treatment to return a specific template
            with patch("app.services.patient.flow_service.get_template_for_treatment", return_value="hormone_therapy_1"):
                
                # Mock get_flow_type_config to return config with enum_value
                mock_config = Mock(spec=FlowTypeConfig)
                mock_config.enum_value = "initial_15_days"
                mock_loader.get_flow_type_config.return_value = mock_config
                
                # Execute
                await service.initialize_default_flow(patient)
                
                # Verify enroll_patient was called with correct FlowType
                mock_flow_engine.enroll_patient.assert_called_once()
                call_args = mock_flow_engine.enroll_patient.call_args
                assert call_args.kwargs["flow_type"] == FlowType.INITIAL_15_DAYS

    async def test_initialize_default_flow_fallback_on_missing_config(self):
        """Test fallback to INITIAL_15_DAYS if config is missing."""
        mock_db = Mock()
        mock_flow_engine = AsyncMock()
        mock_flow_engine.enroll_patient.return_value = Mock(started_at=Mock(isoformat=lambda: "2023-01-01"))
        
        service = PatientFlowService(db=mock_db, flow_engine=mock_flow_engine)
        patient = Mock(spec=Patient)
        patient.id = uuid4()
        patient.treatment_type = "unknown"
        patient.patient_data = {}
        
        with patch("app.services.patient.flow_service.get_template_loader") as mock_get_loader:
            mock_loader = mock_get_loader.return_value
            
            with patch("app.services.patient.flow_service.get_template_for_treatment", return_value="unknown_template"):
                # Return None for config
                mock_loader.get_flow_type_config.return_value = None
                
                await service.initialize_default_flow(patient)
                
                # Should default to INITIAL_15_DAYS
                call_args = mock_flow_engine.enroll_patient.call_args
                assert call_args.kwargs["flow_type"] == FlowType.INITIAL_15_DAYS

    async def test_initialize_default_flow_fallback_on_invalid_enum(self):
        """Test fallback to INITIAL_15_DAYS if enum_value is invalid."""
        mock_db = Mock()
        mock_flow_engine = AsyncMock()
        mock_flow_engine.enroll_patient.return_value = Mock(started_at=Mock(isoformat=lambda: "2023-01-01"))
        
        service = PatientFlowService(db=mock_db, flow_engine=mock_flow_engine)
        patient = Mock(spec=Patient)
        patient.id = uuid4()
        patient.treatment_type = "hormone"
        patient.patient_data = {}
        
        with patch("app.services.patient.flow_service.get_template_loader") as mock_get_loader:
            mock_loader = mock_get_loader.return_value
            
            with patch("app.services.patient.flow_service.get_template_for_treatment", return_value="hormone_therapy_1"):
                
                mock_config = Mock(spec=FlowTypeConfig)
                mock_config.enum_value = "invalid_enum_value"
                mock_loader.get_flow_type_config.return_value = mock_config
                
                await service.initialize_default_flow(patient)
                
                # Should default to INITIAL_15_DAYS
                call_args = mock_flow_engine.enroll_patient.call_args
                assert call_args.kwargs["flow_type"] == FlowType.INITIAL_15_DAYS
