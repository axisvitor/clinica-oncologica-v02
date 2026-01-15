# WhatsApp Integration Runbook

## Monitoring Endpoints
- `GET /api/v2/monitoring/whatsapp/health`
- `GET /api/v2/monitoring/whatsapp/queue-stats`
- `GET /api/v2/monitoring/whatsapp/dlq-stats`
- `GET /api/v2/monitoring/whatsapp/metrics`
- `GET /api/v2/webhooks/whatsapp/idempotency/stats`

## DLQ Investigation
1. Check DLQ metrics via `/api/v2/monitoring/whatsapp/dlq-stats`.
2. Inspect failed message records in the `whatsapp_delivery_failures` table.
3. Validate failure reason and retry metadata in `dlq_metadata`.
4. Confirm the patient record exists and phone number is correct.

## Reprocess Messages from DLQ
1. Review the DLQ entry and confirm it is safe to retry.
2. Use the DLQ requeue workflow (`DLQHandler.requeue_for_retry`) in the admin tooling.
3. Monitor queue size and delivery status after requeue.

## Reset Circuit Breaker
1. Identify breaker state from `/api/v2/monitoring/whatsapp/health`.
2. Use `RedisCircuitBreaker.reset_async()` or `force_closed()` from a maintenance shell.
3. Validate the breaker state returns to `closed` and traffic resumes.

## Scaling Evolution API Instances
1. Provision additional Evolution API instances.
2. Update `WHATSAPP_EVOLUTION_INSTANCE_NAME` or route new traffic by instance.
3. Confirm webhook URLs and HMAC secrets are configured per instance.
4. Monitor queue and DLQ sizes during scale-out.

## Alerts and Thresholds
- Duplicate webhook rate > 5% (idempotency stats).
- DLQ size growth or requeue rate spike.
- Circuit breaker state `open` for more than 5 minutes.
- Webhook signature failures exceeding 10/min.
