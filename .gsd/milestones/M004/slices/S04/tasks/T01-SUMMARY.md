---
id: T01
parent: S04
milestone: M004
provides:
  - Cookie-only auth/session resolution at the official HTTP and websocket chokepoints, with focused proof that legacy header/bearer/query transport is rejected.
key_files:
  - backend-hormonia/app/dependencies/auth_session_contract.py
  - backend-hormonia/app/api/v2/auth_session_shared.py
  - backend-hormonia/app/api/v2/routers/auth.py
  - backend-hormonia/app/api/websockets.py
  - backend-hormonia/tests/api/v2/test_auth_session_priority.py
  - backend-hormonia/tests/api/test_websocket_session_auth_contract.py
  - backend-hormonia/tests/api/v2/test_auth_local_login.py
  - .gsd/DECISIONS.md
key_decisions:
  - Treat the session cookie as the only accepted official staff session transport at the resolver/extractor layer; legacy `X-Session-ID`, session-as-Bearer, and websocket query/header session transport are ignored or explicitly rejected instead of preserving precedence rules.
patterns_established:
  - Resolver helpers may keep legacy parameters for compatibility, but the canonical path now fails closed unless a session cookie is present.
  - Websocket handshake auth now distinguishes rejected legacy transport (`AUTH_WEBSOCKET_SESSION_INVALID`) from lookup failures (`AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED`) while staying cookie-only on the happy path.
observability_surfaces:
  - `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
duration: 1h55m
verification_result: passed
completed_at: 2026-03-14T13:51:22-03:00
blocker_discovered: false
---

# T01: Hard-cut legacy session transport at the auth chokepoints

**Cut the official auth/websocket chokepoints over to cookie-only staff session transport, removed login `X-Session-ID` residue, and rewrote the focused proof so header/bearer/query fallback now fails loudly instead of passing silently.**

## What Happened

I changed `backend-hormonia/app/dependencies/auth_session_contract.py` so the official staff session resolver only accepts the session cookie. It still populates `request.state.session_id`, `request.state.user_id`, and `request.state.user_role` on the cookie-backed happy path, but it now logs and rejects `X-Session-ID` and session-as-Bearer attempts with a 401 `Session cookie required` surface instead of honoring precedence/fallback rules.

I changed `backend-hormonia/app/api/v2/auth_session_shared.py` to the same cookie-only contract for the shared resolver seam. Legacy header/query/bearer parameters remain in the signature so downstream callers don’t explode structurally, but they no longer participate in session resolution.

In `backend-hormonia/app/api/v2/routers/auth.py`, I removed the local header/bearer extractor logic and the debug login `X-Session-ID` response header emission. The canonical login payload shape stayed intact, verify-session still works from the cookie-backed path, and logout keeps the same success payload while reading the canonical session only from cookie-backed request state.

In `backend-hormonia/app/api/websockets.py`, I kept the handshake/query parameter plumbing only long enough to reject it deterministically. Cookie-backed websocket auth still succeeds, invalid cookie sessions still emit `AUTH_WEBSOCKET_SESSION_INVALID`, lookup exceptions still emit `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED`, and legacy query/header/bearer session transport is now rejected explicitly with the invalid-session code before any lookup path can masquerade as an official contract.

I rewrote the focused proof files so they now prove the post-cut boundary instead of the old precedence model: cookie success, explicit rejection of legacy HTTP/header/bearer/query transport, absence of login `X-Session-ID` residue, and preserved websocket diagnostics. I also updated the direct dependency unit proof in `backend-hormonia/tests/unit/test_auth_dependencies.py` so the local unit seam no longer asserts the retired precedence contract.

I appended the contract change to `.gsd/DECISIONS.md` and advanced `.gsd/STATE.md` to T02.

## Verification

Passed:
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_localization.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/integration/test_auth_hard_cut_end_to_end.py`
- `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py`

Recorded residue state:
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` → completed with 5 drift notes.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend` → failed with 5 issues, all in the expected S04 follow-on residue space (`x_session_id` / `session_bearer_fallback` allowlist drift around `auth_session_shared.py`, `auth.py`, and websocket anchors). That republish/tombstone work belongs to T03.

## Diagnostics

Use the focused pytest pack first to distinguish the failure class:
- HTTP resolver/extractor regressions: `tests/api/v2/test_auth_session_priority.py`
- websocket contract regressions: `tests/api/test_websocket_session_auth_contract.py`
- canonical auth route/login residue regressions: `tests/api/v2/test_auth_local_login.py`

For slice-level boundary drift, rerun:
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

The websocket failure surface remains attributable by stable error code: rejected/invalid session attempts emit `AUTH_WEBSOCKET_SESSION_INVALID`, lookup failures emit `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED`.

## Deviations

- Updated `backend-hormonia/tests/unit/test_auth_dependencies.py` even though it was outside the task’s expected-output list, because it directly asserted the retired header/bearer precedence contract and would otherwise become a lying local proof.

## Known Issues

- The S01 runtime residue allowlist is now stale relative to the T01 cut. `verify-runtime-residue.sh --check backend` fails until T03 republishes the backend residue boundary and handles the remaining root `/session/*` retirement work.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_session_contract.py` — reduced the official staff session resolver to cookie-only input and added explicit legacy transport rejection logging/401 surface.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — reduced the shared session resolver seam to cookie-only input.
- `backend-hormonia/app/api/v2/routers/auth.py` — removed local header/bearer session extraction and stopped emitting login `X-Session-ID` debug headers.
- `backend-hormonia/app/api/websockets.py` — made websocket session auth cookie-only while preserving pinned invalid/lookup-failed diagnostics.
- `backend-hormonia/tests/api/v2/test_auth_session_priority.py` — rewrote focused HTTP resolver proof around cookie-only success and header/bearer rejection.
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` — rewrote websocket proof around cookie-only success plus explicit rejection of legacy query/header/bearer session transport.
- `backend-hormonia/tests/api/v2/test_auth_local_login.py` — added proof for absent login `X-Session-ID` residue, cookie-backed auth success, and header/bearer rejection on canonical auth routes.
- `backend-hormonia/tests/unit/test_auth_dependencies.py` — aligned the direct dependency unit proof with the new cookie-only contract.
- `.gsd/DECISIONS.md` — recorded the cookie-only auth chokepoint decision for downstream slice work.
- `.gsd/milestones/M004/slices/S04/S04-PLAN.md` — marked T01 complete.
- `.gsd/STATE.md` — advanced the slice next action to T02.
