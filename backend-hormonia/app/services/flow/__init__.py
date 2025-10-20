"""
Flow Services Module
====================

Unified flow management system with clear separation of concerns.

This module consolidates:
- flow.py (main service)
- flow_core.py (core logic)
- flow_engine.py (execution engine)
- enhanced_flow_engine.py (enhanced engine - duplicate)
- flow_orchestrator.py (orchestration)
- flow_error_handler.py (error handling)
- flow_validation.py (validation)
- flow_monitoring.py (monitoring)
- flow_analytics.py (analytics)
- flow_dashboard.py (dashboard)
- flow_data_integrity.py (data integrity)
- flow_integrity.py (integrity - duplicate)
- flow_management.py (management)
- flow_template.py (templates)
- flow_event_broadcaster.py (event broadcasting)
- flow_engine_ai_integration.py (AI integration)
- quiz_flow_integration.py (quiz integration)

Total: 17 files → 4 files (76% reduction)

Public API:
    FlowService: Main business logic and CRUD operations
    FlowEngine: Flow execution and orchestration
    FlowAnalytics: Analytics, monitoring, and dashboard data
    FlowTemplates: Template management and AI integration

Example:
    >>> from app.services.flow import FlowService, FlowEngine
    >>>
    >>> # Business logic
    >>> service = FlowService(db)
    >>> flow = await service.create_flow(data)
    >>>
    >>> # Execution
    >>> engine = FlowEngine(db)
    >>> result = await engine.execute_flow(flow.id, context)
    >>>
    >>> # Analytics
    >>> from app.services.flow import FlowAnalytics
    >>> analytics = FlowAnalytics(db)
    >>> metrics = await analytics.get_metrics(flow.id)
"""

# Public exports will be added after consolidation
# from .flow_service import FlowService
# from .flow_engine import FlowEngine
# from .flow_analytics import FlowAnalytics
# from .flow_templates import FlowTemplates

__all__ = [
    # "FlowService",
    # "FlowEngine",
    # "FlowAnalytics",
    # "FlowTemplates",
]

__version__ = "2.0.0"  # Version 2.0 - Consolidated from 17 files to 4
