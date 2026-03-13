# S02: Backend Auth/Session Hotspot Refactor

**Goal:** Split backend auth/session responsibilities into focused modules behind the stable `app.dependencies.auth_dependencies` surface, without visible contract drift for session-first auth, admin wrappers, or websocket/session callers.
**Demo:** Focused backend auth/session proof passes while `backend-hormonia/app/dependencies/auth_dependencies.py` is materially smaller and the same public dependency names still serve existing callers.
**Requirements:** Owns `R034`. Supports `R036`, `R037`, `R038`, and `R039`.

## Must-Haves

- `backend-hormonia/app/dependencies/auth_dependencies.py` remains the public import/override surface, but delegates session resolution/cache hydration, user adaptation, role checks, and legacy bearer/websocket compatibility into focused modules. (`R034`, `R037`)
- `get_current_user_from_session()` preserves mapping-style session dicts, `request.state.session_id` / `user_id` / `user_role`, explicit `ENABLE_COOKIE_PRIORITY` behavior, the user-id-centric happy path, and user-safe auth failures. (`R037`, `R039`)
- Admin/roles/websocket compatibility seams keep working without caller import churn, and compatibility residue is isolated instead of silently deleted. (`R036`, `R037`, `R038`)
- Focused proof stays green via new split-contract tests, existing auth/session/websocket/login suites, and a structural size/split check. (`R034`, `R039`)

## Proof Level

