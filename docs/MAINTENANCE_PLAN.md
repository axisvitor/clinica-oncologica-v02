# Frontend Maintenance Plan
**Status**: Low Priority - Post-Wave 3 Cleanup
**Last Updated**: 2025-10-06

## Overview

This document outlines remaining maintenance tasks after Wave 3 completion. All critical and high-priority issues have been resolved. These are cleanup items to improve code quality and developer experience.

---

## ✅ Completed (Wave 3 + Critical Fixes)

1. **WebSocket URL Construction** - Fixed relative path handling
2. **Role Normalization** - Case-insensitive role comparisons
3. **Admin Access Control** - Supports ADMIN/super_admin variants
4. **Vite Backend Alias** - Corrected path for Linux compatibility
5. **AdminAuthContext Location** - Moved to src/contexts for TypeScript compilation
6. **Sensitive Logging** - Removed console.log with tokens
7. **Alert Components** - Replaced browser alert() with React components
8. **Error Handling** - Added HTTP 503/timeout fallbacks
9. **Session Management** - Removed redundant useSessionManagement (Firebase handles it)

---

## 🔧 Remaining Maintenance Tasks

### 1. WebSocket Subscription Management

**Status**: Documentation Added
**Priority**: Low

**Current State**:
- `useWebSocket.ts` has automatic cleanup via useEffect return function (line 178-182)
- Cleanup is triggered when component unmounts or auth token changes
- **No code changes needed** - working as designed

**Consumer Responsibilities**:
- Components using `useWebSocket` should avoid storing subscriptions in state
- Let the hook manage connection lifecycle automatically
- Example pattern:
  ```typescript
  // ✅ Good - let hook manage lifecycle
  const { lastMessage } = useWebSocket({ url: '/clinical-metrics' })

  // ❌ Bad - manual subscription management
  const ws = useWebSocket()
  useEffect(() => {
    ws.subscribe('room1') // Don't do this
  }, [])
  ```

**Testing**:
- Add integration tests for WebSocket reconnection scenarios
- Mock WebSocket in Vitest to verify cleanup behavior
- File: `tests/hooks/useWebSocket.integration.test.ts` (to be created)

---

### 2. Hardcoded Data Placeholders

**Status**: Needs Implementation
**Priority**: Low
**Estimated Effort**: 2-4 hours

**Affected Files**:
1. `src/pages/AnalyticsPage.tsx:208-310`
   - "Pacientes ativos/pausados" cards with static numbers
   - Sentiment analysis data (mocked)

2. `src/pages/ClinicalMonitoringDashboard.tsx:269-333`
   - RadarChart engagement scores (hardcoded)
   - Alert distribution data (static)

**Proposed Solution**:
```typescript
// Add feature flags for data readiness
const FEATURE_FLAGS = {
  ANALYTICS_PATIENT_DATA: false,  // Set true when API ready
  CLINICAL_ENGAGEMENT_RADAR: false,
  ALERT_DISTRIBUTION: false
}

// Wrap sections with conditional rendering
{FEATURE_FLAGS.ANALYTICS_PATIENT_DATA ? (
  <RealDataComponent />
) : (
  <PlaceholderCard>
    <p>Dados em implementação - Disponível em breve</p>
  </PlaceholderCard>
)}
```

**Action Items**:
- [ ] Create `src/config/featureFlags.ts`
- [ ] Wrap hardcoded sections with feature flags
- [ ] Add placeholder UI components
- [ ] Document which endpoints need implementation

---

### 3. ESLint Configuration

**Status**: Broken (pre-existing)
**Priority**: Medium
**Estimated Effort**: 1-2 hours

**Current Error**:
```
TypeError: Key "rules": Key "@typescript-eslint/prefer-const":
Could not find "prefer-const"
```

**Root Cause**:
- Outdated ESLint config referencing removed rules
- Config file: `.eslintrc.js` or `eslint.config.js`

**Proposed Fix**:
1. Update ESLint plugins to latest versions:
   ```bash
   npm update @typescript-eslint/eslint-plugin @typescript-eslint/parser
   ```

2. Review and clean ESLint rules:
   - Remove deprecated rules
   - Use flat config format (ESLint 9+)
   - Align with current TypeScript version

