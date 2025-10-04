# WebSocket Client Consolidation Plan

## Executive Summary

Two WebSocket client implementations exist with near-identical functionality. This document outlines a safe migration strategy to consolidate to a single, canonical implementation.

## Current State Analysis

### File Locations
1. **Primary (Recommended)**: `frontend-hormonia/src/lib/websocket.ts` (362 lines)
2. **Duplicate (Legacy)**: `frontend-hormonia/lib/websocket.ts` (324 lines)

### Feature Comparison

| Feature | src/lib/websocket.ts | lib/websocket.ts | Status |
|---------|---------------------|------------------|---------|
| **Configuration** | ✅ Runtime config resolution + fallback | ❌ Static env var only | Primary superior |
| **Type Safety** | ✅ `data: any` | ✅ `data: unknown` | Legacy superior |
| **Null Handling** | ✅ Graceful WS_BASE_URL null handling | ❌ No null handling | Primary superior |
| **Dev-only Logging** | ✅ `import.meta.env.DEV` guards | ❌ Always logs | Primary superior |
| **Type Guards** | ❌ None | ✅ `isObject()` checks | Legacy superior |
| **Token Validation** | ❌ None | ✅ `token.trim() !== ''` | Legacy superior |
| **Runtime Config** | ✅ `getRuntimeConfigSync()` | ❌ None | Primary superior |
| **Production Safety** | ✅ Disables WS gracefully | ❌ May throw errors | Primary superior |

### Key Differences

#### 1. Configuration Resolution (Primary Advantage)
**src/lib/websocket.ts** (Lines 4-24):
```typescript
function resolveWsBaseUrl(): string | null {
  const envUrl = (import.meta.env as any).VITE_WS_BASE_URL
  if (envUrl && envUrl.length) return envUrl

  const runtime = getRuntimeConfigSync()
  if (runtime?.VITE_WS_BASE_URL) return runtime.VITE_WS_BASE_URL

  // Fallback to proxy
  if (typeof window !== 'undefined') {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    return `${proto}://${window.location.host}/ws`
  }
  return null
}
```

**lib/websocket.ts** (Line 4):
```typescript
const WS_BASE_URL = import.meta.env['VITE_WS_URL'] || 'ws://localhost:8000/ws'
```

#### 2. Type Safety (Legacy Advantage)
**lib/websocket.ts**:
- Uses `unknown` for data types (stricter)
- Imports `isObject()` type guard (line 2)
- Validates object types before spread (lines 120, 126)

**src/lib/websocket.ts**:
- Uses `any` for data types (permissive)
- No type guards
- Direct spread operations (lines 154, 159)

#### 3. Production Safety
**src/lib/websocket.ts** (Lines 21-24, 65-73):
- Gracefully disables WebSocket if URL missing
- Logs warning instead of throwing
- Skips connection attempt if URL null

**lib/websocket.ts**:
- No null URL handling
- Will attempt connection with hardcoded fallback

## Component Dependencies

### Direct Imports from `lib/websocket` (LEGACY)

1. **hooks/auth/useApiAuth.ts** (line 3)
   ```typescript
   import { wsManager } from '../../lib/websocket'
   ```
   - Status: External to tsconfig include paths
   - Risk: Low (hook is outside src/)

2. **src/contexts/AuthContext.tsx** (line 8)
   ```typescript
   import { wsManager } from '../lib/websocket'
   ```
   - Status: CRITICAL - Core authentication context
   - Risk: HIGH - Used app-wide

3. **src/hooks/auth/useApiAuth.ts** (line 3)
   ```typescript
   import { wsManager } from '../../lib/websocket'
   ```
   - Status: Duplicate hook in src/
   - Risk: MEDIUM - Authentication hook

4. **tests/integration/websocket.test.ts** (line 2)
   ```typescript
   import { wsManager } from '../../lib/websocket'
   ```
   - Status: Test file
   - Risk: LOW - Can be updated with tests

### Type Imports (Indirect)

Multiple files import WebSocket types through re-export chains:
- `types/index.ts` → `types/websocket.ts`
- `lib/types/websocket.ts` → Already deprecated, forwards to `types/websocket.ts`
- `src/lib/types/api.ts` → Re-exports from `types/websocket.ts`

## Migration Strategy

### Phase 1: Enhance Primary Implementation ⚠️

**Goal**: Add type safety from legacy to primary

**Actions**:
1. Add `isObject()` type guard utility to `src/lib/utils/type-guards.ts`
2. Update `handleMessage()` to use type guards (lines 154, 159)
3. Change `data: any` → `data: unknown` in WebSocketMessage interface
4. Add token validation in `updateToken()` method

**Risk**: LOW - Additive changes only

### Phase 2: Add Deprecation Warnings 📢

**Goal**: Warn developers using legacy client

**Actions**:
1. Add console warning to `lib/websocket.ts`:
   ```typescript
   console.warn(
     '[DEPRECATED] lib/websocket.ts is deprecated. ' +
     'Import from src/lib/websocket.ts instead. ' +
     'This file will be removed in a future version.'
   )
   ```

**Risk**: NONE - Warning only

### Phase 3: Update Imports 🔄

**Goal**: Migrate all components to primary client

**Priority Order**:
1. ✅ Tests (lowest risk)
2. ✅ Hooks outside src/
3. ✅ src/hooks/auth/useApiAuth.ts
4. ⚠️ src/contexts/AuthContext.tsx (LAST - highest risk)

**Import Path Updates**:
```typescript
// OLD (absolute)
import { wsManager } from '../../lib/websocket'
import { wsManager } from '../lib/websocket'

