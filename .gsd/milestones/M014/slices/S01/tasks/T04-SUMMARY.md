---
id: T04
parent: S01
milestone: M014
key_files:
  - backend-hormonia/app/integrations/wuzapi/webhook.py
  - backend-hormonia/app/integrations/whatsapp/security/hmac_validator.py
  - backend-hormonia/app/services/webhook_service.py
  - backend-hormonia/app/services/webhook/idempotency.py
  - backend-hormonia/tests/security/test_m014_s01_webhook_replay.py
  - backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py
  - backend-hormonia/tests/services/test_webhook_service_fail_closed.py
key_decisions:
  - D019: Webhook replay and idempotency failures fail closed at ingress with 403/409/503 status semantics and PHI-safe diagnostics.
  - MEM069: Webhook replay hardening treats uniqueness as an ingress authorization gate and logs only hashed identifiers.
duration: 
verification_result: passed
completed_at: 2026-05-13T07:19:16.897Z
blocker_discovered: false
---

# T04: Hardened WuzAPI and generic webhook ingress so HMAC/timestamp/idempotency replay failures deny before processing side effects.

**Hardened WuzAPI and generic webhook ingress so HMAC/timestamp/idempotency replay failures deny before processing side effects.**

## What Happened

Implemented fail-closed webhook ingress behavior across the WuzAPI router, generic WebhookService, and shared AtomicWebhookIdempotency fallback. WuzAPI now honors WHATSAPP_WEBHOOK_HMAC_ENABLED, requires WHATSAPP_WUZAPI_WEBHOOK_SECRET when HMAC is enabled, validates optional/required webhook timestamps via a centralized validator, and denies duplicate events with 409 or idempotency infrastructure uncertainty with 503 before calling message, receipt, DLQ, DB, provider, or flow-continuation handlers. Generic WebhookService now raises HTTPException for duplicate/idempotency-denied inbound webhooks instead of returning a successful duplicate response, and the direct fallback path no longer tries a fail-open DB uniqueness check when Redis cannot prove idempotency. AtomicWebhookIdempotency DB fallback no longer returns acquired on fallback errors. Added M014/S01 security tests for invalid HMAC, missing secret, stale timestamp, duplicate event, Redis failure, and valid signed fixture behavior; updated existing WuzAPI integration tests to make HMAC-disabled fixtures explicit and to expect 409/503 denial semantics.

## Verification

Ran the required task pytest command for webhook replay hardening: 32 tests passed, covering the new security contract, existing WuzAPI integration fixture flows, and generic WebhookService fail-closed cases. Also ran the shared AtomicWebhookIdempotency regression suite after changing fallback behavior: 21 tests passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_webhook_replay.py backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py backend-hormonia/tests/services/test_webhook_service_fail_closed.py` | 0 | ✅ pass — 32 passed in 2.91s | 26981ms |
| 2 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/services/webhook/test_atomic_idempotency.py -q` | 0 | ✅ pass — 21 passed | 25353ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/integrations/wuzapi/webhook.py`
- `backend-hormonia/app/integrations/whatsapp/security/hmac_validator.py`
- `backend-hormonia/app/services/webhook_service.py`
- `backend-hormonia/app/services/webhook/idempotency.py`
- `backend-hormonia/tests/security/test_m014_s01_webhook_replay.py`
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py`
- `backend-hormonia/tests/services/test_webhook_service_fail_closed.py`
