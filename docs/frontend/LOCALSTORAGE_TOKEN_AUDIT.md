# LocalStorage Token Access Audit Report

**Generated:** 2025-10-06
**Scope:** frontend-hormonia/src/pages directory
**Purpose:** Identify direct localStorage token access and manual Authorization header construction

---

## Executive Summary

### Total Violations Found: **3 instances**

All violations are in the **AdminPage.tsx** file, which uses direct localStorage access for authentication tokens instead of the centralized `apiClient` from `@/lib/api-client`.

### Risk Level: **MEDIUM**

While the number of violations is low, the pattern could lead to:
- Inconsistent authentication across the application
- Bypassing centralized token management
- Potential security issues if tokens are not properly handled
- Code duplication and maintenance burden

---

## Detailed Findings

### 1. AdminPage.tsx - Line 61

**File:** `C:\Meu Projetos\clinica-oncologica-v02\frontend-hormonia\src\pages\AdminPage.tsx`
**Line:** 61
**Function:** `handleBackup()`

#### Current Code:
```typescript
const response = await fetch('/api/v1/admin/backup', {
  method: 'POST',
  headers: {
    ['Authorization']: `Bearer ${localStorage.getItem('token')}`
  }
})
```

#### Issue:
- Direct `localStorage.getItem('token')` access
- Manual Authorization header construction
- Uses native `fetch()` instead of `apiClient`

#### Recommended Fix:
```typescript
const response = await apiClient.request<Blob>('/api/v1/admin/backup', {
  method: 'POST'
})

// For blob download handling:
const blob = await response
const url = window.URL.createObjectURL(blob)
const a = document.createElement('a')
a.href = url
a.download = `backup-${new Date().toISOString()}.zip`
a.click()
```

---

### 2. AdminPage.tsx - Line 89

**File:** `C:\Meu Projetos\clinica-oncologica-v02\frontend-hormonia\src\pages\AdminPage.tsx`
**Line:** 89
**Function:** `handleClearCache()`

#### Current Code:
```typescript
const response = await fetch('/api/v1/admin/cache/clear', {
  method: 'POST',
  headers: {
    ['Authorization']: `Bearer ${localStorage.getItem('token')}`
  }
})
```

#### Issue:
- Direct `localStorage.getItem('token')` access
- Manual Authorization header construction
- Uses native `fetch()` instead of `apiClient`

#### Recommended Fix:
```typescript
await apiClient.post<void>('/api/v1/admin/cache/clear')
```

---

### 3. AdminPage.tsx - Line 112

**File:** `C:\Meu Projetos\clinica-oncologica-v02\frontend-hormonia\src\pages\AdminPage.tsx`
**Line:** 112
**Function:** `handleSaveSettings()`

#### Current Code:
```typescript
const response = await fetch('/api/v1/admin/settings', {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
    ['Authorization']: `Bearer ${localStorage.getItem('token')}`
  },
  body: JSON.stringify({
    ai_enabled: aiEnabled,
    auto_reply: autoReply,
    maintenance_mode: maintenanceMode,
    debug_mode: debugMode
  })
})
```

#### Issue:
- Direct `localStorage.getItem('token')` access
- Manual Authorization header construction
- Manual Content-Type header (apiClient handles this)
- Uses native `fetch()` instead of `apiClient`

#### Recommended Fix:
```typescript
await apiClient.put<void>('/api/v1/admin/settings', {
  ai_enabled: aiEnabled,
  auto_reply: autoReply,
  maintenance_mode: maintenanceMode,
  debug_mode: debugMode
})
```

---

## Files Without Violations

The following files were audited and found to be **compliant** (using `apiClient` or no API calls):

### ✅ Clean Files:
- **AnalyticsPage.tsx** - Uses `apiClient.analytics.*` methods
- **FlowsPage.tsx** - Uses hooks that internally use `apiClient`
- **PatientsPage.tsx** - Uses hooks that internally use `apiClient`
- **QuizPage.tsx** - Uses `apiClient.quiz.*` and `apiClient.patients.*` methods
- **SettingsPage.tsx** - Uses hooks for API calls, no direct fetch
- **WhatsAppPage.tsx** - Component-based, no API calls in page
- **MessagesPage.tsx** - Uses `apiClient.messages.*` and `apiClient.patients.*` methods
- **PatientDetailPage.tsx** - Uses `apiClient` throughout
- **LoginPage.tsx** - Uses `useAuth()` context, no direct API calls
- **AlertsPage.tsx** - Uses `apiClient.alerts.*` methods
- **DashboardPage.tsx** - Uses `apiClient.analytics.*` methods
- **medico/MedicoLogin.tsx** - Uses `useMedicoAuth()` context
- **medico/MedicoDashboard.tsx** - Uses context for auth
- **medico/PacientesList.tsx** - Uses `apiClient.patients.*` methods

---

## Priority Ranking

### Priority 1: MEDIUM - AdminPage.tsx
**Frequency of Use:** Medium
**User Role:** Admin only
**Impact:** Medium

The Admin page is accessed by administrators for system management tasks. While not as frequently used as patient-facing pages, these operations should still use the centralized API client for consistency.

**Recommended Action:** Refactor all three violations in a single update.

---

