---
id: T02
parent: S04
milestone: M015
key_files:
  - scripts/security/m015-runtime/artifact_seam.py
  - backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py
key_decisions:
  - Implement `artifact_seam.py` as a standalone runtime helper that uses real HTTP calls to `http://api:8080` with cookie-backed sessions, not TestClient/dependency overrides or Bearer shortcuts.
  - For T02 evidence helpers, store hashes, status classes, booleans, and route labels only; never store raw upload bytes, raw header values, session IDs, private storage paths, or static URLs.
  - Keep T02 scoped to upload app-route proof helpers and contracts; report/export runtime proof remains T03 and runner execution remains T05.
duration: 
verification_result: passed
completed_at: 2026-05-14T16:37:46.721Z
blocker_discovered: false
---

# T02: Built the S04 private upload artifact probe helper and test contracts for gated private downloads, public/static split, safe headers, and redaction-safe upload evidence.

**Built the S04 private upload artifact probe helper and test contracts for gated private downloads, public/static split, safe headers, and redaction-safe upload evidence.**

## What Happened

Added `scripts/security/m015-runtime/artifact_seam.py` with the first S04 artifact seam implementation. The helper bootstraps synthetic owner, foreign, and admin staff sessions in PostgreSQL, applies Alembic before probing, builds multipart upload requests, and calls the running FastAPI app over internal Compose HTTP using the real session cookie contract. The upload probe creates private and public synthetic uploads, verifies private responses point to `/api/v2/upload/{id}/download` instead of `/uploads`, checks owner/admin private downloads for safe attachment headers, checks anonymous/cross-owner denial without private byte/path/redirect leakage, confirms direct static access to the private storage path is denied, and confirms intentionally public uploads remain available through `/uploads`. The evidence helpers summarize upload outcomes as status codes/classes, header booleans, body-match booleans, hashes, and explicit raw-value persistence flags. Added `test_m015_s04_artifact_runtime_contract.py` to guard real HTTP/cookie usage, multipart construction, safe summary shape, denial leakage checks, and header-value non-persistence.

## Verification

Fresh T02 verification passed after the last edit: `python3 -m py_compile scripts/security/m015-runtime/artifact_seam.py && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_s04_artifact_runtime_contract.py tests/api/v2/test_private_upload_serving.py tests/security/test_m014_s04_private_artifact_serving.py -q`. Pytest reported `...................... [100%]` for 22 tests.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 -m py_compile scripts/security/m015-runtime/artifact_seam.py && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_s04_artifact_runtime_contract.py tests/api/v2/test_private_upload_serving.py tests/security/test_m014_s04_private_artifact_serving.py -q` | 0 | ✅ pass — artifact_seam.py compiled and 22 upload/runtime-contract regression tests reached 100% | 23400ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `scripts/security/m015-runtime/artifact_seam.py`
- `backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py`
