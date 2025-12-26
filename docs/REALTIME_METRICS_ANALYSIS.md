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
