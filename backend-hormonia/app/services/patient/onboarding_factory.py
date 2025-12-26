"""
Factory for OnboardingCoordinator and related services.

This factory handles dependency injection for patient onboarding workflow.

Phase 2 Simplification:
- Removed SagaIntegrationService wrapper (0% business logic)
- Now passes SagaOrchestrator directly to coordinator

FIX: Uses TYPE_CHECKING to avoid circular import with SagaOrchestrator.
The actual import happens at runtime inside the function.
"""

from __future__ import annotations

# Standard library imports
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any, Optional

# Third-party imports
from sqlalchemy.ext.asyncio import AsyncSession

# Local application imports
from app.domain.messaging.core import MessageService
from app.domain.patient.onboarding.completion_service import CompletionService
from app.domain.patient.onboarding.coordinator import OnboardingCoordinator
from app.domain.patient.onboarding.creation_service import CreationService
from app.domain.patient.onboarding.notification_service import NotificationService
from app.domain.patient.onboarding.validation_service import ValidationService
from app.repositories.patient import PatientRepository
from app.services.enhanced_flow_engine import get_enhanced_flow_engine
from app.services.patient.flow_service import PatientFlowService
from app.services.patient.integrity_service import PatientIntegrityService
from app.services.unified_whatsapp_service import UnifiedWhatsAppService

# FIX: Use TYPE_CHECKING to avoid circular import
# SagaOrchestrator imports PatientFlowService which causes circular import chain
if TYPE_CHECKING:
    from app.orchestration.saga_orchestrator import SagaOrchestrator

# Module-level executor removed - now using centralized executor manager
# Use get_io_executor() for shared I/O operations


def get_onboarding_coordinator(
    db: Any, saga_orchestrator: Optional["SagaOrchestrator"] = None
) -> OnboardingCoordinator:
    """
    Factory function to create a fully configured OnboardingCoordinator instance.
    Handles all dependency injection and service wiring.

    Phase 2 Simplification:
    - Removed SagaIntegrationService wrapper (0% business logic)
    - Now passes SagaOrchestrator directly to coordinator
    """
    # Base Repositories & Services
    repo = PatientRepository(db)
    integrity_service = PatientIntegrityService(db, repo)

    enhanced_flow_engine = get_enhanced_flow_engine(db)
    flow_service = PatientFlowService(db, enhanced_flow_engine)

    message_service = MessageService(db)
    whatsapp_service = UnifiedWhatsAppService(db)

    # Use centralized I/O executor for all domain services
    shared_executor = get_io_executor()

    # Domain Services
    validation_service = ValidationService(db=db, executor=shared_executor)

    notification_service = NotificationService(
        message_service=message_service,
        whatsapp_service=whatsapp_service,
        executor=shared_executor,
    )

    completion_service = CompletionService(
        db=db,
        flow_service=flow_service,
        notification_service=notification_service,
        executor=shared_executor,
    )

    creation_service = CreationService(
        db=db,
        integrity_service=integrity_service,
        completion_service=completion_service,
        notification_service=notification_service,
        validation_service=validation_service,
        flow_service=flow_service,
        executor=shared_executor,
    )

    # Coordinator (now uses SagaOrchestrator directly - Phase 2 simplification)
    return OnboardingCoordinator(
        db=db,
        integrity_service=integrity_service,
        validation_service=validation_service,
        saga_orchestrator=saga_orchestrator,  # Direct usage, no wrapper
        notification_service=notification_service,
        completion_service=completion_service,
        creation_service=creation_service,
    )
