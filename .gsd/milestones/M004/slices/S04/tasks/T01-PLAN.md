---
estimated_steps: 4
estimated_files: 7
---

# T01: Hard-cut legacy session transport at the auth chokepoints

**Slice:** S04 — Superfícies legadas de auth/sessão aposentadas
**Milestone:** M004

## Description

Collapse the two live auth/session resolver stacks and the canonical auth/websocket request extractors onto one cookie-only staff session contract. This task closes the highest-risk path first: if either resolver or extractor keeps accepting header, bearer, or query fallback, S04 is not real no matter what the rest of the repo says.

## Steps

1. Change `auth_session_contract.py` and `auth_session_shared.py` so the official staff session resolver accepts cookie-backed session state only, keeping canonical `request.state` and user-resolution side effects intact.
2. Remove legacy session transport handling from `api/v2/routers/auth.py` and stop emitting debug `X-Session-ID` response headers without changing canonical login/verify/logout payloads.
3. Remove websocket header/query session fallback in `api/websockets.py` while preserving the pinned websocket auth error codes and failure-path behavior.
4. Rewrite the focused proof files so they assert cookie-only success plus explicit rejection/absence for header, bearer, query, and debug-header residue.

## Must-Haves

- [ ] `auth_session_contract.py` and `auth_session_shared.py` reject `X-Session-ID` and session-as-Bearer transport for the official staff path.
- [ ] `api/v2/routers/auth.py` no longer extracts session IDs from headers/bearer fallback or emits `X-Session-ID` on login responses.
- [ ] Websocket auth rejects query/header session transport but still surfaces `AUTH_WEBSOCKET_SESSION_INVALID` and `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED` deterministically.
- [ ] Focused tests prove cookie-only success and legacy transport rejection explicitly.

## Verification

- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py`
- Confirm the updated tests assert absence of login `X-Session-ID` response headers and rejection of header/bearer/query fallback, not just happy-path cookie success.

## Observability Impact

- Signals added/changed: explicit 401 rejection surfaces for header/bearer session transport and preserved websocket auth error codes for invalid/lookup-failed session attempts.
- How a future agent inspects this: rerun the focused pytest pack and inspect the failing assertion to see whether the break is in HTTP session resolution, auth response headers, or websocket auth fallback handling.
- Failure state exposed: the tests distinguish “canonical cookie flow regressed” from “legacy transport still accepted,” and websocket failures remain attributable by stable error code.

## Inputs

- `backend-hormonia/app/dependencies/auth_session_contract.py` — primary request-session resolver still accepting cookie/header/bearer precedence.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — helper/websocket resolver still accepting bearer/header/cookie/query fallback.
- `backend-hormonia/app/api/v2/routers/auth.py` — canonical auth router still has local legacy extraction and debug header emission.
- `backend-hormonia/app/api/websockets.py` — websocket auth path with the pinned diagnostic codes that must survive the cut.
- S02/S03 handoff: frontend no longer emits these legacy transports, so any surviving acceptance here is backend inertia only.

## Expected Output

- `backend-hormonia/app/dependencies/auth_session_contract.py` — cookie-only official resolver behavior with unchanged canonical request-state side effects.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — cookie-only shared resolver behavior for in-scope staff session auth.
- `backend-hormonia/app/api/v2/routers/auth.py` — canonical auth routes without header/bearer extraction or debug `X-Session-ID` emission.
- `backend-hormonia/app/api/websockets.py` — websocket auth path without query/header session fallback and with stable rejection diagnostics preserved.
- `backend-hormonia/tests/api/v2/test_auth_session_priority.py` — focused rejection/acceptance proof for the new resolver contract.
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` — websocket proof updated to the post-cut transport boundary.
- `backend-hormonia/tests/api/v2/test_auth_local_login.py` — proof that canonical login still works without legacy response-header residue.
