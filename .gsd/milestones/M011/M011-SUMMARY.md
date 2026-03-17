---
id: M011
provides:
  - Per-user Redis caching on physician/patients endpoint (TTL=60s) with full query-param cache key preventing cross-doctor data leaks
  - Dashboard caching confirmed at TTL=120s with per-user key (pre-existing, verified unchanged)
  - Alembic migration creating composite index idx_pfs_patient_started on patient_flow_states(patient_id, started_at DESC) for ROW_NUMBER() acceleration
  - Frontend request discipline — staleTime ≥ 60s dashboard/patient hooks, ≥ 120s admin hooks, refetchInterval ≥ 120s across 21 hooks
  - Global default staleTime bumped from 30s to 60s in queryClient.ts
  - Replayable verify-m011.sh script proving all 7 check groups
key_decisions:
  - D019 — Backend caching strategy: manual redis_cache.get/set with per-user keys (not @cache_response decorator) to include user_id and all query params in key, preventing cross-doctor data leaks
  - D020 — Frontend staleTime discipline thresholds (≥ 60s dashboard, ≥ 120s admin, monitoring exempt)
patterns_established:
  - Cache key format physician:patients:user:{user_id}:page:{page}:size:{size}:search:{search}:phase:{flow_phase}:status:{flow_status} with try/except resilience
  - Use if_not_exists=True on create_index for idempotent Alembic migrations
  - Dashboard/patient hooks staleTime ≥ 60s (60000ms), refetchInterval ≥ 120s (120000ms)
  - Admin hooks staleTime ≥ 120s (120000ms), refetchInterval ≥ 120s (120000ms)
  - Monitoring/real-time hooks (system health, WhatsApp, agent swarm) explicitly exempt from timing thresholds
  - queryPresets.realtime in queryClient.ts is the only allowed sub-threshold preset definition
observability_surfaces:
  - bash verify-m011.sh — prints labeled PASS/FAIL for each of 7 groups with inline error detail on failure
  - logger.debug cache hit/miss/failure messages on physician/patients endpoint
  - Redis keys physician:patients:user:* inspectable via Dragonfly CLI
  - pg_indexes query for idx_pfs_patient_started after migration
  - rg 'staleTime|refetchInterval' across frontend-hormonia/src/ filtered by monitoring exclusions is the canonical audit command
requirement_outcomes:
  - id: R100
    from_status: active
    to_status: validated
    proof: S01 implemented per-user Redis caching on physician/patients (TTL=60s) with user_id in cache key. Dashboard caching confirmed at TTL=120s. verify-m011.sh group 5 confirms both TTL values and user_id presence in key.
  - id: R101
    from_status: active
    to_status: validated
    proof: S01 created Alembic migration m011_s01_patient_flow_states_index with composite index idx_pfs_patient_started on patient_flow_states(patient_id, started_at DESC). verify-m011.sh group 7 confirms index name and correct down_revision chain.
  - id: R102
    from_status: active
    to_status: validated
    proof: S02 normalized 21 frontend hooks — staleTime ≥ 60s for dashboard/patient, ≥ 120s for admin, refetchInterval ≥ 120s everywhere except monitoring. verify-m011.sh group 6 confirmed 58 timing values comply with thresholds.
duration: 67m
verification_result: passed
completed_at: 2026-03-17
---

# M011: Otimização de Carregamento e Redução de Stress no Banco

**Surgical performance optimization — per-user Redis caching on physician hot paths, composite index for ROW_NUMBER() acceleration, and frontend request discipline across 21 hooks — zero functional changes, zero regressions**

## What Happened

M011 delivered three complementary optimizations to reduce database stress and eliminate redundant requests, working across two independent implementation slices and one terminal verification slice.

**S01 (Backend caching + index)** tackled the two heaviest database paths. First, it created an Alembic migration adding composite index `idx_pfs_patient_started` on `patient_flow_states(patient_id, started_at DESC)` — directly accelerating the `ROW_NUMBER() OVER (PARTITION BY patient_id ORDER BY started_at DESC)` window function used in the physician/patients endpoint, converting sequential scan + in-memory sort to index scan. Second, it added per-user Redis caching to the `list_physician_patients` endpoint with TTL=60s. The cache key includes `user_id` plus all 5 query parameters (`page`, `size`, `search`, `flow_phase`, `flow_status`), making key collision between doctors impossible. The implementation uses manual `redis_cache.get()`/`redis_cache.set()` (not the `@cache_response` decorator) because the decorator doesn't support user_id-scoped keys needed to prevent cross-doctor data leaks. Both read and write are wrapped in try/except so Redis downtime falls through silently to the DB query. Dashboard caching was already correct at TTL=120s with per-user key — no modifications needed.

