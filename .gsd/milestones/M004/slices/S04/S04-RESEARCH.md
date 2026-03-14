# S04 — Research

**Date:** 2026-03-14

## Summary

This research targets S04’s support role for the active requirements **R047**, **R048**, and **R049**. After S03, the shipped frontend is already clean: it no longer emits `X-Session-ID`, `Authorization: Bearer <session_id>`, or websocket `?session_id=` fallback. What remains is backend-owned residue. That means S04 is not a cross-stack migration anymore; it is a backend boundary-tightening slice whose job is to retire or explicitly tombstone legacy auth/session transport without regressing the canonical cookie-backed session contract.

The main implementation constraint is that legacy transport is accepted in **two independent resolver stacks** today. `backend-hormonia/app/dependencies/auth_session_contract.py` resolves session IDs for the main dependency path with settings-driven precedence, while `backend-hormonia/app/api/v2/auth_session_shared.py` resolves them for helper-family callers and websockets with a different hardcoded precedence. If S04 cuts only one stack, the old contract survives through the other. The legacy root `/session/*` router is also still mounted and still carries Firebase-era behavior and narrative, but I found no official frontend/runtime caller that still needs it.

Primary recommendation: implement S04 as a boundary cut, not a scattered cleanup. First collapse legacy acceptance at the resolver chokepoints (`auth_session_contract.py`, `auth_session_shared.py`, and auth/websocket request extractors). Then tombstone or explicitly reject the root `/session/*` island. Finally, clean the helper wrappers, test harnesses, and residue allowlist so the verifier, the tests, and the runtime all describe the same post-cut contract.

## Recommendation

Take a **cookie-first canonicalization + explicit retirement** approach:

1. **Decide the post-S04 transport contract explicitly**: cookie-backed session is canonical for the official app; `X-Session-ID`, session-as-Bearer, websocket query `session_id`, and root `/session/*` are no longer part of the official runtime.
2. **Cut both resolver stacks together**:
   - `backend-hormonia/app/dependencies/auth_session_contract.py`
   - `backend-hormonia/app/api/v2/auth_session_shared.py`
   - any local request extractors that still re-implement lookup logic, especially `backend-hormonia/app/api/v2/routers/auth.py`
3. **Retire the root `/session/*` island explicitly** rather than letting it disappear silently. A tombstone or explicit rejection is safer than accidental 404 drift because S04’s goal is to prove that the old surface is intentionally dead.
4. **Update direct helper consumers** that still encode header/bearer assumptions. The standout risk is `backend-hormonia/app/api/v2/routers/localization.py`, which is still header-only and will need a real contract change.
5. **Rewrite the tests and fixtures before trusting green**. Several current backend tests and fixtures still send both cookie and legacy headers, which can keep suites green while the runtime remains ambiguous.
6. **Republish the S01 residue boundary** in the same change so S04 leaves a durable regression gate, not just passing tests.

Why this approach: S03 already proved the frontend side of the cut. S04 should cash that in by removing backend inertia cleanly and observably, not by adding another compatibility layer or third resolver path.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Canonical session auth resolution | `backend-hormonia/app/dependencies/auth_session_contract.py` + `backend-hormonia/app/api/v2/auth_session_shared.py` | These are the real acceptance chokepoints. Collapse them; do not create a third auth/session resolver. |
| Explicit legacy route retirement | Existing mounted root router `backend-hormonia/app/routers/auth_session.py` via `app/core/router_registry.py` | The legacy island is already centralized. Tombstone or reject it centrally instead of leaving partial dead endpoints or route-by-route drift. |
| Stable websocket auth diagnostics | `AUTH_WEBSOCKET_SESSION_INVALID` and `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED` in `backend-hormonia/app/api/websockets.py` | These error surfaces are already pinned. Keep them while removing query/header fallback so operational diagnostics do not regress. |
| Runtime residue enforcement | `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` + `verify-runtime-residue.sh` | S04 needs the verifier to agree with the new boundary or the cut will rot immediately. |

## Existing Code and Patterns

