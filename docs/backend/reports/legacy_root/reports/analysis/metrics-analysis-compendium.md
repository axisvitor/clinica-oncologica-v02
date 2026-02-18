# Metrics & Monitoring Analysis Compendium

## Merged Content: metrics-analysis-index.md

# Real-time Metrics Analysis - Documentation Index

**Analysis Date:** December 22, 2025
**Status:** Complete - Critical Gap Identified

This analysis covers the frontend real-time metrics dashboard and its missing backend implementation.

---

## Documents in This Analysis

### 1. METRICS_FEATURE_SUMMARY.md (START HERE)
**Purpose:** Executive summary for stakeholders
**Read Time:** 10 minutes
**Audience:** Product managers, tech leads, stakeholders

**Contains:**
- Quick summary of findings
- What the dashboard does
- Impact analysis
- Timeline and effort estimates
- Decision matrix
- Success criteria

**Key Takeaway:**
> Frontend is complete and production-ready, backend is completely missing. 6-10 hours of development needed.

---

### 2. REALTIME_METRICS_ANALYSIS.md
**Purpose:** Detailed technical analysis
**Read Time:** 20 minutes
**Audience:** Engineers, architects

**Contains:**
- Frontend code analysis (endpoints, data flow, types)
- Backend status (what exists, what's missing)
- Dependency mapping
- Implementation plan (4 phases)
- Data requirements specification
- WebSocket protocol spec
- Risk assessment
- Complete files referenced

**Key Findings:**
- 3 HTTP endpoints missing
- 1 WebSocket endpoint missing
- 1 export endpoint missing
- Zero compatibility with existing dashboard endpoints

---

### 3. METRICS_API_TECHNICAL_SPEC.md
**Purpose:** Implementation specification for engineers
**Read Time:** 30 minutes
**Audience:** Backend developers implementing the feature

**Contains:**
- 6 detailed endpoint specifications (request/response)
- WebSocket protocol specification
- Database schema requirements
- Performance considerations (caching, optimization)
- Security requirements
- Error handling specification
- Testing requirements
- Deployment checklist

**Each Endpoint Includes:**
- Purpose and description
- Request format with examples
- Response format with complete JSON
- Error responses and codes
- Cache strategy
- Business logic details
- SQL examples

---

## Quick Navigation

### For Different Roles

#### Product Manager / Stakeholder
1. Read: METRICS_FEATURE_SUMMARY.md
2. Focus on: Impact, timeline, effort estimates
3. Key question: "How long to fix?" → 2-3 days

#### Tech Lead / Architect
1. Read: REALTIME_METRICS_ANALYSIS.md (full)
2. Review: METRICS_API_TECHNICAL_SPEC.md (sections 1-2)
3. Key question: "What do we need to implement?" → See spec

#### Backend Developer (Assigning Work)
1. Skim: METRICS_FEATURE_SUMMARY.md (for context)
2. Read: METRICS_API_TECHNICAL_SPEC.md (all sections)
3. Reference: REALTIME_METRICS_ANALYSIS.md (implementation phases)
4. Key task: Implement 5 endpoints + WebSocket

#### Frontend Developer (Verifying Integration)
1. Review: METRICS_API_TECHNICAL_SPEC.md (sections 1-2, 3.1)
2. Check: Response formats match expectations
3. Test: Integration with MetricsDashboard.tsx
4. Key file: `/frontend-hormonia/src/types/metrics.ts`

---

## Key Findings Summary

### Production Status
- **Frontend:** ✓ Complete, production-ready
- **Backend:** ✗ Missing, not implemented
- **Current Status:** Feature is broken in production
- **Impact:** CRITICAL - Cannot monitor system

### What's Missing

#### HTTP Endpoints (need to create)
```
GET /api/v2/metrics/summary       → KPI data (6 values)
GET /api/v2/metrics/realtime      → Detailed metrics (4 groups + trends)
GET /api/v2/metrics/alerts        → Alert list
POST /api/v2/metrics/alerts/{id}/acknowledge → Mark alert read
POST /api/v2/metrics/export       → Download data (JSON/CSV/PDF)
```

#### WebSocket Endpoint (need to create)
```
WS /api/v2/metrics/live → Real-time metrics stream (5-10s updates)
```

#### Business Logic (need to implement)
- Engagement metrics calculation
- Quiz completion rate tracking
- AI personalization impact scoring
- System health aggregation
- Alert generation and tracking

---

## Implementation Phases

### Phase 1: Backend Endpoints (2-3 hours)
Create `/app/api/v2/routers/metrics.py` with all 5 HTTP endpoints

### Phase 2: WebSocket Handler (1-2 hours)
Create real-time metrics streaming to connected clients

### Phase 3: Frontend Integration (1 hour)
Verify endpoint paths and data format compatibility

### Phase 4: Testing & Validation (1-2 hours)
Unit tests, integration tests, load testing

**Total: 6-10 hours**

---

## Response Format Examples

### MetricsSummary (GET /metrics/summary)
```json
{
  "engagement_rate": 65.5,
  "quiz_completion_rate": 78.3,
  "ai_personalization_impact": 42.1,
  "active_patients": 247,
  "daily_messages": 1523,
  "system_health_score": 98.5,
  "timestamp": "2025-12-22T14:30:00-03:00"
}
```

### RealTimeMetrics (GET /metrics/realtime)
```json
{
  "engagement": { /* 8 fields + 7-day trend */ },
  "quiz": { /* 5 fields + monthly stats + 7-day trend */ },
  "ai_personalization": { /* 7 fields + impact metrics */ },
  "system_performance": { /* 8 system metrics */ },
  "alerts_count": 3,
  "last_updated": "2025-12-22T14:30:15-03:00"
}
```

### Alerts (GET /metrics/alerts)
```json
{
  "alerts": [
    {
      "id": "uuid",
      "title": "Alert title",
      "description": "Details",
      "severity": "high",
      "category": "system",
      "status": "active",
      "created_at": "ISO8601",
      "metadata": {}
    }
  ]
}
```

See METRICS_API_TECHNICAL_SPEC.md for complete examples and all response formats.

---

## Frontend Components Using These Endpoints

| Component | Endpoints | Status |
|-----------|-----------|--------|
| MetricsDashboard | summary, realtime, alerts, live | Waiting for backend |
| EngagementChart | realtime (engagement) | Waiting for backend |
| QuizCompletionChart | realtime (quiz) | Waiting for backend |
| AIPersonalizationChart | realtime (ai_personalization) | Waiting for backend |
| SystemHealthChart | realtime (system_performance) | Waiting for backend |
| AlertsPanel | alerts, acknowledge | Waiting for backend |
| MetricsDashboardPage | export | Waiting for backend |

---

## Critical Questions Answered

### Q: Is this feature used in production?
**A:** YES - MetricsDashboardPage is exposed in the application and users can navigate to it.

### Q: Can it be removed?
**A:** NOT RECOMMENDED - Removes monitoring capability that users expect.

### Q: Can it be stubbed with mock data?
**A:** TEMPORARY ONLY - Would mislead users about system state. Not production-ready.

### Q: How long to implement?
**A:** 6-10 hours of development, 2-3 days with testing and deployment.

### Q: What data does it expect?
**A:** See "Response Format Examples" above and METRICS_API_TECHNICAL_SPEC.md for complete specs.

### Q: Is the frontend code good quality?
**A:** YES - Well-structured React components with proper TypeScript types and error handling.

### Q: What's the backend impact?
**A:** HIGH - Requires data aggregation service, real-time streaming, database optimization, alert management.

---

## Files to Review

### Frontend (Review to understand needs)
- `/frontend-hormonia/src/features/metrics/MetricsDashboard.tsx` (505 lines)
- `/frontend-hormonia/src/features/metrics/MetricsWebSocket.tsx` (279 lines)
- `/frontend-hormonia/src/types/metrics.ts` (430 lines) - Type definitions
- `/frontend-hormonia/src/lib/api-client/dashboard.ts` (175 lines) - API client

### Backend (Currently exist, but are incompatible)
- `/backend-hormonia/app/api/v2/routers/dashboard.py` - Different endpoint structure

### To Create
- `/backend-hormonia/app/api/v2/routers/metrics.py` - Main implementation
- `/backend-hormonia/app/api/v2/routers/metrics_ws.py` - WebSocket handler
- `/backend-hormonia/app/services/metrics_service.py` - Business logic

---

## Next Steps

### For Product/Engineering Manager
1. Review METRICS_FEATURE_SUMMARY.md
2. Assess business priority (is monitoring critical?)
3. Assign resources (1-2 backend developers)
4. Set timeline (2-3 days)

### For Backend Lead
1. Read METRICS_API_TECHNICAL_SPEC.md completely
2. Plan database queries and optimization
3. Design caching strategy
4. Create implementation tasks

### For Assigned Developer
1. Read METRICS_API_TECHNICAL_SPEC.md sections 1-2 (endpoints)
2. Set up metrics router with 5 endpoints
3. Implement data aggregation service
4. Create WebSocket handler
5. Add comprehensive tests
6. Deploy and monitor

---

## Success Metrics

After implementation, the metrics dashboard should:
- ✓ Load without errors
- ✓ Display real-time engagement metrics (updated 5-10s)
- ✓ Show quiz completion trends
- ✓ Display AI personalization impact
- ✓ Show system health (admin users)
- ✓ List and manage alerts
- ✓ Support metric data export
- ✓ Response time < 200ms (p95)
- ✓ Support 100+ concurrent WebSocket connections

---

## Questions or Clarifications?

**For Frontend Questions:**
- See MetricsDashboard.tsx and types/metrics.ts

**For Backend Specification:**
- See METRICS_API_TECHNICAL_SPEC.md

**For Implementation Timeline:**
- See METRICS_FEATURE_SUMMARY.md (effort estimates)

**For Detailed Analysis:**
- See REALTIME_METRICS_ANALYSIS.md

---

## Document Versions

| Document | Version | Date | Status |
|----------|---------|------|--------|
| METRICS_FEATURE_SUMMARY.md | 1.0 | 2025-12-22 | Complete |
| REALTIME_METRICS_ANALYSIS.md | 1.0 | 2025-12-22 | Complete |
| METRICS_API_TECHNICAL_SPEC.md | 1.0 | 2025-12-22 | Complete |
| METRICS_ANALYSIS_INDEX.md | 1.0 | 2025-12-22 | This file |

---

**Analysis Type:** Frontend-Backend Gap Analysis
**Confidence Level:** HIGH (100% - All endpoints confirmed missing)
**Recommendation:** IMPLEMENT backend endpoints (6-10 hours)

Generated by Research Agent | December 22, 2025


---\n
## Merged Content: realtime-metrics-analysis.md

# Real-time Metrics Endpoint Analysis Report

**Date:** 2025-12-22
**Status:** Critical Gap Identified
**Priority:** High

---

## Executive Summary

The frontend MetricsDashboard component implements a **comprehensive real-time metrics dashboard** that calls three specific API endpoints:

1. `/api/v2/metrics/summary` - Summary metrics
2. `/api/v2/metrics/realtime` - Real-time detailed metrics
3. `/api/v2/metrics/alerts` - Alert data

**Critical Finding:** Only partial backend support exists. The `/api/v2/metrics/realtime` endpoint is **NOT implemented** in the backend.

---

## Frontend Implementation Analysis

### File: `/frontend-hormonia/src/features/metrics/MetricsDashboard.tsx`

#### Endpoints Called
```typescript
// Line 71-84: Fetch summary metrics
const response = await fetch('/api/v2/metrics/summary', {
  credentials: 'include'
});

// Line 86-101: Fetch real-time metrics
const response = await fetch('/api/v2/metrics/realtime', {
  credentials: 'include'
});

// Line 103-118: Fetch alerts
const response = await fetch('/api/v2/metrics/alerts', {
  credentials: 'include'
});

// Line 154: Acknowledge alerts
const response = await fetch(`/api/v2/metrics/alerts/${alertId}/acknowledge`, {
  method: 'POST',
  credentials: 'include'
});
```

#### Data Flow
1. **Initial Load** (useEffect line 121-144):
   - Calls all three endpoints in parallel: `Promise.all([fetchSummary(), fetchRealTimeMetrics(), fetchAlerts()])`
   - Sets `isLoading = false` once complete

2. **Periodic Refresh** (line 137-141):
   - Refreshes summary and alerts every 5 seconds (configurable)
   - Does NOT refresh real-time metrics via HTTP (uses WebSocket instead)

3. **WebSocket Connection** (line 147-150):
   - Connects to `/api/v2/metrics/live` WebSocket
   - Updates `realTimeMetrics` state with incoming messages

#### Data Structure Expected

From `/types/metrics.ts`:

```typescript
interface RealTimeMetrics {
  engagement: EngagementMetrics;           // 8 fields
  quiz: QuizMetrics;                        // 5 fields + nested arrays
  ai_personalization: AIPersonalizationMetrics;  // 7 fields
  system_performance: SystemPerformanceMetrics;  // 8 fields
  alerts_count: number;
  last_updated: string;
}

interface MetricsSummary {
  engagement_rate: number;
  quiz_completion_rate: number;
  ai_personalization_impact: number;
  active_patients: number;
  daily_messages: number;
  system_health_score: number;
  timestamp: string;
}
```

#### UI Components Dependent on Data

| Component | Requires | Status |
|-----------|----------|--------|
| KPI Cards (engagement, quizzes, AI, system) | `MetricsSummary` | Summary metrics only |
| EngagementChart | `realTimeMetrics.engagement` | Needs realtime data |
| QuizCompletionChart | `realTimeMetrics.quiz` | Needs realtime data |
| AIPersonalizationChart | `realTimeMetrics.ai_personalization` | Needs realtime data |
| SystemHealthChart | `realTimeMetrics.system_performance` | Admin-only, needs realtime |
| AlertsPanel | `alerts[]` | Works with alerts endpoint |
| WebSocket Status Badge | Connection state | Works with WebSocket |

---

## Backend Implementation Status

### Existing Dashboard Endpoints

**File:** `/backend-hormonia/app/api/v2/routers/dashboard.py`

```python
@router.get("/main", response_model=DashboardMainResponse)
async def get_main_dashboard(...)
  # Returns: patient_metrics, message_metrics, alert_metrics, flow_metrics, recent_activity

@router.get("/patient/{patient_id}", response_model=DashboardPatientResponse)
async def get_patient_dashboard(...)
  # Returns: patient-specific metrics

@router.get("/physician", response_model=DashboardPhysicianResponse)
async def get_physician_dashboard(...)
  # Returns: physician-specific metrics
```

### Missing Endpoints

| Endpoint | Expected Behavior | Status |
|----------|-------------------|--------|
| `/api/v2/metrics/summary` | KPI summary (engagement, quizzes, AI, system) | **NOT FOUND** |
| `/api/v2/metrics/realtime` | Real-time detailed metrics (engagement, quiz, AI, system) | **NOT FOUND** |
| `/api/v2/metrics/alerts` | Alert list | **NOT FOUND** |
| `/api/v2/metrics/alerts/{id}/acknowledge` | Mark alert as acknowledged | **NOT FOUND** |
| `/api/v2/metrics/live` (WebSocket) | Live metrics stream | **NOT FOUND** |
| `/api/v2/metrics/export` | Export metrics data | **NOT FOUND** (called in MetricsDashboardPage.tsx:57) |

### Available Alternatives

The backend has these related endpoints:
- `/api/v2/dashboard/main` - Main dashboard (different format)
- `/api/v2/dashboard/patient/{id}` - Patient dashboard
- `/api/v2/dashboard/physician` - Physician dashboard
- `/api/v2/enhanced-analytics/*` - Advanced analytics endpoints
- `/api/v2/admin/system/metrics` - System metrics (admin only)
- `/metrics` - Prometheus metrics endpoint

---

## Frontend API Client Integration

### File: `/frontend-hormonia/src/lib/api-client/dashboard.ts`

```typescript
getRealTimeMetrics: async (): Promise<{
  active_patients: number
  pending_messages: number
  unread_alerts: number
  last_updated: string
}> => {
  return client.get('/api/v2/dashboard/metrics/realtime')
}
```

**Note:** Even the API client expects `/api/v2/dashboard/metrics/realtime` (not `/api/v2/metrics/realtime`), suggesting inconsistency.

---

## Current Production Status

### Frontend Usage
- **Active in Production:** YES
- **Feature Criticality:** HIGH
- **Components Affected:** MetricsDashboard, MetricsDashboardPage
- **User Impact:** CRITICAL - Dashboard displays no real-time metrics data

### Backend Status
- **Implemented:** NO
- **API Endpoint:** Missing
- **Data Source:** Not defined
- **Production Ready:** NO

---

## Decision Matrix

### Option 1: Implement Missing Endpoints (RECOMMENDED)

**Pros:**
- Completes the feature as designed
- Provides real-time metrics as intended
- Supports WebSocket live updates
- Enables proper alert management

**Cons:**
- Requires backend implementation
- Need database queries for metrics
- Must implement WebSocket handler
- Time investment needed

**Effort:** 4-6 hours
**Priority:** HIGH

---

### Option 2: Stub/Mock Endpoints

**Pros:**
- Quickly resolves build errors
- Allows testing UI with dummy data
- Low implementation effort

**Cons:**
- No real functionality
- Dashboard shows fake data
- Not production-ready
- Misleads users about system state

**Effort:** 1-2 hours
**Priority:** NOT RECOMMENDED

---

### Option 3: Remove Frontend Feature

**Pros:**
- Eliminates broken functionality
- Reduces maintenance burden
- No backend implementation needed

**Cons:**
- Removes valuable monitoring capability
- Poor UX (partial dashboard)
- User disappointment
- May violate requirements

**Effort:** 1 hour
**Priority:** NOT RECOMMENDED

---

## Recommended Implementation Plan

### Phase 1: Backend Endpoints (2-3 hours)

**Create:** `/app/api/v2/routers/metrics.py`

```python
# Endpoints needed:
GET /metrics/summary - Aggregated KPIs
GET /metrics/realtime - Detailed real-time metrics
GET /metrics/alerts - List of active alerts
POST /metrics/alerts/{id}/acknowledge - Mark alert acknowledged
POST /metrics/export - Export metrics data

# WebSocket endpoint:
WS /metrics/live - Real-time metrics stream
```

**Data Sources:**
- Patient engagement data → analytics tables
- Quiz completion metrics → quiz response tables
- AI personalization stats → conversation tables
- System health → health check tables
- Alerts → alerts/monitoring tables

### Phase 2: WebSocket Handler (1-2 hours)

**File:** `/app/api/v2/routers/metrics_ws.py`

```python
# Implement WebSocket connection
# Send metrics updates every 5-10 seconds
# Handle authentication
# Support ping/pong heartbeat
```

### Phase 3: Frontend Integration (1 hour)

- Verify endpoint paths match frontend expectations
- Test data format compatibility
- Implement error handling
- Add loading states

### Phase 4: Testing & Validation (1-2 hours)

- Unit tests for endpoints
- Integration tests for data flow
- Performance testing for WebSocket
- Load testing for concurrent users

---

## Data Requirements Specification

### MetricsSummary Response

```json
{
  "engagement_rate": 0.0-100.0,
  "quiz_completion_rate": 0.0-100.0,
  "ai_personalization_impact": 0.0-100.0,
  "active_patients": 0-N,
  "daily_messages": 0-N,
  "system_health_score": 0.0-100.0,
  "timestamp": "ISO8601"
}
```

### RealTimeMetrics Response

```json
{
  "engagement": {
    "total_patients": integer,
    "active_patients": integer,
    "engagement_rate": 0.0-100.0,
    "response_rate": 0.0-100.0,
    "avg_response_time_hours": number,
    "daily_active_users": integer,
    "weekly_active_users": integer,
    "monthly_active_users": integer,
    "engagement_trend": [{"date": "YYYY-MM-DD", "active_users": integer}]
  },
  "quiz": {
    "total_quizzes_sent": integer,
    "completed_quizzes": integer,
    "completion_rate": 0.0-100.0,
    "avg_completion_time_minutes": number,
    "quiz_types": {"type": {"total_sessions": int, "completed_sessions": int, "completion_rate": float}},
    "monthly_quiz_stats": {
      "total_sent": integer,
      "total_completed": integer,
      "total_expired": integer,
      "total_active": integer,
      "average_score": 0.0-100.0,
      "completion_rate": 0.0-100.0,
      "expiration_rate": 0.0-100.0
    },
    "completion_trend": [{"date": "YYYY-MM-DD", "completed_quizzes": integer}]
  },
  "ai_personalization": {
    "total_messages_processed": integer,
    "personalized_messages": integer,
    "personalization_rate": 0.0-100.0,
    "avg_personalization_score": 0.0-100.0,
    "safety_interventions": integer,
    "fallback_rate": 0.0-100.0,
    "response_quality_score": 0.0-100.0,
    "personalization_impact": [{"metric": string, "value": number, "unit": string}]
  },
  "system_performance": {
    "cpu_usage": 0.0-100.0,
    "memory_usage": 0.0-100.0,
    "disk_usage": 0.0-100.0,
    "active_connections": integer,
    "response_time_ms": integer,
    "error_rate": 0.0-100.0,
    "uptime_seconds": integer,
    "throughput_rps": number
  },
  "alerts_count": integer,
  "last_updated": "ISO8601"
}
```

### Alerts Response

```json
{
  "alerts": [
    {
      "id": "uuid",
      "title": string,
      "description": string,
      "severity": "low|medium|high|critical",
      "category": "system|healthcare|security|performance|data_integrity|ai_service",
      "status": "active|acknowledged|resolved|suppressed",
      "created_at": "ISO8601",
      "source": string,
      "metadata": {}
    }
  ]
}
```

---

## WebSocket Message Format

### Client to Server

```json
{
  "type": "ping"
}
```

### Server to Client

```json
{
  "type": "metrics_update|alert|ping|pong",
  "data": {
    // Real-time metrics or alert data
  },
  "timestamp": "ISO8601"
}
```

---

## Questions for Product/Engineering

1. **Real-time frequency:** Should metrics update every 5s, 10s, or 30s?
2. **Historical data:** Should `/metrics/realtime` return current snapshot only or time-series?
3. **Caching:** Should metrics be cached? If so, for how long?
4. **Authentication:** Should metrics require specific permissions (admin vs doctor)?
5. **Alert severity:** What triggers different severity levels?
6. **Export formats:** Should export support JSON, CSV, PDF?

---

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Metrics data inconsistency | Medium | High | Implement caching strategy, validate data |
| WebSocket connection drops | Medium | Medium | Implement reconnection logic (already in frontend) |
| Performance degradation | Low | High | Add rate limiting, caching, pagination |
| Data privacy exposure | Low | High | Implement role-based filtering |

---

## Conclusion

**The realtime metrics feature is CRITICAL and currently NON-FUNCTIONAL in production.**

The frontend is fully implemented and waiting for backend support. The endpoints are hardcoded and expected by the UI components.

### Recommended Action:
**Implement the missing backend endpoints** as specified in Phase 1-4 above.

### Timeline:
- Backend implementation: 4-6 hours
- Testing & validation: 1-2 hours
- **Total: ~7 hours**

### Success Criteria:
- All three endpoints respond with correct data format
- WebSocket streams metrics every 5-10 seconds
- Frontend dashboard displays real metrics
- Alert acknowledgment works end-to-end
- No errors in browser console
- Performance meets SLA (response < 200ms)

---

## Files Referenced

### Frontend
- `/frontend-hormonia/src/features/metrics/MetricsDashboard.tsx` - Main component
- `/frontend-hormonia/src/pages/MetricsDashboardPage.tsx` - Page wrapper
- `/frontend-hormonia/src/features/metrics/MetricsWebSocket.tsx` - WebSocket handler
- `/frontend-hormonia/src/types/metrics.ts` - Type definitions
- `/frontend-hormonia/src/lib/api-client/dashboard.ts` - API client

### Backend
- `/backend-hormonia/app/api/v2/routers/dashboard.py` - Existing dashboard endpoints
- `/backend-hormonia/app/api/v2/metrics.py` - Prometheus metrics (not related)

### Missing
- `/backend-hormonia/app/api/v2/routers/metrics.py` - **NEEDS CREATION**
- `/backend-hormonia/app/api/v2/routers/metrics_ws.py` - **NEEDS CREATION**

---

**Generated by Research Agent**
**Analysis Type:** Frontend-Backend Gap Analysis
**Confidence:** HIGH (100% gap confirmed)


---\n
## Merged Content: dashboard-metrics-endpoints-analysis.md

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


---\n
## Merged Content: follow-up-metrics-monitoring.md

# Follow-Up System - Métricas e Monitoring

**Versão:** 1.0
**Data:** 2025-12-24
**Objetivo:** Dashboard de métricas e KPIs para o sistema de follow-up

---

## 📊 KPIs Principais

### **1. Follow-Up Action Metrics**

```python
# Implementar em FollowUpSystemService.get_metrics()

{
    "actions": {
        "total_pending": 142,        # Actions waiting execution
        "total_completed": 1829,     # Successfully completed actions
        "total_failed": 23,          # Failed actions
        "completion_rate": 0.987,    # completed / (completed + failed)

        "by_type": {
            "empathetic_response": {
                "pending": 45,
                "completed": 678,
                "failed": 5,
                "avg_execution_time_seconds": 3.2
            },
            "medical_clarification": {
                "pending": 12,
                "completed": 234,
                "failed": 3,
                "avg_execution_time_seconds": 4.1
            },
            "escalation_notification": {
                "pending": 8,
                "completed": 156,
                "failed": 8,
                "avg_execution_time_seconds": 2.8
            },
            "provider_alert": {
                "pending": 3,
                "completed": 89,
                "failed": 4,
                "avg_execution_time_seconds": 5.3
            },
            "conversation_continuation": {
                "pending": 74,
                "completed": 672,
                "failed": 3,
                "avg_execution_time_seconds": 2.1
            }
        },

        "by_priority": {
            "critical": {"pending": 2, "avg_wait_time_minutes": 1.2},
            "high": {"pending": 18, "avg_wait_time_minutes": 5.7},
            "medium": {"pending": 87, "avg_wait_time_minutes": 45.3},
            "low": {"pending": 35, "avg_wait_time_minutes": 180.4}
        },

        "avg_execution_time_seconds": 3.5,
        "p95_execution_time_seconds": 8.2,
        "p99_execution_time_seconds": 15.1
    }
}
```

**Alertas:**
- `total_failed > 50`: 🚨 High failure rate, investigate immediately
- `completion_rate < 0.95`: ⚠️ Completion rate degraded
- `avg_execution_time_seconds > 10`: ⚠️ Slow execution
- `by_priority.critical.pending > 5`: 🚨 Critical actions backing up

---

### **2. Escalation Alert Metrics**

```python
{
    "alerts": {
        "total_active": 18,           # Unresolved alerts
        "total_acknowledged": 12,     # Acknowledged but not resolved
        "total_resolved": 245,        # Successfully resolved
        "resolution_rate": 0.932,     # resolved / (resolved + active)

        "by_level": {
            "critical": {
                "active": 2,
                "acknowledged": 1,
                "resolved": 34,
                "avg_acknowledgment_time_minutes": 8.5,
                "avg_resolution_time_hours": 2.3
            },
            "high": {
                "active": 7,
                "acknowledged": 5,
                "resolved": 89,
                "avg_acknowledgment_time_minutes": 25.2,
                "avg_resolution_time_hours": 6.7
            },
            "medium": {
                "active": 9,
                "acknowledged": 6,
                "resolved": 122,
                "avg_acknowledgment_time_minutes": 45.8,
                "avg_resolution_time_hours": 24.5
            }
        },

        "by_concern_type": {
            "severe_pain": {"active": 3, "resolved": 45},
            "side_effect": {"active": 5, "resolved": 78},
            "mental_health": {"active": 4, "resolved": 56},
            "medication_issue": {"active": 2, "resolved": 34},
            "emergency": {"active": 1, "resolved": 12},
            "general_concern": {"active": 3, "resolved": 20}
        },

        "avg_resolution_time_hours": 12.4,
        "p95_resolution_time_hours": 36.8,
        "p99_resolution_time_hours": 72.1,

        "overdue_alerts": 3,  # active > 48h
        "unacknowledged_alerts": 6  # created > 2h, not acknowledged
    }
}
```

**Alertas:**
- `by_level.critical.active > 3`: 🚨 Multiple critical alerts
- `overdue_alerts > 5`: 🚨 Alerts not being resolved
- `unacknowledged_alerts > 10`: ⚠️ Alerts not being seen
- `avg_resolution_time_hours > 24`: ⚠️ Slow resolution

---

### **3. Storage & Persistence Metrics**

```python
{
    "storage": {
        "redis_healthy": true,
        "redis_latency_ms": 2.3,
        "redis_memory_used_mb": 156.7,
        "redis_keys_count": 1847,

        "fallback_active": false,
        "fallback_entries": 0,

        "sync_stats": {
            "last_rehydration": "2025-12-24T08:00:00-03:00",
            "rehydrated_actions": 142,
            "rehydrated_alerts": 18,
            "rehydration_errors": 0,

            "last_memory_to_redis_sync": "2025-12-24T08:05:00-03:00",
            "synced_actions": 0,  # No Redis downtime
            "synced_alerts": 0,
            "sync_errors": 0
        },

        "cache_stats": {
            "conversation_contexts": 234,
            "hit_rate": 0.87,
            "miss_rate": 0.13,
            "avg_context_size_kb": 4.2
        }
    }
}
```

**Alertas:**
- `redis_healthy == false`: 🚨 Redis down, using fallback
- `fallback_active == true`: ⚠️ Fallback mode active
- `redis_latency_ms > 50`: ⚠️ Slow Redis response
- `sync_errors > 5`: 🚨 Sync issues detected

---

### **4. Message Deduplication Metrics**

```python
{
    "deduplication": {
        "total_checks": 5678,
        "duplicates_blocked": 234,
        "duplicates_rate": 0.041,  # 4.1% blocked

        "by_message_type": {
            "flow_message": {
                "checks": 2345,
                "blocked": 89,
                "block_rate": 0.038
            },
            "follow_up": {
                "checks": 1567,
                "blocked": 78,
                "block_rate": 0.050
            },
            "empathetic": {
                "checks": 1234,
                "blocked": 45,
                "block_rate": 0.036
            },
            "escalation": {
                "checks": 532,
                "blocked": 22,
                "block_rate": 0.041
            }
        },

        "cache_efficiency": {
            "avg_window_hours": 2.0,
            "cache_size_keys": 456,
            "avg_ttl_remaining_minutes": 67.3
        },

        "false_positives": 3,  # Legitimate msgs blocked
        "false_negative": 1    # Duplicates not caught
    }
}
```

**Alertas:**
- `duplicates_rate > 0.10`: ⚠️ High duplicate rate (>10%)
- `false_positives > 10`: 🚨 Too many legitimate msgs blocked
- `duplicates_rate < 0.01`: ℹ️ Very low, check if working

---

### **5. Flow Service Integration Metrics**

```python
{
    "flow_integration": {
        "flow_messages_sent": 1234,
        "follow_ups_registered": 1189,  # Should be ~same as sent
        "registration_rate": 0.964,     # 96.4% registered

        "registration_failures": 45,
        "failure_reasons": {
            "follow_up_service_unavailable": 23,
            "redis_error": 12,
            "timeout": 7,
            "other": 3
        },

        "avg_registration_time_ms": 12.3,
        "p95_registration_time_ms": 45.6,

        "response_tracking": {
            "messages_with_expected_response": 1189,
            "patients_responded": 978,
            "response_rate": 0.823,  # 82.3% responded
            "avg_response_time_hours": 8.7,

            "follow_ups_triggered": 211,  # 1189 - 978
            "follow_up_effectiveness": {
                "responded_after_followup": 156,
                "effectiveness_rate": 0.739  # 73.9%
            }
        }
    }
}
```

**Alertas:**
- `registration_rate < 0.90`: 🚨 Many flow messages not registered
- `response_rate < 0.70`: ⚠️ Low patient response rate
- `effectiveness_rate < 0.50`: ⚠️ Follow-ups not effective

---

## 📈 Dashboard Views

### **View 1: Executive Summary (Real-time)**

```
┌─────────────────────────────────────────────────────────────────────┐
│                   FOLLOW-UP SYSTEM DASHBOARD                        │
│                   Last Update: 2025-12-24 14:35:22                  │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────┬──────────────────────┬──────────────────────┐
│   PENDING ACTIONS    │   ACTIVE ALERTS      │   SYSTEM HEALTH      │
│                      │                      │                      │
│      142             │        18            │    ✅ HEALTHY        │
│   ⬆️ +12 (1h)        │   ⬇️ -3 (1h)         │   Redis: ✅ 2.3ms    │
│                      │                      │   Fallback: ❌ Off   │
└──────────────────────┴──────────────────────┴──────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   COMPLETION RATE                                                   │
│                                                                     │
│   98.7%  ████████████████████████████████████████████▌             │
│                                                                     │
│   Target: 95%  ✅ Above target                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   CRITICAL ALERTS (Requires Immediate Attention)                   │
│                                                                     │
│   2 Critical Alerts Active                                         │
│   - Severe pain reported by Patient #1234 (2h ago) ⏰ URGENT       │
│   - Emergency escalation for Patient #5678 (45m ago) 🚨 CRITICAL   │
│                                                                     │
│   6 Unacknowledged Alerts (> 2h)                                   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   RESPONSE TRACKING (Last 24h)                                     │
│                                                                     │
│   Messages Sent:          1,234                                    │
│   Patients Responded:       978  (82.3%)  ✅                        │
│   Follow-ups Triggered:     211  (17.7%)                           │
│   Responded After FU:       156  (73.9% effectiveness)             │
└─────────────────────────────────────────────────────────────────────┘
```

---

### **View 2: Operations Dashboard**

```
┌─────────────────────────────────────────────────────────────────────┐
│                   FOLLOW-UP OPERATIONS                              │
└─────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────┬────────────────────────────────┐
│   ACTIONS BY TYPE                  │   ACTIONS BY PRIORITY          │
│                                    │                                │
│   Empathetic Response:    45       │   Critical:      2  ⏰         │
│   Medical Clarification:  12       │   High:         18  ⚠️         │
│   Escalation:              8       │   Medium:       87             │
│   Provider Alert:          3       │   Low:          35             │
│   Conversation:           74       │                                │
└────────────────────────────────────┴────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   EXECUTION PERFORMANCE                                             │
│                                                                     │
│   Avg Execution Time:     3.5s  ✅                                  │
│   P95 Execution Time:     8.2s  ✅                                  │
│   P99 Execution Time:    15.1s  ⚠️ (Target: <10s)                  │
│                                                                     │
│   Slowest Actions (Last Hour):                                     │
│   - Medical Clarification #abc123: 24.5s (AI timeout)              │
│   - Provider Alert #def456: 18.7s (notification delay)             │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   DEDUPLICATION                                                     │
│                                                                     │
│   Total Checks:        5,678                                       │
│   Duplicates Blocked:    234  (4.1%)                               │
│                                                                     │
│   By Type:                                                         │
│   - Flow Messages:     89 blocked (3.8%)                           │
│   - Follow-ups:        78 blocked (5.0%)  ⚠️ Higher than expected  │
│   - Empathetic:        45 blocked (3.6%)                           │
│   - Escalation:        22 blocked (4.1%)                           │
│                                                                     │
│   False Positives:      3  ⚠️ Review blocked messages              │
└─────────────────────────────────────────────────────────────────────┘
```

---

### **View 3: Alert Management Dashboard**

```
┌─────────────────────────────────────────────────────────────────────┐
│                   ESCALATION ALERTS                                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   ALERTS BY SEVERITY                                                │
│                                                                     │
│   Critical:   2 active   (Avg resolution: 2.3h)   🚨               │
│   High:       7 active   (Avg resolution: 6.7h)   ⚠️               │
│   Medium:     9 active   (Avg resolution: 24.5h)                   │
│                                                                     │
│   Overdue (>48h):     3 alerts  ⚠️                                  │
│   Unacknowledged:     6 alerts  ⚠️                                  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   ALERTS BY CONCERN TYPE (Last 7 days)                             │
│                                                                     │
│   Severe Pain:        3 active,  45 resolved  ████████             │
│   Side Effects:       5 active,  78 resolved  ████████████         │
│   Mental Health:      4 active,  56 resolved  █████████            │
│   Medication Issue:   2 active,  34 resolved  ██████               │
│   Emergency:          1 active,  12 resolved  ███                  │
│   General Concern:    3 active,  20 resolved  ████                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│   TEAM PERFORMANCE                                                  │
│                                                                     │
│   Dr. Silva:      Acknowledged: 45   Resolved: 42   Avg: 5.2h     │
│   Dr. Costa:      Acknowledged: 38   Resolved: 35   Avg: 6.8h     │
│   Nurse Maria:    Acknowledged: 67   Resolved: 64   Avg: 8.1h     │
│   Nurse João:     Acknowledged: 54   Resolved: 51   Avg: 7.3h     │
│                                                                     │
│   Unassigned:     12 alerts  ⚠️                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🚨 Alert Rules (Prometheus/Grafana)

### **Critical Alerts (PagerDuty)**

```yaml
# alerts/follow_up_critical.yml

groups:
  - name: follow_up_critical
    interval: 1m
    rules:
      - alert: CriticalAlertsBackingUp
        expr: follow_up_active_alerts{level="critical"} > 3
        for: 5m
        labels:
          severity: critical
          team: medical
        annotations:
          summary: "Multiple critical patient alerts pending"
          description: "{{ $value }} critical alerts active for >5min"

      - alert: FollowUpServiceDown
        expr: up{job="follow_up_service"} == 0
        for: 2m
        labels:
          severity: critical
          team: engineering
        annotations:
          summary: "Follow-up service is down"

      - alert: RedisDownFollowUpFallback
        expr: follow_up_redis_healthy == 0
        for: 5m
        labels:
          severity: critical
          team: engineering
        annotations:
          summary: "Redis down, using in-memory fallback"
          description: "Data loss risk if service restarts"

      - alert: HighActionFailureRate
        expr: rate(follow_up_actions_failed_total[5m]) > 0.1
        for: 10m
        labels:
          severity: critical
          team: engineering
        annotations:
          summary: "High follow-up action failure rate"
          description: "{{ $value }} actions/min failing"
```

---

### **Warning Alerts (Slack)**

```yaml
# alerts/follow_up_warnings.yml

groups:
  - name: follow_up_warnings
    interval: 5m
    rules:
      - alert: UnacknowledgedAlertsAccumulating
        expr: follow_up_unacknowledged_alerts > 10
        for: 15m
        labels:
          severity: warning
          team: medical
        annotations:
          summary: "Many patient alerts not being acknowledged"

      - alert: SlowFollowUpExecution
        expr: histogram_quantile(0.95, follow_up_execution_time_seconds) > 10
        for: 30m
        labels:
          severity: warning
          team: engineering
        annotations:
          summary: "Slow follow-up action execution"
          description: "P95 execution time: {{ $value }}s"

      - alert: LowPatientResponseRate
        expr: follow_up_patient_response_rate < 0.70
        for: 2h
        labels:
          severity: warning
          team: clinical
        annotations:
          summary: "Patient response rate dropped below 70%"

      - alert: HighDuplicationBlockRate
        expr: follow_up_dedup_block_rate > 0.10
        for: 1h
        labels:
          severity: warning
          team: engineering
        annotations:
          summary: "High message deduplication block rate"
          description: "{{ $value }} messages blocked as duplicates"
```

---

## 📊 Grafana Dashboard JSON

```json
{
  "dashboard": {
    "title": "Follow-Up System Monitoring",
    "panels": [
      {
        "title": "Pending Actions",
        "targets": [{
          "expr": "follow_up_pending_actions_total"
        }],
        "type": "graph"
      },
      {
        "title": "Active Alerts by Severity",
        "targets": [{
          "expr": "follow_up_active_alerts{level=~\"critical|high|medium\"}"
        }],
        "type": "bargauge"
      },
      {
        "title": "Completion Rate",
        "targets": [{
          "expr": "follow_up_actions_completed_total / (follow_up_actions_completed_total + follow_up_actions_failed_total)"
        }],
        "type": "stat"
      },
      {
        "title": "Execution Time (P95)",
        "targets": [{
          "expr": "histogram_quantile(0.95, follow_up_execution_time_seconds)"
        }],
        "type": "graph"
      },
      {
        "title": "Patient Response Rate",
        "targets": [{
          "expr": "follow_up_patient_responses_total / follow_up_messages_sent_total"
        }],
        "type": "graph"
      }
    ]
  }
}
```

---

## 🔍 Logging Strategy

### **Log Levels**

```python
# CRITICAL - System failures
logger.critical("Redis down and fallback failed - DATA LOSS IMMINENT")

# ERROR - Action failures, important errors
logger.error(f"Failed to execute follow-up action {action_id}: {error}")

# WARNING - Degraded performance, potential issues
logger.warning(f"Slow execution time: {execution_time}s > 10s threshold")

# INFO - Important events
logger.info(f"Follow-up action {action_id} completed successfully")

# DEBUG - Detailed troubleshooting
logger.debug(f"Deduplication check for patient {patient_id}: {result}")
```

---

### **Structured Logging (JSON)**

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "follow_up_action_completed",
    action_id=str(action.action_id),
    patient_id=str(action.patient_id),
    action_type=action.follow_up_type.value,
    execution_time_seconds=3.2,
    status="success"
)

# Output:
# {
#   "event": "follow_up_action_completed",
#   "action_id": "abc-123",
#   "patient_id": "xyz-789",
#   "action_type": "empathetic_response",
#   "execution_time_seconds": 3.2,
#   "status": "success",
#   "timestamp": "2025-12-24T14:35:22-03:00"
# }
```

---

## 🎯 SLOs (Service Level Objectives)

| Metric | Target | Measurement | Alert Threshold |
|--------|--------|-------------|-----------------|
| **Action Completion Rate** | ≥ 95% | completed / (completed + failed) | < 90% |
| **Critical Alert Response** | < 15 min | time_to_acknowledgment | > 30 min |
| **Critical Alert Resolution** | < 4 hours | time_to_resolution | > 8 hours |
| **System Availability** | ≥ 99.5% | uptime / total_time | < 99% |
| **P95 Execution Time** | < 10 seconds | histogram_quantile(0.95) | > 15 seconds |
| **Patient Response Rate** | ≥ 75% | responses / messages_sent | < 70% |
| **Redis Availability** | ≥ 99.9% | redis_uptime / total_time | < 99% |

---

## 📞 On-Call Runbook

### **Scenario 1: High Action Failure Rate**

**Alert:** `HighActionFailureRate > 10%`

**Steps:**
1. Check Celery worker status: `celery inspect active`
2. Review error logs: `grep "Failed to execute" /var/log/follow_up.log`
3. Check Redis connectivity: `redis-cli ping`
4. Verify WhatsApp service: `curl http://whatsapp-api/health`
5. Restart workers if needed: `systemctl restart celery-worker`

---

### **Scenario 2: Redis Down**

**Alert:** `RedisDownFollowUpFallback`

**Steps:**
1. Check Redis status: `systemctl status redis`
2. Review Redis logs: `tail -f /var/log/redis/redis.log`
3. Attempt restart: `systemctl restart redis`
4. Monitor fallback metrics
5. When Redis recovers: Monitor sync_memory_to_redis() execution
6. Verify no data loss: Check action counts before/after

---

### **Scenario 3: Critical Alerts Backing Up**

**Alert:** `CriticalAlertsBackingUp > 3`

**Steps:**
1. Check staff availability
2. Review alert details in dashboard
3. Manually assign to available staff if needed
4. Escalate to on-call physician if > 5 alerts
5. Document reason for backup

---

**Última Atualização:** 2025-12-24
**Versão:** 1.0
**Status:** ✅ Ready for Implementation


---\n

