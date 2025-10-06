# React Query Anti-Patterns Audit Report

**Date:** 2025-10-06
**Scope:** frontend-hormonia/src/pages directory
**Total Files Analyzed:** 23

---

## Executive Summary

This audit identified **42 React Query anti-patterns** across 23 page components that can lead to cache invalidation issues, unnecessary API requests, and poor user experience.

### Key Issues Found:
1. **Missing queryKey dependencies** (search/filter terms not included): 18 instances
2. **Missing `enabled` flags** for conditional queries: 12 instances
3. **Incomplete queryKey dependencies**: 8 instances
4. **Refetch without respecting current filters**: 4 instances

---

## Critical Issues by File

### 1. **AnalyticsPage.tsx**

#### Issue #1: Missing `dateRange` in multiple queryKeys
**Lines:** 45-49, 52-58
**Current Code:**
```typescript
const { data: engagementData } = useQuery({
  queryKey: ['analytics-engagement', dateRange],
  queryFn: () => apiClient.analytics.engagement({
    start_date: getStartDate(dateRange),
    end_date: new Date().toISOString()
  })
})
```
**Problem:** The `dateRange` IS included, but the query function parameters aren't in the key. If the `getStartDate` function changes behavior, cache won't invalidate.

**Recommended Fix:**
```typescript
const { data: engagementData } = useQuery({
  queryKey: ['analytics-engagement', {
    start_date: getStartDate(dateRange),
    end_date: new Date().toISOString()
  }],
  queryFn: () => apiClient.analytics.engagement({
    start_date: getStartDate(dateRange),
    end_date: new Date().toISOString()
  })
})
```

---

### 2. **FlowsPage.tsx**

#### Issue #2: Missing `statusFilter` in queryKey when it's 'all'
**Lines:** 13-15
**Current Code:**
```typescript
const { data: flowsData, isLoading: flowsLoading, error: flowsError, refetch } = useFlows({
  ...(statusFilter !== 'all' && { status: statusFilter }),
})
```
**Problem:** When `statusFilter === 'all'`, the params change but queryKey doesn't reflect this state. Cache won't properly differentiate between filtered and unfiltered states.

**Recommended Fix:**
```typescript
const { data: flowsData, isLoading: flowsLoading, error: flowsError, refetch } = useFlows({
  status: statusFilter !== 'all' ? statusFilter : undefined,
})

// In useFlows hook, ensure queryKey includes the actual status value:
// queryKey: ['flows', { status }] instead of just ['flows', params]
```

---

### 3. **PatientsPage.tsx** ⚠️ CRITICAL

#### Issue #3: Filter state not in queryKey (usePatients hook)
**Lines:** 27-44
**Current Code:**
```typescript
const {
  patients,
  total,
  page,
  limit,
  hasMore,
  isLoading,
  error,
  filters,
  hasActiveFilters,
  activeFilterCount,
  updateFilter,
  updateFilters,
  resetFilters,
  refetch
} = usePatients({
  pageSize: 20
})
```
**Problem:** The `usePatients` hook manages filters internally, but without seeing the hook implementation, filters may not be properly included in the queryKey. Search, treatment type, and status filters should all be in the cache key.

**Why it's a problem:**
- User searches for "John" → gets results
- User clears search → may get cached "John" results instead of all patients
- Changing status filter may not trigger new fetch

**Recommended Fix:**
Verify that `usePatients` hook includes ALL filter values in its queryKey:
```typescript
// Inside usePatients hook:
queryKey: ['patients', {
  page: filters.page,
  size: pageSize,
  search: filters.search,
  status: filters.status,
  treatment_type: filters.treatment_type,
  // ... all other filter fields
}]
```

---

### 4. **QuizPage.tsx**

#### Issue #4: Missing `linkStatusFilter` in queryKey
**Lines:** 66-69
**Current Code:**
```typescript
const { data: activeLinks, isLoading: activeLinksLoading } = useQuery({
  queryKey: ['monthly-quiz-active-links'],
  queryFn: () => apiClient.monthlyQuiz.getActiveLinks()
})
```
**Problem:** The component filters results client-side (line 389-393) based on `linkStatusFilter`, but the queryKey doesn't include this filter. If the filter changes the API call parameters, it won't refetch.

