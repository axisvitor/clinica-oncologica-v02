# S01: Ingress, Replay e Rate-Limit Fail-Closed

**Goal:** Harden the externally reachable and browser/session ingress boundaries so missing/invalid CSRF, password-reset replay, webhook replay/idempotency failures, duplicate-patient oracle probes, and spoofed X-Forwarded-For/rate-limit failures deny before DB, queue, provider, or saga side effects while legitimate fixture flows still pass.
**Demo:** Reviewer runs focused backend pytest for CSRF, password reset/webhook replay, duplicate-oracle and trusted-proxy rate limiting; denied paths return 403/409/422/429 before queue/provider/DB side effects while legitimate fixture paths still pass.

## Must-Haves

- Owned requirement: R012. Supporting requirements: R013, R015, R017, R018.
- Q3 Threat Surface:
- Abuse: cross-site state changes on cookie/session endpoints, reset-token reuse, webhook replay/double processing, patient duplicate probing, X-Forwarded-For spoofing to bypass rate limits.
- Data exposure: patient identifiers, names, emails, phones, CPF, reset tokens, cookies and webhook payloads must not appear in errors, logs, or proof artifacts.
- Input trust: browser headers/cookies, reset JWTs, webhook HMAC/timestamps/event IDs, patient create payloads and proxy headers are untrusted until validated by shared guards.
- Q4 Requirement Impact:
- R012 is closed for CSRF, reset replay, webhook replay, duplicate oracle and rate-limit/XFF proof at controlled backend-test level.
- R013 receives concrete evidence for the X-Forwarded-For/rate-limit proof gap.
- R015/R017/R018 are preserved by controlled fixture-only tests and PHI/secret-safe diagnostics.
- Decisions revisited/used: D015, D016, D017.
- Verification for the slice:
- `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py backend-hormonia/tests/security/test_m014_s01_webhook_replay.py backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py`
- `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/unit/test_webhook_rate_limiting.py backend-hormonia/tests/unit/middleware/test_rate_limiter.py backend-hormonia/tests/auth/test_csrf_middleware.py backend-hormonia/tests/api/v2/test_auth_password_recovery.py backend-hormonia/tests/integration/test_password_reset_migration_flow.py backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py backend-hormonia/tests/services/test_webhook_service_fail_closed.py backend-hormonia/tests/api/v2/test_patients_create.py backend-hormonia/tests/integration/test_duplicate_prevention.py`
- Done means denied paths produce explicit 403/409/422/429/503-class fail-closed responses as appropriate before side effects; valid fixture requests continue to pass; failure logs carry only reason/correlation/request identifiers and never raw PHI, reset tokens, cookies, secrets, webhook bodies, or private paths.

## Proof Level

- This slice proves: Contract/integration proof through deterministic backend pytest with mocked Redis, SMTP, WuzAPI and DB/session fixtures. Real production runtime, live providers, real patient data and production-like harnesses are not required for S01 and remain out of scope for R014/M015.

## Integration Closure

S01 wires shared ingress protections into FastAPI middleware, auth/password reset service, rate-limit identity, WuzAPI/generic webhook entrypoints, and patient creation validation. Later slices consume these hardened ingress assumptions: S02 ADK ownership, S03 browser persistence, S04 upload/private serving, and S05 final evidence matrix/JWT/config posture. No downstream roadmap change is needed based on code reconnaissance.

## Verification

- Denied ingress attempts must emit PHI-safe structured diagnostics with reason, route/method, request_id or correlation_id, event_type where applicable, and redacted/hashed client identity only. Future agents inspect pytest assertions and log-cap fixtures; no diagnostics may include patient names, phones, CPF, emails, reset tokens, cookies, HMAC secrets, webhook payloads or filesystem paths.

## Tasks

- [x] **T01: Fail closed rate limiting with trusted-proxy client identity** `est:1.5d`
  ---
  estimated_steps: 8
  estimated_files: 6
  skills_used:
    - api-design
    - tdd
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/utils/rate_limiter.py`, `backend-hormonia/app/middleware/rate_limit_core.py`, `backend-hormonia/app/middleware/distributed_rate_limiter.py`, `backend-hormonia/app/utils/request_context.py`, `backend-hormonia/app/utils/client_ip.py`, `backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py`, `backend-hormonia/tests/unit/test_webhook_rate_limiting.py`, `backend-hormonia/tests/unit/middleware/test_rate_limiter.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py backend-hormonia/tests/unit/test_webhook_rate_limiting.py backend-hormonia/tests/unit/middleware/test_rate_limiter.py

