# Frontend API Usage Analysis - Cache TTL Recommendations

**Analysis Date:** 2025-12-21
**Agent:** Analyst (Hive-Mind Swarm)
**Objective:** Analyze API usage patterns and recommend optimal cache TTLs for frontend

---

## Executive Summary

Analyzed frontend API usage across 87+ components and hooks. Identified clear caching patterns with recommendations to optimize both backend HTTP cache middleware and frontend React Query configuration.

**Key Findings:**
- Backend cache middleware currently uses 60-120s TTL for authenticated endpoints
- Frontend uses 30s default staleTime with query-specific overrides
- Mismatch between backend and frontend cache durations creates unnecessary API calls
- High-frequency dashboard queries refresh every 30s (too aggressive)
- Static data (treatment types) correctly cached with Infinity

---

## Current Backend Cache Configuration

**Source:** `/backend-hormonia/app/middleware/cache_middleware.py`

```python
# Current Backend TTL Configuration
default_ttl = 300  # 5 minutes (public/unauthenticated)
authenticated_ttl = 90  # 90 seconds (authenticated default)

endpoint_ttl = {
    "/api/v2/patients": 120,      # 2 minutes
    "/api/v2/dashboard": 60,       # 1 minute
    "/api/v2/templates": 300,      # 5 minutes
    "/api/v2/reports": 180,        # 3 minutes
}
```

**Cache Features:**
- ETag-based conditional requests (304 Not Modified)
- User-specific cache keys (prevents data leakage)
- CSRF token integration
- Cache-Control headers
- Automatic cache invalidation support

---

## Current Frontend Cache Configuration

**Source:** `/frontend-hormonia/src/lib/react-query/queryClient.ts`

```typescript
// Global React Query Defaults
staleTime: 30 * 1000,        // 30 seconds (Phase 2.2 enhancement)
gcTime: 5 * 60 * 1000,       // 5 minutes
refetchOnWindowFocus: true,
refetchOnReconnect: true,
refetchOnMount: false,

// Query Presets
realtime: { staleTime: 10s, refetchInterval: 10s }
static: { staleTime: 1h, gcTime: Infinity }
paginated: { staleTime: 30s, gcTime: 5min }
userSpecific: { staleTime: 1min, gcTime: 10min }
```

---

## API Endpoint Usage Analysis

### 1. HIGH-FREQUENCY ENDPOINTS (Polled/Real-time)

#### `/api/v2/dashboard/main`
**Current Config:**
- Backend TTL: 60s
- Frontend: staleTime 30s, refetchInterval 30s (DashboardPage.tsx:46)

**Usage Pattern:**
- Viewed on every dashboard page load
- Polled every 30 seconds while dashboard is open
- Contains: patient counts, response rates, alerts, activity

**Volatility:** High (real-time stats)

**Recommendation:**
| Layer | Setting | Value | Rationale |
|-------|---------|-------|-----------|
| Backend TTL | 30s | 30 seconds | Align with frontend refresh rate |
| Frontend staleTime | 30s | 30 seconds | Keep current (appropriate for real-time) |
| Frontend refetchInterval | 60s | 60 seconds | Reduce from 30s to ease server load |

**Expected Impact:** 50% reduction in dashboard API calls (from every 30s to every 60s)

---

#### `/api/v2/dashboard/physician`
**Current Config:**
- Backend TTL: 60s
- Frontend: staleTime 60s, refetchInterval 120s (PhysicianDashboard.tsx:84-85)

**Usage Pattern:**
- Physician-specific dashboard metrics
- Patient risk assessments
- Upcoming interactions

**Volatility:** Medium-High (clinical data updates frequently)

**Recommendation:**
| Layer | Setting | Value | Rationale |
|-------|---------|-------|-----------|
| Backend TTL | 90s | 90 seconds | Increase to match frontend pattern |
| Frontend staleTime | 60s | 60 seconds | Keep current (good balance) |
| Frontend refetchInterval | 120s | 120 seconds | Keep current (appropriate) |

---

### 2. MEDIUM-FREQUENCY ENDPOINTS (Lists/Tables)

#### `/api/v2/patients` (List)
**Current Config:**
- Backend TTL: 120s (2 minutes)
- Frontend: staleTime 30s (usePatients.ts:209)

**Usage Pattern:**
- Patient list page (primary view)
- Search/filter operations (debounced 300ms)
- Pagination (cursor-based)
- Prefetch next page on scroll

**Volatility:** Medium (patients added/updated moderately)