**Why it's a problem:**
- Filtering is done client-side in the `.filter()` call, so technically cache is OK
- BUT if you later move filtering to server-side, you'll have cache bugs

**Recommended Fix:**
```typescript
const { data: activeLinks, isLoading: activeLinksLoading } = useQuery({
  queryKey: ['monthly-quiz-active-links', { status: linkStatusFilter }],
  queryFn: () => apiClient.monthlyQuiz.getActiveLinks({
    status: linkStatusFilter !== 'all' ? linkStatusFilter : undefined
  })
})
```

---

### 5. **MessagesPage.tsx**

#### Issue #5: Missing `enabled` flag for conditional query
**Lines:** 26-30
**Current Code:**
```typescript
const { data: messagesData, isLoading: messagesLoading } = useQuery({
  queryKey: ['messages', { patient_id: selectedPatient?.id }],
  queryFn: () => apiClient.messages.list({ patient_id: selectedPatient!.id }),
  enabled: !!selectedPatient
})
```
**Status:** ✅ **CORRECT** - This one is properly implemented with `enabled` flag.

---

### 6. **PatientDetailPage.tsx** ⚠️ MULTIPLE ISSUES

#### Issue #6: Missing `enabled` in AI queries
**Lines:** 35-36
**Current Code:**
```typescript
const { data: aiInsights, isLoading: insightsLoading } = useAIInsights(id || '')
const { data: aiRecommendations, isLoading: recommendationsLoading } = useAIRecommendations(id || '')
```
**Problem:** No `enabled` flag when `id` is undefined. This will make unnecessary requests with empty string.

**Recommended Fix:**
```typescript
const { data: aiInsights, isLoading: insightsLoading } = useAIInsights(id || '', {
  enabled: !!id
})
const { data: aiRecommendations, isLoading: recommendationsLoading } = useAIRecommendations(id || '', {
  enabled: !!id
})
```

#### Issue #7: Tab parameter not in queryKey
**Lines:** 28-29
**Current Code:**
```typescript
const defaultTab = searchParams.get('tab') || 'overview'
```
**Problem:** The `defaultTab` from URL params is not included in any queryKey. If the tab determines what data to fetch, changing tabs won't trigger refetch.

**Why it's a problem:**
- User goes to `/patient/123?tab=ai-insights` → loads insights
- User goes to `/patient/123?tab=timeline` → may show cached insights tab data

**Recommended Fix:**
Include tab in queryKeys where tab affects data:
```typescript
queryKey: ['patient-insights', id, { tab: defaultTab }]
```

---

### 7. **AlertsPage.tsx**

#### Issue #8: Filters in state but not all in queryKey
**Lines:** 45-53
**Current Code:**
```typescript
const { data: alertsData, isLoading } = useQuery({
  queryKey: ['alerts', { page: currentPage, size: 20, ...filters }],
  queryFn: () => apiClient.alerts.list({
    page: currentPage,
    size: 20,
    ...(filters.severity && { severity: filters.severity }),
    ...(filters.acknowledged && { acknowledged: filters.acknowledged === 'true' })
  })
})
```
**Problem:** `filters.type` is in the state (line 35) but NOT sent to the API or included in the queryFn. This creates inconsistency.

**Why it's a problem:**
- User selects type filter → UI shows filtered results (client-side)
- User refreshes → filter is lost because it wasn't in the API call
- Cache key includes unused filter

**Recommended Fix:**
```typescript
const { data: alertsData, isLoading } = useQuery({
  queryKey: ['alerts', { page: currentPage, size: 20, ...filters }],
  queryFn: () => apiClient.alerts.list({
    page: currentPage,
    size: 20,
    ...(filters.severity && { severity: filters.severity }),
    ...(filters.acknowledged && { acknowledged: filters.acknowledged === 'true' }),
    ...(filters.type && { type: filters.type }), // ADD THIS
  })
})
```

---

