# M004/S06 — Research

**Date:** 2026-03-14

## Summary

S06 supports the two still-relevant active requirements for this slice: **R047** and **R053**. R047 is the remaining mounted proof that the official stack really runs without Firebase-auth runtime config; R053 is the broader requirement that milestone closure rests on replayable integrated proof instead of cleanup-only evidence. **R051** and **R052** are not S06 work. S06 should also recheck already-validated **R050** in the mounted runtime, but it does not reopen frontend contract cleanup itself.

The repo already has almost everything needed for S06. The canonical auth lifecycle proof exists in `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`, the backend operational no-Firebase checks exist in `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`, and the exact stack launch contract was already published in `.gsd/milestones/M002/slices/S04/S04-PROOF.md`. The missing piece is composition: boot the local stack with Firebase vars blank and WuzAPI mocked, seed a replay-safe admin proof user plus reset token outside repo artifacts, run the existing auth acceptance, then finish with thin routed smoke for `/dashboard`, `/admin`, and `/whatsapp`.

The main surprise is that broad “run everything” verification would be dishonest here. There are still historical tests and even non-canonical source files with merge-conflict markers or pre-cut assumptions (`/admin/login`, Firebase-era E2E expectations, mock-auth-only RBAC specs). S06 should therefore use a deliberately narrow proof pack centered on the canonical runtime and mounted browser behavior, not repo-wide pytest/vitest/playwright sweeps.

## Recommendation

Use the existing S04 proof contract as the execution spine and keep S06 narrow.