3. Add to CI pipeline:
   ```json
   {
     "scripts": {
       "lint": "eslint src --ext .ts,.tsx --report-unused-disable-directives --max-warnings 0",
       "lint:fix": "npm run lint -- --fix",
       "quality": "npm run lint && npm run typecheck && npm run test"
     }
   }
   ```

**Action Items**:
- [ ] Identify ESLint config file location
- [ ] Update plugins and parser
- [ ] Test `npm run lint` passes
- [ ] Integrate into QA workflow

---

### 4. Test Coverage

**Status**: Partial Coverage
**Priority**: Medium
**Estimated Effort**: 4-6 hours

**Current Coverage**:
- ✅ LandingRoute.test.tsx (15 tests)
- ✅ useClinicalMetrics.test.ts (9 tests)
- ✅ useQuestionarios.test.ts (20+ tests)
- ❌ ClinicalMonitoringDashboard WebSocket integration
- ❌ PhysicianDashboard filters/pagination
- ❌ AdminPage role guards (case variations)

**Proposed Test Files**:

**A. WebSocket Integration Test**
```typescript
// tests/integration/ClinicalMonitoring.websocket.test.tsx
import { renderHook, waitFor } from '@testing-library/react'
import { MockWebSocket } from 'vitest-websocket-mock'
import { ClinicalMonitoringDashboard } from '@/pages/ClinicalMonitoringDashboard'

describe('ClinicalMonitoring WebSocket', () => {
  let mockWs: MockWebSocket

  beforeEach(() => {
    mockWs = new MockWebSocket('ws://localhost:8000/clinical-metrics')
  })

  it('invalidates queries on metrics_update event', async () => {
    // Test query invalidation
  })

  it('reconnects after network failure', async () => {
    // Test auto-reconnect
  })

  it('cleans up subscriptions on unmount', async () => {
    // Test cleanup
  })
})
```

**B. Role Guard Tests**
```typescript
// tests/unit/guards/AdminRoleGuard.test.tsx
describe('AdminPage Role Guards', () => {
  it.each([
    { role: 'admin', shouldAllow: true },
    { role: 'ADMIN', shouldAllow: true },
    { role: 'superadmin', shouldAllow: true },
    { role: 'super_admin', shouldAllow: true },
    { role: 'user', shouldAllow: false },
    { role: 'PHYSICIAN', shouldAllow: false }
  ])('role $role should be $shouldAllow', ({ role, shouldAllow }) => {
    // Test access control
  })
})
```

**C. Server-Side Filtering Tests**
```typescript
// tests/unit/QuestionariosPage.filters.test.tsx
describe('QuestionariosPage Server-Side Filtering', () => {
  it('constructs correct query params for search', async () => {
    // Verify API call has search param
  })

  it('resets page to 1 when filters change', async () => {
    // Test pagination reset
  })

  it('debounces search input', async () => {
    // Test search debounce
  })
})
```

**Action Items**:
- [ ] Install vitest-websocket-mock: `npm install -D vitest-websocket-mock`
- [ ] Create integration test directory: `tests/integration/`
- [ ] Write WebSocket integration tests
- [ ] Write role guard tests
- [ ] Write filter/pagination tests
- [ ] Update CI to run all tests

---

### 5. UTF-8 Encoding Issues

**Status**: Intermittent
**Priority**: Low
**Estimated Effort**: 1 hour

**Symptoms**:
- Windows terminal shows: `P�gina n�o`, `Sess�o expirada`
- Files appear correct in VS Code
- Issue occurs during git operations or build output

**Affected Files**:
- `src/pages/LoginPage.tsx` - String literals with accents
- `src/pages/AdminPage.tsx` - Error messages
- `docs/wave3/*.md` - Documentation

**Proposed Solution**:

1. **Re-save files with UTF-8 (no BOM)**:
   ```bash
   # VS Code: File > Save with Encoding > UTF-8
   ```

2. **Add .editorconfig**:
   ```ini
   # .editorconfig
   root = true

   [*]
   charset = utf-8
   end_of_line = lf
   insert_final_newline = true
   trim_trailing_whitespace = true

   [*.{ts,tsx,js,jsx}]
   indent_style = space
   indent_size = 2
   ```