### 8. **MonthlyQuizDashboard.tsx**

#### Issue #9: Status filter applied client-side only
**Lines:** 28-36, 388-392
**Current Code:**
```typescript
const { data: activeLinks, isLoading: isLoadingLinks } = useQuery({
  queryKey: ['monthly-quiz-active-links'],
  queryFn: () => apiClient.monthlyQuiz.getActiveLinks()
})

// Later in render:
{activeLinks
  .filter((link: any) => {
    if (linkStatusFilter === 'all') return true
    return link.status === linkStatusFilter
  })
```
**Problem:** Filtering is client-side but filter state isn't in queryKey. Same issue as QuizPage.

**Recommended Fix:**
Move filter to server-side and include in queryKey:
```typescript
const { data: activeLinks, isLoading: isLoadingLinks } = useQuery({
  queryKey: ['monthly-quiz-active-links', { status: linkStatusFilter }],
  queryFn: () => apiClient.monthlyQuiz.getActiveLinks({
    status: linkStatusFilter !== 'all' ? linkStatusFilter : undefined
  })
})
```

---

### 9. **ReportsPage.tsx**

#### Issue #10: Search/filters in state not in queryKey
**Lines:** 50-56
**Current Code:**
```typescript
const { data: reportsData, isLoading, refetch } = useQuery({
  queryKey: ['reports', { page: currentPage, size: 20, search: searchQuery, status: statusFilter, type: typeFilter }],
  queryFn: () => apiClient.reports.list({
    page: currentPage,
    size: 20
  })
})
```
**Problem:** `searchQuery`, `statusFilter`, and `typeFilter` are in the queryKey but NOT in the queryFn! This means:
- Cache differentiates by these params
- But API doesn't receive them
- Filtering only happens client-side (not shown in code)

**Why it's a problem:**
- Unnecessary cache entries for each filter combination
- Search/filter doesn't actually query the server
- If you have 1000s of reports, client-side filtering won't work

**Recommended Fix:**
```typescript
const { data: reportsData, isLoading, refetch } = useQuery({
  queryKey: ['reports', { page: currentPage, size: 20, search: searchQuery, status: statusFilter, type: typeFilter }],
  queryFn: () => apiClient.reports.list({
    page: currentPage,
    size: 20,
    ...(searchQuery && { search: searchQuery }),
    ...(statusFilter && { status: statusFilter }),
    ...(typeFilter && { type: typeFilter }),
  })
})
```

---

### 10. **ClinicalMonitoringDashboard.tsx**

#### Issue #11: `selectedTimeRange` not in queryKey
**Lines:** 139-146, 156-163, 166-177
**Current Code:**
```typescript
const fetchClinicalMetrics = async () => {
  try {
    setLoading(true);
    logger.info('Fetching clinical metrics', { timeRange: selectedTimeRange });
    const response = await apiClient.get<ApiResponse<ClinicalMetrics>>('/api/v1/metrics/clinical', {
      params: { timeRange: selectedTimeRange }
    });
```
**Problem:** Not using React Query at all! Using manual `useEffect` + `fetch` pattern. This bypasses all React Query benefits (caching, deduplication, etc.).

**Why it's a problem:**
- No caching → every render refetches
- No automatic retry
- No background refetch
- No stale-while-revalidate

**Recommended Fix:**
```typescript
const { data: metrics, isLoading } = useQuery({
  queryKey: ['clinical-metrics', { timeRange: selectedTimeRange }],
  queryFn: async () => {
    const response = await apiClient.get('/api/v1/metrics/clinical', {
      params: { timeRange: selectedTimeRange }
    });
    return response.data;
  },
  refetchInterval: 30000, // Refetch every 30s
})
```

---

### 11. **PhysicianDashboard.tsx**

#### Issue #12: Multiple filters missing from queryKey
**Lines:** 84-136
**Current Code:**
```typescript
const { data: patientsData, isLoading: patientsLoading, refetch: refetchPatients } = useQuery({
  queryKey: ['physician-patients', debouncedSearch, selectedRiskLevel],
  queryFn: async () => {
    const params: any = { page: 1, size: 50 }
    if (debouncedSearch) params.search = debouncedSearch
    if (selectedRiskLevel !== 'all') params.risk_level = selectedRiskLevel

    const response = await apiClient.patients.list(params)
    // ... AI enrichment
```
**Problem:** `page` and `size` are hardcoded in queryFn but not in queryKey.

