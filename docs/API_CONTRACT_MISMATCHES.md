# API Contract Mismatches - Comprehensive Analysis

**Analysis Date:** 2025-10-10
**Analyzed By:** API Schema Analyst (Hive Mind Collective)
**Priority:** HIGH - Critical runtime errors and data inconsistencies

---

## Executive Summary

This document details **5 critical API contract mismatches** between frontend and backend that cause runtime errors, incorrect data rendering, and missing functionality. All mismatches have been confirmed through code inspection and represent **production-blocking issues**.

---

## 1. Admin Users List Response Mismatch

### Severity: **CRITICAL** 🔴

### Issue Description
Frontend and backend use incompatible response structures for the admin users list endpoint, causing data display failures.

### Frontend Expectation
**File:** `frontend-hormonia/src/hooks/useUserAdmin.ts` (line 71, 88-89)
```typescript
// Frontend expects:
{
  items: AdminUser[],
  total: number,
  page: number,
  size: number,
  pages: number
}
```

### Backend Reality
**File:** `backend-hormonia/app/api/v1/admin/users.py` (line 200-208)
```python
# Backend returns:
UserListResponse(
    users=[UserResponse.model_validate(user) for user in users],  # NOT 'items'
    total=total,
    page=page,
    size=size,
    total_pages=total_pages,  # NOT 'pages'
    has_next=has_next,
    has_previous=has_previous
)
```

**Schema Definition:** `backend-hormonia/app/schemas/user_admin.py` (line 111-120)
```python
class UserListResponse(BaseModel):
    users: List[UserResponse]  # ❌ Frontend expects 'items'
    total: int
    page: int
    size: int
    total_pages: int  # ❌ Frontend expects 'pages'
    has_next: bool
    has_previous: bool
```

### Impact
- ❌ `usersResponse?.items` returns `undefined`
- ❌ `usersResponse?.pages` returns `undefined`
- ❌ No users displayed in admin panel
- ❌ Pagination broken completely

### Root Cause
Inconsistent naming conventions between backend schema (`users`, `total_pages`) and frontend expectations (`items`, `pages`).

### Recommended Fix
**Option A (Backend Change):**
```python
class UserListResponse(BaseModel):
    items: List[UserResponse]  # Rename from 'users'
    total: int
    page: int
    size: int
    pages: int  # Rename from 'total_pages'
    has_next: bool
    has_previous: bool
```

**Option B (Frontend Change):**
```typescript
users: usersResponse?.users || [],
totalPages: usersResponse?.total_pages || 0,
```

---

## 2. Missing User Activity Route

### Severity: **CRITICAL** 🔴

### Issue Description
Frontend attempts to call a non-existent activity endpoint, resulting in 404 errors.

### Frontend Call
**File:** `frontend-hormonia/src/lib/api-client.ts` (line 865-866)
```typescript
getActivity: (id: string, params?: { page?: number; size?: number }) =>
  this.request<PaginatedResponse<any>>(`/api/v1/admin/users/${id}/activity`, params ? { params } : {}),
```

### Backend Reality
**File:** `backend-hormonia/app/api/v1/admin/users.py`
- ✅ Routes defined: `/`, `/{user_id}`, `/{user_id}/activate`, `/{user_id}/deactivate`, `/{user_id}/role`, `/{user_id}/permissions`, `/{user_id}/reset-password`
- ❌ NO route for `/{user_id}/activity`

**File:** `backend-hormonia/app/api/v1/admin/__init__.py` (line 15-19)
- Only includes `users_router`, `audit_logs_router`, `audit_cleanup_router`, `system_stats_router`
- No activity tracking routes registered

### Impact
- ❌ HTTP 404 when calling `adminUsers.getActivity(userId)`
- ❌ User activity history unavailable
- ❌ Admin panel feature incomplete

### Root Cause
Frontend implemented ahead of backend - route never created.

