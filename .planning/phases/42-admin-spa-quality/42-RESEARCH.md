# Phase 42: Admin SPA Quality - Research

**Researched:** 2026-03-04
**Domain:** Frontend TypeScript/React SPA quality cleanup — dead code removal, API alignment, TanStack Query migration, tooling setup
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ADMIN-01 | Remove dead Evolution API code from frontend (WhatsAppDashboard.tsx, AdminSettingsTab.tsx, env-validator.ts, runtime-config.ts) | Files fully mapped — exact lines identified |
| ADMIN-02 | Audit hive-mind.ts module — remove or align endpoints that don't exist in backend | Backend has /hive-mind/health and /hive-mind/agents only; other hive-mind endpoints are absent |
| ADMIN-03 | Consolidate API client — eliminate duplicated calls, align types with v2 backend contracts | Duplicate WhatsApp service identified (WhatsAppService.ts vs apiClient.hiveMind); types need Evolution→WuzAPI swap |
| ADMIN-04 | Migrate AgentSwarm.tsx and SystemHealth.tsx from useEffect polling to TanStack Query | Both files confirmed using setInterval polling loops; TanStack Query v5 already installed |
| ADMIN-05 | Configure Prettier and apply to admin SPA | No prettier config found; package.json has no prettier dependency |
| ADMIN-06 | Zero ESLint errors in admin SPA | Currently 0 errors, 1 warning — already passing; confirm with full run |
| ADMIN-07 | Remove unused npm packages (audit via knip) | knip v5.85.0 already available in node_modules |
| ADMIN-08 | Consistent layout and spacing across admin pages | shadcn/ui + Tailwind CSS in use; visual consistency pass needed |
</phase_requirements>

---

## Summary

Phase 42 is a frontend quality cleanup phase for the admin SPA at `frontend-hormonia/`. The work divides into four distinct tracks: (1) dead code elimination for Evolution API references, (2) backend API alignment for the hive-mind frontend module, (3) polling-to-TanStack-Query migration for two components, and (4) tooling setup (Prettier, knip, ESLint verification).

The admin SPA already passes `tsc --noEmit` with zero errors and `eslint .` with zero errors (one warning). This is a major advantage — the phase is about preventing regressions and cleaning code, not fixing a broken build. The most impactful work is replacing Evolution API branding (WhatsApp dashboard shows "WhatsApp Integration Disabled — set VITE_ENABLE_EVOLUTION=true" to every physician) with WuzAPI-aware status using the real `/api/v2/monitoring/wuzapi/session/status` endpoint.

The hive-mind.ts frontend module calls nine endpoints, but the backend hive_mind router only implements two (`/health` and `/agents`). The other seven routes — `/swarm/*`, `/alerts`, `/integration/*`, `/tasks/*`, `/stats` — do not exist in the backend and would 404 on fetch. These dead API calls must be removed or replaced.

**Primary recommendation:** Execute in strict order: ADMIN-01 (Evolution removal) → ADMIN-02/03 (hive-mind API cleanup + type alignment) → ADMIN-04 (TanStack Query migration) → ADMIN-05 (Prettier setup) → ADMIN-07 (knip audit) → ADMIN-06/08 (ESLint confirm + layout pass). TypeScript and ESLint currently pass, so changes must be validated incrementally to avoid introducing regressions.

---

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| React | 19.0.0 | UI framework | Installed |
| TypeScript | 5.9.3 | Type safety | Installed |
| Vite | 6.0.7 | Build tool | Installed |
| @tanstack/react-query | 5.62.0 | Server state management | Installed |
| @tanstack/react-query-persist-client | 5.90.2 | IndexedDB persistence | Installed |
| eslint | 9.17.0 | Linting (flat config) | Installed |
| typescript-eslint | 8.45.0 | TypeScript ESLint rules | Installed |
| tailwindcss | 4.1.13 | CSS framework | Installed |

### Tooling to Add
| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| prettier | 3.x | Code formatting | ADMIN-05 requires it; currently absent |
| eslint-config-prettier | 9.x | Disable ESLint formatting rules that conflict with Prettier | Required when using both |

