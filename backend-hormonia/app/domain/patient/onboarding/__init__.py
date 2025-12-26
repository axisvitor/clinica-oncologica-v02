"""
Patient Onboarding Domain - Modular architecture following SRP.

This package contains specialized services for patient onboarding,
each with a single responsibility:

- ValidationService: Patient data validation and duplicate detection
- NotificationService: Notification delivery (WhatsApp, WebSocket)
- CompletionService: Partial onboarding completion
- CreationService: Direct patient creation
- OnboardingCoordinator: High-level workflow orchestration (ISSUE-005 Phase 5)

Phase 2 Simplification:
- Removed SagaIntegrationService wrapper (0% business logic)
- OnboardingCoordinator now uses SagaOrchestrator directly
"""

from __future__ import annotations

from app.domain.patient.onboarding.completion_service import CompletionService
from app.domain.patient.onboarding.coordinator import OnboardingCoordinator
from app.domain.patient.onboarding.creation_service import CreationService
from app.domain.patient.onboarding.notification_service import NotificationService
from app.domain.patient.onboarding.validation_service import ValidationService

__all__ = [
    "CompletionService",
    "CreationService",
    "NotificationService",
    "OnboardingCoordinator",
    "ValidationService",
]