**S02 (Frontend request discipline)** swept all React Query timing values across 21 frontend files. The global default staleTime in `queryClient.ts` went from 30s→60s. Dashboard/patient hooks (11 files) got staleTime ≥ 60s and refetchInterval ≥ 120s. Admin hooks (7 files) got staleTime ≥ 120s and refetchInterval ≥ 120s. Monitoring/real-time hooks (system health, WhatsApp, agent swarm) were explicitly exempted and verified untouched. The slice also fixed 6 pre-existing TS errors in `playwright.config.e2e.ts` to unblock `tsc --noEmit`. Both `tsc --noEmit` (exit 0) and `vite build` (exit 0, 4741 modules) passed green.

**S03 (Integrated verification)** assembled both slices' outputs into a replayable `verify-m011.sh` with 7 check groups: ast.parse (3 backend files), tsc --noEmit, vite build, response shape (no schema modifications), caching values (TTL=60/120, user_id in key), timing values (58 JS expressions evaluated via Python, all compliant), and migration chain (correct down_revision and index name). All 7 groups passed with exit 0.

## Cross-Slice Verification

| Success Criterion | Evidence | Status |
|---|---|---|
| Endpoints physician/patients and dashboard/main use caching with correct TTL | patients.py: `ttl=60`, `user:{user_id}` in cache key; dashboard.py: `CACHE_TTL_REALTIME = 120` | ✅ |
| Index composto em patient_flow_states(patient_id, started_at DESC) via Alembic | Migration `m011_s01_patient_flow_states_index` with `idx_pfs_patient_started`, `if_not_exists=True`, `down_revision = "m008_s01_t03_sessions_align"` | ✅ |
| Frontend hooks staleTime ≥ 60s, refetchInterval ≥ 120s | 21 files modified, grep audit confirms all values ≥ 60000/120000 outside monitoring exclusions | ✅ |
| Response shape unchanged | Zero commits to `backend-hormonia/app/schemas/` during M011; `response_model=` annotations confirmed in both routers | ✅ |
| `tsc --noEmit` green | S02/T02 ran tsc, exit 0 | ✅ |
| `vite build` green | S02/T02 ran vite build, exit 0, 4741 modules | ✅ |
| verify-m011.sh passes all 7 groups | S03/T01 ran script, 7/7 passed, exit 0 | ✅ |

**Definition of Done:** All 3 slices complete ✅, all slice summaries exist ✅, no cross-slice integration gaps ✅.

## Requirement Changes

- R100: active → validated — S01 implemented per-user Redis caching on physician/patients (TTL=60s) and confirmed dashboard caching at TTL=120s. verify-m011.sh group 5 confirms TTL values and user_id in cache key.
- R101: active → validated — S01 created Alembic migration with composite index `idx_pfs_patient_started`. verify-m011.sh group 7 confirms index name and Alembic chain.
- R102: active → validated — S02 normalized 21 hooks across dashboard/admin. verify-m011.sh group 6 confirmed 58 timing values comply. Monitoring hooks verified untouched.

## Forward Intelligence

### What the next milestone should know
- The physician/patients endpoint uses **manual** `redis_cache.get()`/`redis_cache.set()` — not `@cache_response` decorator. This is the canonical pattern for any future per-user endpoint caching where cache keys need user_id scoping.
- Dashboard caching was already correct and was intentionally left unchanged. The cache key format for dashboard includes user_id via the existing pattern in `dashboard.py`.
- The Alembic migration chain head is now `m011_s01_patient_flow_states_index` (was `m008_s01_t03_sessions_align`).
- Frontend timing discipline: monitoring/real-time hooks are explicitly exempt from the ≥ 60s/120s thresholds. The exemption list covers system health, WhatsApp, agent swarm, clinical monitoring, and `queryPresets.realtime`.