**Recommendation:**
| Layer | Setting | Value | Rationale |
|-------|---------|-------|-----------|
| Backend TTL | 120s | 120 seconds | Keep current (good for authenticated lists) |
| Frontend staleTime | 60s | 60 seconds | Increase from 30s (reduce refetch frequency) |
| Frontend gcTime | 5min | 5 minutes | Keep current (good for pagination) |
| Prefetch | enabled | true | Keep prefetching next page |

**Cache Strategy:**
- Use cursor-based pagination (already implemented)
- Invalidate on mutations (create/update/delete)
- Prefetch adjacent pages
- Debounce search queries (already 300ms)

---

#### `/api/v2/patients/{id}` (Detail)
**Current Config:**
- Backend TTL: 120s (inherits from list endpoint)
- Frontend: staleTime 30s (default)

**Usage Pattern:**
- Patient detail pages
- Prefetched on hover (5min staleTime - queryKeys.ts:203)
- Includes timeline, stats, risk assessment

**Recommendation:**
| Layer | Setting | Value | Rationale |
|-------|---------|-------|-----------|
| Backend TTL | 180s | 3 minutes | Increase for detail views |
| Frontend staleTime | 120s | 2 minutes | Longer for detail pages |
| Frontend gcTime | 10min | 10 minutes | Cache for navigation back |
| Prefetch staleTime | 5min | 5 minutes | Keep current (good for hover) |

---

### 3. LOW-FREQUENCY ENDPOINTS (Semi-Static)

#### `/api/v2/templates`
**Current Config:**
- Backend TTL: 300s (5 minutes)
- Frontend: staleTime 300s (useFlowEngine.ts:83)

**Usage Pattern:**
- Quiz templates
- Flow templates
- Rarely change

**Volatility:** Very Low (templates rarely updated)

**Recommendation:**
| Layer | Setting | Value | Rationale |
|-------|---------|-------|-----------|
| Backend TTL | 600s | 10 minutes | Increase (semi-static data) |
| Frontend staleTime | 600s | 10 minutes | Match backend |
| Frontend gcTime | 30min | 30 minutes | Long cache (rarely changes) |

---

#### Treatment Types (Mock Data)
**Current Config:**
- Backend: N/A (mock data)
- Frontend: staleTime Infinity, gcTime Infinity (usePatients.ts:310-311)

**Recommendation:** Keep current ✅
- Correctly configured as static data
- No backend endpoint needed (consider adding for real data)

---

### 4. ANALYTICS ENDPOINTS

#### `/api/v2/analytics/dashboard`
**Current Config:**
- Backend TTL: N/A (inherits default 90s)
- Frontend: Various by component

**Usage Patterns:**
```typescript
// DashboardPage.tsx - refetchInterval: 30s
// PhysicianDashboard.tsx - staleTime: 60s, refetchInterval: 120s
// ClinicalMonitoring - refetchInterval: 30s
```

**Recommendation:**
| Endpoint | Backend TTL | Frontend staleTime | refetchInterval |
|----------|-------------|-------------------|-----------------|
| `/api/v2/analytics/dashboard` | 60s | 60s | 90s |
| `/api/v2/analytics/engagement` | 120s | 120s | 300s (5min) |
| `/api/v2/analytics/treatment-distribution` | 300s | 300s | false |

**Rationale:**
- Analytics aggregations are expensive
- Data freshness requirements vary by type
- Reduce polling for static analytics

---

### 5. MUTATION OPERATIONS (Write/Update/Delete)

**Pattern Analysis:**
```typescript
// Current: React Query mutations with cache invalidation
mutations: {
  retry: 1,
  retryDelay: 1000,
  networkMode: 'online'
}
```

**Endpoints Requiring Cache Invalidation:**
1. Patient CRUD: Invalidate `['patients']` and `['patients', id]`
2. Quiz submissions: Invalidate `['quiz', 'sessions']`
3. Message sending: Invalidate `['messages']`
4. Alert acknowledgment: Invalidate `['alerts']`

**Recommendation:**
```typescript
// After mutation success - use existing invalidation helpers
invalidateQueries.patient(queryClient, patientId);  // Detail + timeline + stats
invalidateQueries.allPatients(queryClient);         // List
invalidateQueries.analytics(queryClient);           // Dashboard metrics

// Backend: Implement cache invalidation on write
from app.middleware.cache_middleware import invalidate_http_cache_pattern

@router.post("/patients")
async def create_patient(...):
    # ... create logic ...
    invalidate_http_cache_pattern("http:*patients*")
    return patient
```

---

## Cache Strategy Recommendations by Data Type

### Strategy 1: Real-Time Data (High Volatility)
**Examples:** Dashboard metrics, active alerts, system stats