- [x] **T02: Contract CSRF exemptions to non-session ingress only** `est:1d`
  ---
  estimated_steps: 7
  estimated_files: 5
  skills_used:
    - api-design
    - tdd
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/middleware/csrf.py`, `backend-hormonia/tests/auth/test_csrf_middleware.py`, `backend-hormonia/tests/api/v2/test_auth_password_recovery.py`, `backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py backend-hormonia/tests/auth/test_csrf_middleware.py backend-hormonia/tests/api/v2/test_auth_password_recovery.py

- [x] **T03: Make password reset tokens single-use and replay-safe** `est:1.5d`
  ---
  estimated_steps: 8
  estimated_files: 5
  skills_used:
    - api-design
    - tdd
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/core/security.py`, `backend-hormonia/app/services/password_reset_service.py`, `backend-hormonia/tests/api/v2/test_auth_password_recovery.py`, `backend-hormonia/tests/integration/test_password_reset_migration_flow.py`, `backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py backend-hormonia/tests/api/v2/test_auth_password_recovery.py backend-hormonia/tests/integration/test_password_reset_migration_flow.py

- [x] **T04: Deny webhook replay and idempotency infrastructure gaps before processing** `est:1.5d`
  ---
  estimated_steps: 9
  estimated_files: 6
  skills_used:
    - api-design
    - tdd
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/integrations/wuzapi/webhook.py`, `backend-hormonia/app/services/webhook_service.py`, `backend-hormonia/app/services/webhook/idempotency.py`, `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py`, `backend-hormonia/tests/services/test_webhook_service_fail_closed.py`, `backend-hormonia/tests/security/test_m014_s01_webhook_replay.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_webhook_replay.py backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py backend-hormonia/tests/services/test_webhook_service_fail_closed.py

- [x] **T05: Close patient duplicate oracle and run S01 ingress proof** `est:1.5d`
  ---
  estimated_steps: 8
  estimated_files: 7
  skills_used:
    - api-design
    - tdd
    - verify-before-complete
  ---
  - Files: `backend-hormonia/app/services/patient/validation_service.py`, `backend-hormonia/app/services/patient/integrity_service.py`, `backend-hormonia/app/domain/patient/onboarding/validation_service.py`, `backend-hormonia/app/api/v2/routers/patients/crud.py`, `backend-hormonia/tests/api/v2/test_patients_create.py`, `backend-hormonia/tests/integration/test_duplicate_prevention.py`, `backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py backend-hormonia/tests/security/test_m014_s01_webhook_replay.py backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py backend-hormonia/tests/api/v2/test_patients_create.py backend-hormonia/tests/integration/test_duplicate_prevention.py

## Files Likely Touched

- backend-hormonia/app/utils/rate_limiter.py
- backend-hormonia/app/middleware/rate_limit_core.py
- backend-hormonia/app/middleware/distributed_rate_limiter.py
- backend-hormonia/app/utils/request_context.py
- backend-hormonia/app/utils/client_ip.py
- backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py
- backend-hormonia/tests/unit/test_webhook_rate_limiting.py
- backend-hormonia/tests/unit/middleware/test_rate_limiter.py
- backend-hormonia/app/middleware/csrf.py
- backend-hormonia/tests/auth/test_csrf_middleware.py
- backend-hormonia/tests/api/v2/test_auth_password_recovery.py
- backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py
- backend-hormonia/app/core/security.py
- backend-hormonia/app/services/password_reset_service.py
- backend-hormonia/tests/integration/test_password_reset_migration_flow.py
- backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py
- backend-hormonia/app/integrations/wuzapi/webhook.py
- backend-hormonia/app/services/webhook_service.py
- backend-hormonia/app/services/webhook/idempotency.py
- backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py
- backend-hormonia/tests/services/test_webhook_service_fail_closed.py
- backend-hormonia/tests/security/test_m014_s01_webhook_replay.py
- backend-hormonia/app/services/patient/validation_service.py
- backend-hormonia/app/services/patient/integrity_service.py
- backend-hormonia/app/domain/patient/onboarding/validation_service.py
- backend-hormonia/app/api/v2/routers/patients/crud.py
- backend-hormonia/tests/api/v2/test_patients_create.py
- backend-hormonia/tests/integration/test_duplicate_prevention.py
- backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py