// NEW (alias)
import { wsManager } from '@/lib/websocket'
```

**Files to Update**:
1. `tests/integration/websocket.test.ts`
   - Old: `../../lib/websocket`
   - New: `@/lib/websocket`

2. `src/hooks/auth/useApiAuth.ts`
   - Old: `../../lib/websocket`
   - New: `@/lib/websocket`

3. `src/contexts/AuthContext.tsx`
   - Old: `../lib/websocket`
   - New: `@/lib/websocket`

4. `hooks/auth/useApiAuth.ts` (external)
   - Old: `../../lib/websocket`
   - New: `../../src/lib/websocket`

**Risk**: MEDIUM - Verify no breakage after each file

### Phase 4: Verification Testing 🧪

**Goal**: Ensure no regressions

**Test Checklist**:
- [ ] WebSocket connection establishment
- [ ] Authentication flow with WS token
- [ ] Patient room subscriptions
- [ ] Quiz event subscriptions
- [ ] Flow event subscriptions
- [ ] Reconnection logic
- [ ] Graceful disconnection
- [ ] Token updates
- [ ] Error handling
- [ ] TypeScript compilation

**Commands**:
```bash
# Type checking
npm run typecheck

# Run WebSocket tests
npm test tests/integration/websocket.test.ts

# Full test suite
npm test

# Build verification
npm run build
```

**Risk**: NONE - Validation only

### Phase 5: Remove Legacy Client 🗑️

**Goal**: Delete duplicate implementation

**Actions**:
1. Delete `frontend-hormonia/lib/websocket.ts`
2. Update git history documentation
3. Add migration notes to changelog

**Risk**: NONE - Only after all imports migrated

## Rollback Plan

If issues arise during migration:

### Immediate Rollback
```bash
# Revert specific file
git checkout HEAD -- src/contexts/AuthContext.tsx

# Revert all changes
git reset --hard HEAD
```

### Partial Rollback
Keep enhanced primary client, revert imports:
```bash
git checkout HEAD -- src/contexts/AuthContext.tsx
git checkout HEAD -- src/hooks/auth/useApiAuth.ts
```

### Type-Only Rollback
If type changes cause issues:
```typescript
// Temporarily use 'any' instead of 'unknown'
export interface WebSocketMessage {
  event: string
  data: any  // Revert from 'unknown'
  timestamp?: string
  patient_id?: string
  session_id?: string
}
```

## Timeline Estimate

| Phase | Estimated Time | Risk Level |
|-------|---------------|------------|
| Phase 1: Enhancement | 30 minutes | LOW |
| Phase 2: Deprecation | 5 minutes | NONE |
| Phase 3: Migration | 20 minutes | MEDIUM |
| Phase 4: Testing | 45 minutes | NONE |
| Phase 5: Cleanup | 10 minutes | NONE |
| **Total** | **1.8 hours** | **LOW-MEDIUM** |

## Success Criteria

- [ ] All imports use `src/lib/websocket.ts`
- [ ] No TypeScript errors
- [ ] All tests pass
- [ ] WebSocket functionality verified in dev environment
- [ ] No console warnings from deprecated client
- [ ] `lib/websocket.ts` deleted
- [ ] Documentation updated

## Post-Migration Checklist

- [ ] Update import documentation
- [ ] Add migration notes to CHANGELOG
- [ ] Update developer onboarding docs
- [ ] Create PR with detailed description
- [ ] Request code review from team
- [ ] Monitor production logs after deployment
- [ ] Update CI/CD if needed

## Recommended Execution Order

```bash
# 1. Create feature branch
git checkout -b ws-client-consolidation

# 2. Run Phase 1 (Enhancement)
# Add type guards and improve type safety

# 3. Run Phase 2 (Deprecation)
# Add warnings to legacy client

# 4. Run Phase 3 (Migration)
# Update imports one file at a time

# 5. Run Phase 4 (Testing)
npm run typecheck && npm test

# 6. Run Phase 5 (Cleanup)
# Delete legacy file

# 7. Commit and create PR
git add .
git commit -m "feat(websocket): consolidate duplicate WebSocket clients"
git push origin ws-client-consolidation
```

## Additional Notes

### Why src/lib/websocket.ts is Primary

1. **Location**: Inside `src/` (tsconfig includes this)
2. **Runtime Config**: Supports Railway deployment variables
3. **Fallback Logic**: Graceful degradation if WS unavailable
4. **Production Ready**: Non-fatal error handling
5. **Environment Aware**: Dev-only logging

### Why Not Merge Both?

We're enhancing the primary with type safety from legacy rather than merging because:
- Primary has better architecture (runtime config)
- Primary is in correct location (src/lib/)
- Legacy has simple fixes to port (type guards)
- Merging creates confusion about "source of truth"

### Type Guard Utility Location

Create at `src/lib/utils/type-guards.ts`:
```typescript
export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
```

## Coordination Hooks

```bash
# Before starting
npx claude-flow@alpha hooks pre-task --description "ws-client-consolidation"

# After each phase
npx claude-flow@alpha hooks post-edit --file "websocket.ts" --memory-key "swarm/frontend/ws-phase-N"

# After completion
npx claude-flow@alpha hooks post-task --task-id "ws-consolidation"
npx claude-flow@alpha hooks session-end --export-metrics true
```

## Questions for Review

1. Should we maintain backward compatibility with `lib/websocket.ts` exports?
2. Is there a deployment timeline that affects this migration?
3. Are there other teams/services importing from `lib/websocket.ts`?
4. Should we create a codemod script for automatic migration?

---

**Document Version**: 1.0
**Created**: 2025-10-03
**Author**: Code Quality Analyzer Agent
**Status**: Ready for Review