- `backend-hormonia/app/dependencies/auth_session_contract.py` — primary request-session resolver for the main dependency path. Today it still accepts cookie, `X-Session-ID`, and `Authorization: Bearer <session_id>` with settings-driven precedence. This is one of the two mandatory S04 cut points.
- `backend-hormonia/app/api/v2/auth_session_shared.py` — secondary resolver used by helper-family callers and websockets. It currently hardcodes a different order: Bearer → `X-Session-ID` → cookie → query `session_id`. S04 has to keep this file in lockstep with the main resolver or the legacy contract survives.
- `backend-hormonia/app/api/websockets.py` — only live backend websocket query fallback. It already has stable auth diagnostics; reuse those while removing query/header transport acceptance.
- `backend-hormonia/app/api/v2/routers/auth.py` — canonical `/api/v2/auth/*` router, but it still extracts session IDs from cookie/header/Bearer and debug-emits `X-Session-ID` on login in non-production mode.
- `backend-hormonia/app/routers/auth_session.py` — root `/session/*` compatibility island. It still carries Firebase-era semantics, comments, and tests. Best S04 candidate for tombstone or explicit rejection because the official frontend no longer needs it.
- `backend-hormonia/app/api/v2/routers/localization.py` — important surprise: `_get_current_user_simple()` and its compat wrapper still require `X-Session-ID` directly. This is not just leftover narrative; it is a real runtime holdout.
- `backend-hormonia/app/api/v2/templates_shared.py`, `routers/tasks/dependencies.py`, `routers/reports.py`, `routers/enhanced_reports.py`, `routers/admin/dependencies.py`, `routers/patients/base.py` — helper/wrapper surfaces that still encode header or bearer assumptions and will need cleanup after the chokepoint decision.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — authoritative S04 boundary map. It already says frontend scopes are `approved: []`, so any remaining auth/session residue is backend-owned by definition.
- `backend-hormonia/tests/api/v2/test_auth_session_priority.py` — proves header-only and cookie-over-header behavior on the main dependency stack today. These tests are expected to change when S04 lands.
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py` — pins websocket session auth behavior, including the current query fallback and the stable websocket error codes. This is the main guardrail for removing query transport without losing diagnostics.
- `backend-hormonia/tests/auth/test_session_validation.py` — pins the root `/session/*` legacy router behavior. These tests will either be inverted to explicit rejection/tombstone expectations or retired with the route.
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` and shared conftest fixtures — still synthesize legacy headers alongside cookie flows in places. Follow these carefully; they can hide real ambiguity in the runtime.

## Constraints

- **Requirements in play:** S04 supports active **R047** (Firebase leaves the official runtime), **R048** (single canonical auth/session contract), and **R049** (`firebase_uid` not required in runtime identity resolution). The slice is not just cleanup; it must tighten the runtime boundary in a way that advances those requirements.
- **Frontend is already cut over.** S03 proved the official frontend no longer needs `X-Session-ID`, session-as-Bearer, or websocket `?session_id=`. Keeping those paths alive is backend inertia, not a compatibility need for the shipped app.
- **Two resolver stacks exist today.** `auth_session_contract.py` and `auth_session_shared.py` both accept legacy transport and do not share the same precedence. S04 must converge both.
- **Do not remove all bearer auth blindly.** The target is session-as-Bearer fallback, not every possible `Authorization` use across the system.
- **Do not over-cut the response contract accidentally.** The frontend still tracks session/auth state in memory and still receives `session_id` in canonical auth responses. S04 is about retiring legacy transport acceptance, not redesigning the canonical login/verify payloads.
- **`localization.py` is a real contract holdout.** Because it is header-only today, S04 will need a small runtime contract repair there rather than a pure tombstone pass.
- **The residue verifier is part of the slice boundary.** S04 is incomplete if code changes land without the S01 allowlist/report story being republished to match.

## Common Pitfalls

- **Cutting only one resolver path** — Removing `X-Session-ID` or bearer fallback from `auth_session_contract.py` but leaving `auth_session_shared.py` intact will leave legacy auth alive in helper-family routes and websockets.
- **Confusing session-as-Bearer with all bearer auth** — S04 should reject `Authorization: Bearer <session_id>` as session transport, not blindly strip unrelated token-based auth behavior elsewhere.
- **Trusting green tests that still send dual transport** — Some current backend tests/fixtures provide both cookie and legacy header/bearer input. That can hide the fact that the runtime is still accepting more than the canonical contract.
- **Forgetting the advertised surface** — Even after runtime rejection, `X-Session-ID` can still linger in debug headers, CORS/preflight allowances, audit middleware, docstrings, and allowlist anchors. That leaves the contract blurry.
- **Silent `/session/*` disappearance** — A plain removal that turns into generic 404s weakens the proof. S04’s intent is clearer if the legacy router is retired/tombstoned explicitly.

## Open Risks

- `backend-hormonia/app/api/v2/routers/localization.py` may force a slightly broader execution slice than expected because it is still hard-wired to `X-Session-ID` instead of reusing the canonical dependency surface.
- Helper wrappers in reports/tasks/templates/admin/patients may contain enough local session extraction code that the cut fans out into more files than the high-level summaries suggest.
- The websocket contract may regress if query fallback is removed without preserving the existing `AUTH_WEBSOCKET_SESSION_INVALID` / `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED` diagnostics.
- Test harnesses and conftest helpers still manufacturing legacy headers can create false confidence unless they are narrowed to cookie-only canonical flows.
- Infra-adjacent files such as CORS, preflight helpers, and audit middleware may still advertise or read `X-Session-ID` even after auth rejects it, leaving misleading operational residue.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | available — install with `npx skills add wshobson/agents@fastapi-templates` |
| React | `vercel-labs/agent-skills@vercel-react-best-practices` | available — install with `npx skills add vercel-labs/agent-skills@vercel-react-best-practices` |
| Auth/session boundary cleanup | installed `debug-like-expert` skill | installed locally, but not required for this research pass |

## Sources

- The main dependency path still resolves session IDs from cookie, `X-Session-ID`, and `Authorization`, with settings-driven precedence. (source: `backend-hormonia/app/dependencies/auth_session_contract.py`)
- The helper-family/websocket path still resolves Bearer → `X-Session-ID` → cookie → query `session_id`. (source: `backend-hormonia/app/api/v2/auth_session_shared.py`)
- Websocket auth still accepts header/cookie/query session transport and already exposes stable invalid-session diagnostics. (source: `backend-hormonia/app/api/websockets.py`)
- Canonical auth routes still include local request extraction for cookie/header/Bearer and debug `X-Session-ID` response emission on login. (source: `backend-hormonia/app/api/v2/routers/auth.py`)
- The root `/session/*` compatibility island is still mounted and still describes Firebase-era session creation/validation/logout behavior. (source: `backend-hormonia/app/routers/auth_session.py`)
- `localization.py` still authenticates via `X-Session-ID` header directly, making it a real runtime holdout rather than dead documentation. (source: `backend-hormonia/app/api/v2/routers/localization.py`)
- The S01 residue allowlist already classifies `root_legacy_session`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query` as backend-owned residue, while frontend scopes are `approved: []`. (source: `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`)
- Current backend proof still pins header-only priority behavior, websocket query fallback, and legacy root-router behavior, so S04 will need deliberate test inversion rather than incidental cleanup. (source: `backend-hormonia/tests/api/v2/test_auth_session_priority.py`, `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`, `backend-hormonia/tests/auth/test_session_validation.py`)
