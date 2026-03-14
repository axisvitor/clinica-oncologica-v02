# M003/S05 — Research

**Date:** 2026-03-13

## Summary

S05 owns the final proof for **R037 (stable visible contracts)**, **R038 (safer-to-change code in practice)**, and **R039 (strong integrated proof)**. The structural side is already in a good state: the living verifier is green right now (`verify-evidence-map.sh --report all` and `--check all` both pass), `auth_dependencies.py` is down to 675 lines, `src/lib/api-client/index.ts` is 223 lines, `src/lib/api-client/types.ts` is 26 lines, and the deleted compat files are still at zero lines. That means S05 should not reopen refactor discovery; it should close the trust gap between green focused suites and the real assembled runtime.

The missing proof is runtime continuity on the **current** routes and contracts, not on the old browser harness assumptions. The best reusable assets already exist: the S04 cleanup manifest/evidence-map gate for structural closeout, plus the M002 no-Firebase proof recipe for bringing up a real local stack and seeding a session-first auth user. The surprise is how much of the older Playwright inventory is stale: **7 e2e files still reference `/admin/dashboard` or `/admin/whatsapp`**, **13 e2e files still carry Supabase/Firebase/legacy-admin residue**, and `src/AdminApp.tsx` still contains Firebase-era comments. Those files are discoverable, but most are not trustworthy acceptance surfaces for S05.

## Recommendation

Treat S05 as a **narrow assembled-proof slice**, not another cleanup slice.

Recommended execution shape:

1. **Reuse the exact S04 proof pack first**
   - Re-run the six S04 manifest commands unchanged.
   - Re-run `verify-evidence-map.sh --report all` and `--check all` as the structural closeout guard.
   - This rechecks the M003 refactor/deletion boundary before spending time on browser smoke.

2. **Stand up the same no-Firebase local stack used in M002, but keep WuzAPI mocked**
   - Use the M002 `S04-PROOF.md` backend/frontend launch recipe.
   - Keep `FIREBASE_ADMIN_*` and `VITE_FIREBASE_*` blank.
   - Set `WHATSAPP_WUZAPI_USE_MOCK=true` and a local WuzAPI token so the backend boots and `/whatsapp` can render a meaningful status surface.
   - Use the frontend dev server at **5173**, not Vite preview, because the current browser auth proof depends on the dev proxy rewriting `/api/*` → `/api/v2/*`.

3. **Use canonical route smoke, not the stale admin/browser specs**
   - For browser proof, start from **`/admin`** or **`/whatsapp`** while logged out and let the shared `ProtectedRoute` redirect to **`/login`**.
   - Submit the **canonical** login form (`LoginPage`) and assert the redirect returns to the intended route.
   - Then smoke:
     - `/dashboard` with a successful `/api/v2/dashboard/main` fetch and no fatal render/error-card loop
     - `/admin` root render after canonical login
     - `/whatsapp` render with a successful `/api/v2/monitoring/wuzapi/session/status` fetch on mocked WuzAPI
   - Use browser assertions/network logs or browser tools directly; do **not** trust `/admin/dashboard` or `/admin/whatsapp` Playwright flows as acceptance truth.

4. **Add one tiny direct compat-island proof pack**
   - `/session/validate` with no/malformed session should still return **200 + `valid:false`** (legacy contract, not canonical 401 semantics).
   - `/session/logout` should still revoke a live legacy session.
   - Add one explicit bearer-fallback check against the canonical auth path (`Authorization: Bearer <session_id>`) or record a deliberate non-use proof if that path is no longer meant to be exercised in real callers.

5. **Use the canonical Playwright auth acceptance only if the seeded-user contract is available**
   - `tests/e2e/auth/session-first-hard-cut.spec.ts` is still the best reusable real-browser auth proof.
   - Run it only as:
     - `--project=chromium`
     - with the seeded staff env vars exported per run
   - If the seeded user/reset token is not available, S05 should still proceed with browser-tool smoke and record that Playwright acceptance was skipped for fixture reasons rather than silently widening scope.

