---
estimated_steps: 4
estimated_files: 6
---

# T04: Isolate legacy bearer/websocket compatibility and close the backend proof gate

**Slice:** S02 — Backend Auth/Session Hotspot Refactor
**Milestone:** M003

## Description

Fence the remaining Firebase/bearer/websocket compatibility residue behind an explicit module, keep the public dependency surface stable, and close the focused backend proof gate with both runtime-contract tests and a structural split check. This is the task that turns “cleaner files” into actual slice-level proof.

## Steps

1. Create `backend-hormonia/app/dependencies/auth_legacy_firebase.py` and move `verify_firebase_token()`, the bearer-token compatibility branch inside `get_current_user()`, and `get_current_user_websocket()` into it.
2. Rewire `backend-hormonia/app/dependencies/auth_dependencies.py` and `backend-hormonia/app/dependencies/__init__.py` so the same public dependency names keep exporting the split implementation, with session-first behavior still winning on the happy path.
3. Re-run websocket/login/core-flow/hard-cut auth suites, fix any remaining contract or diagnostic drift, and keep websocket failure codes plus user-safe auth errors stable.
4. Run the structural split check and backend evidence verifier so the slice closes with both behavior proof and a measurable hotspot reduction.

## Must-Haves

- [ ] Compatibility residue is isolated, not deleted: legacy bearer/Firebase/websocket logic lives in an explicit module and no longer bloats `auth_dependencies.py`.
- [ ] The slice closes with green focused proof and an objective structure check (`auth_dependencies.py` line budget plus required module existence), not just a nicer-looking diff.

## Verification

- `cd backend-hormonia && pytest -q tests/api/test_websocket_session_auth_contract.py tests/api/v2/test_auth_local_login.py tests/integration/test_local_auth_core_flow.py tests/api/v2/test_auth_hard_cut_cleanup.py`
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

## Observability Impact

- Signals added/changed: Websocket auth failure codes and user-safe auth errors remain stable while the implementation moves behind a dedicated compatibility module.
- How a future agent inspects this: Use the focused pytest gate, the structural split check, and the backend evidence verifier to distinguish behavior regressions from simple file-move mistakes.
- Failure state exposed: Missing compatibility module wiring, websocket diagnostic drift, and hotspot-regression drift become explicit failures instead of subjective review comments.

## Inputs

- `backend-hormonia/tests/api/test_websocket_session_auth_contract.py`, `backend-hormonia/tests/api/v2/test_auth_local_login.py`, and `backend-hormonia/tests/integration/test_local_auth_core_flow.py` — the focused backend proof pack this task must close green.
- `backend-hormonia/app/routers/auth_session.py` and `backend-hormonia/app/dependencies/__init__.py` — compatibility constraints that must stay intact while legacy residue is isolated.

## Expected Output

- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` — explicit home for legacy bearer/Firebase/websocket compatibility logic.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — materially smaller façade backed by green focused proof and the structural split check.
