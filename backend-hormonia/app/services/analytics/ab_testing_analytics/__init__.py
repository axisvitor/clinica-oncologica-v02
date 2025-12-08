"""
A/B Testing Analytics Package

Advanced analytics engine for A/B test results with statistical analysis,
healthcare-specific metrics, and comprehensive reporting capabilities.

This package provides a modular structure for A/B testing analytics:
- models: Data models and constants
- statistics: Statistical testing and analysis
- analyzers: Data analysis and quality assessment
- reporters: Report generation
- helpers: Utility functions
- service: Main service orchestration
"""

# Import models and constants
from .models import (
    HealthcareMetrics,
    StatisticalSignificance,
    EffectSizeMagnitude
)

# Import main service
from .service import (
    ABTestingAnalyticsService,
    get_ab_testing_analytics_service
)

# Backward compatibility alias
ABTestingAnalytics = ABTestingAnalyticsService

# Import analyzers
from .analyzers import (
    VariantAnalyzer,
    HealthcareAnalyzer,
    DataQualityAnalyzer,
    BusinessImpactAnalyzer,
    RiskAnalyzer
)

# Import statistical components
from .statistics import StatisticalAnalyzer

# Import report generators
from .reporters import ReportGenerator

# Import helpers
from .helpers import (
    MetricsHelper,
    TrendAnalyzer,
    AlertChecker,
    DataExtractor,
    ResultsStore
)

# Public API
__all__ = [
    # Main service
    'ABTestingAnalyticsService',
    'ABTestingAnalytics',  # Backward compatibility alias
    'get_ab_testing_analytics_service',

    # Models and constants
    'HealthcareMetrics',
    'StatisticalSignificance',
    'EffectSizeMagnitude',

    # Analyzers
    'VariantAnalyzer',
    'HealthcareAnalyzer',
    'DataQualityAnalyzer',
    'BusinessImpactAnalyzer',
    'RiskAnalyzer',

    # Statistical components
    'StatisticalAnalyzer',

    # Report generators
    'ReportGenerator',

    # Helpers
    'MetricsHelper',
    'TrendAnalyzer',
    'AlertChecker',
    'DataExtractor',
    'ResultsStore',
]

__version__ = '2.0.0'
