# Medico Dashboard Statistics Audit Report

**Generated:** 2025-10-06
**Component:** `frontend-hormonia/src/pages/medico/MedicoDashboard.tsx`
**Issue:** Statistics displaying zero values
**Priority:** HIGH

---

## Executive Summary

The Medico Dashboard component displays four key statistics (Pacientes Ativos, Consultas Hoje, Pendências, Exames Aguardando) that are **hardcoded to zero** with no API integration. This audit provides root cause analysis, data flow documentation, and a comprehensive migration plan.

---

## 1. Root Cause Analysis

### Current Implementation (Lines 93-113)

```tsx
{/* Quick Stats */}
<div className="mt-8 bg-white rounded-lg shadow-md p-6">
  <h2 className="text-xl font-semibold text-gray-900 mb-4">Estatísticas Rápidas</h2>
  <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
    <div className="text-center">
      <p className="text-3xl font-bold text-blue-600">0</p>
      <p className="text-sm text-gray-600">Pacientes Ativos</p>
    </div>
    <div className="text-center">
      <p className="text-3xl font-bold text-green-600">0</p>
      <p className="text-sm text-gray-600">Consultas Hoje</p>
    </div>
    <div className="text-center">
      <p className="text-3xl font-bold text-purple-600">0</p>
      <p className="text-sm text-gray-600">Pendências</p>
    </div>
    <div className="text-center">
      <p className="text-3xl font-bold text-orange-600">0</p>
      <p className="text-sm text-gray-600">Exames Aguardando</p>
    </div>
  </div>
</div>
```

### Root Cause Summary

| Issue | Details |
|-------|---------|
| **Type** | Hardcoded values |
| **Location** | Lines 97, 101, 105, 109 |
| **API Call** | None - no data fetching implemented |
| **State Management** | No state variables for statistics |
| **Error Handling** | Not applicable (no API calls) |

### Why Statistics Show Zero

