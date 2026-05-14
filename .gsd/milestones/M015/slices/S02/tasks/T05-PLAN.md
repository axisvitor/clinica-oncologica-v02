---
estimated_steps: 12
estimated_files: 2
skills_used: []
---

# T05: Run the session seam and commit fresh sanitized evidence artifacts

Why: S02 is an operational proof slice and is not complete until the real root runner exercises the session seam and leaves durable redaction-validated evidence for S05.

Expected executor skills_used frontmatter: `verify-before-complete`, `observability`.
Estimated scope: about 5 steps / 2 stable output files.

Do:
1. Run shell syntax, Compose config, and backend S02/static auth contract gates from the repo root.
2. Run `./scripts/security/verify-m015-runtime-security.sh --seam session` with default teardown.
3. Inspect only stable evidence artifacts (`session-seam-evidence.json`, `session-seam-summary.md`), not `.gsd/` or generated runtime scratch.
4. Verify JSON has `seam=session`, all current/cache-miss/revoked/expired/explicit-revoke/worker cases, redaction `passed`, teardown `complete`, and explicit S03-S05/browser/live-provider/production-data non-goals.
5. If any runtime red signal appears, fix code/harness and rerun; do not document a failing signal as green.

Failure Modes (Q5): Docker unavailable, port collision, build failure, migration failure, API/Redis/worker timeout, redaction failure, or teardown failure all block completion and must leave sanitized diagnostics.
Load Profile (Q6): one full synthetic stack and small request/task set; at 10x parallelism Docker/port/project isolation breaks first.
Negative Tests (Q7): final evidence includes denied revoked, denied expired, denied legacy transport, denied worker-after-revocation, and redaction-passed status; missing any case fails.

## Inputs

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `scripts/security/m015-runtime/session_seam.py`
- `scripts/security/m015-runtime/m015_session_security_taskiq.py`
- `scripts/security/m015-runtime/redaction.py`
- `backend-hormonia/tests/security/test_m015_s02_session_runtime_contract.py`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`

## Expected Output

- `backend-hormonia/docs/reports/security/m015/session-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/session-seam-summary.md`

## Verification

bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s02_session_runtime_contract.py tests/security/test_m015_runtime_harness.py tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py -q && cd .. && ./scripts/security/verify-m015-runtime-security.sh --seam session

## Observability Impact

Produces stable evidence artifacts consumed by S05 and confirms teardown status, redaction status, case-level auth outcomes, and worker denial reasons are inspectable without secrets.
