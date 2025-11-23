# API Versioning Implementation Summary

**Implementation Date:** 2025-01-16
**Status:** ✅ COMPLETE
**Gap ID:** MEDIUM-011

## Overview

Comprehensive API versioning strategy implemented following ADR-007, providing:
- URL-based versioning (/api/v2/, /api/v3/)
- Deprecation headers (RFC 8594)
- Version negotiation
- Deprecation tracking
- Automated client notifications
- Migration tooling

## Files Created/Modified

### Documentation
1. **ADR-007-API-VERSIONING.md** - Architecture decision record
   - Location: `backend-hormonia/docs/architecture/ADR-007-API-VERSIONING.md`
   - Defines versioning strategy, deprecation process, timeline

2. **V2_TO_V3_MIGRATION.md** - Client migration guide
   - Location: `backend-hormonia/docs/api/V2_TO_V3_MIGRATION.md`
   - Step-by-step migration instructions
   - Breaking changes documentation
   - Code examples for JavaScript, Python

3. **VERSIONING_IMPLEMENTATION.md** - This file
   - Implementation summary and usage guide

### Core Infrastructure

4. **app/api/versioning.py** - Versioned router implementation
   - `VersionedRouter` class
   - Deprecation header middleware
   - `deprecated_endpoint` decorator
   - Sunset date tracking

5. **app/middleware/api_version_negotiation.py** - Version negotiation
   - URL path detection (/api/v3/)
   - Accept header parsing (application/vnd.clinica.v3+json)
   - X-API-Version header support
   - Default to latest version

6. **app/api/v3/router.py** - v3 API router
   - v3 endpoint structure
   - Standardized error responses
   - Health and version info endpoints

7. **app/api/v3/__init__.py** - v3 package initialization

### Monitoring & Tracking

8. **app/monitoring/deprecation_tracking.py** - Prometheus metrics
   - `deprecated_endpoint_calls` counter
   - `api_version_usage` counter
   - `api_version_sunset_days` gauge
   - Client migration tracking
   - Deprecation reports

9. **monitoring/grafana/dashboards/api_versioning.json** - Grafana dashboard
   - Version distribution chart
   - Deprecated endpoint usage
   - Client migration progress
   - Sunset countdown
   - Response time comparison

### Automation

10. **app/tasks/deprecation_notifications.py** - Celery tasks
    - Weekly email notifications to clients
    - Urgent emails for near-sunset
    - Sunset metric updates

### Testing

11. **tests/api/test_version_compatibility.py** - Version tests
    - v2 compatibility during deprecation
    - v3 new features
    - Version negotiation
    - Deprecation header validation
    - Performance comparison

### Router Registration

12. **app/core/router_registry.py** - Modified
    - Integrated versioning system
    - Registered v2 (deprecated) and v3 (current)
    - Added version middleware

## Usage Guide

### For Backend Developers

#### Register a New API Version

```python
from app.api.versioning import get_versioned_router
from datetime import datetime, timezone

versioned_router = get_versioned_router()

# Register deprecated version
versioned_router.add_version(
    version="v2",
    router=router_v2,
    sunset_date=datetime(2025, 7, 1, tzinfo=timezone.utc),
    replacement_version="v3"
)

# Register current version
versioned_router.add_version(
    version="v3",
    router=router_v3,
    is_default=True
)

# Add middleware
app.middleware("http")(versioned_router.get_version_middleware())
```

#### Deprecate Individual Endpoint

```python
from app.api.versioning import deprecated_endpoint
from datetime import datetime, timezone

@router.get("/old-endpoint")
@deprecated_endpoint(
    sunset_date=datetime(2025, 7, 1, tzinfo=timezone.utc),
    replacement="/api/v3/new-endpoint"
)
async def old_endpoint():
    return {"message": "This endpoint is deprecated"}
```

#### Track Deprecation Usage

```python
from app.monitoring.deprecation_tracking import get_deprecation_tracker

tracker = get_deprecation_tracker()

# Track API call
await tracker.track_call(
    version="v2",
    endpoint="/patients",
    method="GET",
    client_id="client-123",
    response_time=0.05
)

# Generate report
report = tracker.get_deprecation_report()
print(f"Clients at risk: {len(report['clients_at_risk'])}")
```

### For API Clients

#### Migrate to v3

**Step 1:** Update base URL
```javascript
// Old (v2)
const BASE_URL = 'https://api.clinica.com/api/v2';

// New (v3)
const BASE_URL = 'https://api.clinica.com/api/v3';
```

**Step 2:** Update error handling
```javascript
// Old (v2)
if (response.error) {
  console.error(response.error);
}

// New (v3)
if (response.error) {
  console.error(`[${response.error.code}] ${response.error.message}`);
}
```

**Step 3:** Update pagination
```javascript
// Old (v2) - offset-based
const response = await fetch(`/api/v2/patients?page=1&limit=50`);

// New (v3) - cursor-based
const response = await fetch(`/api/v3/patients?limit=50`);
const { next_cursor, has_more } = response.pagination;
```

See full migration guide: `docs/api/V2_TO_V3_MIGRATION.md`

### For DevOps

#### Schedule Deprecation Notifications

