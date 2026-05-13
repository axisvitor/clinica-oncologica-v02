---
estimated_steps: 22
estimated_files: 6
skills_used: []
---

# T04: Deny webhook replay and idempotency infrastructure gaps before processing

---
estimated_steps: 9
estimated_files: 6
skills_used:
  - api-design
  - tdd
  - verify-before-complete
---

Why: Generic webhooks and WuzAPI ingress are external state-changing paths. Current WuzAPI handling can skip HMAC when the secret is absent and continue after idempotency errors; duplicate events can return a successful duplicate body instead of a denial. S01 requires HMAC/timestamp/idempotency replay failures to deny before message persistence, flow continuation, DLQ enqueue, or provider-like side effects.

Files: `backend-hormonia/app/integrations/wuzapi/webhook.py`, `backend-hormonia/app/services/webhook_service.py`, `backend-hormonia/app/services/webhook/idempotency.py`, and focused webhook tests.

Do:
1. Require WuzAPI HMAC when webhook HMAC is enabled; if enabled but the secret is missing, fail closed before parsing/processing. Keep tests that intentionally disable HMAC explicit via settings.
2. Implement/centralize timestamp validation using existing `WHATSAPP_WEBHOOK_TIMESTAMP_REQUIRED` and `WHATSAPP_WEBHOOK_MAX_TIMESTAMP_AGE_SECONDS` settings; stale, missing or malformed timestamps deny before effects when required.
3. Ensure WuzAPI idempotency acquisition failure from Redis/cache returns a denial (503 for infrastructure failure, 409 for duplicate/replay) and never proceeds to `_handle_message`, `_handle_receipt`, `_route_lid_to_dlq`, DB writes or flow continuation.
4. Make generic `WebhookService.process_inbound_webhook` duplicate/idempotency failures deny consistently instead of silently treating duplicate replay as success.
5. Remove last-resort fail-open behavior from `AtomicWebhookIdempotency` DB fallback; infrastructure failure must not authorize processing.
6. Update WuzAPI/generic webhook tests for the new duplicate status and explicit HMAC-disabled fixtures.
7. Add `backend-hormonia/tests/security/test_m014_s01_webhook_replay.py` with invalid HMAC, missing secret, stale timestamp, duplicate event, Redis idempotency failure and valid fixture path.

Failure Modes (Q5): Missing secret/config denies; invalid HMAC denies 403; stale/malformed timestamp denies 403/401; duplicate event denies 409; Redis/DB idempotency unavailable denies 503 before side effects.

Load Profile (Q6): HMAC/timestamp are O(payload size); idempotency is one atomic Redis write. Under 10x duplicate traffic, Redis/idempotency rejects before DB and queue pressure.

Negative Tests (Q7): missing signature, bad signature, unsupported algorithm, stale/missing timestamp when required, duplicate event ID, body-hash duplicate fallback, idempotency client exception, and valid signed first event.

Done when: duplicate and infrastructure-failure webhooks cannot reach processing handlers, valid signed fixture events still process/ignore appropriately, and logs contain correlation_id/event_type/reason without raw payload, phone, patient ID, token or HMAC secret.

## Inputs

- ``backend-hormonia/app/api/v2/routers/webhooks.py``
- ``backend-hormonia/app/integrations/wuzapi/webhook.py``
- ``backend-hormonia/app/integrations/whatsapp/security/hmac_validator.py``
- ``backend-hormonia/app/services/webhook_service.py``
- ``backend-hormonia/app/services/webhook/idempotency.py``
- ``backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py``
- ``backend-hormonia/tests/services/test_webhook_service_fail_closed.py``

## Expected Output

- ``backend-hormonia/app/integrations/wuzapi/webhook.py``
- ``backend-hormonia/app/services/webhook_service.py``
- ``backend-hormonia/app/services/webhook/idempotency.py``
- ``backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py``
- ``backend-hormonia/tests/services/test_webhook_service_fail_closed.py``
- ``backend-hormonia/tests/security/test_m014_s01_webhook_replay.py``

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_webhook_replay.py backend-hormonia/tests/integrations/wuzapi/test_wuzapi_webhook.py backend-hormonia/tests/services/test_webhook_service_fail_closed.py

## Observability Impact

Webhook denial logs should carry correlation_id, event_type, idempotency reason/status class and route only. Do not log webhook body, message text, phone, patient identifiers, HMAC signature, shared secret or provider token.