### Recommended Fix
**Backend Implementation Needed:**
```python
# In app/api/v1/admin/users.py
@router.get(
    "/{user_id}/activity",
    response_model=PaginatedResponse[UserActivity],
    summary="Get User Activity History"
)
async def get_user_activity(
    user_id: UUID,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_thread_safe_db),
    admin_user: User = Depends(get_admin_user)
) -> PaginatedResponse[UserActivity]:
    """Get activity history for a specific user."""
    # Query audit_events table filtered by user_id
    # Return paginated activity log
    pass
```

---

## 3. Notifications Response Schema Mismatch

### Severity: **HIGH** 🟠

### Issue Description
Notification center expects `items` array but backend returns `notifications` array.

### Frontend Expectation
**File:** `frontend-hormonia/src/components/layout/NotificationCenter.tsx` (line 40)
```typescript
const notifications = notificationsData?.items || []
const unreadCount = notificationsData?.unread_count || 0
```

### Backend Reality
**File:** `backend-hormonia/app/api/v1/auth.py` (line 378-413)
```python
class NotificationListResponse(BaseModel):
    notifications: List[NotificationResponse]  # ❌ Frontend expects 'items'
    total: int
    unread_count: int

@router.get("/notifications")
async def get_notifications(...) -> NotificationListResponse:
    return NotificationListResponse(
        notifications=notifications,  # ❌ Should be 'items'
        total=total,
        unread_count=unread_count
    )
```

### Impact
- ❌ Empty notification list in UI
- ❌ `notificationsData?.items` returns `undefined`
- ✅ `unread_count` works correctly (field name matches)

### Root Cause
Same pattern as issue #1 - inconsistent plural naming (`notifications` vs `items`).

### Recommended Fix
**Backend Change:**
```python
class NotificationListResponse(BaseModel):
    items: List[NotificationResponse]  # Rename from 'notifications'
    total: int
    unread_count: int
```

---

## 4. Dashboard Trend Data Missing

### Severity: **MEDIUM** 🟡

### Issue Description
Frontend dashboard expects trend deltas (percentage changes) but backend only provides raw totals.

### Frontend Expectation
**File:** `frontend-hormonia/src/pages/DashboardPage.tsx` (line 98, 105, 112, 119)
```typescript
// Frontend expects change percentages:
metrics?.patients_change || 0      // e.g., +12%
metrics?.messages_change || 0      // e.g., -5%
metrics?.response_rate_change || 0 // e.g., +3%
metrics?.alerts_change || 0        // e.g., -8%
```

**File:** `frontend-hormonia/src/components/dashboard/QuickStats.tsx` (line 65)
```typescript
change: metrics?.patients_change || 0,  // Expected but missing
```

### Backend Reality
**File:** `backend-hormonia/app/schemas/report.py` (line 155-180)
```python
class DashboardResponse(BaseModel):
    total_patients: int
    active_patients: int
    messages_today: int
    alerts_pending: int
    # ❌ No trend fields like 'patients_change', 'messages_change', etc.
```

**File:** `backend-hormonia/app/services/analytics.py` (line 172-187)
```python
dashboard = DashboardResponse(
    total_patients=total_patients,
    active_patients=active_patients,
    messages_today=messages_today,
    alerts_pending=alerts_pending,
    # ❌ No trend calculations performed
)
```

### Impact
- ⚠️ Trend indicators show 0% change (fallback value)
- ⚠️ No up/down arrows in dashboard cards
- ⚠️ Missing historical comparison data

### Root Cause
Backend returns snapshot data without historical comparison. No logic to calculate week-over-week or day-over-day changes.

### Recommended Fix
**Backend Schema Update:**
```python
class DashboardResponse(BaseModel):
    # ... existing fields ...

    # Trend data (percentage changes)
    patients_change: float = 0.0  # Week-over-week change
    messages_change: float = 0.0
    response_rate_change: float = 0.0
    alerts_change: float = 0.0
    quizzes_change: float = 0.0
```

**Backend Logic Update:**
```python
# In analytics.py
def get_dashboard_data():
    # Calculate current week totals
    current_week_patients = ...

    # Calculate previous week totals
    previous_week_patients = ...

    # Calculate percentage change
    patients_change = ((current_week_patients - previous_week_patients) / previous_week_patients) * 100 if previous_week_patients > 0 else 0

    return DashboardResponse(
        patients_change=round(patients_change, 2),
        ...
    )
```