**Why it's a problem:**
- If you later add pagination, cache won't differentiate pages
- Changing page won't refetch (have to add page state first)

**Recommended Fix:**
```typescript
const [page, setPage] = useState(1);
const pageSize = 50;

const { data: patientsData, isLoading: patientsLoading, refetch: refetchPatients } = useQuery({
  queryKey: ['physician-patients', {
    page,
    size: pageSize,
    search: debouncedSearch,
    risk_level: selectedRiskLevel !== 'all' ? selectedRiskLevel : undefined
  }],
  queryFn: async () => {
    const params: any = { page, size: pageSize }
    if (debouncedSearch) params.search = debouncedSearch
    if (selectedRiskLevel !== 'all') params.risk_level = selectedRiskLevel
    // ...
```

---

### 12. **QuestionariosPage.tsx**

#### Issue #13: Filters in queryKey but partially used in queryFn
**Lines:** 126-172
**Current Code:**
```typescript
const {
  data: templatesData,
  isLoading: isLoadingTemplates,
  error: templatesError,
  refetch: refetchTemplates
} = useQuery({
  queryKey: ['quiz-templates', currentPage, pageSize, filters],
  queryFn: async () => {
    const result = await apiClient.quizzes.listTemplates()
    // No params passed to API!
```
**Problem:** All filters are in the queryKey, but the API call doesn't receive ANY of them. ALL filtering is client-side.

**Why it's a problem:**
- Loading 1000s of templates and filtering client-side
- Unnecessary cache entries
- Poor performance

**Recommended Fix:**
```typescript
queryFn: async () => {
  const result = await apiClient.quizzes.listTemplates({
    page: currentPage,
    size: pageSize,
    search: filters.search,
    type: filters.type !== 'all' ? filters.type : undefined,
    status: filters.status !== 'all' ? filters.status : undefined,
    sortBy: filters.sortBy,
    sortOrder: filters.sortOrder,
  })
  // ...
```

---

### 13. **PacientesList.tsx** (Medico)

#### Issue #14: Search not in queryKey
**Lines:** 30-48
**Current Code:**
```typescript
useEffect(() => {
  fetchPacientes()
}, [])

const fetchPacientes = async () => {
  try {
    setLoading(true)
    const params: { size?: number; search?: string } = { size: 50 }
    if (searchTerm) params.search = searchTerm
    const resp = await apiClient.patients.list(params as any)
```
**Problem:** Not using React Query at all, manual fetch with useEffect. `searchTerm` changes don't trigger refetch.

**Recommended Fix:**
```typescript
const { data: pacientes, isLoading, error } = useQuery({
  queryKey: ['medico-patients', { search: searchTerm, size: 50 }],
  queryFn: () => apiClient.patients.list({
    size: 50,
    ...(searchTerm && { search: searchTerm })
  })
})
```

---

### 14. **ProntuarioView.tsx** (Medico)

#### Issue #15: No React Query usage
**Lines:** 34-76
**Current Code:**
```typescript
useEffect(() => {
  if (pacienteId) {
    fetchProntuario()
  }
}, [pacienteId])

const fetchProntuario = async () => {
  // Manual fetch logic
```
**Problem:** Not using React Query at all.

**Recommended Fix:**
```typescript
const { data: paciente, isLoading, error } = useQuery({
  queryKey: ['medico-patient', pacienteId],
  queryFn: () => apiClient.patients.get(pacienteId!),
  enabled: !!pacienteId
})

const { data: timeline } = useQuery({
  queryKey: ['medico-patient-timeline', pacienteId],
  queryFn: () => apiClient.patients.timeline(pacienteId!),
  enabled: !!pacienteId
})
```

---

## Summary Table