Why this approach: it closes **R037/R038/R039** with the least churn. It reuses the green structural proof, reuses the best existing auth acceptance recipe, adds only the missing compat-island checks, and avoids spending S05 time rehabilitating stale browser specs that were written for routes and auth models the repo no longer ships.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Structural closeout drift | `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` + `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md` | This is already the living M003 cleanup gate and the authoritative deleted-vs-retained boundary. |
| Real no-Firebase auth acceptance | `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` + `.gsd/milestones/M002/slices/S04/S04-PROOF.md` | This is the one browser proof already aligned to the shipped session-first auth contract and it includes the startup/seed contract. |
| Legacy `/session/*` semantics | `backend-hormonia/tests/auth/test_session_validation.py` | It already pins the retained compatibility router behavior, including the non-canonical `200 + valid:false` invalid-session contract. |
| Current admin/auth route truth | `frontend-hormonia/src/app/routes/routeDefinitions.tsx` + `frontend-hormonia/src/pages/LoginPage.tsx` | These files reflect the current real redirect path (`/admin/*` → shared `/login`), which the old Playwright admin specs do not. |
| Current WhatsApp operator surface | `frontend-hormonia/src/pages/WhatsAppPage.tsx` + `frontend-hormonia/src/features/whatsapp/WhatsAppDashboard.tsx` + `backend-hormonia/app/api/v2/monitoring/wuzapi.py` | These are the actual current UI/backend surfaces, not the stale `/admin/whatsapp` e2e assumptions. |

## Existing Code and Patterns

- `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md` — authoritative S05 starting checklist: exact proof commands, deleted residue, retained compatibility islands.
- `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` — living structural gate; current baseline is green and reports the post-S04 line counts and zero-line deleted compat surfaces.
- `.gsd/milestones/M002/slices/S04/S04-PROOF.md` — reusable no-Firebase stack recipe, seeded-user contract, and Playwright auth acceptance command.
- `frontend-hormonia/src/app/routes/routeDefinitions.tsx` — top-level `/admin/*` is wrapped by the shared `ProtectedRoute`, so unauthenticated admin access goes to `/login`, not to a canonical public `/admin/login` flow.
- `frontend-hormonia/src/pages/LoginPage.tsx` — canonical browser login uses accessible `Email` / `Senha` labels and redirects to `location.state.from.pathname` when present; this is the right path for `/admin` and `/whatsapp` smoke.
- `frontend-hormonia/src/app/providers/AuthContext.tsx` — `login()` / `restoreSession()` prefetch dashboard data after auth, but `prefetchDashboard()` swallows errors; auth success does **not** prove dashboard success.
- `backend-hormonia/app/core/router_registry.py` — the legacy `/session` router is still explicitly mounted at the app level, so S05 must treat it as a real runtime surface.
- `backend-hormonia/app/api/v2/routers/auth.py` — canonical auth still accepts cookie, `X-Session-ID`, and `Authorization: Bearer <session_id>` extraction in `_get_session_id_from_request()`.
- `backend-hormonia/tests/auth/test_session_validation.py` — compatibility proof for `/session/validate` and `/session/logout`; invalid sessions return `200` with `valid:false`, not the canonical `/api/v2/auth/verify-session` 401 behavior.
- `frontend-hormonia/src/pages/DashboardPage.tsx` — assembled dashboard route renders `QuickStats`, tabs, and error UI around `apiClient.dashboard.getMain({ time_range: 'week' })`; there is no equivalent focused browser-proof pack in M003 yet.
- `frontend-hormonia/src/pages/WhatsAppPage.tsx` + `frontend-hormonia/src/features/whatsapp/WhatsAppDashboard.tsx` — current WhatsApp route is `/whatsapp`, not `/admin/whatsapp`, and it depends on WuzAPI status plus queue/message stats.
- `frontend-hormonia/tests/e2e/playwright.config.e2e.ts` — starts only the frontend dev server, defaults to five browser projects, and therefore must be constrained explicitly when used for S05 acceptance.

## Constraints

- **S05 owns R037, R038, and R039.** The slice is not done when focused tests are green; it is done when the affected runtime surfaces are re-proven assembled.
- **The structural gate is already green.** S05 should not widen back into hotspot discovery unless the evidence-map gate regresses.
- **Use the frontend dev server (`npm run dev` at 5173), not preview, for browser smoke.** The current auth/browser proof relies on the Vite dev proxy rewriting `/api/*` to `/api/v2/*`; preview does not provide that development proxy behavior.
- **Backend boot still needs WuzAPI mock/token configuration even though staff auth is no-Firebase.** Without that, `/whatsapp` becomes an infrastructure failure rather than a useful continuity signal.
- **`/session/*` is a retained compatibility island with different semantics from `/api/v2/auth/*`.** Do not assert canonical 401 behavior against `/session/validate`.
- **`/admin/login` is not the canonical unauthenticated entrypoint.** The top-level route tree protects `/admin/*` before `AdminApp` loads, so the reliable acceptance path is `/admin` → shared `/login` → successful return.
- **Playwright config will discover many stale specs by default.** S05 should run only the named spec(s) it trusts.

## Common Pitfalls