3. **Git attributes** (ensure LF line endings):
   ```gitattributes
   # .gitattributes
   * text=auto eol=lf
   *.{ts,tsx,js,jsx,json,md} text eol=lf
   ```

**Action Items**:
- [ ] Create `.editorconfig`
- [ ] Create/update `.gitattributes`
- [ ] Re-save affected files
- [ ] Verify in Windows terminal: `git diff` shows no encoding issues

---

### 6. Directory Consolidation

**Status**: Planned
**Priority**: Low
**Estimated Effort**: 2-3 hours

**Current Issues**:
- Contexts split between `src/contexts/` and `contexts/` (✅ AdminAuthContext moved)
- Some hooks in `src/hooks/`, others in `hooks/`
- Import inconsistency: some use `@/contexts`, others use relative paths

**Proposed Structure**:
```
frontend-hormonia/
├── src/
│   ├── contexts/          # All contexts here
│   │   ├── AuthContext.tsx
│   │   ├── AdminAuthContext.tsx
│   │   └── ThemeContext.tsx
│   ├── hooks/             # All hooks here
│   │   ├── api/
│   │   ├── auth/
│   │   └── useWebSocket.ts
│   ├── components/
│   ├── pages/
│   └── lib/
├── tests/                 # Mirror src structure
└── public/
```

**Migration Steps**:
1. Move remaining files to `src/`
2. Update all imports to use `@/` alias
3. Remove empty directories
4. Update TypeScript paths in `tsconfig.json`
5. Verify build passes

**Action Items**:
- [ ] Audit remaining files outside `src/`
- [ ] Create migration script
- [ ] Execute migration
- [ ] Update imports
- [ ] Test build

---

## 📊 Priority Matrix

| Task | Impact | Effort | Priority | Timeline |
|------|--------|--------|----------|----------|
| ESLint Fix | Medium | Low | **High** | Next sprint |
| Test Coverage | High | Medium | **Medium** | 1-2 weeks |
| Placeholder Flags | Low | Low | Low | Backlog |
| UTF-8 Encoding | Low | Low | Low | Backlog |
| Directory Consolidation | Low | Medium | Low | Backlog |
| WebSocket Docs | Low | Low | ✅ Done | - |

---

## 🎯 Recommended Timeline

**Sprint 1 (This Week)**:
- Fix ESLint configuration
- Document WebSocket cleanup behavior (✅ Done)

**Sprint 2 (Next Week)**:
- Add WebSocket integration tests
- Add role guard tests
- Add filter/pagination tests

**Sprint 3 (Following Week)**:
- Implement feature flags for placeholders
- Fix UTF-8 encoding issues
- Create .editorconfig

**Backlog (Future)**:
- Directory consolidation
- Complete test coverage to 80%+
- Performance monitoring integration

---

## 📝 Testing Checklist

Before marking any task complete:

- [ ] `npm run lint` passes with zero errors
- [ ] `npm run typecheck` passes with zero errors
- [ ] `npm run test` passes with all tests
- [ ] `npm run build` completes successfully
- [ ] Manual testing in dev environment
- [ ] Manual testing in Railway staging (if applicable)
- [ ] Documentation updated
- [ ] Git commit with clear description

---

## 📚 References

- [Wave 3 Implementation Summary](./wave3/WAVE3_IMPLEMENTATION_SUMMARY.md)
- [Supabase Cleanup Report](./wave3/SUPABASE_CLEANUP_COMPLETE.md)
- [Performance Metrics](./performance/WAVE3_PERFORMANCE_METRICS.md)
- [Critical Fixes Commit](https://github.com/axisvitor/clinica-oncologica-v02/commit/a2785c2)

---

## 🤝 Contributing

When working on maintenance tasks:

1. Create feature branch: `git checkout -b maintenance/task-name`
2. Make changes following existing patterns
3. Run full test suite
4. Update this document with progress
5. Create PR with clear description
6. Request review from team

---

**Next Review Date**: After Sprint 2 completion
**Document Owner**: Development Team
**Last Contributor**: Claude Code Assistant