## Migration Pattern

### Standard Pattern for Migration:

#### Before:
```typescript
const response = await fetch('/api/v1/endpoint', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${localStorage.getItem('token')}`
  },
  body: JSON.stringify(data)
})
```

#### After:
```typescript
const response = await apiClient.post('/api/v1/endpoint', data)
```

### ApiClient Methods Available:

```typescript
// GET requests
apiClient.get<T>(endpoint, options?)

// POST requests
apiClient.post<T>(endpoint, body?, options?)

// PUT requests
apiClient.put<T>(endpoint, body?, options?)

// DELETE requests
apiClient.delete<T>(endpoint, options?)

// Generic request
apiClient.request<T>(endpoint, options)
```

### ApiClient Benefits:

1. **Automatic Authorization** - Handles Bearer token automatically
2. **Centralized Token Management** - Single source of truth for auth state
3. **Retry Logic** - Built-in exponential backoff for failed requests
4. **Error Handling** - Consistent error types and messages
5. **Request Transformation** - Automatic JSON parsing and Content-Type headers
6. **Timeout Protection** - Prevents hanging requests
7. **Type Safety** - Full TypeScript support with generics

---

## Implementation Recommendations

### Step 1: Update AdminPage.tsx

Create a single PR that updates all three violations in AdminPage.tsx:

```typescript
// Add import if not present
import { apiClient } from '@/lib/api-client'

// Update handleBackup
const handleBackup = async () => {
  setIsLoading(true)
  try {
    // For blob responses, you may need special handling
    const url = `${apiClient.getBaseURL()}/api/v1/admin/backup`
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiClient['authToken']}` // Access through apiClient
      }
    })

    // Or better yet, add to apiClient.admin namespace
    const blob = await response.blob()
    const downloadUrl = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = downloadUrl
    a.download = `backup-${new Date().toISOString()}.zip`
    a.click()
    setMessage({ type: 'success', text: 'Backup realizado com sucesso!' })
  } catch (error) {
    setMessage({ type: 'error', text: 'Erro ao realizar backup' })
  } finally {
    setIsLoading(false)
  }
}

// Update handleClearCache
const handleClearCache = async () => {
  setIsLoading(true)
  try {
    await apiClient.post('/api/v1/admin/cache/clear')
    setMessage({ type: 'success', text: 'Cache limpo com sucesso!' })
  } catch (error) {
    setMessage({ type: 'error', text: 'Erro ao limpar cache' })
  } finally {
    setIsLoading(false)
  }
}

// Update handleSaveSettings
const handleSaveSettings = async () => {
  setIsLoading(true)
  try {
    await apiClient.put('/api/v1/admin/settings', {
      ai_enabled: aiEnabled,
      auto_reply: autoReply,
      maintenance_mode: maintenanceMode,
      debug_mode: debugMode
    })
    setMessage({ type: 'success', text: 'Configurações salvas com sucesso!' })
  } catch (error) {
    setMessage({ type: 'error', text: 'Erro ao salvar configurações' })
  } finally {
    setIsLoading(false)
  }
}
```

### Step 2: Optional - Add Admin Namespace to ApiClient

For better organization, consider adding an `admin` namespace to `apiClient`:

```typescript
// In api-client.ts
admin = {
  backup: async () => {
    // Special handling for blob response
    const url = `${this.baseURL}/api/v1/admin/backup`
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        ...(this.authToken ? { 'Authorization': `Bearer ${this.authToken}` } : {})
      }
    })

    if (!response.ok) {
      throw new ApiError(response.status, await response.json())
    }

    return await response.blob()
  },

  clearCache: () =>
    this.post<void>('/api/v1/admin/cache/clear'),

  updateSettings: (settings: {
    ai_enabled?: boolean
    auto_reply?: boolean
    maintenance_mode?: boolean
    debug_mode?: boolean
  }) =>
    this.put<void>('/api/v1/admin/settings', settings)
}
```

---

## Testing Checklist

After implementing fixes:

- [ ] Verify authentication still works for admin operations
- [ ] Test backup download functionality
- [ ] Test cache clearing
- [ ] Test settings update
- [ ] Verify error handling displays proper messages
- [ ] Test with expired tokens (should redirect to login)
- [ ] Test with network errors (should show appropriate error message)
- [ ] Verify loading states work correctly

---

## Related Files

### ApiClient Location:
`frontend-hormonia/src/lib/api-client.ts`

### Authentication Context:
- `frontend-hormonia/src/contexts/AuthContext.tsx` (main auth)
- `frontend-hormonia/src/contexts/AdminAuthContext.tsx` (admin-specific)
- `frontend-hormonia/src/contexts/MedicoAuthContext.tsx` (medico-specific)

---

## Conclusion

The audit found **3 violations** all concentrated in a single file (AdminPage.tsx). This is a positive finding as:

1. **Limited Scope** - Only one file needs updating
2. **Low Risk** - Admin-only functionality
3. **Easy Fix** - All violations follow the same pattern
4. **Good Architecture** - Rest of the application already uses apiClient correctly

### Recommendation:
Proceed with refactoring AdminPage.tsx to use apiClient for consistency and maintainability. Consider adding the admin namespace to apiClient for better code organization.

---

**Report End**