### Already Available (no install needed)
| Tool | Version | Purpose |
|------|---------|---------|
| knip | 5.85.0 | Unused package/file detection | Already in node_modules |

**Installation for Prettier:**
```bash
cd frontend-hormonia
npm install --save-dev prettier eslint-config-prettier
```

---

## Architecture Patterns

### Recommended Project Structure
The admin SPA already follows this structure — no restructuring needed:
```
src/
├── lib/api-client/          # API client modules (hive-mind.ts lives here)
├── components/hive-mind/    # AgentSwarm.tsx, SystemHealth.tsx
├── features/whatsapp/       # WhatsAppDashboard.tsx
├── features/admin/tabs/     # AdminSettingsTab.tsx
├── lib/                     # runtime-config.ts, env-validator.ts
└── types/                   # api-wave2.ts, system-stats.ts
```

### Pattern 1: TanStack Query v5 with refetchInterval

**What:** Replace `useEffect + setInterval` data-fetching loops with `useQuery({ refetchInterval: 30000 })`.
**When to use:** Any component that polls a REST endpoint on a timer.
**Key difference from v4:** In TanStack Query v5, `useQuery` options are an object literal — no more overloads.

```typescript
// Source: @tanstack/react-query v5 API (version 5.62.0 installed)
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

// Before (current pattern in AgentSwarm.tsx and SystemHealth.tsx):
useEffect(() => {
  const fetchAgents = async () => { /* ... */ };
  fetchAgents();
  const interval = setInterval(fetchAgents, 30000);
  return () => clearInterval(interval);
}, []);

// After (TanStack Query v5 pattern):
const { data, isLoading, error } = useQuery({
  queryKey: ["hive-mind", "agents"],
  queryFn: () => apiClient.hiveMind.agents.list(),
  refetchInterval: 30000,
  retry: 2,
});
```

**QueryClient is already set up** — `App.tsx` uses `PersistQueryClientProvider` and `ProductionProvider.tsx` uses `QueryClientProvider`. Components inside the provider tree can call `useQuery` directly.

### Pattern 2: Removing Evolution API dead code

**What:** Strip all `VITE_ENABLE_EVOLUTION` / `VITE_EVOLUTION_API_URL` references and replace the disabled-state UI in WhatsAppDashboard with WuzAPI status from `/api/v2/monitoring/wuzapi/session/status`.
**Files requiring changes:**

| File | What to change |
|------|----------------|
| `src/features/whatsapp/WhatsAppDashboard.tsx` | Remove `isEvolutionEnabled` state; remove disabled-state guard block; fetch WuzAPI status via `useQuery` |
| `src/features/admin/tabs/AdminSettingsTab.tsx` | Remove "Evolution API URL" input field and its label (lines 202-209) |
| `src/lib/runtime-config.ts` | Remove `VITE_ENABLE_EVOLUTION` and `VITE_EVOLUTION_API_URL` from `RuntimeConfig` interface and `CONFIG` object |
| `src/lib/env-validator.ts` | Remove `VITE_ENABLE_EVOLUTION` and `VITE_EVOLUTION_API_URL` from `ENV_VALIDATION_RULES` |
| `src/types/api-wave2.ts` | Rename `evolution_api` field in `ServiceStatusMetrics` → `whatsapp_api` or `wuzapi` |
| `src/types/system-stats.ts` | Rename `evolution_api` field in `ServiceStatusMetrics` interface |

**WuzAPI backend endpoint contract** (from `backend-hormonia/app/api/v2/monitoring/wuzapi.py`):
```
GET /api/v2/monitoring/wuzapi/session/status
Response: {
  "connected": boolean,
  "logged_in": boolean,
  "timestamp": string,   // ISO8601
  "mock": boolean,       // optional — only when USE_MOCK=true
  "error": string        // optional — only on failure
}
```

### Pattern 3: Hive-Mind API Alignment

**What:** The frontend `hive-mind.ts` module calls 9 endpoints. The backend only exposes 2.