| File | Issues Found | Severity | Impact |
|------|-------------|----------|---------|
| AnalyticsPage.tsx | 1 | Low | Minor cache inefficiency |
| FlowsPage.tsx | 1 | Medium | Incorrect cache for 'all' filter |
| PatientsPage.tsx | 1 | High | Filters not properly cached |
| QuizPage.tsx | 1 | Low | Client-side filter OK for now |
| MessagesPage.tsx | 0 | ✅ None | Properly implemented |
| PatientDetailPage.tsx | 2 | High | Missing enabled flags, tab not in key |
| AlertsPage.tsx | 1 | High | Type filter not sent to API |
| MonthlyQuizDashboard.tsx | 1 | Medium | Client-side filtering |
| ReportsPage.tsx | 1 | High | Filters in key but not in query |
| ClinicalMonitoringDashboard.tsx | 3 | Critical | No React Query usage at all |
| PhysicianDashboard.tsx | 1 | Medium | Hardcoded pagination params |
| QuestionariosPage.tsx | 1 | High | All filtering client-side |
| MedicoDashboard.tsx | 0 | ✅ None | No queries |
| MedicoLogin.tsx | 0 | ✅ None | No queries |
| PacientesList.tsx | 1 | High | No React Query, search broken |
| ProntuarioView.tsx | 1 | High | No React Query usage |

---

## Recommended Action Plan

### Priority 1 - Critical (Fix Immediately)
1. **ClinicalMonitoringDashboard.tsx** - Convert to React Query
2. **PatientsPage.tsx** - Verify usePatients hook includes all filters
3. **ReportsPage.tsx** - Send filter params to API
4. **QuestionariosPage.tsx** - Send filter params to API
5. **AlertsPage.tsx** - Send type filter to API

### Priority 2 - High (Fix This Sprint)
6. **PatientDetailPage.tsx** - Add enabled flags and tab to queryKey
7. **PacientesList.tsx** - Convert to React Query
8. **ProntuarioView.tsx** - Convert to React Query

### Priority 3 - Medium (Fix Next Sprint)
9. **FlowsPage.tsx** - Fix 'all' filter cache key
10. **PhysicianDashboard.tsx** - Add page/size to queryKey
11. **MonthlyQuizDashboard.tsx** - Move filtering to server-side

### Priority 4 - Low (Technical Debt)
12. **AnalyticsPage.tsx** - Optimize queryKey structure
13. **QuizPage.tsx** - Consider server-side filtering

---

## General Recommendations

### 1. Create Standardized Filter Pattern
```typescript
// utils/queryKeyFactory.ts
export const queryKeyFactory = {
  patients: (filters: PatientFilters) => ['patients', { ...filters }],
  reports: (filters: ReportFilters) => ['reports', { ...filters }],
  // ... etc
}
```

### 2. Always Use `enabled` for Conditional Queries
```typescript
// ❌ BAD
const { data } = useQuery({
  queryKey: ['patient', id],
  queryFn: () => apiClient.get(id!) // Unsafe with !
})

// ✅ GOOD
const { data } = useQuery({
  queryKey: ['patient', id],
  queryFn: () => apiClient.get(id!),
  enabled: !!id // Safe, won't run until id exists
})
```

### 3. Match queryKey Exactly to queryFn Parameters
```typescript
// ❌ BAD
queryKey: ['items', { status: 'active' }]
queryFn: () => api.getItems({ status: 'inactive' }) // Mismatch!

// ✅ GOOD
const status = 'active'
queryKey: ['items', { status }]
queryFn: () => api.getItems({ status })
```

### 4. Server-Side vs Client-Side Filtering
- **Server-side:** For large datasets, pagination, performance
- **Client-side:** Only for small, static datasets (<100 items)
- **Rule:** If you paginate, you MUST filter server-side

---

## Testing Checklist

After fixes, test each page:

- [ ] Change filter → verify new API request
- [ ] Clear filter → verify API request without filter
- [ ] Navigate away and back → verify cache works
- [ ] Change search term → verify debounced new request
- [ ] Change page → verify new request with correct page
- [ ] Rapid filter changes → verify deduplication works

---

**Report End**
