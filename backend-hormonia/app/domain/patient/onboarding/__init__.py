"""
Patient Onboarding Domain - Modular architecture following SRP.

This package contains specialized services for patient onboarding,
each with a single responsibility:

- ValidationService: Patient data validation and duplicate detection
- SagaIntegrationService: Saga pattern orchestration
- NotificationService: Notification delivery (WhatsApp, WebSocket)
- CompletionService: Partial onboarding completion
- CreationService: Direct patient creation
- OnboardingCoordinator: High-level workflow orchestration (ISSUE-005 Phase 5)
"""

from .validation_service import ValidationService
from .saga_integration_service import SagaIntegrationService
from .notification_service import NotificationService
from .completion_service import CompletionService
from .creation_service import CreationService
from .coordinator import OnboardingCoordinator

__all__ = [
    "ValidationService",
    "SagaIntegrationService",
    "NotificationService",
    "CompletionService",
    "CreationService",
    "OnboardingCoordinator",
]