1. **Preflight the boundary before starting servers.**
   - Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`.
   - Run the backend operational/auth preflight pack that already proves the no-Firebase runtime surfaces and canonical auth contract in-process:
     - `cd backend-hormonia && pytest -q tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py`

2. **Boot the assembled local stack exactly like the prior proof, not with a new ad-hoc recipe.**
   - Backend: blank `FIREBASE_ADMIN_*`, set a dummy `WHATSAPP_WUZAPI_TOKEN`, and keep `WHATSAPP_WUZAPI_USE_MOCK=true`.
   - Frontend: set `VITE_API_URL`, `VITE_API_BASE_URL`, and `VITE_WS_BASE_URL` explicitly at Vite launch, with `VITE_FIREBASE_*` blank.
   - Reuse `bg_shell`-style persistent server startup later instead of one-shot commands so browser proof and direct probes hit the same live processes.

3. **Seed proof auth material ephemerally.**
   - Reuse the M003/S05 pattern: create/update a local admin proof user and generate a fresh reset token using `backend-hormonia/.venv`, `app.database.SessionLocal`, `app.models.user.User`, and `app.core.security.create_password_reset_token`.
   - Write only masked env/export material to `/tmp`, never to `.gsd/` or tracked files.

4. **Use the existing Playwright auth acceptance for the expensive auth lifecycle.**
   - `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` already asserts blank Firebase env vars, successful login, reload/session restore, reset request, reset confirm, in-app password rotation, logout, logout-all, and absence of Firebase network traffic.
   - Keep it Chromium-only, exactly as authored.

5. **Add only a thin routed smoke on top.**
   - After canonical login succeeds, verify:
     - `/dashboard` loads and survives the real `/api/v2/dashboard/main` fetch.
     - `/admin` renders the shipped admin tree for the same authenticated admin user.
     - `/whatsapp` loads against mocked WuzAPI and completes a successful `/api/v2/monitoring/wuzapi/session/status` request.
   - Prefer browser-tool smoke or a tiny focused browser spec over reusing older admin/WhatsApp E2E files, because many of those still encode stale `/admin/login` or mock-auth assumptions.

6. **Do not broaden S06 into cleanup.**
   - If the mounted proof fails, debug the live stack. Do not widen into M005 schema cleanup or repo-wide dead-code/test hygiene.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Mounted no-Firebase stack launch contract | `.gsd/milestones/M002/slices/S04/S04-PROOF.md` | Already records the exact backend/frontend process env needed for local proof: blank Firebase auth vars, local ports, and mocked WuzAPI. Reusing it avoids inventing another startup story. |
| Canonical staff auth lifecycle proof | `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` | This is already the operator-facing acceptance pack for login → restore → reset → password change → logout → logout-all, and it explicitly rejects Firebase network drift. |
| No-Firebase operational truth checks | `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`, `/health/ready`, `/api/v2/system/config` | These surfaces already prove the runtime stops advertising Firebase and reports `session_auth` as the live readiness concept. |
| Official route ownership | `frontend-hormonia/src/app/routes/routeDefinitions.tsx` | Shows the shipped app treats `/dashboard` and `/whatsapp` as first-class protected routes and wraps `/admin/*` behind the canonical `ProtectedRoute`, so S06 can smoke the real paths rather than old standalone admin assumptions. |
| Replay-safe seeded proof contract | `.gsd/milestones/M003/slices/S05/tasks/T02-SUMMARY.md` | Establishes the right discipline: seed locally, keep credentials/reset tokens masked in `/tmp`, and run helper code under `backend-hormonia/.venv` with the same env contract as the live backend. |
| Cookie-only HTTP behavior | `frontend-hormonia/src/lib/api-client/core.ts` + `frontend-hormonia/src/services/whatsapp/WhatsAppService.ts` | `getSessionHeaders()` now returns `{}`, so shared frontend requests stay cookie-backed. That is the real runtime contract S06 must prove. |

## Existing Code and Patterns

- `.gsd/milestones/M002/slices/S04/S04-PROOF.md` — authoritative assembled-stack recipe for backend/frontend launch, seeded proof-user env names, and the existing Playwright acceptance entrypoint.
- `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts` — real Chromium auth proof; already checks blank Firebase envs, no Firebase requests, and the full login/restore/reset/logout lifecycle.
- `frontend-hormonia/tests/e2e/README.md` and `frontend-hormonia/tests/e2e/SETUP_INSTRUCTIONS.md` — current E2E guidance points at the session-first hard-cut spec, not provider-era auth.
- `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py` — pins readiness, system health, validation, initialization, and public config to the no-Firebase session-first runtime.
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` — focused backend integration proof for canonical login/verify/reset/logout behavior without legacy transport acceptance.
- `backend-hormonia/tests/integration/test_local_auth_core_flow.py` — direct contract proof for login → protected route → logout across DB + Redis session state.
- `frontend-hormonia/src/app/routes/routeDefinitions.tsx` — official route map: `/dashboard` and `/whatsapp` are protected app routes; `/admin/*` is wrapped by the canonical outer `ProtectedRoute` before the admin app loads.
- `frontend-hormonia/src/features/auth/ProtectedRoute.tsx` — unauthenticated official entrypoint is `/login`, which matters because older E2E files still assume `/admin/login` as the public admin gateway.
- `frontend-hormonia/src/features/admin/AdminProtectedRoute.tsx` — inner admin guard still redirects to `/admin/login`, but that only matters after the outer official route gate lets the admin app mount.
- `frontend-hormonia/src/pages/DashboardPage.tsx` — rooted on the real `/api/v2/dashboard/main` fetch and visible `Dashboard` heading; good smoke target.
- `frontend-hormonia/src/features/admin/AdminDashboard.tsx` — real admin root renders `Admin Dashboard`; good authenticated smoke target once the app reaches `/admin`.
- `frontend-hormonia/src/features/whatsapp/WhatsAppDashboard.tsx` — the routed `/whatsapp` page depends first on `/api/v2/monitoring/wuzapi/session/status`, then queue/message endpoints; the smoke should prove status fetch success before going deeper.
- `backend-hormonia/app/api/v2/monitoring/wuzapi.py` — mocked WuzAPI status endpoint calls `connect()` before reading status, so with `WHATSAPP_WUZAPI_USE_MOCK=true` the route should report `connected=true` / `logged_in=true`.
- `backend-hormonia/app/config/settings/integrations.py` — important operational constraint: `WHATSAPP_WUZAPI_TOKEN` is still startup-required outside test mode even when the mock client is used.
- `frontend-hormonia/public/config.js` + `src/lib/runtime-config.ts` + `src/lib/config-initializer.tsx` — local dev does not rely on remote runtime config fetch; Vite launch envs drive API/WS wiring directly, so process-launch env correctness matters.

## Constraints

- **Requirement scope:** S06 supports active **R047** and **R053**. It rechecks mounted behavior for already-validated **R050**, but it should not drift into **R051** or **R052** work.
- **Backend startup still needs WuzAPI token plumbing:** `WHATSAPP_WUZAPI_USE_MOCK=true` is not enough by itself; `WHATSAPP_WUZAPI_TOKEN` must still be set or startup validation fails.
- **Official unauthenticated entrypoint is `/login`, not `/admin/login`:** the outer route gate in `routeDefinitions.tsx` enforces that before the admin sub-app is mounted.
- **Frontend requests are cookie-only now:** `apiClient.getSessionHeaders()` returns `{}`, so any S06 smoke that relies on `X-Session-ID` or session-as-Bearer is proving the wrong contract.
- **The auth Playwright spec is fixture-gated:** it skips if `E2E_SESSION_FIRST_*` env vars are missing, so S06 must prepare the seeded proof user and reset token first.
- **Local process env matters more than runtime fetches in dev:** Vite dev mode uses `import.meta.env`/runtime-config directly; wrong launch vars can make the browser fail while backend truth probes stay green.
- **Broad repo-wide verification is unsafe noise:** unresolved merge markers still exist in non-canonical files such as `backend-hormonia/app/dependencies/auth_legacy_firebase.py` and in several historical test files, so “run all tests” is not a trustworthy S06 closeout strategy.
- **Current workspace prerequisites are already favorable:** `backend-hormonia/.venv` exists locally, `frontend-hormonia/node_modules` exists locally, and `frontend-hormonia/public/config.js` is present, so S06 can assume standard local execution rather than bootstrapping tooling first.

## Common Pitfalls

- **Using stale admin E2E suites as the acceptance baseline** — many older files still assume `/admin/login`, standalone admin auth, or mock auth. Use the canonical hard-cut auth spec plus thin route smoke instead.
- **Launching the backend with mock WuzAPI but no token** — startup validation will fail before auth proof starts. Supply a dummy local token together with `WHATSAPP_WUZAPI_USE_MOCK=true`.
- **Forgetting to blank Firebase vars at process launch** — S06 is specifically a mounted no-Firebase proof, so blank `FIREBASE_ADMIN_*` and `VITE_FIREBASE_*` in the live server/browser processes, not just in tests.
- **Persisting proof credentials or reset tokens in repo artifacts** — keep seeded-user values masked and ephemeral in `/tmp`, following the M003/S05 pattern.
- **Running broad pytest/vitest/playwright sweeps after a red signal** — historical failures from conflict markers or stale suites will bury the actual mounted-runtime issue and make the proof less honest.
- **Asserting the wrong `/whatsapp` success state** — the meaningful smoke is a successful mocked WuzAPI status fetch and route render, not deep message-sending coverage.

## Open Risks

- The existing browser hard-cut proof was previously red at the real `/login` → `/dashboard` transition even while direct backend login probes were green. That exact browser/bootstrap seam may still be the first live blocker S06 hits.
- `/whatsapp` is sensitive to process env and mock status behavior. If the backend boots without the expected mock/token contract, the page can render a disconnected/unavailable state that looks like a frontend problem but is really stack boot drift.
- The seeded proof user must have real admin access. A non-admin user would make `/dashboard` look green while `/admin` fails for the wrong reason.
- Unresolved conflict markers in dormant or compatibility-only files are still present. If S06 command scope drifts into broad compile or test collection, those unrelated failures will contaminate the slice proof.
- The admin route stack still has two layers (`ProtectedRoute` and `AdminProtectedRoute`) with different login redirects. If browser smoke targets the wrong entrypoint, it can misdiagnose a routing decision as an auth regression.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | available — install with `npx skills add wshobson/agents@fastapi-templates` |
| React | `vercel-labs/agent-skills@vercel-react-best-practices` | available — install with `npx skills add vercel-labs/agent-skills@vercel-react-best-practices` |
| Playwright | `currents-dev/playwright-best-practices-skill@playwright-best-practices` | available — install with `npx skills add currents-dev/playwright-best-practices-skill@playwright-best-practices` |
| Redis | `mindrally/skills@redis-best-practices` | available — install with `npx skills add mindrally/skills@redis-best-practices` |

## Sources

- S06’s active requirement target is the mounted no-Firebase runtime proof supporting **R047** and **R053**, while **R051** and **R052** remain later-milestone work. (source: preloaded `.gsd/REQUIREMENTS.md` and M004 roadmap/context)
- The official backend/frontend proof contract after S04/S05 explicitly leaves assembled-stack replay for S06 and says the remaining residue is now smaller and more honest. (source: preloaded `S04-SUMMARY.md`, `S05-SUMMARY.md`)
- The exact local-stack launch contract with blank Firebase vars, local ports, and mocked WuzAPI was already documented during the earlier hard cut. (source: `.gsd/milestones/M002/slices/S04/S04-PROOF.md`)
- The canonical browser auth acceptance already exists and is intended as the operator-facing proof for session-first staff auth. (source: `frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts`, `frontend-hormonia/tests/e2e/README.md`, `frontend-hormonia/tests/e2e/SETUP_INSTRUCTIONS.md`)
- The backend operational no-Firebase surfaces are already pinned by focused tests for readiness, system health, validation, initialization, and public config. (source: `backend-hormonia/tests/api/v2/test_system_auth_hard_cut_operational.py`)
- The mounted backend auth contract is already covered by focused integration tests for local auth core flow and hard-cut end-to-end behavior. (source: `backend-hormonia/tests/integration/test_local_auth_core_flow.py`, `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py`)
- The shipped app routes `/dashboard`, `/whatsapp`, and `/admin/*` through the canonical protected routing layer, which makes `/login` the real unauthenticated entrypoint. (source: `frontend-hormonia/src/app/routes/routeDefinitions.tsx`, `frontend-hormonia/src/features/auth/ProtectedRoute.tsx`)
- Frontend shared HTTP requests no longer emit legacy session headers. (source: `frontend-hormonia/src/lib/api-client/core.ts`, `frontend-hormonia/src/services/whatsapp/WhatsAppService.ts`)
- `/whatsapp` depends first on the WuzAPI monitoring status endpoint, and the mock client returns connected/logged-in state after `connect()`. (source: `frontend-hormonia/src/features/whatsapp/WhatsAppDashboard.tsx`, `backend-hormonia/app/api/v2/monitoring/wuzapi.py`, `backend-hormonia/app/integrations/wuzapi/mock.py`)
- Backend startup still requires `WHATSAPP_WUZAPI_TOKEN` outside test mode even when the mock client is enabled. (source: `backend-hormonia/app/config/settings/integrations.py`)
- Local dev frontend wiring depends on Vite launch envs rather than a live runtime-config fetch. (source: `frontend-hormonia/public/config.js`, `frontend-hormonia/src/lib/runtime-config.ts`, `frontend-hormonia/src/lib/config-initializer.tsx`)
- Replay-safe proof seeding should stay in `/tmp`, using the backend virtualenv and no persisted credentials/tokens in repo artifacts. (source: `.gsd/milestones/M003/slices/S05/tasks/T02-SUMMARY.md`)
- Broad verification is noisy and unsafe because unresolved merge-conflict markers remain in historical/non-canonical files. (source: repo search with `rg '^<<<<<<<|^=======|^>>>>>>>'` over `frontend-hormonia`, `backend-hormonia`, `.gsd`)
- Optional external skills were discovered for FastAPI, React, Playwright, and Redis, but none are currently installed as project-specific skills for this slice. (source: `npx skills find "FastAPI"`, `npx skills find "React"`, `npx skills find "Playwright"`, `npx skills find "Redis"`)
