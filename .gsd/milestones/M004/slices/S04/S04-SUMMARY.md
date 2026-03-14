---
id: S04
parent: M004
milestone: M004
provides:
  - The official backend auth/session runtime is now cookie-only, root `/session/*` is an explicit 410 tombstone, and the backend residue guard matches that reduced post-cut boundary.
requires:
  - slice: S02
    provides: Canonical backend login, verify-session, restore, and logout semantics centered on `user_id`.
  - slice: S03
    provides: Official frontend `/login`, `/dashboard`, and `/admin/*` flows that no longer depend on legacy auth/session transport.
affects:
  - S05
  - S06
key_files:
  - backend-hormonia/app/dependencies/auth_session_contract.py
  - backend-hormonia/app/api/v2/auth_session_shared.py
  - backend-hormonia/app/api/v2/routers/auth.py
  - backend-hormonia/app/api/websockets.py
  - backend-hormonia/app/api/v2/routers/localization.py
  - backend-hormonia/app/api/v2/routers/admin/dependencies.py
  - backend-hormonia/app/routers/auth_session.py
  - backend-hormonia/app/core/router_registry.py
  - backend-hormonia/tests/api/v2/test_auth_session_priority.py
  - backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py
  - backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py
  - backend-hormonia/tests/auth/test_session_validation.py
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
key_decisions:
  - Treat the session cookie as the only accepted official staff session transport at the HTTP and websocket chokepoints.
  - Allow remaining helper/admin wrapper legacy header or bearer strings to survive only as rejection/detection or test-bypass suppression, never as accepted session resolution inputs.
  - Keep root `/session/*` mounted only as an explicit 410 tombstone with stable diagnostics, and prove that separately from the residue allowlist.
patterns_established:
  - Transport retirement is only considered done when focused tests prove both the happy cookie path and explicit rejection of the retired legacy path.
  - Route retirement and residue republication move together: update the runtime surface, the focused test, the allowlist, and the readable handoff in one slice.
  - Header-only rejection probes should clear ambient client cookies before asserting failure so the proof does not pass accidentally.