1. **No API Integration**: Values are literally hardcoded as `0` in JSX
2. **No State Variables**: No React state to store fetched statistics
3. **No useEffect Hook**: No lifecycle method to trigger data fetching
4. **No Error Handling**: No try/catch blocks (because there's no API call to fail)
5. **No Loading States**: Component doesn't check if data is being loaded

---

## 2. Current vs. Expected Data Flow

### Current Data Flow (Broken)

```
┌─────────────────────────────────────────┐
│  MedicoDashboard Component Render       │
├─────────────────────────────────────────┤
│                                         │
│  ┌──────────────────────────────┐      │
│  │   Hardcoded Statistics       │      │
│  │   - Pacientes Ativos: 0      │      │
│  │   - Consultas Hoje: 0        │      │
│  │   - Pendências: 0            │      │
│  │   - Exames Aguardando: 0     │      │
│  └──────────────────────────────┘      │
│                                         │
│  No API calls                           │
│  No state management                    │
│  No data fetching                       │
└─────────────────────────────────────────┘
```

### Expected Data Flow (To Be Implemented)

```
┌─────────────────────────────────────────────────────────────────┐
│  MedicoDashboard Component Lifecycle                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Component Mount                                             │
│     └─> useEffect() triggers                                    │
│                                                                 │
│  2. API Call                                                    │
│     └─> GET /api/v1/medico/dashboard-stats                      │
│         ├─> Headers: Authorization: Bearer {firebase_token}     │
│         └─> Response: {                                         │
│               pacientes_ativos: number                          │
│               consultas_hoje: number                            │
│               pendencias: number                                │
│               exames_aguardando: number                         │
│             }                                                   │
│                                                                 │
│  3. State Update                                                │
│     └─> setStats(response.data)                                 │
│                                                                 │
│  4. Re-render                                                   │
│     └─> Display actual statistics from API                      │
│                                                                 │
│  5. Error Handling                                              │
│     └─> If API fails, show error message or fallback to zeros   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Backend Endpoint Requirements

### Required Endpoint: `GET /api/v1/medico/dashboard-stats`

**Purpose:** Fetch dashboard statistics specific to the authenticated medico (doctor)

**Authentication:** Firebase JWT token required in Authorization header

**Response Schema:**

```typescript
interface MedicoDashboardStats {
  pacientes_ativos: number;      // Active patients assigned to this medico
  consultas_hoje: number;         // Scheduled consultations for today
  pendencias: number;             // Pending tasks/actions
  exames_aguardando: number;      // Exams awaiting review/results
  timestamp: string;              // ISO timestamp of data generation
}
```

**Example Response:**

```json
{
  "pacientes_ativos": 42,
  "consultas_hoje": 5,
  "pendencias": 12,
  "exames_aguardando": 8,
  "timestamp": "2025-10-06T14:30:00Z"
}
```

### Backend Implementation Location

**File:** `backend-hormonia/app/api/v1/medico.py` (to be created)

**SQL Queries Required:**

```sql
-- Pacientes Ativos
SELECT COUNT(DISTINCT p.id)
FROM patients p
WHERE p.is_active = true
  AND EXISTS (
    SELECT 1 FROM patient_flows pf
    WHERE pf.patient_id = p.id
      AND pf.medico_id = :current_medico_id
  );

-- Consultas Hoje
SELECT COUNT(*)
FROM appointments a
WHERE a.medico_id = :current_medico_id
  AND DATE(a.scheduled_at) = CURRENT_DATE
  AND a.status != 'cancelled';

-- Pendências
SELECT COUNT(*)
FROM tasks t
WHERE t.medico_id = :current_medico_id
  AND t.status = 'pending'
  AND t.due_date <= CURRENT_DATE;

-- Exames Aguardando
SELECT COUNT(*)
FROM exam_results er
WHERE er.medico_id = :current_medico_id
  AND er.status = 'pending_review';
```

---

## 4. Frontend Migration Plan

### Phase 1: API Client Extension

**File:** `frontend-hormonia/src/lib/api-client.ts`

**Action:** Add medico namespace with dashboard stats method

```typescript
// Add to ApiClient class
medico = {
  dashboardStats: async () => {
    return this.request<MedicoDashboardStats>('/api/v1/medico/dashboard-stats');
  },

  // Future endpoints
  pacientes: async () => {
    return this.request<Paciente[]>('/api/v1/medico/pacientes');
  }
}
```

### Phase 2: Type Definitions

**File:** `frontend-hormonia/src/types/api-responses.ts`

**Action:** Add MedicoDashboardStats interface

```typescript
export interface MedicoDashboardStats {
  pacientes_ativos: number;
  consultas_hoje: number;
  pendencias: number;
  exames_aguardando: number;
  timestamp: string;
}
```

### Phase 3: Component Refactor

**File:** `frontend-hormonia/src/pages/medico/MedicoDashboard.tsx`

**Changes Required:**

1. **Add State Management**
   ```typescript
   const [stats, setStats] = useState<MedicoDashboardStats | null>(null);
   const [loading, setLoading] = useState(true);
   const [error, setError] = useState<string | null>(null);
   ```

2. **Add Data Fetching Hook**
   ```typescript
   useEffect(() => {
     const fetchDashboardStats = async () => {
       try {
         setLoading(true);
         const data = await apiClient.medico.dashboardStats();
         setStats(data);
       } catch (err) {
         logger.error('Failed to fetch dashboard stats', { error: err });
         setError(err instanceof Error ? err.message : 'Unknown error');
       } finally {
         setLoading(false);
       }
     };

     fetchDashboardStats();
   }, []);
   ```

3. **Update JSX Rendering**
   ```tsx
   {/* Quick Stats */}
   <div className="mt-8 bg-white rounded-lg shadow-md p-6">
     <h2 className="text-xl font-semibold text-gray-900 mb-4">Estatísticas Rápidas</h2>

     {loading ? (
       <div className="flex justify-center items-center py-12">
         <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
       </div>
     ) : error ? (
       <div className="bg-red-50 border border-red-200 rounded-lg p-4">
         <p className="text-red-800">Erro ao carregar estatísticas: {error}</p>
       </div>
     ) : (
       <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
         <div className="text-center">
           <p className="text-3xl font-bold text-blue-600">
             {stats?.pacientes_ativos ?? 0}
           </p>
           <p className="text-sm text-gray-600">Pacientes Ativos</p>
         </div>
         <div className="text-center">
           <p className="text-3xl font-bold text-green-600">
             {stats?.consultas_hoje ?? 0}
           </p>
           <p className="text-sm text-gray-600">Consultas Hoje</p>
         </div>
         <div className="text-center">
           <p className="text-3xl font-bold text-purple-600">
             {stats?.pendencias ?? 0}
           </p>
           <p className="text-sm text-gray-600">Pendências</p>
         </div>
         <div className="text-center">
           <p className="text-3xl font-bold text-orange-600">
             {stats?.exames_aguardando ?? 0}
           </p>
           <p className="text-sm text-gray-600">Exames Aguardando</p>
         </div>
       </div>
     )}
   </div>
   ```

### Phase 4: Testing

**Test Cases:**

1. **Successful Data Load**
   - Verify statistics display correctly
   - Check loading state appears during fetch
   - Confirm loading state disappears after fetch

2. **Error Handling**
   - Simulate 401 Unauthorized (expired token)
   - Simulate 500 Internal Server Error
   - Simulate network timeout
   - Verify error messages display correctly

3. **Empty Data**
   - Test with medico who has zero patients
   - Verify zeros display (not null/undefined)

4. **Authentication**
   - Verify Authorization header is sent
   - Test with invalid token
   - Test with missing token

---

## 5. Implementation Checklist

### Backend Tasks

- [ ] Create `backend-hormonia/app/api/v1/medico.py`
- [ ] Implement `GET /api/v1/medico/dashboard-stats` endpoint
- [ ] Add Firebase authentication dependency
- [ ] Write SQL queries for statistics
- [ ] Add endpoint to router registry
- [ ] Create Pydantic response models
- [ ] Add unit tests for endpoint
- [ ] Add integration tests with auth

### Frontend Tasks

- [ ] Add `MedicoDashboardStats` interface to types
- [ ] Extend `ApiClient` with `medico` namespace
- [ ] Add `dashboardStats()` method to API client
- [ ] Update `MedicoDashboard.tsx` with state management
- [ ] Add `useEffect` hook for data fetching
- [ ] Update JSX with conditional rendering
- [ ] Add loading spinner component
- [ ] Add error message display
- [ ] Test with live backend endpoint
- [ ] Add retry logic for failed requests

### Documentation

- [ ] Update API documentation with new endpoint
- [ ] Document authentication requirements
- [ ] Add endpoint to Swagger/OpenAPI spec
- [ ] Update frontend component documentation

---

## 6. Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Backend endpoint not implemented | HIGH | Coordinate with backend team before frontend changes |
| Authentication issues | MEDIUM | Test with valid Firebase tokens, handle 401 errors gracefully |
| Database query performance | MEDIUM | Add indexes on medico_id columns, use EXPLAIN ANALYZE |
| Missing data tables (appointments, tasks, exams) | HIGH | Verify database schema before implementation |
| State management race conditions | LOW | Use proper cleanup in useEffect |

---

## 7. Future Enhancements

1. **Real-time Updates**: WebSocket integration for live statistics
2. **Historical Trends**: Chart showing statistics over time
3. **Drill-down**: Click statistic to view detailed list
4. **Caching**: Cache dashboard stats for 5 minutes to reduce API calls
5. **Refresh Button**: Manual refresh trigger
6. **Auto-refresh**: Periodic background refresh every 30 seconds

---

## 8. Related Files

### Frontend Files
- `frontend-hormonia/src/pages/medico/MedicoDashboard.tsx` - Main component
- `frontend-hormonia/src/lib/api-client.ts` - API client
- `frontend-hormonia/src/types/api-responses.ts` - TypeScript types
- `frontend-hormonia/src/contexts/MedicoAuthContext.tsx` - Authentication

### Backend Files (Existing)
- `backend-hormonia/app/api/v1/dashboard.py` - Generic dashboard (reference)
- `backend-hormonia/app/api/v1/auth.py` - Authentication
- `backend-hormonia/app/dependencies.py` - Authentication dependencies

### Backend Files (To Create)
- `backend-hormonia/app/api/v1/medico.py` - Medico-specific endpoints
- `backend-hormonia/app/schemas/medico.py` - Pydantic models
- `backend-hormonia/tests/api/v1/test_medico.py` - Unit tests

---

## 9. Comparison with PacientesList.tsx

The `PacientesList.tsx` component (in the same directory) **already implements the correct pattern**:

**Good Example from PacientesList.tsx:**

```typescript
// Lines 27-30: useEffect hook with API call
useEffect(() => {
  fetchPacientes()
}, [])

// Lines 31-51: Async function with proper error handling
const fetchPacientes = async () => {
  try {
    setLoading(true)
    const params: { size?: number; search?: string } = { size: 50 }
    if (searchTerm) params.search = searchTerm
    const resp = await apiClient.patients.list(params as any)
    const mapped: Paciente[] = (resp.items || []).map((p: any) => ({
      id: p.id,
      nome: p.name,
      cpf: p.cpf || '',
      data_nascimento: p.birth_date || '',
      telefone: p.phone || '',
      email: p.email || ''
    }))
    setPacientes(mapped)
  } catch (err) {
    setError(err instanceof Error ? err.message : 'Erro desconhecido')
  } finally {
    setLoading(false)
  }
}
```

**Recommendation:** Use `PacientesList.tsx` as a template for implementing dashboard statistics fetching.

---

## 10. Conclusion

**Current State:**
Statistics are hardcoded to zero with no data fetching mechanism.

**Required Changes:**
- Backend: New endpoint `/api/v1/medico/dashboard-stats`
- Frontend: State management, API integration, error handling

**Estimated Effort:**
- Backend: 4-6 hours (endpoint + tests)
- Frontend: 2-3 hours (component refactor + testing)
- Total: 6-9 hours

**Priority:** HIGH - Affects core functionality and user trust

**Next Steps:**
1. Review this audit with backend team
2. Confirm database schema supports required queries
3. Implement backend endpoint first
4. Test backend endpoint with Postman/curl
5. Implement frontend changes
6. End-to-end testing

---

**Report Generated By:** Claude Code Quality Analyzer
**Date:** 2025-10-06
**Confidence:** High (100% - Root cause confirmed by code inspection)
