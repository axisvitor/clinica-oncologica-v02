from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor
# from sqlalchemy.orm import

from app.repositories.patient import PatientRepository
from app.services.patient.integrity_service import PatientIntegrityService
from app.services.patient.flow_service import PatientFlowService
from app.domain.messaging.core import MessageService
from app.services.unified_whatsapp_service import UnifiedWhatsAppService
from app.services.enhanced_flow_engine import get_enhanced_flow_engine
from app.domain.patient.onboarding.coordinator import OnboardingCoordinator
from app.domain.patient.onboarding.validation_service import ValidationService
from app.domain.patient.onboarding.saga_integration_service import SagaIntegrationService
from app.domain.patient.onboarding.notification_service import NotificationService
from app.domain.patient.onboarding.completion_service import CompletionService
from app.domain.patient.onboarding.creation_service import CreationService
from app.orchestration.saga_orchestrator import SagaOrchestrator

# Global thread pool for sync operations in async context
_onboarding_thread_pool = ThreadPoolExecutor(max_workers=5, thread_name_prefix="onboarding_factory")

def get_onboarding_coordinator(db: Any, saga_orchestrator: Optional[SagaOrchestrator] = None) -> OnboardingCoordinator:
    """
    Factory function to create a fully configured OnboardingCoordinator instance.
    Handles all dependency injection and service wiring.
    """
    # Base Repositories & Services
    repo = PatientRepository(db)
    integrity_service = PatientIntegrityService(db, repo)
    
    enhanced_flow_engine = get_enhanced_flow_engine(db)
    flow_service = PatientFlowService(db, enhanced_flow_engine)
    
    message_service = MessageService(db)
    whatsapp_service = UnifiedWhatsAppService(db)
    
    # Domain Services
    validation_service = ValidationService(db=db, executor=_onboarding_thread_pool)
    
    notification_service = NotificationService(
        message_service=message_service,
        whatsapp_service=whatsapp_service,
        executor=_onboarding_thread_pool,
    )
    
    saga_integration_service = SagaIntegrationService(
        saga_orchestrator=saga_orchestrator
    )
    
    completion_service = CompletionService(
        db=db,
        flow_service=flow_service,
        notification_service=notification_service,
        executor=_onboarding_thread_pool,
    )
    
    creation_service = CreationService(
        db=db,
        integrity_service=integrity_service,
        completion_service=completion_service,
        notification_service=notification_service,
        validation_service=validation_service,
        flow_service=flow_service,
        executor=_onboarding_thread_pool,
    )
    
    # Coordinator
    return OnboardingCoordinator(
        db=db,
        integrity_service=integrity_service,
        validation_service=validation_service,
        saga_service=saga_integration_service,
        notification_service=notification_service,
        completion_service=completion_service,
        creation_service=creation_service,
    )