- **Using the old admin/WhatsApp Playwright specs as acceptance truth** — current evidence says they are stale. There are **7 e2e files** still referencing `/admin/dashboard` or `/admin/whatsapp`, and **13 e2e files** still carrying Supabase/Firebase/legacy-admin residue. Run only the canonical auth spec or use browser tools.
- **Treating login redirect as dashboard proof** — `AuthContext` prefetches dashboard data non-blockingly. You can land on `/dashboard` with auth working while dashboard data still fails. Assert `/api/v2/dashboard/main` or visible dashboard content separately.
- **Using `/admin/login` for final admin acceptance** — the inner admin login form does not provide the current top-level route truth, and many stale tests wait for `/admin/dashboard`, which is not the current routed destination.
- **Running Playwright across all projects** — `auth/session-first-hard-cut.spec.ts` already skips non-Chromium at runtime, so use `--project=chromium` to avoid wasted time and noisy output.
- **Forgetting the retained bearer/session header paths** — S04 explicitly retained bearer fallback and `/session/*`; if S05 never touches them, the milestone closeout is incomplete.

## Open Risks

- **Assembled dashboard/admin runtime drift may still exist even with green auth/client suites.** Current M003 proof covers auth/client contracts well, but not the fully rendered dashboard/admin pages on a live local stack.
- **WhatsApp continuity depends on mocked infrastructure being present.** `WhatsAppDashboard` will poll WuzAPI status and queue/message stats immediately; missing mock/token/Redis will create noisy failures unrelated to the refactor itself.
- **Bearer fallback has weak recent end-to-end evidence.** The code still supports it, but the M003 slice-close packs did not explicitly replay a bearer-only caller.
- **Legacy `/session/*` proof is compatibility-heavy.** The best existing suite still uses Firebase-named mocks and vocabulary, so failures there may require careful diagnosis to separate naming residue from real contract breakage.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | available — install with `npx skills add wshobson/agents@fastapi-templates` |
| React | `vercel-labs/agent-skills@vercel-react-best-practices` | available — install with `npx skills add vercel-labs/agent-skills@vercel-react-best-practices` |
| Playwright | `currents-dev/playwright-best-practices-skill@playwright-best-practices` | available — install with `npx skills add currents-dev/playwright-best-practices-skill@playwright-best-practices` |
| PostgreSQL | `github/awesome-copilot@postgresql-optimization` | available — install with `npx skills add github/awesome-copilot@postgresql-optimization` |

## Sources

- Current M003 cleanup boundary, retained compatibility islands, and exact reusable proof commands (source: `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md`)
- Current S04 handoff and final slice-close observations (source: `.gsd/milestones/M003/slices/S04/S04-SUMMARY.md`, `.gsd/milestones/M003/slices/S04/S04-UAT.md`)
- Current backend/frontend split-task handoffs and proof surfaces for S02/S03 (source: `.gsd/milestones/M003/slices/S02/tasks/T01-SUMMARY.md` … `T04-SUMMARY.md`, `.gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md` … `T04-SUMMARY.md`)
- Current structural baseline is still green: `verify-evidence-map.sh --report all` and `--check all` both pass with `backend.auth_dependencies.lines=675`, `frontend.api_client_index.lines=223`, `frontend.api_client_types.lines=26`, and zero-line deleted compat files (source: `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`, `--check all`)
- Reusable no-Firebase local-stack startup and seeded-user contract for real-browser auth proof (source: `.gsd/milestones/M002/slices/S04/S04-PROOF.md`)
- Current route/auth redirect truth (source: `frontend-hormonia/src/app/routes/routeConfig.ts`, `frontend-hormonia/src/app/routes/routeDefinitions.tsx`, `frontend-hormonia/src/pages/LoginPage.tsx`, `frontend-hormonia/src/app/providers/AuthContext.tsx`)
- Current admin shell and stale-comment residue (source: `frontend-hormonia/src/AdminApp.tsx`, `frontend-hormonia/src/app/routes/AdminRoutes.tsx`, `frontend-hormonia/src/features/admin/AdminProtectedRoute.tsx`)
- Current WhatsApp UI/backend surfaces (source: `frontend-hormonia/src/pages/WhatsAppPage.tsx`, `frontend-hormonia/src/features/whatsapp/WhatsAppDashboard.tsx`, `backend-hormonia/app/api/v2/monitoring/wuzapi.py`, `backend-hormonia/app/integrations/whatsapp/api/routes.py`)
- Current `/session/*` compatibility semantics and canonical bearer/session extraction behavior (source: `backend-hormonia/app/core/router_registry.py`, `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/tests/auth/test_session_validation.py`, `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`)
- Playwright/e2e drift inventory and discoverability checks (source: `frontend-hormonia/tests/e2e/playwright.config.e2e.ts`, `npx playwright test --list auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts`, `rg` counts over `frontend-hormonia/tests/e2e`)
- External skill suggestions (source: `npx skills find "FastAPI"`, `"React"`, `"Playwright"`, `"PostgreSQL"`)
