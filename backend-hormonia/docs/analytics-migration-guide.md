# Analytics Domain Migration Guide

## Quick Reference

### Old Import (Deprecated)
```python
from app.services.analytics import AnalyticsService
```

### New Import (Recommended)
```python
from app.domain.analytics import AnalyticsService
```

## Module Structure

```
app/domain/analytics/
├── __init__.py              # Public API
├── analytics_service.py     # Main orchestrator (152 lines)
├── metrics_collector.py     # Data collection (528 lines)
├── dashboard_generator.py   # Dashboard data (484 lines)
└── report_builder.py        # Reports & analysis (519 lines)
```

## Available Imports

```python
# Main service (recommended for most use cases)
from app.domain.analytics import AnalyticsService

# Advanced: Direct component access
from app.domain.analytics import (
    AnalyticsService,      # Main orchestrator
    MetricsCollector,      # Raw metrics collection
    DashboardGenerator,    # Dashboard generation
    ReportBuilder,         # Report building
    AnalyticsError         # Domain exception
)
```

## Usage Examples

### Basic Usage (Most Common)
```python
from app.domain.analytics import AnalyticsService
from app.schemas.report import AnalyticsRequest

# Initialize service
service = AnalyticsService(db)

# Get dashboard data
dashboard = service.get_dashboard_data(doctor_id=None)

# Get full analytics
request = AnalyticsRequest(
    start_date=start_date,
    end_date=end_date,
    metrics=["engagement", "quiz", "alerts"],
    patient_ids=None,  # All patients
    doctor_id=doctor_id
)
analytics = service.get_analytics(request)

# Get treatment distribution
distribution = service.get_treatment_distribution(period="30d", doctor_id=None)

# Detect patterns
patterns = service.detect_patterns(patient_id=None, days_back=30)
```

### Advanced: Direct Component Usage
```python
from app.domain.analytics import MetricsCollector, DashboardGenerator, ReportBuilder

# Initialize components
collector = MetricsCollector(db)
dashboard_gen = DashboardGenerator(db, collector)
report_builder = ReportBuilder(db, collector)

# Collect specific metrics
patient_metrics = collector.get_patient_metrics(
    patient_id=patient_id,
    start_date=start_date,
    end_date=end_date,
    metrics=["engagement", "quiz"]
)

# Generate dashboard
dashboard = dashboard_gen.generate_dashboard(doctor_id=doctor_id)

# Build custom report
report = report_builder.build_analytics_report(request)
```

## API Compatibility

All public methods remain the same:

| Method | Original Location | New Location | Status |
|--------|------------------|--------------|--------|
| `get_analytics()` | `app.services.analytics` | `app.domain.analytics` | ✓ Compatible |
| `get_dashboard_data()` | `app.services.analytics` | `app.domain.analytics` | ✓ Compatible |
| `get_treatment_distribution()` | `app.services.analytics` | `app.domain.analytics` | ✓ Compatible |
| `detect_patterns()` | `app.services.analytics` | `app.domain.analytics` | ✓ Compatible |

## Component Responsibilities

### MetricsCollector
**Purpose**: Raw data collection and aggregation

**Use When**:
- You need specific metrics without full analytics
- Building custom analytics dashboards
- Collecting metrics for external systems

**Key Methods**:
- `get_patient_metrics()` - Patient-specific metrics
- `get_system_metrics()` - System-wide metrics
- `get_quick_stats_consolidated()` - Optimized quick stats
- `calculate_avg_response_time()` - Response time calculation

### DashboardGenerator
**Purpose**: Real-time dashboard data and visualizations

**Use When**:
- Generating dashboard views
- Creating chart data
- Getting recent activity feeds
- Calculating trends

**Key Methods**:
- `generate_dashboard()` - Complete dashboard
- `_get_engagement_chart_data()` - Engagement charts
- `_get_alert_severity_chart_data()` - Alert charts
- `_get_treatment_progress_chart_data()` - Progress charts

### ReportBuilder
**Purpose**: Comprehensive reports and pattern analysis

**Use When**:
- Generating full analytics reports
- Analyzing patterns and trends
- Detecting anomalies
- Building treatment distributions

**Key Methods**:
- `build_analytics_report()` - Full report
- `build_treatment_distribution()` - Treatment analysis
- `detect_patterns()` - Pattern detection
- `_analyze_engagement_trends()` - Trend analysis

### AnalyticsService
**Purpose**: Main orchestrator (recommended entry point)

**Use When**:
- Standard analytics operations
- You don't need to customize components
- Following best practices

**Key Methods**:
- `get_analytics()` - Full analytics
- `get_dashboard_data()` - Dashboard
- `get_treatment_distribution()` - Treatment stats
- `detect_patterns()` - Pattern detection

## Migration Checklist

- [ ] Update import statements to use `app.domain.analytics`
- [ ] Test existing analytics endpoints
- [ ] Verify dashboard data generation
- [ ] Check report generation functionality
- [ ] Validate pattern detection
- [ ] Update any direct method calls (if applicable)
- [ ] Remove deprecation warnings from logs

## Breaking Changes

**None.** This refactoring maintains full backward compatibility.

The old import path will continue to work but will emit deprecation warnings:
```
DeprecationWarning: app.services.analytics.AnalyticsService is deprecated.
Use app.domain.analytics.AnalyticsService instead.
This compatibility wrapper will be removed in v3.0.0.
```

## Performance Notes

All performance optimizations have been preserved:

✓ CTE-based consolidated stats (4 queries → 1 query)
✓ Single GROUP BY for engagement charts (14 queries → 1 query)
✓ Eager loading to prevent N+1 queries
✓ Query performance monitoring
✓ Database retry logic
✓ Optimized response time calculations

## Testing

All existing tests should pass without modification. The refactored code maintains:

- Same public API
- Same return types
- Same error handling
- Same mock object compatibility

## Support

For questions or issues:
1. Check `/home/user/clinica-oncologica-v02/backend-hormonia/docs/analytics-refactoring-report.md` for detailed documentation
2. Review component docstrings in source files
3. Contact the development team

## Timeline

- **v2.0.0**: New domain structure introduced, old import deprecated
- **v2.x.x**: Both imports work (with deprecation warnings)
- **v3.0.0**: Old import path will be removed

**Recommendation**: Migrate to `app.domain.analytics` as soon as possible to avoid future breaking changes.
