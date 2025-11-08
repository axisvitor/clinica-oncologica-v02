# Frontend V2 Migration - Action Items

## Quick Stats
- **Overall Completion**: 87%
- **Critical Issues**: 5 (must fix)
- **High Priority Issues**: 6 (should fix)
- **Estimated Fix Time**: 3-8 hours

---

## PRIORITY 1: CRITICAL (Fix Before Release)

### 1. Fix Test File V1 References ⚠️ CRITICAL
**File**: `src/hooks/api/__tests__/usePhysicianRiskAssessments.test.ts`
**Lines**: 67, 97, 177, 180
**Time**: 5 min

```typescript
// WRONG (current):
expect(apiClient.request).toHaveBeenCalledWith(
  '/api/v1/physician/risk-assessments'
)

// RIGHT (should be):
expect(apiClient.request).toHaveBeenCalledWith(
  '/api/v2/physician/risk-assessments'
)
```

**Status**: Tests will fail if not fixed

---

### 2. Consolidate Direct Fetch Calls
**Files**:
- `src/pages/MetricsDashboardPage.tsx:57`
- `src/pages/AdminPage.tsx:118`
- `src/pages/ReportsPage.tsx:64`

**Time**: 30 min

Instead of:
```typescript
const response = await fetch(`${apiClient.getBaseURL()}/api/v2/metrics/export`, ...)
```

Use:
```typescript
// Create proper apiClient methods or use request()
const response = await apiClient.request('/api/v2/metrics/export', options)
```

---

### 3. Remove Duplicate Hooks
**Files**:
- `src/hooks/useSystemStats.ts` (same as)
- `src/hooks/api/useSystemStats.ts`

**Time**: 15 min

**Action**: Consolidate into one, use barrel export from index

---

### 4. Fix TypeScript Errors
**File**: `src/lib/api-client-wrapper.ts`
**Issue**: `@ts-nocheck` header (type checking disabled for entire file)

**Time**: 1 hour

**Action**: Remove `@ts-nocheck` and fix actual type errors

---

## PRIORITY 2: HIGH (Next Sprint)

### 5. Fix Type Safety Issues (956 instances)
**Estimated Time**: 2-3 hours

**Key Issues**:
- 234+ overuse of `any` type
- 189+ overuse of `unknown` type
- 42+ `@ts-ignore` directives
- Field name mismatches (data vs items)

**Action Plan**:
1. Review `api-responses.ts` vs `api-wave2.ts` for consistency
2. Replace generic `any` with specific types
3. Update response field mappings

---

### 6. Remove Duplicate Components
**Files**:
- `src/components/dashboard/AlertsPanel.tsx`
- `src/components/metrics/AlertsPanel.tsx`

**Time**: 30 min

**Action**: Review for differences, keep DRY principle

---

### 7. Update Documentation Comments
**Files**:
- `src/components/admin/RoleAssignmentModal.tsx:412`
- `src/services/whatsapp/WhatsAppService.ts:87`

**Time**: 10 min

**Action**: Update v1 backend references to v2

---

## PRIORITY 3: MEDIUM (Nice to Have)

### 8. Server-Side Filtering Migration
**Files**:
- `src/hooks/api/useQuestionarios.ts` (lines 64-65)
- `src/hooks/usePatients.ts` (lines 63-70)

**Status**: Already documented and prepared for backend support

---

### 9. WebSocket Implementation
**File**: `src/hooks/useUserAdmin.ts:36`
**Issue**: Missing `/ws/admin/users` endpoint
**Status**: Blocked on backend implementation

---

### 10. Enhance Test Coverage
**Current**: 11 test files
**Target**: 25+ test files

**Priority Files**:
- API client modules
- AuthContext provider
- Query hooks

**Time**: 3-4 hours

---

## PRIORITY 4: LOW (Documentation)

### 11. API Client Documentation
- Endpoint mappings
- Error handling patterns
- Migration guide

---

### 12. Dashboard Consolidation Review
12 dashboard implementations exist. Document why each is needed.

---

### 13. Config Cleanup
Remove legacy v1 references from comments

---

## Verification Checklist

After fixing Priority 1 items:

- [ ] Run test suite: `npm test`
- [ ] Type check: `npm run typecheck`
- [ ] Lint: `npm run lint`
- [ ] Verify no /api/v1/ references in src code
- [ ] All fetch() calls use apiClient or proper abstraction
- [ ] No @ts-nocheck directives in critical files
- [ ] Build succeeds: `npm run build`

---

## File-by-File Fixes

### usePhysicianRiskAssessments.test.ts
Lines to fix: 67, 97, 177, 180
- Replace `/api/v1/` with `/api/v2/`

### MetricsDashboardPage.tsx (Line 57)
```typescript
// BEFORE
const response = await fetch('/api/v2/metrics/export', {

// AFTER
const response = await apiClient.request('/api/v2/metrics/export', {
```

### AdminPage.tsx (Line 118)
```typescript
// BEFORE
const response = await fetch(url, {

// AFTER
const response = await apiClient.request('/api/v2/admin/settings', {
```

### ReportsPage.tsx (Line 64)
Use existing: `apiClient.reports.download(id)`

### useSystemStats.ts Consolidation
Keep: `src/hooks/api/useSystemStats.ts`
Delete: `src/hooks/useSystemStats.ts`
Update imports throughout codebase

---

## Branch Strategy

1. Create feature branch: `frontend/fix-v2-migration-issues`
2. Complete Priority 1 fixes
3. Run full test suite
4. Create PR with migration report
5. Schedule Priority 2 fixes for next sprint

---

## Questions?

See main report: `../FRONTEND_V2_MIGRATION_ANALYSIS.md`
