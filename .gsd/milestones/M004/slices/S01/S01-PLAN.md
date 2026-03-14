# S01: Guardrails do corte canônico de runtime

**Goal:** Freeze an executable, scoped residue boundary for the official auth/session runtime so later M004 slices can remove Firebase-era behavior without losing sight of what is still live.
**Demo:** A future agent can run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all` to see exactly which official runtime surfaces still carry `firebase_uid`, root legacy `/session/*`, `X-Session-ID`, session-as-Bearer fallback, websocket `session_id` query fallback, and Firebase narrative residue; and can run `--check all` plus the verifier regression test to fail when new residue appears or approved hotspots drift without the slice boundary being updated.

## Requirement Coverage

- Supported by this slice: **R047** — Firebase sai de vez do runtime oficial.
- Supported by this slice: **R048** — Auth/sessão converge para um contrato canônico único.
- Supported by this slice: **R049** — A identidade canônica deixa de depender de `firebase_uid` no runtime.
- Supported by this slice: **R050** — O frontend oficial usa apenas o contrato canônico sem resíduo funcional de Firebase.
- Not claimed here: S01 is an enabling slice only; runtime convergence itself still lands in S02–S06.

## Must-Haves

- Add a slice-local verifier plus a machine-readable allowlist that reports and guards the known official-runtime residue classes: `firebase_uid`, root legacy `/session/*`, `X-Session-ID`, session-as-Bearer fallback, websocket `session_id` query fallback, and Firebase narrative/comments in shipped auth/session surfaces.  
  _Supports: R047, R048, R049, R050_
- Keep the guardrail scoped to the official runtime boundary (`backend-hormonia/app`, `frontend-hormonia/src`, and slice-local proof artifacts) with explicit exclusions for schema/model residue, unrelated vendor/session strings, and historical docs/tests so the signal stays actionable.  
  _Supports: R047, R048, R049, R050_
- Back the verifier with a real regression test that proves approved compatibility islands pass while newly introduced header/bearer/query/comment residue fails loudly and names the category/file that drifted.  
  _Supports: R047, R048, R049, R050_
- Publish the approved official surfaces, retained compatibility islands, out-of-scope exclusions, and downstream cut order in slice artifacts so S02–S05 can update one boundary contract instead of reopening repo-wide discovery.  
  _Supports: R047, R048, R049, R050_

## Proof Level

- This slice proves: contract
- Real runtime required: no
- Human/UAT required: no

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`

## Observability / Diagnostics

- Runtime signals: `verify-runtime-residue.sh --report <backend|frontend|all>` emits per-category file/count output for approved residue plus named drift notes for newly detected surfaces.
- Inspection surfaces: `runtime-residue-allowlist.json`, `S01-RESEARCH.md`, `S01-SUMMARY.md`, `S01-UAT.md`, the verifier stdout/exit code, and `tests/unit/test_runtime_residue_guard.py`.
- Failure visibility: `--check` fails with the residue category, unexpected file, or moved approved hotspot that caused drift, so the next agent knows whether the problem is a real reintroduction or stale boundary bookkeeping.
- Redaction constraints: output is limited to source paths, categories, static counts, and verification commands; never emit session tokens, cookies, headers with live values, or user data.

## Integration Closure

- Upstream surfaces consumed: `backend-hormonia/app/core/router_registry.py`, `backend-hormonia/app/routers/auth_session.py`, `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/api/websockets.py`, `backend-hormonia/app/core/redis_manager/session_cache.py`, `backend-hormonia/app/api/v2/user_cache_shared.py`, `frontend-hormonia/src/app/providers/AuthContext.tsx`, `frontend-hormonia/src/lib/api-client/core.ts`, `frontend-hormonia/src/lib/api-client/auth.ts`, `frontend-hormonia/src/lib/api-client/enhanced-analytics.ts`, `frontend-hormonia/src/lib/websocket.ts`, `frontend-hormonia/src/hooks/useWebSocket.ts`, `frontend-hormonia/src/hooks/auth/useSessionManagement.ts`, `frontend-hormonia/src/features/admin/AdminSessionManager.tsx`, `frontend-hormonia/src/AdminApp.tsx`, `frontend-hormonia/src/utils/init-validator.ts`, `frontend-hormonia/src/types/admin.ts`, and `frontend-hormonia/shared-types/src/admin.ts`.
- New wiring introduced in this slice: a machine-readable residue allowlist, a scoped `--report` / `--check` verifier, and a regression test that binds the allowlist to expected pass/fail behavior.
- What remains before the milestone is truly usable end-to-end: S02 must converge backend identity/session onto `user_id`, S03 must cut the official frontend over to the canonical contract, S04 must retire or tombstone legacy surfaces, S05 must remove adjacent Firebase runtime residue, and S06 must prove the assembled no-Firebase stack.

## Tasks

- [ ] **T01: Build the scoped runtime-residue verifier and regression harness** `est:55m`
  - Why: The slice only becomes real once the residue boundary is executable and can fail on drift; later artifact work should close against a living contract, not prose.
  - Files: `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`, `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`, `backend-hormonia/tests/unit/test_runtime_residue_guard.py`
  - Do: Create a machine-readable allowlist grouped by residue class and official-runtime scope; implement `verify-runtime-residue.sh` with `--report` / `--check` and `backend` / `frontend` / `all` scopes, explicit out-of-scope exclusions, deterministic counts, and named drift failures; then add a subprocess-style pytest regression that proves approved residue fixtures pass while new unallowlisted residue fails in the expected category.
  - Verify: `(cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py) && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
  - Done when: the verifier and regression test are green, `--report` enumerates the approved live residue by category/file/count, and `--check` fails only on real scope drift.
- [ ] **T02: Publish the official-runtime residue map and slice handoff** `est:45m`
  - Why: S02–S05 need one durable map of approved official surfaces, retained compat islands, and exclusions; the script alone is not enough for downstream execution.
  - Files: `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`, `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`, `.gsd/milestones/M004/slices/S01/S01-UAT.md`, `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`, `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`
  - Do: Update `S01-RESEARCH.md` with the finalized category-by-category residue map and the explicit official-versus-compat boundary, write `S01-SUMMARY.md` with the downstream cut order and inherited verification commands, write `S01-UAT.md` with the reviewer checklist for new residue and stale allowlist drift, and reconcile all three artifacts against the verifier output so later slices update one shared boundary.
  - Verify: `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
  - Done when: the slice artifacts name each approved hotspot and exclusion explicitly, the handoff tells S02–S05 what must be removed versus temporarily retained, and the verifier stays green against the published boundary.

## Files Likely Touched

- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`
- `.gsd/milestones/M004/slices/S01/S01-UAT.md`
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py`
