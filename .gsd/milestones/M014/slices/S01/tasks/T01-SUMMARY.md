---
id: T01
parent: S01
milestone: M014
key_files:
  - backend-hormonia/app/utils/client_ip.py
  - backend-hormonia/app/utils/rate_limiter.py
  - backend-hormonia/app/middleware/rate_limit_core.py
  - backend-hormonia/app/middleware/distributed_rate_limiter.py
  - backend-hormonia/app/utils/request_context.py
  - backend-hormonia/app/config/settings/security.py
  - backend-hormonia/app/config/settings/integrations.py
  - backend-hormonia/app/config/settings/__init__.py
  - backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py
  - backend-hormonia/tests/unit/test_webhook_rate_limiting.py
  - backend-hormonia/tests/unit/middleware/test_rate_limiter.py
key_decisions:
  - D018: Shared trusted-proxy client identity and fail-closed ingress rate-limit infrastructure policy.
duration: 
verification_result: passed
completed_at: 2026-05-13T06:09:38.100Z
blocker_discovered: false
---

# T01: Hardened rate-limit ingress identity with a trusted-proxy boundary and fail-closed Redis/error handling before endpoint side effects.

**Hardened rate-limit ingress identity with a trusted-proxy boundary and fail-closed Redis/error handling before endpoint side effects.**

## What Happened

Added `app.utils.client_ip` as the shared client identity boundary. It defaults to `request.client.host`, only honors `X-Forwarded-For` or `X-Real-IP` when `RATE_LIMIT_TRUST_PROXY_HEADERS=true` and the direct peer matches `RATE_LIMIT_TRUSTED_PROXIES`, handles malformed proxy headers by falling back to the peer, and exposes hashed/redacted identifiers for structured logs. SlowAPI limiters, distributed middleware identity, webhook rate limiting, and request audit context now use that helper instead of ad hoc proxy-header parsing. Redis-backed ingress rate checks now fail closed by default on unavailable Redis, pipeline errors, and timeouts; the webhook decorator raises 429 before endpoint execution, and the distributed middleware/`DistributedRateLimiter.acquire` honor fail-closed behavior unless explicitly configured otherwise. Rate-limit logs were changed to PHI-safe structured diagnostics with reason, route/method when available, scope, request correlation when present, and hashed client/identifier keys instead of raw IPs, XFF chains, or phone numbers. Added explicit settings fields for rate-limit fail-closed and trusted-proxy configuration, plus WhatsApp trusted-proxy documentation fields, and updated existing tests that documented fail-open behavior.

## Verification

Ran the task-required focused pytest command after the final code change. The suite covered the new security tests plus updated webhook and distributed rate limiter unit tests: trusted and untrusted proxy identity resolution, Redis missing/error fail-closed denial, over-limit global/per-phone webhook denials, endpoint-not-called assertions, and PHI-safe log assertions. Final result: 38 tests passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py backend-hormonia/tests/unit/test_webhook_rate_limiting.py backend-hormonia/tests/unit/middleware/test_rate_limiter.py` | 0 | ✅ pass — 38 passed in 1.63s | 26131ms |

## Deviations

None.

## Known Issues

Existing pytest-asyncio deprecation warning about unset asyncio_default_fixture_loop_scope appears during verification; tests pass and this task did not change pytest configuration.

## Files Created/Modified

- `backend-hormonia/app/utils/client_ip.py`
- `backend-hormonia/app/utils/rate_limiter.py`
- `backend-hormonia/app/middleware/rate_limit_core.py`
- `backend-hormonia/app/middleware/distributed_rate_limiter.py`
- `backend-hormonia/app/utils/request_context.py`
- `backend-hormonia/app/config/settings/security.py`
- `backend-hormonia/app/config/settings/integrations.py`
- `backend-hormonia/app/config/settings/__init__.py`
- `backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py`
- `backend-hormonia/tests/unit/test_webhook_rate_limiting.py`
- `backend-hormonia/tests/unit/middleware/test_rate_limiter.py`