Add to Celery Beat config:
```python
CELERYBEAT_SCHEDULE = {
    'send-deprecation-notifications': {
        'task': 'send_deprecation_notifications',
        'schedule': crontab(day_of_week=1, hour=10, minute=0),  # Mondays 10am
    },
    'update-sunset-metrics': {
        'task': 'update_sunset_metrics',
        'schedule': crontab(hour=0, minute=0),  # Daily at midnight
    },
}
```

#### Monitor API Versions

1. **Grafana Dashboard:**
   - URL: `http://grafana:3000/d/api-versioning`
   - Metrics: version distribution, deprecated usage, migration progress

2. **Prometheus Queries:**
   ```promql
   # Version usage
   sum by (version) (rate(api_version_usage_total[5m]))

   # Deprecated calls
   sum(rate(api_deprecated_endpoint_calls_total[1h]))

   # Migration progress
   (1 - (count(api_deprecated_endpoint_calls_total > 0) / count(api_version_usage_total > 0))) * 100
   ```

3. **Alerts:**
   ```yaml
   - alert: HighDeprecatedUsage
     expr: rate(api_deprecated_endpoint_calls_total[5m]) > 100
     for: 1h
     annotations:
       summary: "High usage of deprecated API v2"

   - alert: SunsetApproaching
     expr: api_version_sunset_days_remaining{version="v2"} < 30
     annotations:
       summary: "API v2 sunset in <30 days"
   ```

## Testing

Run version compatibility tests:
```bash
# All version tests
pytest tests/api/test_version_compatibility.py -v

# Specific test classes
pytest tests/api/test_version_compatibility.py::TestV2APICompatibility -v
pytest tests/api/test_version_compatibility.py::TestV3APIFeatures -v
pytest tests/api/test_version_compatibility.py::TestVersionNegotiation -v
```

## Deprecation Timeline

| Phase | Dates | Status | Actions |
|-------|-------|--------|---------|
| **Announce** | Jan - Mar 2025 | ✅ Active | v3 released, v2 deprecated headers |
| **Warn** | Apr - Jun 2025 | Planned | Weekly emails, usage tracking |
| **Sunset** | Jul 1, 2025 | Scheduled | v2 removed, returns 410 Gone |

## Metrics & Monitoring

### Prometheus Metrics

- `api_version_usage_total{version, client_id, endpoint}` - Total requests by version
- `api_deprecated_endpoint_calls_total{version, endpoint, client_id, method}` - Deprecated calls
- `api_deprecated_endpoints_active{version}` - Number of deprecated endpoints
- `api_version_sunset_days_remaining{version}` - Days until sunset
- `api_clients_migrated_total{from_version, to_version}` - Migration count
- `api_version_response_time_seconds{version, endpoint}` - Response times by version

### Grafana Panels

1. **Version Distribution** (pie chart) - Traffic split between versions
2. **Deprecated Endpoint Calls** (graph) - Top 10 deprecated endpoints
3. **Clients Using Deprecated APIs** (table) - Client list with call counts
4. **Days Until Sunset** (stat) - Countdown to v2 sunset
5. **Client Migration Progress** (gauge) - % of clients migrated
6. **Response Time Comparison** (graph) - v2 vs v3 performance

## Next Steps

### Immediate (Week 1)
- ✅ Infrastructure implemented
- ✅ v3 router created
- ✅ Deprecation tracking enabled
- ✅ Tests written
- ⏳ Deploy to staging

### Short-term (Weeks 2-4)
- ⏳ Implement v3 endpoints (patients, quiz, webhooks)
- ⏳ Test migration in staging
- ⏳ Send first deprecation emails
- ⏳ Monitor Grafana dashboard

### Medium-term (Months 2-6)
- ⏳ Client migration support (office hours)
- ⏳ Monthly deprecation reports
- ⏳ Track migration progress
- ⏳ Address client concerns

### Long-term (Month 7+)
- ⏳ Sunset v2 API (July 1, 2025)
- ⏳ Remove v2 code
- ⏳ Cleanup deprecated infrastructure

## Support Resources

- **Migration Guide:** `docs/api/V2_TO_V3_MIGRATION.md`
- **ADR:** `docs/architecture/ADR-007-API-VERSIONING.md`
- **Grafana Dashboard:** `/d/api-versioning`
- **Email Support:** api-support@clinica.com
- **Office Hours:** Tuesdays 10am-12pm BRT

## Architecture Decisions

Key decisions documented in ADR-007:

1. **URL-based versioning** - Clear, explicit, browser-friendly
2. **6-month deprecation period** - Sufficient time for migration
3. **RFC 8594 headers** - Standard Sunset/Deprecation headers
4. **Cursor pagination in v3** - Better performance for large datasets
5. **Standardized error format** - Consistent error responses

## Success Criteria

✅ **Infrastructure:**
- Versioned router implemented
- Deprecation headers working
- Metrics tracking enabled
- Tests passing

⏳ **Migration:**
- 95%+ clients migrated by June 2025
- <100 req/min to deprecated endpoints by sunset
- No production incidents during migration

⏳ **Documentation:**
- Migration guide complete
- Client communications sent
- Support resources available

---

**Status:** ✅ COMPLETE
**Last Updated:** 2025-01-16
**Implemented By:** Backend API Developer (MEDIUM-011)
