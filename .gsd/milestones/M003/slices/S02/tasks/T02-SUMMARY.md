---
id: T02
parent: S02
milestone: M003
provides:
  - Split session resolution, cache hydration, and dict→User adaptation into focused backend auth modules while keeping `auth_dependencies` as the public façade.
key_files:
  - backend-hormonia/app/dependencies/auth_dependencies.py
  - backend-hormonia/app/dependencies/auth_session_contract.py
  - backend-hormonia/app/dependencies/auth_session_cache.py
  - backend-hormonia/app/dependencies/auth_user_adapter.py
key_decisions:
  - Keep `ENABLE_COOKIE_PRIORITY` authoritative inside the extracted session contract instead of converging to the authorization-first shared helper order.
  - Avoid module-level `app.api.v2.*` imports from the split auth modules because that package’s router-loading side effects create circular imports back into `auth_dependencies`.
patterns_established:
  - Keep `get_current_user_from_session()` and `get_current_user_object_from_session()` as thin public façades that delegate into focused split modules.
  - Localize request-state writes (`session_id`, `user_id`, `user_role`) and permission enrichment in the session contract so precedence and side effects stay testable at one seam.
observability_surfaces:
  - cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/unit/test_auth_session_identity_contract.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_hard_cut_cleanup.py
  - cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/unit/test_auth_session_identity_contract.py tests/auth/test_user_conversion.py
  - request.state.session_id / user_id / user_role assertions in the focused session contract suites
  - auth session fallback / timeout / inactive-user logs now emit from auth_session_contract.py and auth_session_cache.py
duration: ~2h including recovery closeout
verification_result: passed
completed_at: 2026-03-13T01:02:00Z
blocker_discovered: false
---

# T02: Extract session resolution and cache hydration modules

**Extracted the session-first auth seam into contract/cache modules, added early adapter delegation to satisfy the split-contract gate, and kept the public dependency surface stable.**

## What Happened

`backend-hormonia/app/dependencies/auth_session_contract.py` now owns request-facing session resolution: explicit cookie/header/authorization precedence under `ENABLE_COOKIE_PRIORITY`, `request.state.session_id` writes, permission enrichment, and the stable `resolve_authenticated_session_user()` entrypoint that `auth_dependencies.get_current_user_from_session()` now delegates to.

`backend-hormonia/app/dependencies/auth_session_cache.py` now owns the session-data hot path behind that contract: canonical embedded-user extraction, cache hydration for canonical `id` plus compatibility `firebase_uid`, Redis session rehydration after DB fallback, timeout-safe Redis lookups, and Redis/DB fallback orchestration. The happy path remains user-id-centric; `firebase_uid` is compatibility-only rather than a required local-auth key.

`backend-hormonia/app/dependencies/auth_dependencies.py` is materially slimmer and remains the stable override/import façade. `get_current_user_from_session()` still returns mapping-style payloads, still adds `permissions`, and still writes `request.state.session_id`, `request.state.user_id`, and `request.state.user_role`. `get_current_user_object_from_session()` now delegates into `backend-hormonia/app/dependencies/auth_user_adapter.py`, which was extracted one task early because the focused split-contract suite already required that delegation seam to go green.

A brief attempt to reuse `app.api.v2.user_cache_shared` directly at module import time caused a real circular import through `app.api.v2.__init__` router registration. I backed that out and kept the serializer logic local inside the split auth modules; this preserves the runtime contract without reintroducing import-time side effects.

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/unit/test_auth_session_identity_contract.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_hard_cut_cleanup.py` → pass (`................... [100%]`). This verifies the task must-haves directly: mapping-style payloads still carry `permissions`, request-state side effects still land on `request.state`, canonical `user_id` payloads work without `firebase_uid`, and explicit cookie/header/authorization precedence remains test-covered.
- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/unit/test_auth_session_identity_contract.py tests/auth/test_user_conversion.py` → pass (`.................. [100%]`). This confirms the early `auth_user_adapter` extraction still preserves the dict→`User` conversion contract and the thinner façade delegation.
- `cd backend-hormonia && wc -l app/dependencies/auth_dependencies.py` → `1128`. The façade is much smaller than the pre-split 1579 lines, but the slice-wide `<1100` structural gate is still pending later extractions.
- The remaining slice verification packs were not rerun in this recovery closeout. They still belong to T03/T04 because `auth_role_dependencies.py` and `auth_legacy_firebase.py` are not extracted yet.

## Diagnostics

Re-run the focused T02 gate above to localize regressions to the session contract/cache seam. Failures in precedence, request-state writes, or canonical `user_id` handling surface in `tests/unit/test_auth_dependency_module_split.py`, `tests/unit/test_auth_session_identity_contract.py`, and `tests/api/v2/test_auth_session_priority.py` instead of leaking through the monolith. Fallback/cache issues now live behind logs in `backend-hormonia/app/dependencies/auth_session_contract.py` and `backend-hormonia/app/dependencies/auth_session_cache.py`.

## Deviations

Extracted `backend-hormonia/app/dependencies/auth_user_adapter.py` during T02 instead of waiting for T03 because the focused split-contract verification for this task already required `get_current_user_object_from_session()` to delegate into a split adapter module.

## Known Issues

The slice-level structural/backend proof is not fully green yet: `backend-hormonia/app/dependencies/auth_dependencies.py` is still 1128 lines, and `auth_role_dependencies.py` / `auth_legacy_firebase.py` remain for T03/T04.

## Files Created/Modified

- `backend-hormonia/app/dependencies/auth_dependencies.py` — reduced the public auth façade to thin delegation for session resolution and session-user adaptation.
- `backend-hormonia/app/dependencies/auth_session_contract.py` — extracted request-side session precedence, request-state writes, and permission enrichment.
- `backend-hormonia/app/dependencies/auth_session_cache.py` — extracted canonical session payload shaping, cache hydration, Redis activity updates, and DB fallback orchestration.
- `backend-hormonia/app/dependencies/auth_user_adapter.py` — extracted mapping-style session payload → `User` adaptation used by the public façade.
- `.gsd/DECISIONS.md` — recorded the import-cycle constraint on `app.api.v2.*` reuse for split auth modules.
- `.gsd/milestones/M003/slices/S02/tasks/T02-SUMMARY.md` — durable closeout summary for the extracted session/auth modules.
