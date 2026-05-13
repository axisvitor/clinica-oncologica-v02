---
estimated_steps: 21
estimated_files: 8
skills_used: []
---

# T01: Fail closed rate limiting with trusted-proxy client identity

---
estimated_steps: 8
estimated_files: 6
skills_used:
  - api-design
  - tdd
  - verify-before-complete
---

Why: S01 cannot prove rate-limit hardening while `check_rate_limit_redis`, `multi_layer_rate_limit`, `DistributedRateLimiter.acquire`, and client identity resolution either fail open or trust `X-Forwarded-For` without a trusted proxy boundary. This task closes the XFF/rate-limit proof gap before route handlers execute.

Files: `backend-hormonia/app/utils/rate_limiter.py`, `backend-hormonia/app/middleware/rate_limit_core.py`, `backend-hormonia/app/middleware/distributed_rate_limiter.py`, `backend-hormonia/app/utils/request_context.py`, optional new `backend-hormonia/app/utils/client_ip.py`, and focused tests under `backend-hormonia/tests/security/` plus existing rate-limit unit tests.

Do:
1. Add or reuse one shared helper for client identity that defaults to `request.client.host` and only honors `X-Forwarded-For`/`X-Real-IP` when an explicit trusted-proxy setting and trusted peer/CIDR allow it.
2. Point SlowAPI `limiter`/`auth_limiter`, `RateLimitMiddleware._get_client_identifier`, webhook multi-layer rate limiting, and `get_request_context` at that helper instead of ad hoc header parsing.
3. Make Redis/rate-limit infrastructure failures fail closed for ingress protection: manual webhook rate checks should raise/return denial instead of allowing, and distributed middleware should honor fail-closed for Redis and unexpected errors.
4. Keep localhost/health exemptions intentional and documented; do not add broad endpoint exemptions to make tests pass.
5. Update existing tests that currently document fail-open behavior so the new expected contract is explicit.
6. Add `backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py` with untrusted-XFF spoof, trusted-proxy XFF, Redis unavailable/error, and over-limit cases.

Failure Modes (Q5): Redis unavailable/error/timeout returns 429 or configured fail-closed denial before endpoint execution; malformed XFF falls back to peer IP or denies if proxy trust is required; missing request/client does not collapse all callers into an attacker-controlled key.

Load Profile (Q6): Shared Redis sorted-set/key operations stay O(log n) per request; denial must avoid DB/provider/saga work; 10x load should hit Redis/rate-limit budget first, not Python memory or downstream DB.

Negative Tests (Q7): spoofed `X-Forwarded-For`, multi-hop malformed headers, Redis `None`, Redis pipeline/script exceptions, over-limit global and per-phone webhook scopes.

Done when: rate-limit denials happen before wrapped endpoints are called, XFF is ignored unless the peer is trusted, and all updated/new rate-limit tests pass with PHI-safe log assertions.

## Inputs

- ``backend-hormonia/app/utils/rate_limiter.py``
- ``backend-hormonia/app/middleware/rate_limit_core.py``
- ``backend-hormonia/app/middleware/distributed_rate_limiter.py``
- ``backend-hormonia/app/utils/request_context.py``
- ``backend-hormonia/app/config/settings/security.py``
- ``backend-hormonia/app/config/settings/integrations.py``
- ``backend-hormonia/tests/unit/test_webhook_rate_limiting.py``
- ``backend-hormonia/tests/unit/middleware/test_rate_limiter.py``

## Expected Output

- ``backend-hormonia/app/utils/client_ip.py``
- ``backend-hormonia/app/utils/rate_limiter.py``
- ``backend-hormonia/app/middleware/rate_limit_core.py``
- ``backend-hormonia/app/middleware/distributed_rate_limiter.py``
- ``backend-hormonia/app/utils/request_context.py``
- ``backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py``
- ``backend-hormonia/tests/unit/test_webhook_rate_limiting.py``
- ``backend-hormonia/tests/unit/middleware/test_rate_limiter.py``

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py backend-hormonia/tests/unit/test_webhook_rate_limiting.py backend-hormonia/tests/unit/middleware/test_rate_limiter.py

## Observability Impact

Add/adjust structured rate-limit logs with route, method, denial reason, scope and redacted/hashed client identity; never log raw XFF chains, phone numbers, cookies, tokens or request bodies.
