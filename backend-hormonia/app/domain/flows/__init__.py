"""
Flow Domain Module - Domain-Driven Design for Flow Orchestration

This module provides a modular, domain-driven architecture for flow management,
replacing the monolithic flow_orchestrator.py with focused, single-responsibility modules.

Architecture:
- orchestrator.py: Thin coordinator that delegates to domain modules
- state/: Flow state management and validation
- messaging/: Message composition and delivery
- scheduling/: Quiz and follow-up scheduling
- templates/: Template rendering and context building
- rules/: Business rules execution
- ab_testing/: A/B testing management
- analytics/: Event tracking and metrics
- error_handling/: Error handling and recovery

Usage:
    from app.domain.flows import FlowOrchestrator, create_flow_orchestrator

    # Create orchestrator
    orchestrator = create_flow_orchestrator(db_session)

    # Start patient flow
    result = await orchestrator.start_patient_flow(patient_id)
"""

# Main orchestrator
from .orchestrator import (
    FlowOrchestrator,
    FlowExecutionContext,
    FlowExecutionResult,
    FlowExecutionState,
    FlowOperationType,
    create_flow_orchestrator,
    get_flow_orchestrator
)

# State management
from .state import FlowStateManager, FlowStateValidator

# Messaging
from .messaging import MessageComposer, MessageSender

# Scheduling
from .scheduling import QuizScheduler, FollowUpScheduler

# Templates
from .templates import TemplateRenderer, TemplateContextBuilder

# Rules
from .rules import FlowRulesEngine, RuleConditionEvaluator

# A/B Testing
from .ab_testing import ABTestManager, VariantSelector

# Analytics
from .analytics import AnalyticsCollector, FlowMetricsCalculator

# Error Handling
from .error_handling import (
    FlowErrorHandler,
    FlowError,
    ErrorSeverity,
    ErrorRecoveryManager,
    RecoveryStrategy,
    RetryRecoveryStrategy,
    FallbackRecoveryStrategy
)


__all__ = [
    # Main orchestrator
    'FlowOrchestrator',
    'FlowExecutionContext',
    'FlowExecutionResult',
    'FlowExecutionState',
    'FlowOperationType',
    'create_flow_orchestrator',
    'get_flow_orchestrator',

    # State management
    'FlowStateManager',
    'FlowStateValidator',

    # Messaging
    'MessageComposer',
    'MessageSender',

    # Scheduling
    'QuizScheduler',
    'FollowUpScheduler',

    # Templates
    'TemplateRenderer',
    'TemplateContextBuilder',

    # Rules
    'FlowRulesEngine',
    'RuleConditionEvaluator',

    # A/B Testing
    'ABTestManager',
    'VariantSelector',

    # Analytics
    'AnalyticsCollector',
    'FlowMetricsCalculator',

    # Error Handling
    'FlowErrorHandler',
    'FlowError',
    'ErrorSeverity',
    'ErrorRecoveryManager',
    'RecoveryStrategy',
    'RetryRecoveryStrategy',
    'FallbackRecoveryStrategy',
]


__version__ = '2.0.0'
__author__ = 'Clínica Oncológica Development Team'