- This slice proves: integration
- Real runtime required: no
- Human/UAT required: no

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/unit/test_auth_session_identity_contract.py tests/auth/test_user_conversion.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_dependency_override_contract.py tests/auth/test_session_role_enforcement.py tests/api/test_websocket_session_auth_contract.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_hard_cut_cleanup.py`
- `cd backend-hormonia && python3 - <<'PY'
from pathlib import Path
required = [
    Path('app/dependencies/auth_session_contract.py'),
    Path('app/dependencies/auth_session_cache.py'),
    Path('app/dependencies/auth_user_adapter.py'),
    Path('app/dependencies/auth_role_dependencies.py'),
    Path('app/dependencies/auth_legacy_firebase.py'),
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    raise SystemExit(f'missing split modules: {missing}')
line_count = len(Path('app/dependencies/auth_dependencies.py').read_text().splitlines())
if line_count >= 1100:
    raise SystemExit(f'auth_dependencies.py still too large: {line_count} lines')
print({'auth_dependencies_lines': line_count, 'split_modules': [str(path) for path in required]})
PY`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend`

## Observability / Diagnostics

- Runtime signals: preserve session-source / Redis-fallback / inactive-user logging in the extracted modules, and keep websocket auth failures on the stable `AUTH_WEBSOCKET_SESSION_INVALID` / `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED` codes.
- Inspection surfaces: targeted pytest suites above, `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report backend`, and the structural split check for module existence plus `auth_dependencies.py` line count.
- Failure visibility: `request.state.session_id` / `user_id` / `user_role`, deterministic 401/403/503 auth failures, and websocket error payloads carrying `details.connection_id` remain inspectable after the split.
- Redaction constraints: keep raw bearer tokens, full session IDs, and secret-bearing payloads out of logs; prefix-only session diagnostics and user-safe error details remain the boundary.

## Integration Closure

- Upstream surfaces consumed: `backend-hormonia/app/api/v2/auth_session_shared.py`, `backend-hormonia/app/api/v2/user_cache_shared.py`, `backend-hormonia/app/api/v2/routers/admin/dependencies.py`, `backend-hormonia/app/api/v2/routers/roles/dependencies.py`, `backend-hormonia/app/api/websockets.py`, `backend-hormonia/app/routers/auth_session.py`, `backend-hormonia/app/dependencies/__init__.py`
- New wiring introduced in this slice: `backend-hormonia/app/dependencies/auth_dependencies.py` becomes a stable façade over `auth_session_contract.py`, `auth_session_cache.py`, `auth_user_adapter.py`, `auth_role_dependencies.py`, and `auth_legacy_firebase.py`, while wrapper modules keep depending on the existing public dependency names.
- What remains before the milestone is truly usable end-to-end: S03 still has to split the frontend client/type hotspot, S04 still has to prove and remove or isolate dead compatibility residue, and S05 still has to replay integrated cross-surface smoke.

## Tasks

- [x] **T01: Add failing split-contract tests for auth seams** `est:1h`
  - Why: Freeze the session, adapter, override, and websocket/admin compatibility contracts before code moves so the refactor has a concrete stop condition tied to `R034`, `R037`, and `R039`.
  - Files: `backend-hormonia/tests/unit/test_auth_dependency_module_split.py`, `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py`, `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`
  - Do: Add new tests that intentionally pin the planned split modules and delegation seams: session-ID precedence stays explicit under `ENABLE_COOKIE_PRIORITY`, canonical session hydration stays user-id-first without requiring `firebase_uid`, dict→`User` adaptation strips non-model keys safely, admin wrappers still honor narrower dependency overrides, and websocket auth diagnostics stay stable when session auth fails.
  - Verify: `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_dependency_override_contract.py`
  - Done when: The new tests exist, assert the intended split contract in executable form, and fail against the pre-split implementation for the expected missing-module/delegation reasons.
- [x] **T02: Extract session resolution and cache hydration modules** `est:2h`
  - Why: The hottest and riskiest part of the file is the session-first dict seam, so it gets split first to advance `R034` without disturbing the broader wrapper surface.
  - Files: `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/auth_session_contract.py`, `backend-hormonia/app/dependencies/auth_session_cache.py`, `backend-hormonia/tests/unit/test_auth_dependency_module_split.py`, `backend-hormonia/tests/unit/test_auth_session_identity_contract.py`, `backend-hormonia/tests/api/v2/test_auth_session_priority.py`
  - Do: Move session ID resolution, request-state side effects, permission enrichment, canonical embedded-user handling, cache lookup, and Redis/DB fallback orchestration into focused modules; reuse `app.api.v2.auth_session_shared` / `user_cache_shared` where their contract already matches; keep `get_current_user_from_session()` in `auth_dependencies.py` as the stable public callable and preserve the current cookie/header/authorization precedence deliberately.
  - Verify: `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/unit/test_auth_session_identity_contract.py tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_hard_cut_cleanup.py`
  - Done when: The session dict seam passes the new and existing contract tests, `auth_dependencies.py` no longer owns the bulk of session-resolution/cache code, and no request-state or precedence regression appears.
- [x] **T03: Extract user adaptation and role wrapper seams** `est:90m`
  - Why: Dict→`User` conversion and role-gated wrappers are separate contracts with override sensitivity, and isolating them makes the hotspot materially smaller while supporting `R036`, `R037`, and `R038`.
  - Files: `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/auth_user_adapter.py`, `backend-hormonia/app/dependencies/auth_role_dependencies.py`, `backend-hormonia/app/dependencies/__init__.py`, `backend-hormonia/app/api/v2/routers/admin/dependencies.py`, `backend-hormonia/app/api/v2/routers/roles/dependencies.py`, `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py`
  - Do: Move dict→`User` normalization, timestamp coercion, role normalization, and field filtering into `auth_user_adapter.py`; move admin/doctor/current-active-admin checks into `auth_role_dependencies.py`; keep `auth_dependencies.py` and `app.dependencies.__init__` as the stable import surface; and update admin/roles wrappers to prefer canonical `id`/`user_id` data while keeping `firebase_uid` as an explicit compatibility fallback instead of a hard requirement.
  - Verify: `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/auth/test_user_conversion.py tests/auth/test_session_role_enforcement.py tests/api/v2/test_auth_dependency_override_contract.py`
  - Done when: User-object conversion and role enforcement live in focused modules, override-sensitive wrappers still pass their regression tests, and callers keep the same import paths.
- [x] **T04: Isolate legacy bearer/websocket compatibility and close the backend proof gate** `est:2h`
  - Why: The slice is only done when the remaining Firebase/bearer/websocket compatibility residue is fenced behind an explicit module and the focused backend proof pack is green, which is the bridge from `R034` to `R039`.
  - Files: `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/dependencies/auth_legacy_firebase.py`, `backend-hormonia/app/dependencies/__init__.py`, `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`, `backend-hormonia/tests/api/v2/test_auth_local_login.py`, `backend-hormonia/tests/integration/test_local_auth_core_flow.py`
  - Do: Move `verify_firebase_token()`, the bearer-token compatibility branch inside `get_current_user()`, and `get_current_user_websocket()` into `auth_legacy_firebase.py`; keep the public dependency names exported from `auth_dependencies.py` / `app.dependencies.__init__`; preserve session-first behavior and websocket auth diagnostics; then rerun the focused auth/session/login/websocket suites plus the structural split check and backend evidence verifier.
  - Verify: `cd backend-hormonia && pytest -q tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_hard_cut_cleanup.py && python3 - <<'PY'
from pathlib import Path
required = [
    Path('app/dependencies/auth_session_contract.py'),
    Path('app/dependencies/auth_session_cache.py'),
    Path('app/dependencies/auth_user_adapter.py'),
    Path('app/dependencies/auth_role_dependencies.py'),
    Path('app/dependencies/auth_legacy_firebase.py'),
]
missing = [str(path) for path in required if not path.exists()]
if missing:
    raise SystemExit(f'missing split modules: {missing}')
line_count = len(Path('app/dependencies/auth_dependencies.py').read_text().splitlines())
if line_count >= 1100:
    raise SystemExit(f'auth_dependencies.py still too large: {line_count} lines')
print({'auth_dependencies_lines': line_count, 'split_modules': [str(path) for path in required]})
PY && bash ../.gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend`
  - Done when: The focused backend auth/session/websocket/login suites and structural split checks all pass, `auth_dependencies.py` is a stable façade instead of the hotspot implementation bucket, and the slice leaves S04 a clearly isolated compatibility surface instead of more drift.

## Files Likely Touched

- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/app/dependencies/auth_session_contract.py`
- `backend-hormonia/app/dependencies/auth_session_cache.py`
- `backend-hormonia/app/dependencies/auth_user_adapter.py`
- `backend-hormonia/app/dependencies/auth_role_dependencies.py`
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py`
- `backend-hormonia/app/dependencies/__init__.py`
- `backend-hormonia/app/api/v2/routers/admin/dependencies.py`
- `backend-hormonia/app/api/v2/routers/roles/dependencies.py`
- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py`
- `backend-hormonia/tests/api/v2/test_auth_dependency_override_contract.py`
- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`
