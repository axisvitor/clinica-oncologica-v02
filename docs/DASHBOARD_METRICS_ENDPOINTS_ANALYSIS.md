# Dashboard & Metrics Endpoints Analysis

**Date:** 2025-12-22
**Status:** CRITICAL GAPS IDENTIFIED

## Executive Summary

The frontend expects **realtime metrics endpoints** at two paths:
- `/api/v2/dashboard/metrics/realtime`
- `/api/v2/metrics/realtime`

**FINDING:** Neither endpoint exists in the backend. The dashboard router has NO realtime metrics endpoint defined.

## Current Backend Endpoints

### 1. Dashboard Router (`/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/dashboard.py`)

**Existing Endpoints:**
- `GET /main` - Main dashboard overview with widgets
- `GET /patient/{patient_id}` - Patient-specific dashboard
- `GET /physician` - Physician-specific dashboard

**Cache Configuration:**
- TTL: 120 seconds (2 minutes) for realtime widgets
- Cache key pattern: `dashboard:main:user:{user_id}:range:{time_range}`

**Metrics Returned:**
- Patient metrics
- Message metrics
- Alert metrics
- Flow metrics
- Recent activity
- Engagement data

**FINDING:** Dashboard endpoints return metrics but are NOT marked as "realtime" and don't have a dedicated realtime endpoint.

---

### 2. Health/Metrics Router (`/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/health/metrics.py`)

**Existing Endpoints:**
- `GET /metrics` - Prometheus-compatible metrics (plain text)
- `GET /metrics/system` - System resource metrics (CPU, memory, disk, network)
- `GET /metrics/application` - Application-level metrics (request rates, error rates, sessions)
- `GET /metrics/custom` - Custom business metrics (active patients, messages, quizzes, alerts)

**Response Type:** JSON models
**Authentication:** Required (get_current_user)
**Mount Point:** Appears to be under `/health` route prefix

---

### 3. System Metrics Router (`/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/system/metrics.py`)

**Existing Endpoints:**
- `GET /metrics` - System performance metrics (CPU, memory, disk, network, DB pool, cache)
- `GET /info` - System information and feature flags

**Authentication:** Admin role required
**Rate Limit:** 20 requests/minute for metrics, 30 requests/minute for info
**Cache:** 10 minutes for system info

**FINDING:** This is admin-only, not suitable for regular user dashboards.

---

### 4. Performance Router (`/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/performance.py`)

**Visible Endpoints** (partial read):
- `GET /cache/metrics` - Cache performance metrics
- `GET /` (implied) - Performance overview

**Authentication:** Admin role required
**FINDING:** This is admin-only, not suitable for realtime user dashboards.

---

## Frontend Expectations vs Backend Reality

| Frontend Expectation | Backend Reality | Status |
|---|---|---|
| `/api/v2/dashboard/metrics/realtime` | No endpoint | **MISSING** |
| `/api/v2/metrics/realtime` | No endpoint | **MISSING** |
| JSON response with realtime data | Health metrics available in `/health/metrics/*` | PARTIAL |
| User-accessible (not admin-only) | Health metrics require auth but not admin | PARTIAL |
| Real-time updates (< 2 min cache) | Dashboard uses 120s TTL | COMPATIBLE |

---

## What Endpoints SHOULD Exist

### Option 1: Add to Dashboard Router (Preferred)
**File:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/dashboard.py`

```python
@router.get("/metrics/realtime")
async def get_dashboard_metrics_realtime(
    request: Request,
    current_user: Dict = Depends(_get_current_user_simple),
    service: DashboardService = Depends(get_dashboard_service),
) -> Dict[str, Any]:
    """
    Get realtime dashboard metrics for current user.

    Returns:
    - Patient metrics (active, alerts)
    - Message metrics (sent, pending)
    - Alert metrics (total, critical)
    - Flow metrics (active, completed)
    - System status
    """
    # Implementation here
```

**Route:** `GET /api/v2/dashboard/metrics/realtime`

### Option 2: Add Top-Level Metrics Router
**Create:** `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/metrics.py`

```python
router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/realtime")
async def get_realtime_metrics(
    current_user: Dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get realtime system and application metrics.

    Aggregates:
    - Health status
    - Active users/sessions
    - Message throughput
    - Alert status
    - System resource usage
    """
    # Implementation here
```

**Route:** `GET /api/v2/metrics/realtime`

---

## Recommended Implementation Plan

### Phase 1: Add Dashboard Realtime Endpoint
1. Extend `dashboard.py` with `GET /metrics/realtime` endpoint
2. Use 60-second cache TTL for realtime data
3. Return minimal set of metrics:
   - Active patient count
   - Pending alerts
   - Unread messages
   - System status

### Phase 2: Add Top-Level Metrics Router (Future)
1. Create `metrics.py` with realtime aggregation
2. Combine health, performance, and application metrics
3. Support filtering by metric type

### Phase 3: WebSocket Support (Advanced)
1. Add WebSocket endpoint for true realtime updates
2. Push metrics on 30-second intervals
3. Allow subscriptions to specific metric types

---

## Current Metric Categories Available

### Dashboard Service Provides:
- `get_patient_metrics()` - Active patients, alerts
- `get_message_metrics()` - Sent, received, pending
- `get_alert_metrics()` - Total, critical, resolved
- `get_flow_metrics()` - Active flows, completion rate
- `get_recent_activity()` - Last 10-15 activities
- `get_engagement_chart_data()` - 30-day engagement

### Health Service Provides:
- Database health (latency, pool utilization)
- Redis health (latency, hit rate)
- Worker health (active count, failed tasks)
- Storage health (utilization)

### System Service Provides (Admin):
- CPU, memory, disk, network
- Database connection pool
- Cache statistics
- Active sessions

---

## Cache Strategy Recommendations

| Endpoint | TTL | Rationale |
|---|---|---|
| `/dashboard/metrics/realtime` | 60s | Balance between freshness and load |
| `/metrics/realtime` | 30-60s | Need quick updates for monitoring |
| `/health/metrics/*` | 30s | System health critical |
| `/system/metrics` (admin) | 120s | Less frequent admin checks |

---

## Security Considerations

1. **Dashboard Realtime**: User can only see their own metrics
2. **Health Metrics**: Authenticated users only (current implementation)
3. **System Metrics**: Admin role required (current implementation)
4. **Rate Limiting**:
   - 60/minute for dashboard realtime
   - 30/minute for system metrics
   - 20/minute for performance metrics

---

## Files Involved

**Current Dashboard:**
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/dashboard.py`

**Existing Metrics/Health:**
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/health/metrics.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/system/metrics.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/api/v2/routers/performance.py`

**Service Layer:**
- `app/services/dashboard_service.py` (provides metric calculation methods)

**Route Registration:**
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/core/application_factory.py`

---

## Next Steps

1. **Immediate:** Add `/dashboard/metrics/realtime` endpoint to dashboard router
2. **Short-term:** Verify frontend endpoints and expected response format
3. **Medium-term:** Optimize cache keys and TTL based on usage patterns
4. **Long-term:** Consider WebSocket endpoint for true realtime updates

---

**Status:** Ready for implementation
