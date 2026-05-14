---
estimated_steps: 14
estimated_files: 4
skills_used: []
---

# T04: Build the session runtime probe and redaction-validated evidence

Why: The runner/worker wiring is not enough; S02 needs an executable probe that drives API/cache/DB/worker boundaries and writes durable PHI-safe evidence for the exact session cases claimed.

Expected executor skills_used frontmatter: `tdd`, `observability`, `verify-before-complete`.
Estimated scope: about 9 steps / 4 files.

Do:
1. Add `scripts/security/m015-runtime/session_seam.py` for `session-probe`; run/apply migrations or a shared migration helper, seed synthetic local-auth users/sessions, and call `http://api:8080` with `X-Forwarded-Proto: https` and `Host: api`.
2. Drive API calls with cookie-backed staff auth only and include a negative legacy-header/Bearer proof.
3. Use `/api/v2/users/me` for dependency-level auth proof and `/api/v2/users/sessions/{session_id}` for explicit revocation invalidation proof.
4. Manipulate Dragonfly `session:<id>` keys and PostgreSQL `sessions` rows to prove active cache hit success, cache-miss DB fallback/rehydration, revoked stale-cache denial, expired stale-cache denial, and explicit revocation cache deletion.
5. Dispatch `app.tasks.m015_session_security_taskiq` through Dragonfly; include active-session worker allow and queued-before-revocation gate case returning `denied/session_revoked` after DB revocation.
6. Write `session-seam-evidence.json` and `session-seam-summary.md` via `write_validated_json/text`, storing command, correlation ID, timestamps, versions, API status codes, cache/DB/worker outcomes, sanitized failure classes, session hashes/booleans only, and non-goals.
7. Add/update static evidence-shape tests and README usage/recovery/non-goal notes.

Failure Modes (Q5): migration missing -> probe migration phase fails; API 5xx/malformed JSON -> endpoint/status/failure class and non-zero; Redis unavailable -> cache/broker class; Taskiq result timeout -> worker phase fails; redaction finding -> evidence phase fails before durable write.
Load Profile (Q6): small fixture/session/key/task set per isolated run; at 10x runs DB migration locks, Dragonfly memory, worker concurrency, and Docker resources break first.
Negative Tests (Q7): legacy header denied, revoked stale cache denied, expired stale cache denied, raw cookie/session/provider/PHI evidence rejected, worker denied after gate+revocation, and provider/artifact seams listed only as non-goals.

## Inputs

- `scripts/security/m015-runtime/redaction.py`
- `scripts/security/m015-runtime/db_seam.py`
- `scripts/security/m015-runtime/m015_session_security_taskiq.py`
- `scripts/security/m015-runtime/docker-compose.yml`
- `scripts/security/verify-m015-runtime-security.sh`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `scripts/security/m015-runtime/tests/test_runner_contract.py`

## Expected Output

- `scripts/security/m015-runtime/session_seam.py`
- `scripts/security/m015-runtime/README.md`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `scripts/security/m015-runtime/tests/test_runner_contract.py`

## Verification

PYTHONPATH=backend-hormonia python -m py_compile scripts/security/m015-runtime/session_seam.py scripts/security/m015-runtime/m015_session_security_taskiq.py && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_runtime_harness.py tests/security/test_m015_s02_session_runtime_contract.py -q

## Observability Impact

Adds durable session evidence/summary generation, probe phase status, sanitized endpoint/worker/cache failure classes, and non-goal accounting for downstream matrix work.