```typescript
{
  staleTime: 30_000,        // 30 seconds
  gcTime: 120_000,          // 2 minutes
  refetchInterval: 60_000,  // 1 minute
  refetchOnWindowFocus: true,
}
```

**Backend TTL:** 30-60 seconds

---

### Strategy 2: User-Modified Data (Medium Volatility)
**Examples:** Patient lists, messages, quiz sessions

```typescript
{
  staleTime: 60_000,        // 1 minute
  gcTime: 300_000,          // 5 minutes
  refetchOnWindowFocus: false,
  refetchOnReconnect: true,
}
```

**Backend TTL:** 90-120 seconds

---

### Strategy 3: Reference Data (Low Volatility)
**Examples:** Templates, reports, settings

```typescript
{
  staleTime: 600_000,       // 10 minutes
  gcTime: 1_800_000,        // 30 minutes
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
}
```

**Backend TTL:** 300-600 seconds (5-10 minutes)

---

### Strategy 4: Static Data (No Volatility)
**Examples:** Treatment types, constant lists

```typescript
{
  staleTime: Infinity,
  gcTime: Infinity,
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
}
```

**Backend TTL:** 3600 seconds (1 hour) or longer

---

## Comprehensive TTL Recommendation Table

| Endpoint | Current Backend | Recommended Backend | Current Frontend | Recommended Frontend | Reasoning |
|----------|----------------|---------------------|-----------------|---------------------|-----------|
| `/api/v2/dashboard/main` | 60s | **30s** | 30s refetch | **60s refetch** | Reduce polling, align with volatility |
| `/api/v2/dashboard/physician` | 60s | **90s** | 60s/120s | **Keep current** | Already well-configured |
| `/api/v2/patients` (list) | 120s | **120s** | 30s | **60s** | Increase frontend to reduce calls |
| `/api/v2/patients/{id}` | 120s | **180s** | 30s | **120s** | Detail pages less volatile |
| `/api/v2/templates` | 300s | **600s** | 300s | **600s** | Semi-static, rarely changes |
| `/api/v2/reports` | 180s | **300s** | default | **180s** | Reports generated infrequently |
| `/api/v2/analytics/*` | 90s | **120s** | varies | **120s** | Expensive aggregations |
| `/api/v2/messages` | 90s | **60s** | default | **60s** | Moderate freshness needed |
| `/api/v2/quiz/sessions` | 90s | **90s** | 30s | **60s** | User-specific, moderate volatility |
| `/api/v2/alerts` | 90s | **45s** | default | **45s** | Alerts need faster updates |

---

## Performance Impact Estimation

### Current State
- Dashboard polls every 30s = 120 requests/hour
- Patient list refetches every 30s when stale = ~100 requests/hour
- Analytics queries refresh aggressively = ~80 requests/hour

### After Optimization
- Dashboard polls every 60s = **60 requests/hour** (-50%)
- Patient list 60s staleTime = **~50 requests/hour** (-50%)
- Analytics 120s staleTime = **~30 requests/hour** (-62%)

**Total Expected Reduction:** ~40-50% fewer API calls for read operations

**Benefits:**
1. **Reduced Server Load:** 40-50% fewer requests to backend
2. **Lower Database Queries:** HTTP cache hits reduce DB load
3. **Faster User Experience:** More data served from cache
4. **Reduced Bandwidth:** ETag 304 responses are tiny
5. **Better Battery Life:** Fewer network requests on mobile

---

## Implementation Recommendations

### Phase 1: Backend Updates (Priority: High)

```python
# backend-hormonia/app/middleware/cache_middleware.py

# Updated endpoint TTLs
self.endpoint_ttl = {
    # High-volatility (real-time)
    "/api/v2/dashboard/main": 30,          # Reduced from 60s
    "/api/v2/alerts": 45,                  # New: faster alert updates

    # Medium-volatility (user data)
    "/api/v2/dashboard/physician": 90,     # Increased from 60s
    "/api/v2/patients": 120,               # Keep current
    "/api/v2/messages": 60,                # Reduced from 90s
    "/api/v2/quiz": 90,                    # Keep current

    # Low-volatility (reference data)
    "/api/v2/templates": 600,              # Increased from 300s
    "/api/v2/reports": 300,                # Increased from 180s
    "/api/v2/analytics": 120,              # New: expensive queries
}
```

### Phase 2: Frontend Updates (Priority: High)

**File:** `frontend-hormonia/src/lib/query-keys.ts`

Add cache time hints to query key factories:

```typescript
export const queryCacheConfig = {
  // Real-time data
  dashboard: { staleTime: 30_000, refetchInterval: 60_000 },
  alerts: { staleTime: 30_000, refetchInterval: 45_000 },

  // User data
  patients: {
    list: { staleTime: 60_000, gcTime: 300_000 },
    detail: { staleTime: 120_000, gcTime: 600_000 }
  },

  // Reference data
  templates: { staleTime: 600_000, gcTime: 1_800_000 },
  treatmentTypes: { staleTime: Infinity, gcTime: Infinity },
};
```

**Update usage in hooks:**

```typescript
// usePatients.ts - Line 209
staleTime: 60_000, // Increased from 30s

// DashboardPage.tsx - Line 46
refetchInterval: 60_000, // Increased from 30s

// PhysicianDashboard.tsx - Lines 84-85
staleTime: 60_000,       // Keep
refetchInterval: 120_000 // Keep
```

### Phase 3: Cache Invalidation (Priority: Medium)

**Backend:** Add automatic cache invalidation to mutations

```python
# backend-hormonia/app/api/v2/routers/patients.py

from app.middleware.cache_middleware import invalidate_http_cache_pattern

@router.post("/patients")
async def create_patient(...):
    patient = await patient_service.create(data)

    # Invalidate affected caches
    invalidate_http_cache_pattern("http:*patients*")
    invalidate_http_cache_pattern("http:*dashboard*")

    return patient

@router.patch("/patients/{patient_id}")
async def update_patient(...):
    patient = await patient_service.update(patient_id, data)

    # Invalidate specific patient and lists
    invalidate_http_cache_pattern(f"http:*patients/{patient_id}*")
    invalidate_http_cache_pattern("http:*patients*list*")

    return patient
```

**Frontend:** Already implemented ✅
```typescript
// Existing implementation in hooks
queryClient.invalidateQueries({ queryKey: ['patients'] });
queryClient.invalidateQueries({ queryKey: ['patients', id] });
```

### Phase 4: Monitoring (Priority: Low)

Add cache metrics:

```python
# backend-hormonia/app/middleware/cache_middleware.py

@app.get("/api/v2/cache/stats")
async def cache_stats():
    """Return cache hit/miss rates and TTL effectiveness"""
    return {
        "http_cache": {
            "total_requests": cache_manager.get_stat("total"),
            "cache_hits": cache_manager.get_stat("hits"),
            "cache_misses": cache_manager.get_stat("misses"),
            "hit_rate": cache_manager.get_stat("hit_rate"),
            "etag_304": cache_manager.get_stat("etag_304"),
        }
    }
```

---

## Risk Analysis

### Low Risk ✅
- Increasing TTLs for templates/reports (rarely change)
- Adding cache invalidation on mutations (improves consistency)
- Frontend staleTime adjustments (transparent to users)

### Medium Risk ⚠️
- Dashboard refresh rate changes (monitor user feedback)
- Patient list staleTime increase (ensure mutations invalidate correctly)

### Mitigation Strategies
1. **Gradual Rollout:** Implement in staging first
2. **Monitoring:** Track cache hit rates and user-reported staleness
3. **Feature Flags:** Allow disabling aggressive caching per user
4. **Force Refresh:** Add manual refresh buttons for critical views

---

## Next Steps

1. ✅ **Review this analysis** with backend and frontend teams
2. ⬜ **Create implementation tasks** for each phase
3. ⬜ **Update cache middleware** with new TTL values
4. ⬜ **Update frontend hooks** with new staleTime values
5. ⬜ **Add cache invalidation** to mutation endpoints
6. ⬜ **Test in staging** with real usage patterns
7. ⬜ **Monitor metrics** after production deployment
8. ⬜ **Document learnings** for future optimization

---

## Appendix: Query Usage Patterns

### Files Analyzed
- 87 TypeScript files with React Query usage
- 52 API client modules
- 30+ hooks using `staleTime`/`gcTime`/`refetchInterval`

### Key Files
1. `lib/react-query/queryClient.ts` - Global defaults
2. `lib/query-keys.ts` - Query key factories
3. `hooks/usePatients.ts` - Patient queries
4. `pages/DashboardPage.tsx` - Dashboard metrics
5. `middleware/cache_middleware.py` - Backend HTTP cache

### Query Patterns Found
- **30s staleTime:** Most common (default from Phase 2.2)
- **60s+ staleTime:** Used for slower-changing data
- **Infinity:** Correctly used for static data
- **refetchInterval:** Used for real-time dashboards (30s-120s)

---

**Analysis completed by:** Analyst Agent (Hive-Mind Swarm)
**Coordination:** npx claude-flow@alpha hooks
**Next Agent:** Coder Agent (for implementation)