observability_surfaces:
  - `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py`
  - `cd backend-hormonia && pytest -q tests/api/v2/test_localization.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/integration/test_auth_hard_cut_end_to_end.py`
  - `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
drill_down_paths:
  - .gsd/milestones/M004/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M004/slices/S04/tasks/T03-SUMMARY.md
duration: ~4h35m
verification_result: passed
completed_at: 2026-03-14T16:31:44-03:00
---

# S04: Superfícies legadas de auth/sessão aposentadas

**The official backend auth/session path is now cookie-only: legacy header/bearer/query transport is rejected, root `/session/*` is a stable 410 tombstone instead of a live compatibility island, and the backend residue guard now describes only the smaller post-cut rejection/Firebase boundary that remains.**

## What Happened

S04 finished the backend side of the auth/session convergence that S02 and S03 set up. The first cut happened at the chokepoints: `auth_session_contract.py`, `auth_session_shared.py`, canonical auth route extraction, and websocket auth no longer honor `X-Session-ID`, session-as-Bearer, or websocket `session_id` query/header transport as accepted staff session inputs. The cookie-backed happy path stayed intact, but any attempt to use the retired transport now fails closed with deterministic HTTP or websocket diagnostics instead of slipping through precedence rules.

The second cut removed the same transport contract from the helper seams that could have kept it alive indirectly. Localization, template/task/report/patient/message helpers, and the in-scope admin wrapper layer were converged onto cookie-backed session resolution. A few wrapper seams still notice legacy header/bearer presence, but only to avoid masking attempted-auth behavior in tests or diagnostics; they no longer forward those values into canonical session lookup. The acceptance proof was tightened accordingly: cookie + CSRF only on the happy path, explicit header-only rejection after clearing client cookies, and no more dual-transport fixture crutch.

The final cut retired the root compatibility island itself. `backend-hormonia/app/routers/auth_session.py` now serves only an explicit 410 tombstone for `/session/*`, with `AUTH_LEGACY_SESSION_ROUTE_RETIRED`, the retired path, the canonical replacement prefix, and the required cookie transport. `router_registry.py` was updated to register that surface honestly as a retirement router, and the focused pytest file was rewritten around tombstone behavior so the route cannot drift into silent 404 disappearance or accidentally revive legacy behavior.

Once the runtime boundary was reduced, S01 was republished to match it. The backend residue allowlist no longer approves root-session or Firebase-narrative anchors. The green backend report/check now lists only the still-approved post-S04 categories: `firebase_uid`, a small amount of explicit `x_session_id` and `session_bearer_fallback` rejection/detection residue, and websocket `session_id` query anchors that survive only as rejection plumbing. That leaves S05 and S06 with a smaller, honest boundary instead of the old mixed transport/runtime story.

## Verification

Full slice closeout was replayed after the task work and passed:

- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py`
  - Passed: 18 tests.
- `cd backend-hormonia && pytest -q tests/api/v2/test_localization.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/integration/test_auth_hard_cut_end_to_end.py`
  - Passed: 42 tests.
- `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py`
  - Passed: 5 tests.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
  - Passed; report lists only `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query` residue in the approved backend scopes.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
  - Passed; allowlist and code agree on the reduced post-S04 backend boundary.

The replay still emits the existing `pytest_asyncio` loop-scope deprecation warning. It is unchanged and non-blocking.

## Requirements Advanced

- R047 — Advanced the no-Firebase runtime cut by removing the remaining official backend acceptance of legacy staff session transport and shrinking the approved backend residue map to Firebase-adjacent/runtime-adjacent leftovers only.
- R049 — Advanced the identity convergence by ensuring the official auth/session path no longer depends on alternative transport contracts that could bypass the canonical `user_id`-centered session flow.

## Requirements Validated

- R048 — Validated by the combined S02+S03+S04 proof: canonical login/verify-session/restore/logout behavior remains green on the cookie-backed contract, the official frontend consumes only that contract, and `/session/*`, `X-Session-ID`, session-as-Bearer, and websocket `session_id` fallback are no longer officially accepted runtime transport.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

- none

## Known Limitations

- `firebase_uid` remains approved backend residue across auth/cache/adapter seams and still belongs to S05.
- A small amount of `x_session_id`, `session_bearer_fallback`, and websocket `session_id` text still survives as rejection/detection scaffolding in backend seams; that is intentional after S04 and should only shrink further with proof.
- S04 is contract proof, not assembled-stack proof. The full local no-Firebase runtime replay across `/dashboard`, `/admin`, and `/whatsapp` still belongs to S06.

## Follow-ups

- S05: remove the remaining functional Firebase/runtime-adjacent residue (`firebase_uid`, cache/audit/user-adapter narrative and related seams) without reopening the session transport boundary.
- S06: replay the assembled local stack with Firebase Auth envs blank and verify the canonical runtime across `/login`, `/dashboard`, `/admin`, and `/whatsapp`.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_session_contract.py` — reduced official HTTP session resolution to cookie-only input and explicit legacy transport rejection.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — aligned the shared session resolver seam to the same cookie-only contract.
- `backend-hormonia/app/api/v2/routers/auth.py` — removed canonical auth-route header/bearer session extraction and login `X-Session-ID` residue.
- `backend-hormonia/app/api/websockets.py` — kept websocket auth cookie-only while preserving pinned invalid-session and lookup-failed diagnostics.
- `backend-hormonia/app/api/v2/routers/localization.py` — moved route-local staff auth onto the canonical cookie-backed contract.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` — stopped forwarding legacy header/bearer transport into admin session resolution while preserving attempted-auth detection where needed.
- `backend-hormonia/app/routers/auth_session.py` — replaced the live root compatibility island with a 410 tombstone router.
- `backend-hormonia/app/core/router_registry.py` — registered `/session/*` honestly as a retirement surface.
- `backend-hormonia/tests/api/v2/test_auth_session_priority.py` — rewrote HTTP resolver proof around cookie success plus header/bearer rejection.
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` — rewrote websocket proof around cookie success plus explicit rejection of legacy query/header/bearer transport.
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py` — tightened hard-cut proof to cookie + CSRF only and explicit header-only rejection.
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` — removed dual-transport fixtures and proved the integrated auth flow still rejects header-only transport when cookies are absent.
- `backend-hormonia/tests/auth/test_session_validation.py` — pinned deterministic 410 tombstone behavior for representative `/session/*` routes.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — republished the reduced backend residue boundary after the transport hard cut and tombstone.
- `.gsd/milestones/M004/slices/S04/S04-UAT.md` — published the slice replay tailored to the cookie-only backend contract and `/session/*` retirement.

## Forward Intelligence

### What the next slice should know
- The official frontend no longer depends on any of the retired backend session transport surfaces. If S05 or S06 reintroduces `X-Session-ID`, session-as-Bearer, or `/session/*` semantics, that is fresh regression, not compatibility necessity.
- The backend residue guard is useful again because it now separates accepted runtime behavior from rejection-only scaffolding. Preserve that distinction when shrinking the remaining approved categories.
- The fastest way to lie to yourself on this boundary is to forget ambient cookies in tests; keep clearing client cookies before asserting header-only rejection.

### What's fragile
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` detection-only legacy strings — they are still intentionally present, so future cleanup must distinguish detection scaffolding from transport acceptance before deleting them.
- Websocket auth diagnostics — the transport cut is only trustworthy while `AUTH_WEBSOCKET_SESSION_INVALID` and `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED` stay pinned to the right branches.

### Authoritative diagnostics
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` — the fastest trustworthy signal that the reduced backend residue boundary still matches the code.
- `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py` — the tightest proof that `/session/*` remains an explicit 410 tombstone instead of reviving or disappearing.
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py` — the tightest chokepoint proof for cookie-only auth plus stable websocket diagnostics.

### What assumptions changed
- "Frontend cutover is enough; the backend can keep accepting legacy transport safely" — false; helper seams, websocket handshake plumbing, and root `/session/*` still kept the old contract alive until S04 removed or tombstoned them explicitly.
- "Once the focused tests pass, the residue guard will already agree" — false; S04 still needed allowlist republication and documentation updates before the reduced backend boundary became a durable regression gate.