| Frontend call | Backend endpoint | Exists? |
|---------------|-----------------|---------|
| `hiveMind.health()` | `GET /api/v2/hive-mind/health` | YES |
| `hiveMind.agents.list()` | `GET /api/v2/hive-mind/agents` | YES |
| `hiveMind.agents.get(id)` | `GET /api/v2/hive-mind/agents/{id}` | NO — 404 |
| `hiveMind.agents.metrics(id)` | `GET /api/v2/hive-mind/agents/{id}/metrics` | NO — 404 |
| `hiveMind.alerts()` | `GET /api/v2/hive-mind/alerts` | NO — 404 |
| `hiveMind.integration.getStatus()` | `GET /api/v2/hive-mind/integration/status` | NO — 404 |
| `hiveMind.integration.setMode()` | `PUT /api/v2/hive-mind/integration/mode` | NO — 404 |
| `hiveMind.integration.setMigrationPercentage()` | `PUT /api/v2/hive-mind/integration/migration-percentage` | NO — 404 |
| `hiveMind.swarm.getStatus()` | `GET /api/v2/hive-mind/swarm/status` | NO — 404 |
| `hiveMind.swarm.getAgents()` | `GET /api/v2/hive-mind/swarm/agents` | NO — 404 |
| `hiveMind.tasks.processFlows()` | `POST /api/v2/hive-mind/tasks/process-flows` | NO — 404 |
| `hiveMind.tasks.conductQuiz()` | `POST /api/v2/hive-mind/tasks/conduct-quiz/{id}` | NO — 404 |
| `hiveMind.stats()` | `GET /api/v2/hive-mind/stats` | NO — 404 |

**Decision required (ADMIN-02):** Remove the 11 dead methods from `hive-mind.ts` and from the `HiveMindApi` interface. Trim `HiveMindPage.tsx` to only render `SystemHealth` (uses `/health`) and `AgentSwarm` (uses `/agents`).

Types that are ONLY used by dead endpoints (`SwarmStatus`, `IntegrationStatus`, `AgentMetrics`, `HiveMindSystemStats`, `ProcessFlowsResponse`, `ConductQuizResponse`) should also be removed from `hive-mind.ts`.

### Pattern 4: Prettier Configuration

**What:** Add a standard Prettier config for the admin SPA.
**Standard `.prettierrc` for this project:**
```json
{
  "semi": false,
  "singleQuote": true,
  "tabWidth": 2,
  "trailingComma": "es5",
  "printWidth": 100,
  "plugins": []
}
```

Note: The existing codebase uses `import x from 'y'` (single quotes) and generally omits semicolons in some files. Check the majority of existing files before choosing `semi: true/false` — existing `.tsx` files under `features/admin/` use no trailing semicolons on most statements but do use them at end of expressions. Use `semi: false` only if that is consistently the pattern; otherwise default to `semi: true`.

**Add to `package.json` scripts:**
```json
"format": "prettier --write 'src/**/*.{ts,tsx}'",
"format:check": "prettier --check 'src/**/*.{ts,tsx}'"
```

**Add to `eslint.config.js`** to disable formatting rules:
```javascript
import prettierConfig from 'eslint-config-prettier'
// Add as last item in the config array:
prettierConfig
```

### Pattern 5: Knip Audit for Unused Packages

**What:** Run knip to detect unused npm packages.
**Command:**
```bash
cd frontend-hormonia
npx knip --include-entry-exports
```

**Expected output format:** List of unused dependencies and devDependencies.
**Then:** Remove each confirmed unused package with `npm uninstall <package>`.

**Packages likely unused (to verify with knip):**
- `@radix-ui/react-*` components that aren't imported anywhere (many shadcn/ui primitives may be installed but not used)
- `embla-carousel-react` — check if carousel is used
- `vaul` — check if drawer is used
- `cmdk` — check if command palette is used
- `input-otp` — check if OTP input is used
- `react-resizable-panels` — check if resizable panels are used

**Do NOT remove** packages whose types-only (`@types/*`) usages or devDependency usage may not be caught by knip. Verify before uninstalling.

