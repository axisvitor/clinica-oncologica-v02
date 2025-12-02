"""
Test Dependency Injection Implementation (ISSUE-004)

Validates that PatientOnboardingService properly implements dependency injection
for MessageService and UnifiedWhatsAppService.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy.orm import Session

from app.domain.patient.onboarding.coordinator import PatientOnboardingService
from app.services.patient.integrity_service import PatientIntegrityService
from app.services.patient.flow_service import PatientFlowService
from app.services.message import MessageService
from app.services.unified_whatsapp_service import UnifiedWhatsAppService


class TestDependencyInjection:
    """Test suite for ISSUE-004: Dependency Injection Pattern"""

    def test_constructor_accepts_injected_services(self):
        """Test that constructor accepts message_service and whatsapp_service"""
        # Arrange
        mock_db = Mock(spec=Session)
        mock_integrity = Mock(spec=PatientIntegrityService)
        mock_flow = Mock(spec=PatientFlowService)
        mock_message_service = Mock(spec=MessageService)
        mock_whatsapp_service = Mock(spec=UnifiedWhatsAppService)

        # Act
        service = PatientOnboardingService(
            db=mock_db,
            integrity_service=mock_integrity,
            flow_service=mock_flow,
            message_service=mock_message_service,
            whatsapp_service=mock_whatsapp_service,
            saga_orchestrator=None
        )

        # Assert
        assert service.message_service is mock_message_service
        assert service.whatsapp_service is mock_whatsapp_service
        assert service.db is mock_db
        assert service.integrity_service is mock_integrity
        assert service.flow_service is mock_flow

    def test_no_internal_service_instantiation(self):
        """Test that services are NOT created internally"""
        # Arrange
        mock_db = Mock(spec=Session)
        mock_integrity = Mock(spec=PatientIntegrityService)
        mock_flow = Mock(spec=PatientFlowService)
        mock_message_service = Mock(spec=MessageService)
        mock_whatsapp_service = Mock(spec=UnifiedWhatsAppService)

        # Act - patch the service classes to detect if they're instantiated
        with patch('app.services.patient.onboarding_service.MessageService') as MockMessageService, \
             patch('app.services.patient.onboarding_service.UnifiedWhatsAppService') as MockWhatsAppService:

            service = PatientOnboardingService(
                db=mock_db,
                integrity_service=mock_integrity,
                flow_service=mock_flow,
                message_service=mock_message_service,
                whatsapp_service=mock_whatsapp_service,
                saga_orchestrator=None
            )

            # Assert - services should NOT be instantiated internally
            MockMessageService.assert_not_called()
            MockWhatsAppService.assert_not_called()

    def test_services_are_injectable_for_mocking(self):
        """Test that injected services can be easily mocked for testing"""
        # Arrange
        mock_db = Mock(spec=Session)
        mock_integrity = Mock(spec=PatientIntegrityService)
        mock_flow = Mock(spec=PatientFlowService)

        # Create mock services with specific behavior
        mock_message_service = MagicMock(spec=MessageService)
        mock_message_service.schedule_message.return_value = Mock(id=123, content="test")

        mock_whatsapp_service = MagicMock(spec=UnifiedWhatsAppService)
        mock_whatsapp_service.send_message.return_value = True

        # Act
        service = PatientOnboardingService(
            db=mock_db,
            integrity_service=mock_integrity,
            flow_service=mock_flow,
            message_service=mock_message_service,
            whatsapp_service=mock_whatsapp_service,
            saga_orchestrator=None
        )

        # Assert - we can control the behavior through injected mocks
        assert service.message_service.schedule_message.return_value.id == 123
        assert service.whatsapp_service.send_message.return_value is True

    def test_constructor_validates_dependency_injection_pattern(self):
        """Test that constructor follows proper DI pattern"""
        # Arrange
        mock_db = Mock(spec=Session)
        mock_integrity = Mock(spec=PatientIntegrityService)
        mock_flow = Mock(spec=PatientFlowService)
        mock_message_service = Mock(spec=MessageService)
        mock_whatsapp_service = Mock(spec=UnifiedWhatsAppService)

        # Act
        service = PatientOnboardingService(
            db=mock_db,
            integrity_service=mock_integrity,
            flow_service=mock_flow,
            message_service=mock_message_service,
            whatsapp_service=mock_whatsapp_service,
            saga_orchestrator=None
        )

        # Assert - all dependencies are injected, not created
        assert isinstance(service.message_service, Mock), "message_service should be injected"
        assert isinstance(service.whatsapp_service, Mock), "whatsapp_service should be injected"

        # Verify no internal creation happens
        assert service.message_service is mock_message_service
        assert service.whatsapp_service is mock_whatsapp_service


class TestDependencyInjectionDocumentation:
    """Verify that code includes proper DI documentation"""

    def test_constructor_has_di_documentation(self):
        """Verify constructor docstring mentions dependency injection"""
        # Get the constructor's docstring
        docstring = PatientOnboardingService.__init__.__doc__

        # Assertions
        assert docstring is not None, "Constructor should have documentation"
        assert "DEPENDENCY INJECTION" in docstring.upper(), "Should mention dependency injection pattern"
        assert "message_service" in docstring, "Should document message_service parameter"
        assert "whatsapp_service" in docstring, "Should document whatsapp_service parameter"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
