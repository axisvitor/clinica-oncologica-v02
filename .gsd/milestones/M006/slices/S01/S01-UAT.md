# S01: Fechar a costura auth/session legado ainda “viva” — UAT

**Milestone:** M006
**Written:** 2026-03-15

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S01 republishes backend auth/session contracts and guardrails rather than a new human-facing workflow; the trustworthy proof is the focused pytest pack, the static seam check, and the residue verifier/report surface.

## Preconditions

- Start in the repo root: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1`.
- Python dependencies for `backend-hormonia` are installed and the normal backend test environment is available.
- The shared backend test harness variables are configured the same way they were for the green slice replay; no Firebase Auth runtime credentials are required for this slice proof.
- No manual server startup is needed; every check below is command-driven.

## Smoke Test

1. Run:
   ```bash
   bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend
   ```
2. **Expected:** Output contains `[backend] - no approved residue`, may list `[backend-proof-only]` entries, and ends with `RESULT: --check backend OK`.

## Test Cases

### 1. Canonical auth/session slice pack stays green

1. Run:
   ```bash
   cd backend-hormonia && pytest -q \
     tests/unit/test_auth_dependencies.py \
     tests/unit/test_runtime_residue_guard.py \
     tests/api/v2/test_auth_session_priority.py \
     tests/api/v2/test_auth_hard_cut_cleanup.py \
     tests/api/v2/test_system_auth_hard_cut_operational.py \
     tests/api/test_websocket_session_auth_contract.py \
     tests/auth/test_session_validation.py \
     tests/integration/test_auth_hard_cut_end_to_end.py
   ```
2. **Expected:** Pytest exits 0. Cookie-backed auth, verify-session, admin/system checks, websocket auth contract, root `/session/*` retirement, and the end-to-end session flow all stay green without requiring any Firebase/bearer fallback.

### 2. Legacy HTTP transports fail closed with stable diagnostics

1. Run:
   ```bash
   cd backend-hormonia && pytest -q tests/api/v2/test_auth_hard_cut_cleanup.py -k "rejects_legacy_header_transport_without_cookie or stable_diagnostics"
   ```
2. **Expected:** `2 passed`. The covered requests that send `X-Session-ID` or session-as-Bearer without the session cookie receive stable closed-failure responses instead of being accepted or silently treated as authenticated.

### 3. The lazy bearer/Firebase seam is gone from `auth_dependencies.py`

1. Run:
   ```bash
   python3 - <<'PY'
   from pathlib import Path
   text = Path('backend-hormonia/app/dependencies/auth_dependencies.py').read_text(encoding='utf-8')
   for needle in ('authenticate_legacy_bearer_user', '_get_auth_legacy_firebase', '_get_firebase_service'):
       assert needle not in text, needle
   print('legacy auth seam retired')
   PY
   ```
2. **Expected:** The command prints `legacy auth seam retired` and exits 0.

### 4. Backend residue reporting separates real drift from retired proof boundaries

1. Run:
   ```bash
   bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend
   ```
2. **Expected:** Output contains `[backend]` with `no approved residue`, plus `[backend-proof-only]` entries for the surviving explicit rejection/quarantine boundaries (`firebase_uid`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`). The command ends with `RESULT: --report backend OK`.

## Edge Cases

### Mixed cookie + bearer input still resolves by the cookie contract

1. Run:
   ```bash
   cd backend-hormonia && pytest -q tests/unit/test_auth_dependencies.py -k mixed_cookie_and_bearer
   ```
2. **Expected:** `1 passed`. The presence of a legacy bearer token alongside a valid session cookie does not reopen bearer auth; the request still resolves through the canonical session dependency.

### Admin test mode still fails closed when legacy transport is attempted

1. Run:
   ```bash
   cd backend-hormonia && pytest -q tests/api/v2/test_auth_hard_cut_cleanup.py -k admin_dependency_rejects_legacy_transport_without_cookie_even_in_test_mode
   ```
2. **Expected:** `1 passed`. The admin wrapper only uses its no-auth test fallback when there was no auth attempt at all; a legacy header/bearer attempt without the cookie is rejected.

### WebSocket `session_id` query fallback remains retirement-only, not accepted auth

1. Run:
   ```bash
   cd backend-hormonia && pytest -q tests/api/test_websocket_session_auth_contract.py -k rejects_legacy_session_transport_without_cookie
   ```
2. **Expected:** `1 passed`. A websocket handshake that relies on legacy `session_id` transport without the canonical cookie is rejected with the published auth diagnostic.

## Failure Signals

- `verify-runtime-residue.sh --check backend` reports any approved residue or fails with `unexpected_file=` / `moved_proof_boundary=`.
- The focused cleanup pytest run no longer returns `2 passed`, or starts accepting legacy header/bearer transport without the cookie.
- The static seam check raises on `authenticate_legacy_bearer_user`, `_get_auth_legacy_firebase`, or `_get_firebase_service` appearing again in `auth_dependencies.py`.
- `--report backend` stops showing the split between `[backend]` and `[backend-proof-only]`, which means the republished boundary model drifted.

## Requirements Proved By This UAT

- R052 — Advances the requirement by proving backend auth/session no longer treats legacy bearer/header/query transport as approved live behavior and by turning the residue verifier into a zero-approved regression guard for this seam.

## Not Proven By This UAT

- R052 is not fully validated here; S02 still owns structural Firebase-era schema residue, S03 still owns repo-wide bridge/docs/workflow cleanup, and S04 still owns the integrated final absence/schema/mounted proof pack.

## Notes for Tester

This slice is intentionally narrow. Seeing `firebase_uid` in `[backend-proof-only]` is not a failure by itself; it is the published signal that those remaining mentions are explicit quarantine or rejection surfaces, not approved live residue. Treat any new approved hit as regression, and treat disappearance of a proof-only boundary as suspicious unless the owning cleanup slice also removed or republished its focused proof.
