---
estimated_steps: 4
estimated_files: 8
---

# T02: Converge remaining helper consumers and acceptance proof on the cookie-only contract

**Slice:** S04 — Superfícies legadas de auth/sessão aposentadas
**Milestone:** M004

## Description

Once the chokepoints are cut, the remaining risk is quieter: helper wrappers and test fixtures can still require or advertise `X-Session-ID`/Bearer session transport and make the runtime look green by sending both cookie and header. This task repairs those direct consumers, with `localization.py` as the first-class holdout, and forces the acceptance pack to prove the real post-cut contract.

## Steps

1. Migrate `localization.py` off direct `X-Session-ID` header requirements onto the canonical cookie-backed session dependency while preserving user-role checks and missing/expired-session errors.
2. Sweep the remaining S01-approved helper wrappers in scope so they reuse canonical session resolution instead of parsing `X-Session-ID`/Bearer transport locally; include reports/patients/quiz shared wrappers if they still advertise or require legacy transport after the first pass.
3. Narrow focused helper tests and the hard-cut acceptance fixtures to cookie + CSRF only so they stop masking runtime ambiguity with dual transport.
4. Re-run the helper/integration proof pack and tighten any failure assertions needed to show explicit rejection rather than incidental breakage.

## Must-Haves

- [ ] `localization.py` no longer requires `X-Session-ID` directly for authenticated staff access.
- [ ] Remaining in-scope helper wrappers stop advertising or accepting header/bearer staff session transport and reuse the canonical dependency surface instead.
- [ ] Acceptance fixtures and tests stop sending both cookie and `X-Session-ID` together as a fallback crutch.
- [ ] The helper/integration proof pack stays green on cookie-only canonical session behavior.

## Verification

- `cd backend-hormonia && pytest -q tests/api/v2/test_localization.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/integration/test_auth_hard_cut_end_to_end.py`
- Confirm the updated tests authenticate via session cookie + CSRF only and include at least one explicit rejection assertion for retired header/bearer transport.

## Observability Impact

- Signals added/changed: helper endpoints should now fail with canonical unauthorized/session-expired responses instead of header-specific messages, and the acceptance pack should reveal if any route still secretly needs legacy transport.
- How a future agent inspects this: rerun the helper/integration pack and compare which route fails — localization, a shared helper surface, or the end-to-end auth flow.
- Failure state exposed: the proof pack makes transport-coupled helper regressions visible immediately because dual-transport fixtures are removed.

## Inputs

- `backend-hormonia/app/api/v2/routers/localization.py` — direct runtime holdout still wired to `X-Session-ID`.
- `backend-hormonia/app/api/v2/templates_shared.py` — shared helper still documents and resolves bearer/header/cookie precedence.
- `backend-hormonia/app/api/v2/routers/tasks/dependencies.py` — helper dependency still parses `X-Session-ID`/Bearer directly.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` — admin dependency still detects `Authorization`/`X-Session-ID` before canonical session dependency resolution.
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` — acceptance pack currently synthesizes both cookie and `X-Session-ID` in `_session_request_parts()`.
- T01 output: resolver/extractor layer already cut to cookie-only, so helper updates should consume that contract rather than reinvent it.

## Expected Output

- `backend-hormonia/app/api/v2/routers/localization.py` — authenticated staff access resolved through the canonical cookie-backed session dependency.
- `backend-hormonia/app/api/v2/templates_shared.py` — shared helper aligned to the post-cut transport contract.
- `backend-hormonia/app/api/v2/routers/tasks/dependencies.py` — task helper dependency no longer header/bearer-driven.
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py` — admin dependency no longer treats `X-Session-ID`/Bearer as an official session transport signal.
- `backend-hormonia/tests/api/v2/test_localization.py` — localization proof updated to the canonical cookie-backed contract.
- `backend-hormonia/tests/api/v2/test_auth_hard_cut_cleanup.py` — focused cleanup proof updated to explicit legacy transport rejection.
- `backend-hormonia/tests/integration/test_auth_hard_cut_end_to_end.py` — acceptance flow proving cookie + CSRF only.
