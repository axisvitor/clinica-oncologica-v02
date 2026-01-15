# WhatsApp Integration Security

## Security Audit Checklist
- HMAC validation enabled in production (`WHATSAPP_WEBHOOK_HMAC_ENABLED=true`).
- Webhook secret configured (`WHATSAPP_WEBHOOK_SECRET` or `WHATSAPP_EVOLUTION_WEBHOOK_SECRET`).
- Webhook rate limiting active (500/min per IP+instance, 10/min for invalid signatures).
- HMAC failure block enabled after 5 consecutive failures (15-minute block).
- Secrets are injected via environment variables only; no hardcoded keys.
- Logs avoid sensitive payloads; phone numbers are not logged in clear text.
- Circuit breaker protects Evolution API against cascading failures.
- Idempotency keys use Redis `SET NX EX` with TTLs for deduplication.

## Configuration Summary

### Environment Variables
- `WHATSAPP_WEBHOOK_SECRET`: HMAC secret for webhook validation.
- `WHATSAPP_WEBHOOK_HMAC_ENABLED`: Enable/disable HMAC validation (default: true).
- `WHATSAPP_EVOLUTION_API_URL`: Evolution API base URL.
- `WHATSAPP_EVOLUTION_API_KEY`: Evolution API key.
- `WHATSAPP_EVOLUTION_INSTANCE_NAME`: Default instance name.
- `REDIS_URL`: Redis for idempotency, queue, and rate limiting.

### Rate Limiting and Timeouts
- Evolution API rate limiter: 100 req/min (client-side).
- Evolution health check timeout: 10 seconds.
- Evolution request timeout: 30 seconds.
- Webhook rate limit: 500/min per IP+instance.
- HMAC failure rate limit: 10/min per IP+instance.

### Circuit Breaker
- Failure threshold: 5 consecutive failures.
- Recovery timeout: 60 seconds.
- Success threshold: 3 successes to close from half-open.

### Idempotency TTLs
- Message events: 24 hours.
- Status updates: 1 hour.

### DLQ and Retry Policies
- Max retries: 3.
- Backoff delays: 60s, 120s, 240s.
- Failure categories: `RATE_LIMIT`, `TIMEOUT`, `INVALID_PHONE`, `API_ERROR`.
