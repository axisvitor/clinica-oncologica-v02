# M004/S01 — Research

**Date:** 2026-03-14

## Summary

S01 now closes on an executable residue boundary instead of a recommendation. `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` and `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` are the official truth for the six runtime residue classes inside the `backend` and `frontend` scopes: `firebase_uid`, `root_legacy_session`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`, and `firebase_narrative`. Final reruns on 2026-03-14 ended with `RESULT: --report all OK` and `RESULT: --check all OK`; the map below mirrors that exact output.

The boundary is intentionally narrow. It covers the official auth/session runtime plus the explicit compatibility islands still shipped in `backend-hormonia/app` and `frontend-hormonia/src`. It does **not** treat repo-wide Firebase or `/session` strings as failures. Schema/model residue, historical docs/tests, and unrelated vendor/public session strings stay excluded so S02–S05 can cut live runtime behavior instead of fighting noise.

Downstream ownership is now explicit: S02 already converged the canonical backend auth/session helper path, so the backend `firebase_uid` hotspots left in this report are fallback-only helper passthroughs plus deliberate legacy/admin seams rather than happy-path blockers. S03 removes official frontend emission of `X-Session-ID`, `Authorization: Bearer <session_id>`, and websocket `session_id` query fallback; S04 retires the root `/session/*` island and backend acceptance of the legacy auth/session inputs; S05 removes the remaining adjacent/helper/admin `firebase_uid` and Firebase-narrative residue that survives after the transport cut.

## Recommendation

Treat the handoff pack as a three-part contract:

1. **Executable boundary:** `runtime-residue-allowlist.json` and `verify-runtime-residue.sh` define the approved files, anchors, scopes, and exclusions.
2. **Readable map:** this research artifact explains why each approved hotspot is still live, which slice owns its removal, and which paths are intentionally excluded.
3. **Change discipline:** when a future slice removes a hotspot, moves an approved anchor, or narrows the scope, update the allowlist, this file, `S01-SUMMARY.md`, and `S01-UAT.md` in the same change. A green verifier with stale docs is still drift.

`--report all` is the inventory surface; `--check all` is the gate. If `--check` fails because a hotspot moved or disappeared, treat that as bookkeeping drift first and decide whether the removal was intentional before changing code or the allowlist. After S02, a flat backend `firebase_uid` count does not imply the helper path stayed unchanged: the verifier measures surviving literals, so semantic shrinkage can mean relabeling fallback-only hotspots and updating the handoff even when the inventory still has the same files.

## Finalized Residue Boundary

### Official runtime surfaces in scope

The frozen S01 failure surface is the union of the category roots defined in `runtime-residue-allowlist.json`, filtered by the scope defaults in that file:

- `backend` scope: Python sources under the approved auth/session/runtime roots in `backend-hormonia/app`
- `frontend` scope: TypeScript/TSX sources under the approved auth/api/websocket/admin roots in `frontend-hormonia/src` plus the shared admin types package
- Proof artifacts: the slice-local allowlist, verifier, and subprocess regression harness that explain and enforce the boundary

### Retained compatibility islands inside that boundary

These strings are still intentionally live in S01 and therefore approved rather than treated as surprise drift:

- The root legacy `/session/*` router mount and `backend-hormonia/app/routers/auth_session.py`
- Backend acceptance of `X-Session-ID`, `Authorization: Bearer <session_id>`, and websocket `session_id` query fallback while the runtime is still converging
- Frontend emission of `X-Session-ID`, `Authorization: Bearer <session_id>`, and websocket `session_id` query fallback while the official client is still pre-cutover
- `firebase_uid` compatibility keys in backend auth/session/cache helpers and official admin/client type surfaces
- Firebase-era operational comments/narrative that still appear in shipped runtime files

### Out-of-scope exclusions (`runtime-residue-allowlist.json`)

| Exclusion id | Why excluded | Paths |
|---|---|---|
| `schema_model_residue` | Schema/model residue belongs to M005, not the S01 official runtime failure surface. | `backend-hormonia/app/models/**`, `backend-hormonia/app/schemas/**` |
| `historical_docs_tests` | Historical docs, generated docs, and tests may mention the legacy contract without representing live runtime drift. | `backend-hormonia/tests/**`, `backend-hormonia/docs/**`, `backend-hormonia/app/api/v2/routers/docs/**`, `frontend-hormonia/tests/**`, `frontend-hormonia/src/**/__tests__/**`, `frontend-hormonia/src/**/*.test.ts`, `frontend-hormonia/src/**/*.test.tsx`, `frontend-hormonia/src/**/*.spec.ts`, `frontend-hormonia/src/**/*.spec.tsx`, `docs/**` |
| `vendor_or_unrelated_session_strings` | WuzAPI, quiz/public session strings, mocks, and other unrelated clients are not the staff auth/session runtime boundary frozen in S01. | `backend-hormonia/app/api/v2/monitoring/wuzapi.py`, `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py`, `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py`, `frontend-hormonia/src/features/whatsapp/**`, `frontend-hormonia/src/services/whatsapp/**`, `frontend-hormonia/src/mocks/**`, `frontend-hormonia/src/monitoring/**` |

## Approved Hotspot Inventory

The lists below use the exact category ids and scope names from `runtime-residue-allowlist.json` and `verify-runtime-residue.sh`.

### `firebase_uid`

**Meaning:** compatibility-oriented `firebase_uid` residue that still survives in fallback-only helper paths, legacy/root-session seams, and official admin compatibility types.

- `backend` — 14 files / 133 matching lines
  - `backend-hormonia/app/api/v2/auth_session_shared.py` (5)
  - `backend-hormonia/app/api/v2/patients_shared_helpers.py` (3)
  - `backend-hormonia/app/api/v2/patients_utils.py` (4)
  - `backend-hormonia/app/api/v2/routers/admin/utils.py` (1)
  - `backend-hormonia/app/api/v2/routers/auth.py` (7)
  - `backend-hormonia/app/api/v2/user_cache_shared.py` (8)
  - `backend-hormonia/app/core/redis_manager/session_cache.py` (8)
  - `backend-hormonia/app/dependencies/auth_dependencies.py` (25)
  - `backend-hormonia/app/dependencies/auth_legacy_firebase.py` (20)
  - `backend-hormonia/app/dependencies/auth_role_dependencies.py` (4)
  - `backend-hormonia/app/dependencies/auth_session_cache.py` (24)
  - `backend-hormonia/app/dependencies/auth_session_contract.py` (4)
  - `backend-hormonia/app/dependencies/auth_user_adapter.py` (1)
  - `backend-hormonia/app/routers/auth_session.py` (19)
- `frontend` — 4 files / 6 matching lines
  - `frontend-hormonia/shared-types/src/admin.ts` (1)
  - `frontend-hormonia/src/lib/api-client/admin.ts` (1)
  - `frontend-hormonia/src/lib/api-client/normalizers.ts` (3)
  - `frontend-hormonia/src/types/admin.ts` (1)
- **Post-S02 interpretation:** the backend count stays flat because the verifier measures surviving literals, not happy-path lookup order. The canonical helper family is green; the `auth_dependencies.py`, `auth_session_contract.py`, `auth_session_cache.py`, `auth_session_shared.py`, and `user_cache_shared.py` hits now represent compatibility-only fallback or passthrough behavior instead of canonical identity selection.
- **Temporarily preserved in S01:** the remaining backend hits also include deliberate root `/session/*`, legacy Firebase auth, adjacent patient/admin helpers, cache serialization seams, and compatibility metadata that later slices still need visible; the frontend still exposes admin/client compatibility fields.
- **Cut owner:** S04 removes the root `/session/*`-bound backend Firebase seams as part of transport retirement. S05 removes the remaining fallback-only helper, adjacent/backend-helper, and frontend admin/type compatibility residue that survives after the transport cut.

### `root_legacy_session`

**Meaning:** the root `/session/*` compatibility island that still ships beside `/api/v2/auth/*`.

- `backend` — 2 files / 8 matching lines
  - `backend-hormonia/app/core/router_registry.py` (1)
  - `backend-hormonia/app/routers/auth_session.py` (7)
- `frontend` — no approved surfaces
- **Temporarily preserved in S01:** the mount and router stay live so later slices can retire them deliberately instead of assuming they are already dead.
- **Cut owner:** S04. Keep this island stable through S02/S03 while the canonical backend/frontend contract is proven, then retire, reject, or tombstone it explicitly.

### `x_session_id`

**Meaning:** legacy `X-Session-ID` emission and acceptance across backend helpers and frontend clients.

- `backend` — 16 files / 28 matching lines
  - `backend-hormonia/app/api/v2/_quiz_shared.py` (1)
  - `backend-hormonia/app/api/v2/auth_session_shared.py` (1)
  - `backend-hormonia/app/api/v2/messages/helpers.py` (1)
  - `backend-hormonia/app/api/v2/patients_utils.py` (1)
  - `backend-hormonia/app/api/v2/routers/admin/dependencies.py` (2)
  - `backend-hormonia/app/api/v2/routers/auth.py` (2)
  - `backend-hormonia/app/api/v2/routers/enhanced_reports.py` (1)
  - `backend-hormonia/app/api/v2/routers/localization.py` (3)
  - `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/_shared.py` (1)
  - `backend-hormonia/app/api/v2/routers/patients/base.py` (1)
  - `backend-hormonia/app/api/v2/routers/reports.py` (1)
  - `backend-hormonia/app/api/v2/routers/tasks/dependencies.py` (2)
  - `backend-hormonia/app/api/v2/templates_shared.py` (3)
  - `backend-hormonia/app/api/websockets.py` (1)
  - `backend-hormonia/app/dependencies/auth_dependencies.py` (2)
  - `backend-hormonia/app/routers/auth_session.py` (5)
- `frontend` — 3 files / 5 matching lines
  - `frontend-hormonia/src/lib/api-client/auth.ts` (1)
  - `frontend-hormonia/src/lib/api-client/core.ts` (3)
  - `frontend-hormonia/src/lib/api-client/enhanced-analytics.ts` (1)
- **Temporarily preserved in S01:** the official client still emits the header and the backend still accepts it in multiple helper families.
- **Cut owner:** S03 removes frontend emission first. S04 removes backend acceptance and any remaining docstring/helper spread once the official app is off the header.

### `session_bearer_fallback`

**Meaning:** `Authorization: Bearer <session_id>` fallback still emitted or accepted by shipped helpers and clients.

- `backend` — 8 files / 11 matching lines
  - `backend-hormonia/app/api/v2/_quiz_shared.py` (1)
  - `backend-hormonia/app/api/v2/auth_session_shared.py` (2)
  - `backend-hormonia/app/api/v2/routers/admin/dependencies.py` (2)
  - `backend-hormonia/app/api/v2/routers/auth.py` (1)
  - `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/_shared.py` (1)
  - `backend-hormonia/app/api/v2/routers/tasks/dependencies.py` (1)
  - `backend-hormonia/app/api/v2/templates_shared.py` (2)
  - `backend-hormonia/app/dependencies/auth_session_contract.py` (1)
- `frontend` — 3 files / 4 matching lines
  - `frontend-hormonia/src/lib/api-client/auth.ts` (1)
  - `frontend-hormonia/src/lib/api-client/core.ts` (2)
  - `frontend-hormonia/src/lib/api-client/enhanced-analytics.ts` (1)
- **Temporarily preserved in S01:** the frontend still emits session-as-Bearer and the backend still resolves it.
- **Cut owner:** S03 removes frontend Bearer-as-session emission. S04 removes backend acceptance and any explanatory residue that still advertises the fallback.

### `websocket_session_id_query`

**Meaning:** websocket `session_id` query fallback still emitted on the client and accepted on the server.

- `backend` — 1 file / 4 matching lines
  - `backend-hormonia/app/api/websockets.py` (4)
- `frontend` — 2 files / 6 matching lines
  - `frontend-hormonia/src/hooks/useWebSocket.ts` (3)
  - `frontend-hormonia/src/lib/websocket.ts` (3)
- **Temporarily preserved in S01:** both sides still know how to speak the fallback, so this cannot be cut safely on only one side.
- **Cut owner:** S03 removes frontend query emission. S04 removes backend acceptance after the browser path is proven canonical.

### `firebase_narrative`

**Meaning:** Firebase-era comments and operational narrative still present in shipped auth/session surfaces.

- `backend` — 1 file / 29 matching lines
  - `backend-hormonia/app/routers/auth_session.py` (29)
- `frontend` — 5 files / 12 matching lines
  - `frontend-hormonia/src/AdminApp.tsx` (2)
  - `frontend-hormonia/src/features/admin/AdminSessionManager.tsx` (5)
  - `frontend-hormonia/src/hooks/auth/useSessionManagement.ts` (3)
  - `frontend-hormonia/src/types/admin.ts` (1)
  - `frontend-hormonia/src/utils/init-validator.ts` (1)
- **Temporarily preserved in S01:** these files still tell the old Firebase story even where runtime behavior has already partially moved.
- **Cut owner:** S04 removes the backend narrative when the root `/session/*` island is retired. S05 removes the remaining frontend/admin narrative and type commentary once the canonical runtime cut is complete.

## Cut Order Snapshot For S02–S05

1. **S02 — backend canonical identity/session cut**
   - Removed backend-happy-path `firebase_uid` dependence from canonical auth/session/cache flows while leaving fallback-only helper residue visible in the guard.
   - Intentionally did **not** delete `/session/*`, `X-Session-ID`, Bearer-as-session, or websocket query fallback yet; those remain explicit transport residue for later slices.
2. **S03 — official frontend canonical contract cut**
   - Remove frontend emission of `X-Session-ID`, `Authorization: Bearer <session_id>`, and websocket `session_id` query fallback.
   - Leave backend acceptance and root `/session/*` stable until S04 retires them deliberately.
3. **S04 — retire legacy auth/session surfaces**
   - Remove or tombstone the root `/session/*` island.
   - Remove backend acceptance of `X-Session-ID`, session-as-Bearer, and websocket query fallback.
   - Collapse backend Firebase narrative in `auth_session.py` as part of that retirement.
4. **S05 — remove adjacent Firebase runtime residue**
   - Remove remaining `firebase_uid` compatibility in adjacent helpers/types/admin surfaces.
   - Remove the remaining frontend/admin Firebase narrative and operational semantics.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Scoped runtime residue inventory and drift detection | `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` | Already emits the approved boundary by category/scope and fails on unexpected files or moved anchors. |
| Machine-readable hotspot ownership | `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` | Keeps file/anchor bookkeeping explicit so later cleanup updates the contract instead of relying on memory. |
| Failure-path proof for the guardrail | `backend-hormonia/tests/unit/test_runtime_residue_guard.py` | Proves unexpected residue and moved hotspots fail with category/path/anchor diagnostics. |
| Historical pattern for scoped residue gates | `.gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh` and `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` | These are the prior milestones’ working examples of targeted, low-noise cleanup guards. |

## Existing Code and Patterns

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — authoritative category ids, scope names, approved hotspots, anchors, and exclusions.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — authoritative `--report` / `--check` surface; use this before reading the repo manually.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — authoritative proof that the guard emits inspectable `unexpected_file=` and `moved_hotspot=` failures.
- `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/dependencies/auth_*`, and `backend-hormonia/app/core/redis_manager/session_cache.py` — the backend happy-path/auth-session core that S02 must canonicalize away from `firebase_uid`.
- `frontend-hormonia/src/lib/api-client/*.ts`, `frontend-hormonia/src/lib/websocket.ts`, and `frontend-hormonia/src/hooks/useWebSocket.ts` — the official frontend contract that S03 must stop emitting through header/bearer/query fallbacks.
- `backend-hormonia/app/routers/auth_session.py` and `backend-hormonia/app/core/router_registry.py` — the retained root `/session/*` compatibility island that S04 must retire explicitly.
- `frontend-hormonia/src/types/admin.ts`, `frontend-hormonia/shared-types/src/admin.ts`, `frontend-hormonia/src/lib/api-client/admin.ts`, and the Firebase narrative files — adjacent/admin residue that S05 must remove once the canonical runtime path is already green.

## Constraints

- S01 is an enabling slice only. It freezes the runtime boundary; it does not prove runtime convergence by itself.
- The official runtime boundary is scoped by the allowlist. Repo-wide Firebase or `/session` greps are intentionally out of scope because they create false positives.
- Multiple live backend resolver families still disagree on source precedence. Until S02/S04 land, the verifier must keep all approved header/bearer/query hotspots visible.
- Websocket query fallback is two-sided. Do not remove only the backend or only the frontend half and then hand-wave the rest.
- Anything left for M005 must be schema/migration residue, not ambiguous live runtime behavior.

## Common Pitfalls

- **Updating the allowlist but not the docs** — later slices need the readable map and cut owner, not just a green script.
- **Cutting frontend fallback and backend fallback in the same unbounded pass** — S03 and S04 split those responsibilities for a reason; keep the blast radius small.
- **Treating all `firebase_uid` files as equal** — some are canonical auth/session blockers for S02, others are adjacent/admin cleanups for S05.
- **Broadening the failure scope to docs/tests/vendor code** — that makes the guard noisy and hides real runtime drift.

## Open Risks

- Resolver drift can still hide behind non-auth V2 helpers until S04 removes the acceptance paths, because `X-Session-ID` and Bearer session fallback have spread beyond the obvious auth router.
- `firebase_uid` still bridges cache/session/user helpers; if S02 only patches the login router, the canonical identity path stays ambiguous.
- Root `/session/*` retirement is deeper than a route delete: `auth_session.py` still mixes session validation/logout with Firebase-bearer behavior and narrative residue.
- Frontend admin types and narrative can make the system look Firebase-shaped even after the happy path is canonical unless S05 closes them deliberately.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | available — `npx skills add wshobson/agents@fastapi-templates` |
| React | `vercel-labs/agent-skills@vercel-react-best-practices` | available — `npx skills add vercel-labs/agent-skills@vercel-react-best-practices` |
| Playwright | `currents-dev/playwright-best-practices-skill@playwright-best-practices` | available — `npx skills add currents-dev/playwright-best-practices-skill@playwright-best-practices` |

## Sources

- The authoritative hotspot definitions, exclusions, and anchors now live in `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` (source: [`.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`](.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json))
- The readable inventory and drift gate now live in `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` (source: [`.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`](.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh))
- Failure-path diagnostics are pinned by the subprocess regression harness in `backend-hormonia/tests/unit/test_runtime_residue_guard.py` (source: [`backend-hormonia/tests/unit/test_runtime_residue_guard.py`](backend-hormonia/tests/unit/test_runtime_residue_guard.py))
- M004 slice ordering and ownership come from the milestone roadmap (source: [`.gsd/milestones/M004/M004-ROADMAP.md`](.gsd/milestones/M004/M004-ROADMAP.md))
- The official runtime motivation and non-goals come from the milestone context (source: [`.gsd/milestones/M004/M004-CONTEXT.md`](.gsd/milestones/M004/M004-CONTEXT.md))
