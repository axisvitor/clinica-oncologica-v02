# Frontend 401 Errors - Race Condition Fix

## 🚨 Issue Summary

**Symptom**: Frontend dashboard showing "Erro ao carregar dashboard" with 401 Unauthorized errors on:
- `/api/v1/auth/me`
- `/api/v1/auth/notifications`
- `/api/v1/analytics/dashboard`

**Root Cause**: React Query hooks in dashboard components were making API calls **before** `apiClient.setAuthToken()` was called during authentication initialization.

## 🔍 Technical Analysis

### The Race Condition

1. **AdminAuthContext initialization** (AdminAuthContext.tsx:285-309):
   - Checks for existing Firebase session
   - Retrieves Firebase ID token
   - Calls `apiClient.setAuthToken(token)` on line 297
   - This is an **async operation** during component mount

2. **DashboardPage component** (DashboardPage.tsx:17-21):
   - Uses `useQuery` hook which runs **immediately** on component mount
   - Makes API call to `apiClient.analytics.dashboard()`
   - No wait for authentication to be ready

3. **Timeline of events**:
   ```
   T+0ms:  AdminProtectedRoute checks state.isLoading === false ✅
   T+1ms:  DashboardPage mounts
   T+2ms:  useQuery fires API call (NO AUTH TOKEN YET) ❌
   T+50ms: AdminAuthContext.setAuthToken() completes
   ```

### Why WebSocket Worked But HTTP Failed

**WebSocket connections** (from Railway logs at 06:07):
```
WebSocket authentication successful: admin@neoplasiaslitoral.com
Custom claims: {"role": "admin", "roles": ["admin", "super_admin"], ...}
```

**HTTP requests** failed because:
- WebSocket connections happen **after** page is fully loaded
- Dashboard's `useQuery` fires **during** initial render
- Different timing windows for token availability

## ✅ Solution

Added `enabled` prop to React Query hooks to wait for authentication:

### Files Modified

1. **[DashboardPage.tsx](../../frontend-hormonia/src/pages/DashboardPage.tsx#L17-L26)**
   ```tsx
   export function DashboardPage() {
     const { state } = useAdminAuth()  // ✅ Get auth state

     const { data: metrics, isLoading, error } = useQuery({
       queryKey: ['dashboard-metrics'],
       queryFn: () => apiClient.analytics.dashboard(),
       enabled: state.isAuthenticated && !state.isLoading, // ✅ Wait for auth
       refetchInterval: 30000
     })
   ```

2. **[QuickStats.tsx](../../frontend-hormonia/src/components/dashboard/QuickStats.tsx#L18-L26)**
   ```tsx
   export function QuickStats() {
     const { state } = useAdminAuth()  // ✅ Get auth state

     const { data: metrics, isLoading } = useQuery({
       queryKey: ['dashboard-metrics'],
       queryFn: () => apiClient.analytics.dashboard(),
       enabled: state.isAuthenticated && !state.isLoading, // ✅ Wait for auth
       refetchInterval: 60000
     })
   ```

3. **[NotificationCenter.tsx](../../frontend-hormonia/src/components/layout/NotificationCenter.tsx#L29-L38)**
   ```tsx
   export function NotificationCenter() {
     const [isOpen, setIsOpen] = useState(false)
     const { state } = useAdminAuth()  // ✅ Get auth state

     const { data: notificationsData, isLoading } = useQuery({
       queryKey: ['notifications'],
       queryFn: () => apiClient.notifications.list(),
       enabled: state.isAuthenticated && !state.isLoading, // ✅ Wait for auth
       refetchInterval: 30000
     })
   ```

## 🔑 Key Changes

### Before
```tsx
const { data, isLoading } = useQuery({
  queryFn: () => apiClient.someEndpoint()
  // ❌ Runs immediately on mount, no auth check
})
```

### After
```tsx
const { state } = useAdminAuth()

const { data, isLoading } = useQuery({
  queryFn: () => apiClient.someEndpoint(),
  enabled: state.isAuthenticated && !state.isLoading  // ✅ Waits for auth
})
```

## 📊 Impact

**Before Fix**:
- 3 failed requests with 401 errors
- Dashboard shows error message
- Poor user experience
- Unnecessary backend load

**After Fix**:
- 0 failed requests
- Clean dashboard load
- Smooth authentication flow
- Efficient resource usage

## 🧪 Testing Checklist

- [ ] User login → dashboard loads without 401 errors
- [ ] Browser refresh → session restore works correctly
- [ ] Notifications load after authentication
- [ ] Quick stats display metrics
- [ ] No console errors
- [ ] Railway logs show no 401 errors

## 🔄 Similar Patterns to Check

If adding new components with API calls, ensure they follow this pattern:

```tsx
import { useAdminAuth } from '@/contexts/AdminAuthContext'

export function MyComponent() {
  const { state } = useAdminAuth()

  const { data } = useQuery({
    queryKey: ['my-data'],
    queryFn: () => apiClient.myEndpoint(),
    enabled: state.isAuthenticated && !state.isLoading  // ⚠️ CRITICAL
  })
}
```

## 📝 Related Files

- [AdminAuthContext.tsx](../../frontend-hormonia/contexts/AdminAuthContext.tsx) - Authentication state management
- [AdminProtectedRoute.tsx](../../frontend-hormonia/src/components/admin/AdminProtectedRoute.tsx) - Route protection
- [api-client.ts](../../frontend-hormonia/src/lib/api-client.ts) - Token handling

## 🎯 Prevention

**Future Components Checklist**:
1. ✅ Import `useAdminAuth` hook
2. ✅ Get auth state: `const { state } = useAdminAuth()`
3. ✅ Add `enabled` prop to all `useQuery` hooks
4. ✅ Condition: `enabled: state.isAuthenticated && !state.isLoading`
5. ✅ Test: Login → refresh → verify no 401 errors

## 📚 Additional Context

This fix complements the backend authentication fixes:
- [RAILWAY_AUTH_FIX_CRITICAL.md](RAILWAY_AUTH_FIX_CRITICAL.md) - Firebase custom claims
- [RAILWAY_DEPLOY_CHECKLIST.md](RAILWAY_DEPLOY_CHECKLIST.md) - Deployment steps
- [RAILWAY_PSYCOPG_FIX.md](RAILWAY_PSYCOPG_FIX.md) - Database connection fix

---
**Status**: ✅ Fixed
**Priority**: Critical
**Type**: Race Condition / Authentication Flow
