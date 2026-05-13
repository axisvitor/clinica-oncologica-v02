# S01: Ingress, Replay e Rate-Limit Fail-Closed — UAT

**Milestone:** M014
**Written:** 2026-05-13T14:20:16.304Z

# UAT — M014/S01 Ingress, Replay e Rate-Limit Fail-Closed

**UAT Type:** Backend security regression / controlled fixture proof.

## Preconditions

- Work from the repository root with backend Python dependencies installed.
- Use controlled local test fixtures only; no production traffic, real patient data, live WuzAPI/Gemini/SMTP providers, or production secrets are required.
- `PYTHONPATH=backend-hormonia` is set for the commands below.

## Steps and Expected Outcomes

1. Run the focused S01 security proof:
   ```bash
   PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py backend-hormonia/tests/security/test_m014_s01_webhook_replay.py backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py
   ```
   Expected: all tests pass; closeout evidence showed **39 passed**. Denied ingress attempts return explicit fail-closed responses before route/provider/queue/DB/saga side effects.

2. Run the supporting regression proof:
   ```bash
   PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/unit/test_webhook_rate_limiting.py backend-hormonia/tests/unit/middleware/test_rate_limiter.py backend-hormonia/tests/auth/test_csrf_middleware.py backend-hormonia/tests/api/v2/test_auth_password_recovery.py backend-hormonia/tests/integration/test_password_reset_migration_flow.py backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py backend-hormonia/tests/services/test_webhook_service_fail_closed.py backend-hormonia/tests/api/v2/test_patients_create.py backend-hormonia/tests/integration/test_duplicate_prevention.py
   ```
   Expected: all tests pass; closeout evidence showed **169 passed**. Legitimate fixture paths for rate limiting, CSRF-backed auth/password flows, WuzAPI webhook handling, and patient creation still work.

3. Review failure output or caplog assertions if either command fails.
   Expected: diagnostics contain only PHI-safe fields such as reason, route/method, request or correlation ID, event type/status, and hashed/redacted client identity. They must not include patient names, emails, phones, CPF, reset tokens, cookies, webhook bodies, HMAC secrets, provider payloads, or private paths.

## Edge Cases Covered

- Spoofed `X-Forwarded-For` is ignored unless the direct peer is a configured trusted proxy; Redis/pipeline/timeout uncertainty fails closed with 429-style denial before endpoint execution.
- Missing, invalid, mismatched, expired, or header-bypass CSRF attempts return 403 before dependency/body/route side effects, while valid double-submit and true provider-webhook fixtures pass.
- Password reset replay returns 409 after hashed JTI consumption; malformed/missing/expired reset tokens deny; cache uncertainty fails closed before password/session mutation.
- WuzAPI/generic webhook invalid HMAC/timestamp denies, duplicate event IDs return 409, idempotency infrastructure gaps return 503, and valid signed fixtures still process.
- Duplicate patient CPF/email/phone/name-like probes return a generic 409 `duplicate_patient` conflict before saga/provider work; malformed validation remains 422; cross-doctor fixture allowance remains intact.

## Not Proven By This UAT

- Production-like runtime behavior, live provider lifecycle, live Redis/queue/SMTP/Gemini/WuzAPI integrations, or real patient data handling.
- ADK session ownership, browser cache/quiz persistence, upload stored-XSS/private artifact serving, JWT revocation multi-worker behavior, DB TLS/RLS posture, and final M014 evidence matrix closure; those are owned by downstream slices S02–S05 / M015 scope.