### Anti-Patterns to Avoid
- **Don't add QueryClient nesting:** App.tsx already wraps with `PersistQueryClientProvider`. Do not add a second `QueryClientProvider` inside AgentSwarm or SystemHealth.
- **Don't use `queryKey` strings alone:** Use arrays `["hive-mind", "health"]` for proper cache invalidation.
- **Don't remove the `AgentStatus`/`SystemHealthOverview` types** from `hive-mind.ts` — they are used by AgentSwarm.tsx and SystemHealth.tsx respectively and map to real backend responses.
- **Don't use `useEffect` for data fetching** in new code — this is the entire point of ADMIN-04.
- **Don't run `prettier --write .`** without a `.prettierignore` — it will try to format `dist/`, `node_modules/`, etc.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Polling with auto-cleanup | `setInterval` + `clearInterval` in `useEffect` | `useQuery({ refetchInterval: N })` | TanStack Query handles background refetch, window focus refetch, cleanup, deduplication |
| Code formatting | Custom ESLint formatting rules | Prettier | Formatting rules in ESLint are slow and conflict-prone |
| Unused dependency detection | Manual audit of imports | knip | knip traces the full import graph including re-exports |
| API response caching | `useState` + manual TTL | `useQuery({ staleTime: N }` | TanStack Query handles staleTime, gcTime, background updates |

---

## Common Pitfalls

### Pitfall 1: TypeScript Breaks After Evolution Removal
**What goes wrong:** Removing `VITE_ENABLE_EVOLUTION` from `RuntimeConfig` causes TypeScript errors anywhere `config?.VITE_ENABLE_EVOLUTION` is accessed.
**Why it happens:** TypeScript strict mode + `noImplicitAny` — removing the field from the interface while accesses remain causes compile errors.
**How to avoid:** Remove field from interface LAST, after removing all access sites. Run `tsc --noEmit` after each file change.
**Warning signs:** Any remaining grep hits for `VITE_ENABLE_EVOLUTION` after cleanup.

### Pitfall 2: Hive-Mind Types Still Exported via index.ts
**What goes wrong:** `src/lib/api-client/index.ts` has `export type * from "./hive-mind"`. Removing types from `hive-mind.ts` may break downstream imports.
**Why it happens:** Re-export barrel patterns make it hard to trace dead type usage.
**How to avoid:** After removing types from `hive-mind.ts`, run `tsc --noEmit` to catch any remaining consumers.
**Warning signs:** `tsc` errors mentioning `SwarmStatus`, `IntegrationStatus`, etc.

### Pitfall 3: Prettier and ESLint Rule Conflicts
**What goes wrong:** Prettier formats code, then ESLint reports errors on the same lines.
**Why it happens:** Some ESLint rules (e.g., `indent`, `semi`) conflict with Prettier's output.
**How to avoid:** Install `eslint-config-prettier` and add it as the LAST item in `eslint.config.js` — it disables all formatting rules.
**Warning signs:** ESLint errors on lines that Prettier just formatted.

### Pitfall 4: knip False Positives on Dynamic Imports
**What goes wrong:** knip reports `recharts` as unused because it's only accessed via dynamic `import('recharts')`.
**Why it happens:** knip may not trace dynamic import expressions inside `LazyRechartsComponents.tsx`.
**How to avoid:** Review knip output carefully before uninstalling. Dynamic imports are real usage.
**Warning signs:** Package is used via `import('pkg')` but knip reports it unused.

### Pitfall 5: useQuery Called Outside QueryClientProvider
**What goes wrong:** AgentSwarm and SystemHealth are rendered inside `HiveMindPage`. If QueryClientProvider isn't in the tree above them, `useQuery` throws.
**Why it happens:** QueryClient context is required at runtime.
**How to avoid:** Verify the render path from `App.tsx` / `AdminApp.tsx` to `HiveMindPage` passes through a `QueryClientProvider`. Already confirmed — `App.tsx` uses `PersistQueryClientProvider`.

### Pitfall 6: WhatsApp Dashboard Still Shows "Evolution API disabled"
**What goes wrong:** After removing `VITE_ENABLE_EVOLUTION` guard, new WuzAPI fetch fails silently and the component shows empty state without a helpful message.
**Why it happens:** WuzAPI endpoint requires auth headers and may not be configured in all environments.
**How to avoid:** Show a meaningful fallback when WuzAPI status fetch returns error: "WhatsApp (WuzAPI) connection status unavailable — check server configuration."

