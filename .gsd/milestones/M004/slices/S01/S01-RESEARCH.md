# M004/S01 — Research

**Date:** 2026-03-14

## Summary

S01 now freezes a smaller, more honest runtime boundary than it did at original closeout. The verifier remains the source of truth, but after S03 the live `frontend` scope is no longer an inventory of approved legacy hotspots — it is a zero-approved reintroduction guard. Latest reruns ended with `RESULT: --report frontend OK`, `RESULT: --check frontend OK`, and `RESULT: --report all OK`; the combined report now shows approved residue only in `backend`.

That change matters because the slice boundary is no longer symmetrical. The official frontend loop has converged on the canonical session-first contract, so the residue categories that used to span both scopes are now backend-owned only: `firebase_uid`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`, and `firebase_narrative`. The `frontend` roots stay in the allowlist with empty approved sets so later work fails loudly if any of those seams reappear.

## Recommendation

Treat the handoff pack as a four-part contract:

1. **Executable boundary:** `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` and `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` define the approved categories, scopes, roots, exclusions, and hotspot anchors.
2. **Readable map:** this research artifact explains the live post-S03 meaning of each category and who owns the remaining cuts.
3. **Condensed handoff:** `S01-SUMMARY.md` is the downstream briefing for slices that only need the current state, not the full rationale.
4. **Reviewer script:** `S01-UAT.md` is the replay checklist; when the boundary changes, update it in the same change as the allowlist and summaries.

Do not delete the `frontend` scopes just because they are empty. Keeping the scope roots with `approved: []` preserves the category vocabulary and turns any frontend reintroduction into an explicit `unexpected_file=` or `moved_hotspot=` failure instead of silent drift.

## Finalized Residue Boundary

### Official runtime surfaces in scope

The frozen S01 failure surface is the union of the category roots defined in `runtime-residue-allowlist.json`, filtered by the scope defaults in that file:

- `backend` scope: Python sources under the approved auth/session/runtime roots in `backend-hormonia/app`
- `frontend` scope: TypeScript/TSX sources under the approved auth/api/websocket/admin roots in `frontend-hormonia/src` plus the shared admin types package
- Proof artifacts: the slice-local allowlist, verifier, and subprocess regression harness that explain and enforce the boundary

### Retained compatibility islands inside that boundary

These strings are still intentionally live and therefore approved rather than treated as surprise drift:

- The root legacy `/session/*` router mount and `backend-hormonia/app/routers/auth_session.py`
- Backend acceptance of `X-Session-ID`, `Authorization: Bearer <session_id>`, and websocket `session_id` query fallback while transport retirement is still pending
- Backend-only `firebase_uid` compatibility keys in auth/session/cache helpers plus adjacent patient/admin serialization seams
- Backend Firebase-era operational narrative in `backend-hormonia/app/routers/auth_session.py`
- The `frontend` scope itself, but with **no approved residue** after S03; it now exists only to catch regressions

### Out-of-scope exclusions (`runtime-residue-allowlist.json`)

| Exclusion id | Why excluded | Paths |
|---|---|---|
| `schema_model_residue` | Schema/model residue belongs to M005, not the S01 official runtime failure surface. | `backend-hormonia/app/models/**`, `backend-hormonia/app/schemas/**` |
| `historical_docs_tests` | Historical docs, generated docs, and tests may mention the legacy contract without representing live runtime drift. | `backend-hormonia/tests/**`, `backend-hormonia/docs/**`, `backend-hormonia/app/api/v2/routers/docs/**`, `frontend-hormonia/tests/**`, `frontend-hormonia/src/**/__tests__/**`, `frontend-hormonia/src/**/*.test.ts`, `frontend-hormonia/src/**/*.test.tsx`, `frontend-hormonia/src/**/*.spec.ts`, `frontend-hormonia/src/**/*.spec.tsx`, `docs/**` |
| `vendor_or_unrelated_session_strings` | WuzAPI, quiz/public session strings, mocks, and other unrelated clients are not the staff auth/session runtime boundary frozen in S01. | `backend-hormonia/app/api/v2/monitoring/wuzapi.py`, `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py`, `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py`, `frontend-hormonia/src/features/whatsapp/**`, `frontend-hormonia/src/services/whatsapp/**`, `frontend-hormonia/src/mocks/**`, `frontend-hormonia/src/monitoring/**` |

## Approved Hotspot Inventory

The lists below use the exact category ids and scope names from `runtime-residue-allowlist.json` and `verify-runtime-residue.sh`.

### `firebase_uid`

**Meaning:** compatibility-oriented `firebase_uid` residue retained in backend fallback helpers and legacy/root-session seams after S03 removed the official frontend admin/type baggage.

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
- `frontend` — no approved residue
- **Post-S03 interpretation:** S02 already canonicalized the backend helper families; S03 removed the official frontend admin/type compatibility baggage. The remaining hits are now entirely backend-owned compatibility, fallback, serialization, and legacy-route residue.
- **Cut owner:** S04 removes the root `/session/*`-bound backend Firebase seams that disappear with transport retirement. S05 removes the remaining backend fallback-only and adjacent/admin `firebase_uid` residue that survives after the transport cut.

### `root_legacy_session`

**Meaning:** the root `/session/*` compatibility island that still ships beside `/api/v2/auth/*`.

- `backend` — 2 files / 8 matching lines
  - `backend-hormonia/app/core/router_registry.py` (1)
  - `backend-hormonia/app/routers/auth_session.py` (7)
- `frontend` — no approved surfaces
- **Temporarily preserved in S01:** this island stays live so S04 can retire, reject, or tombstone it explicitly instead of assuming it is already dead.
- **Cut owner:** S04.

### `x_session_id`

**Meaning:** legacy `X-Session-ID` residue retained in backend acceptance/helpers after S03 removed official frontend emission; the `frontend` scope is now a reintroduction guard.

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
- `frontend` — no approved residue
- **Post-S03 interpretation:** the official frontend no longer emits the header. Every approved hit in this category is now backend acceptance, helper spread, or compatibility documentation.
- **Cut owner:** S04 removes backend acceptance and any remaining docstring/helper spread once transport retirement lands.

### `session_bearer_fallback`

**Meaning:** `Authorization: Bearer <session_id>` residue retained in backend acceptance/helpers after S03 removed official frontend emission; the `frontend` scope is now a reintroduction guard.

- `backend` — 8 files / 11 matching lines
  - `backend-hormonia/app/api/v2/_quiz_shared.py` (1)
  - `backend-hormonia/app/api/v2/auth_session_shared.py` (2)
  - `backend-hormonia/app/api/v2/routers/admin/dependencies.py` (2)
  - `backend-hormonia/app/api/v2/routers/auth.py` (1)
  - `backend-hormonia/app/api/v2/routers/monthly_quiz_operations/_shared.py` (1)
  - `backend-hormonia/app/api/v2/routers/tasks/dependencies.py` (1)
  - `backend-hormonia/app/api/v2/templates_shared.py` (2)
  - `backend-hormonia/app/dependencies/auth_session_contract.py` (1)
- `frontend` — no approved residue
- **Post-S03 interpretation:** Bearer-as-session is now backend-only legacy behavior.
- **Cut owner:** S04 removes backend acceptance and any explanatory residue that still advertises the fallback.

### `websocket_session_id_query`

**Meaning:** websocket `session_id` query fallback retained only in backend acceptance after S03 removed official client emission; the `frontend` scope is now a reintroduction guard.

- `backend` — 1 file / 4 matching lines
  - `backend-hormonia/app/api/websockets.py` (4)
- `frontend` — no approved residue
- **Post-S03 interpretation:** the browser path is now cookie-first; the only approved fallback is the server-side acceptance path that still has to be retired deliberately.
- **Cut owner:** S04 removes backend acceptance after the assembled frontend/browser path is already proven canonical.

### `firebase_narrative`

**Meaning:** Firebase-era narrative/comments retained only in backend compatibility surfaces after S03 removed the shipped frontend auth/admin narrative residue.

- `backend` — 1 file / 29 matching lines
  - `backend-hormonia/app/routers/auth_session.py` (29)
- `frontend` — no approved residue
- **Post-S03 interpretation:** the official frontend no longer tells the Firebase story; the remaining approved narrative is concentrated in the root `/session/*` compatibility island.
- **Cut owner:** S04 collapses the backend narrative in `auth_session.py` as part of the root-route retirement.

## Cut Order Snapshot For S02–S06

1. **S02 — backend canonical identity/session cut**
   - Removed backend happy-path `firebase_uid` dependence from canonical auth/session/cache flows while leaving fallback-only helper residue visible in the guard.
2. **S03 — official frontend canonical contract cut**
   - Removed official frontend emission of `X-Session-ID`, `Authorization: Bearer <session_id>`, websocket `session_id` query fallback, browser `session_id` rehydration, and Firebase-shaped narrative/type baggage.
   - Republished the S01 boundary so `frontend` now reports `no approved residue`.
3. **S04 — retire legacy auth/session surfaces**
   - Remove or tombstone the root `/session/*` island.
   - Remove backend acceptance of `X-Session-ID`, session-as-Bearer, and websocket query fallback.
   - Collapse backend Firebase narrative in `auth_session.py` as part of that retirement.
4. **S05 — remove adjacent Firebase runtime residue**
   - Remove the remaining backend `firebase_uid` compatibility residue and adjacent runtime/helper/admin fallout that survives after transport retirement.
5. **S06 — assembled no-Firebase stack proof**
   - Replay the critical routed stack end to end with the converged backend/frontend contract and no approved runtime residue outside intentionally deferred scope.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Scoped runtime residue inventory and drift detection | `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` | Already emits the approved boundary by category/scope and fails on unexpected files or moved anchors. |
| Machine-readable hotspot ownership | `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` | Keeps file/anchor bookkeeping explicit so later cleanup updates the contract instead of relying on memory. |
| Failure-path proof for the guardrail | `backend-hormonia/tests/unit/test_runtime_residue_guard.py` | Proves unexpected residue and moved hotspots fail with category/path/anchor diagnostics. |
| Frontend cutover replay | `.gsd/milestones/M004/slices/S03/S03-UAT.md` | Encodes the focused proof/build/guard reruns that made the frontend scope go to zero-approved. |

## Existing Code and Patterns

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — authoritative category ids, scope names, roots, approved hotspots, and empty frontend approved sets after S03.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — authoritative `--report` / `--check` surface; use this before reading the repo manually.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — authoritative proof that the guard emits inspectable `unexpected_file=` and `moved_hotspot=` failures.
- `frontend-hormonia/src/lib/api-client/*.ts`, `frontend-hormonia/src/lib/websocket.ts`, `frontend-hormonia/src/hooks/useWebSocket.ts`, and `frontend-hormonia/src/types/admin.ts` — now reintroduction-guard roots rather than approved residue owners.
- `backend-hormonia/app/routers/auth_session.py` and `backend-hormonia/app/core/router_registry.py` — the retained root `/session/*` compatibility island that S04 must retire explicitly.
- `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/dependencies/auth_*`, and `backend-hormonia/app/core/redis_manager/session_cache.py` — the remaining backend `firebase_uid`/transport-heavy residue that later slices still have to remove deliberately.

## Constraints

- S01 is an enabling slice only. It freezes the runtime boundary; it does not prove the full runtime is done.
- The official runtime boundary is scoped by the allowlist. Repo-wide Firebase or `/session` greps are intentionally out of scope because they create false positives.
- Empty `frontend` approved sets are intentional after S03. Do not repopulate them casually; any new frontend hit should be treated as a regression first.
- Anything left for M005 must be schema/migration residue, not ambiguous live runtime behavior.

## Common Pitfalls

- **Updating the allowlist but not the docs** — later slices need the readable map and cut owner, not just a green script.
- **Deleting empty frontend scopes** — keeping the roots with `approved: []` is what makes reintroduction visible.
- **Treating all `firebase_uid` files as equal** — the remaining live hits are backend-owned compatibility/admin/helper residue, not proof that the official frontend still depends on Firebase-shaped contracts.
- **Broadening the failure scope to docs/tests/vendor code** — that makes the guard noisy and hides real runtime drift.

## Open Risks

- Backend resolver drift can still hide behind non-auth V2 helpers until S04 removes the acceptance paths, because `X-Session-ID` and Bearer session fallback have spread beyond the obvious auth router.
- Root `/session/*` retirement is deeper than a route delete: `auth_session.py` still mixes session validation/logout with Firebase-bearer behavior and narrative residue.
- The frontend scope is clean now, so any later reintroduction will show up as guard failures rather than approved debt; that is good, but it also means stale allowlist edits will be noisy if later slices move too fast.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | available — `npx skills add wshobson/agents@fastapi-templates` |
| React | `vercel-labs/agent-skills@vercel-react-best-practices` | available — `npx skills add vercel-labs/agent-skills@vercel-react-best-practices` |
| Playwright | `currents-dev/playwright-best-practices-skill@playwright-best-practices` | available — `npx skills add currents-dev/playwright-best-practices-skill@playwright-best-practices` |

## Sources

- The authoritative hotspot definitions, exclusions, and roots live in `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` (source: [`.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`](.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json))
- The readable inventory and drift gate live in `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` (source: [`.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`](.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh))
- The latest combined inventory came from `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`, which now shows backend-only approved residue and `frontend` as `no approved residue` (source: [`.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`](.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh))
- Backend canonical identity ownership and residual backend transport work come from the S02 handoff (source: [`.gsd/milestones/M004/slices/S02/S02-SUMMARY.md`](.gsd/milestones/M004/slices/S02/S02-SUMMARY.md))
- Frontend canonical contract ownership and verification pack come from the S03 plan/task chain (source: [`.gsd/milestones/M004/slices/S03/S03-PLAN.md`](.gsd/milestones/M004/slices/S03/S03-PLAN.md))