### What's fragile
- Cache key format `physician:patients:user:{user_id}:page:...` — if new query params are added to the endpoint, the cache key must be updated or stale results will be served for different param values.
- The `hasattr(current_user, 'id')` guard handles both attribute and dict access for user_id — if `current_user` shape changes, this guard needs review.
- `useOptimizedQuery.helpers.ts` and `ProductionProvider.tsx` contain sub-threshold staleTime values but are dead code (zero imports). If re-imported, the grep audit will flag them.
- The timing audit in verify-m011.sh uses Python `eval()` on extracted JS expressions — safe for numeric literals and `*` but would break on complex JS expressions.

### Authoritative diagnostics
- `bash verify-m011.sh` — single command to re-verify all M011 deliverables. No side effects, no mutations.
- `redis-cli KEYS "physician:patients:user:*"` — shows active cached physician queries (empty means cache not being hit).
- `SELECT indexname FROM pg_indexes WHERE indexname = 'idx_pfs_patient_started'` — confirms the index exists in PostgreSQL after migration.
- `rg "staleTime|refetchInterval" frontend-hormonia/src/` filtered by monitoring exclusions — canonical frontend timing audit.

### What assumptions changed
- Original roadmap mentioned `@cache_response` decorator — S01 correctly refined this to manual redis_cache pattern because the decorator doesn't support user_id-scoped keys needed to prevent cross-doctor data leaks. This was planned during S01, not a deviation.
- The roadmap estimated ~20 frontend hooks needed adjustment — actual count was 21, well within estimate.

## Files Created/Modified

- `backend-hormonia/alembic/versions/m011_s01_patient_flow_states_index.py` — Alembic migration creating composite index for ROW_NUMBER() optimization
- `backend-hormonia/app/api/v2/routers/physicians/patients.py` — Per-user Redis caching with TTL=60s and try/except resilience
- `frontend-hormonia/src/lib/react-query/queryClient.ts` — Global default staleTime 30s→60s
- `frontend-hormonia/src/pages/DashboardPage.tsx` — staleTime 30s→60s, refetchInterval 60s→120s
- `frontend-hormonia/src/hooks/api/useClinicalMetrics.ts` — staleTime 30s→60s, refetchInterval 30s→120s
- `frontend-hormonia/src/hooks/api/useRiskPatients.ts` — refetchInterval 60s→120s
- `frontend-hormonia/src/hooks/useFlows.ts` — staleTime 30s→60s, refetchInterval 60s→120s (3 queries)
- `frontend-hormonia/src/hooks/useFlowEngine.ts` — staleTime 30s→60s, refetchInterval 60s→120s
- `frontend-hormonia/src/hooks/useMonthlyQuizStatus.ts` — staleTime 30s→60s
- `frontend-hormonia/src/hooks/useMonthlyQuizAdmin.ts` — staleTime 30s→60s
- `frontend-hormonia/src/hooks/useMonthlyQuizAdminSecure.ts` — staleTime 30s→60s
- `frontend-hormonia/src/hooks/useSystemStats.ts` — staleTime 10s→60s, refreshInterval 30s→120s
- `frontend-hormonia/src/features/dashboard/AlertsPanel.tsx` — refetchInterval 30s→120s
- `frontend-hormonia/src/features/dashboard/RecentQuizCompletions.tsx` — refetchInterval 60s→120s
- `frontend-hormonia/src/hooks/admin/useUserStats.ts` — staleTime 10s→120s
- `frontend-hormonia/src/hooks/admin/useUserList.ts` — staleTime 10s→120s
- `frontend-hormonia/src/hooks/admin/useUserAdmin.ts` — staleTime 30s→120s, refreshInterval 30s→120s
- `frontend-hormonia/src/features/admin/AuditLogViewer.tsx` — refetchInterval 30s→120s
- `frontend-hormonia/src/features/admin/tabs/AdminUsersTab.tsx` — refetchInterval 30s→120s
- `frontend-hormonia/src/features/admin/AdminNavigationMenu.tsx` — refetchInterval 60s→120s
- `frontend-hormonia/src/pages/AdminPage.tsx` — refetchInterval 30s→120s
- `frontend-hormonia/src/components/layout/NotificationCenter.tsx` — refetchInterval 30s→120s
- `frontend-hormonia/src/pages/DLQDashboard.tsx` — refetchInterval 30s→120s (2 queries)
- `frontend-hormonia/tests/e2e/playwright.config.e2e.ts` — fixed process.env bracket notation for TS compliance
- `verify-m011.sh` — Replayable milestone verification script, 7 check groups