---

## Code Examples

### TanStack Query v5 useQuery with refetchInterval

```typescript
// AgentSwarm.tsx — after migration
// Source: TanStack Query v5 docs (version 5.62.0)
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

export function AgentSwarm() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["hive-mind", "agents"],
    queryFn: () => apiClient.hiveMind.agents.list(),
    refetchInterval: 30_000,
    retry: 2,
  });

  const agents = data?.agents ?? [];

  if (isLoading) return <AgentSwarmSkeleton />;
  if (error) return <div className="text-red-500">Failed to fetch agents</div>;
  // render agents...
}
```

### WuzAPI Connection Status Query

```typescript
// WhatsAppDashboard.tsx — after Evolution removal
// Source: backend /api/v2/monitoring/wuzapi/session/status contract
import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

interface WuzAPISessionStatus {
  connected: boolean;
  logged_in: boolean;
  timestamp: string;
  mock?: boolean;
  error?: string;
}

// In WhatsAppDashboard component:
const { data: wuzStatus, isLoading } = useQuery<WuzAPISessionStatus>({
  queryKey: ["wuzapi", "session", "status"],
  queryFn: () =>
    apiClient.core.get<WuzAPISessionStatus>("/monitoring/wuzapi/session/status"),
  refetchInterval: 30_000,
});

// Replace Evolution-disabled guard with:
if (!wuzStatus?.connected && !isLoading) {
  // Show WuzAPI-specific status card
}
```

### Prettier .prettierignore

```
# .prettierignore
dist/
node_modules/
coverage/
playwright-report/
*.min.js
```

### Knip Config (if needed)

```json
// knip.json (optional — knip works without config for standard Vite projects)
{
  "entry": ["src/main.tsx", "src/AdminApp.tsx"],
  "project": ["src/**/*.{ts,tsx}"]
}
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|-----------------|--------|
| `useEffect + setInterval` polling | `useQuery({ refetchInterval })` | Deduplication, background fetch, window-focus refetch |
| ESLint v8 + `.eslintrc.*` | ESLint v9 flat config (`eslint.config.js`) | Already migrated (v9.17.0 in use) |
| TypeScript strict: false | `strict: true, noImplicitAny: true, noUncheckedIndexedAccess: true` | Already in tsconfig.json |
| Evolution API (removed in v1.6) | WuzAPI (aiohttp client) | Backend tombstoned in Phase 37; frontend still has dead references |

**Deprecated/outdated in this codebase:**
- `VITE_ENABLE_EVOLUTION` env var: No backend equivalent since Phase 37
- `hive-mind.ts` swarm/tasks/alerts/integration API calls: Backend never implemented these routes
- `setInterval` data polling in AgentSwarm and SystemHealth: Anti-pattern when TanStack Query is available

---

## Open Questions

1. **Service status types after Evolution removal**
   - What we know: `ServiceStatusMetrics` in `api-wave2.ts` and `system-stats.ts` has `evolution_api` field
   - What's unclear: Does the backend's `/admin/system-stats` endpoint actually return `evolution_api` in its payload, or was that field always aspirational?
   - The admin stats endpoint (`stats.py`) does NOT include `evolution_api` in its response — the backend response has `system`, `users`, `appointments`, `revenue` only
   - Recommendation: Remove the entire `ServiceStatusMetrics.evolution_api` field and update or remove the types that depend on it. Check which components actually consume this type and whether they render the field.

2. **WhatsApp Dashboard full refactor vs. minimal Evolution removal**
   - What we know: WhatsAppDashboard.tsx renders children (WhatsAppInstanceManager, WhatsAppMessageSender) that call the whatsapp service which hits `/api/v2/whatsapp/instances`
   - What's unclear: Do those endpoints exist in the backend?
   - Recommendation: Verify `/api/v2/whatsapp/instances` exists. From `router.py`, `whatsapp_router` is included without a prefix, meaning its own prefix applies. The WhatsApp integration routes do exist.

3. **Admin settings /admin/settings endpoint**
   - What we know: `AdminSettingsTab.tsx` calls `GET /admin/settings` and `PUT /admin/settings`
   - What's unclear: This path has no `/api/v2/` prefix — does this endpoint exist?
   - Recommendation: Search backend for `/admin/settings` route. If absent, the tab currently silently falls back to defaults — note this as a pre-existing issue, do not fix in this phase.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 3.2.4 |
| Config file | `vite.config.ts` (vitest inline config) |
| Quick run command | `cd frontend-hormonia && npm test` |
| Full suite command | `cd frontend-hormonia && npm test && npx tsc --noEmit && npx eslint .` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADMIN-01 | Zero grep hits for VITE_ENABLE_EVOLUTION in src/ | Shell grep | `grep -r "VITE_ENABLE_EVOLUTION" frontend-hormonia/src/ \| wc -l` (must be 0) | N/A — shell check |
| ADMIN-02 | hive-mind.ts exports only health + agents functions | Unit | Inspect `hive-mind.ts` manually | N/A |
| ADMIN-03 | tsc --noEmit exits 0 | Type check | `tsc --noEmit` | ✅ passes now |
| ADMIN-04 | AgentSwarm and SystemHealth use useQuery | Code inspection | `grep -n "useQuery" frontend-hormonia/src/components/hive-mind/*.tsx` | ❌ Wave 0 — need to migrate |
| ADMIN-05 | prettier --check exits 0 | Format check | `prettier --check 'src/**/*.{ts,tsx}'` | ❌ Wave 0 — no prettier |
| ADMIN-06 | eslint exits with 0 errors | Lint check | `eslint .` | ✅ 0 errors now |
| ADMIN-07 | knip reports 0 unused packages | Audit | `npx knip` | ✅ knip installed |
| ADMIN-08 | Visual consistency | Manual review | Manual — no automated check | N/A |