---

## 5. Admin Dashboard Using Mock Data

### Severity: **LOW** 🟢 (but concerning for production)

### Issue Description
Admin dashboard bypasses real API and uses hardcoded mock statistics.

### Frontend Implementation
**File:** `frontend-hormonia/src/components/admin/AdminDashboard.tsx` (line 62-85, 144)
```typescript
// Hardcoded mock data
const mockDashboardStats: AdminDashboardStats = {
  users: {
    total: 1247,
    active: 892,
    locked: 15,
    new_today: 23
  },
  security: {
    failed_logins: 47,
    active_sessions: 156,
    blocked_ips: 8
  },
  // ... more mock data
}

// State initialized with mock data (never updated from API)
const [dashboardStats, setDashboardStats] = useState<AdminDashboardStats>(mockDashboardStats)
```

### Impact
- ⚠️ Admin sees fake data (always shows 1247 users, 892 active, etc.)
- ⚠️ No real-time monitoring capability
- ⚠️ Security metrics inaccurate
- ✅ UI rendering works (but with fake data)

### Root Cause
Admin dashboard implemented before backend statistics endpoint. TODO comment at line 159 confirms this.

### Recommended Fix
**Backend Endpoint Needed:**
```python
# In app/api/v1/admin/system_stats.py (already exists but incomplete)
@router.get("/stats/dashboard")
async def get_admin_dashboard_stats(...) -> AdminDashboardStats:
    return AdminDashboardStats(
        users=UserStats(
            total=db.query(User).count(),
            active=db.query(User).filter(User.is_active == True).count(),
            locked=db.query(User).filter(User.locked_until > datetime.utcnow()).count(),
            new_today=db.query(User).filter(User.created_at >= today).count()
        ),
        security=SecurityStats(
            failed_logins=...,  # Query audit_events
            active_sessions=..., # Query sessions table
            blocked_ips=...     # Query rate_limit_events
        ),
        # ... etc
    )
```

**Frontend Hook Update:**
```typescript
// Replace mock data with real API call
const { data: stats } = useQuery({
  queryKey: ['admin-dashboard-stats'],
  queryFn: () => apiClient.get('/api/v1/admin/stats/dashboard'),
  refetchInterval: 30000 // Refresh every 30 seconds
})
```

---

## Summary Matrix

| # | Issue | Severity | Frontend File | Backend File | Impact |
|---|-------|----------|---------------|--------------|--------|
| 1 | Users list response mismatch | 🔴 CRITICAL | `useUserAdmin.ts:71` | `users.py:200` | No users displayed |
| 2 | Missing activity route | 🔴 CRITICAL | `api-client.ts:865` | `users.py` (missing) | 404 errors |
| 3 | Notifications schema mismatch | 🟠 HIGH | `NotificationCenter.tsx:40` | `auth.py:409` | Empty notifications |
| 4 | Dashboard trend data missing | 🟡 MEDIUM | `DashboardPage.tsx:98` | `analytics.py:172` | No trend indicators |
| 5 | Admin dashboard mock data | 🟢 LOW | `AdminDashboard.tsx:144` | (not implemented) | Fake statistics |

---

## Recommended Prioritization

### Phase 1 (Immediate - Production Blocking)
1. Fix **Issue #1** (Users list) - Backend schema change
2. Implement **Issue #2** (Activity route) - New endpoint
3. Fix **Issue #3** (Notifications) - Backend schema change

### Phase 2 (Near-term - UX Enhancement)
4. Implement **Issue #4** (Dashboard trends) - Analytics logic

### Phase 3 (Future - Feature Completion)
5. Replace **Issue #5** (Admin mock data) - Real statistics endpoint

---

## Coordination Metadata

**Hive Mind Session:** `hive/api/analysis`
**Task ID:** `api-analysis`
**Analysis Complete:** ✅
**Next Action:** Share with coder agents for implementation

