"""
Unit Tests for Flow Analytics Module - QW-021 Flow Services Consolidation.

This package contains comprehensive unit tests for the consolidated flow analytics
system, including metrics collection, event broadcasting, health monitoring, and
the main analytics service.

Test Modules:
    - test_metrics_collector: Tests for FlowMetricsCollector (28 tests)
    - test_event_broadcaster: Tests for FlowEventBroadcaster (45 tests)
    - test_monitor: Tests for FlowMonitor (35 tests)
    - test_analytics: Tests for FlowAnalytics (integration tests)

Coverage Target: 80%+ for all analytics modules

Usage:
    # Run all analytics tests
    pytest tests/unit/services/flow/analytics/ -v

    # Run specific test module
    pytest tests/unit/services/flow/analytics/test_metrics_collector.py -v

    # Run with coverage
    pytest tests/unit/services/flow/analytics/ --cov=app.services.flow.analytics

Authors: QW-021 Implementation Team
Date: January 2025
"""

__all__ = []