### Sampling Rate
- **Per task commit:** `cd frontend-hormonia && npx tsc --noEmit && npx eslint . --ext ts,tsx`
- **Per wave merge:** `cd frontend-hormonia && npm test && npx tsc --noEmit && npx eslint .`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] Prettier must be installed: `npm install --save-dev prettier eslint-config-prettier`
- [ ] `.prettierrc` config file to create
- [ ] `.prettierignore` file to create
- [ ] `eslint-config-prettier` to be added to `eslint.config.js`

*(tsc and eslint already pass — no test infrastructure gaps for those checks)*

---

## Sources

### Primary (HIGH confidence)
- Direct file inspection of `frontend-hormonia/src/` — all file contents verified by Read tool
- `backend-hormonia/app/api/v2/monitoring/wuzapi.py` — WuzAPI endpoint contract confirmed
- `backend-hormonia/app/api/v2/routers/hive_mind.py` — confirmed only `/health` and `/agents` implemented
- `backend-hormonia/app/api/v2/router.py` — full route registration list confirmed
- `frontend-hormonia/package.json` — dependency versions confirmed
- `frontend-hormonia/eslint.config.js` — ESLint 9 flat config confirmed
- `frontend-hormonia/tsconfig.json` — strict mode configuration confirmed
- Bash tool: `tsc --noEmit` exits 0, `eslint .` shows 0 errors / 1 warning

### Secondary (MEDIUM confidence)
- TanStack Query v5 API patterns — verified against installed version 5.62.0; patterns match known stable v5 API

### Tertiary (LOW confidence)
- Prettier recommended config — based on project code style inspection; actual choice of `semi: true/false` requires human decision
- knip false positive behavior on dynamic imports — based on general knowledge; verify with actual run

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed installed with exact versions
- Architecture: HIGH — all files read directly, backend endpoints verified
- Pitfalls: HIGH — TypeScript errors for Evolution removal confirmed by direct inspection; polling pattern confirmed by reading source
- API alignment: HIGH — backend router.py and hive_mind.py read directly

**Research date:** 2026-03-04
**Valid until:** 2026-04-03 (stable tooling; TanStack Query v5 API stable)
