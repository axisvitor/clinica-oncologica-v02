# Cloud Run + Cloud Tasks configuration

These templates assume Cloud Tasks + Cloud Scheduler (cloud-native) for background jobs.

Files:
- `service-api.yaml`: API service with Cloud Tasks env vars enabled.
- `service-tasks.yaml`: dedicated task runner service for `/api/v2/internal/tasks/execute`.
- `cloud-tasks-queue.yaml`: Cloud Tasks queue settings (retries disabled; app handles retries).
- `cloud-scheduler-jobs.yaml`: periodic job catalog with task payloads.

Notes:
- Cloud Scheduler runs at minute granularity. The 30-second Celery job is mapped to 1 minute.
- Use OIDC auth for scheduler and Cloud Tasks; set `CLOUD_TASKS_OIDC_SERVICE_ACCOUNT` and IAM accordingly.
- If you prefer a shared secret, set `CLOUD_TASKS_SHARED_SECRET` and send `x-tasks-token`.

Example commands:
```bash
gcloud tasks queues create TASK_QUEUE \
  --location=REGION \
  --queue-config=cloud-tasks-queue.yaml

gcloud scheduler jobs create http JOB_NAME \
  --location=REGION \
  --schedule="*/5 * * * *" \
  --uri="https://REPLACE_WITH_TASKS_SERVICE_URL/api/v2/internal/tasks/execute" \
  --http-method=POST \
  --oidc-service-account-email="REPLACE_WITH_TASKS_INVOKER_SA" \
  --message-body='{"task_name":"process_scheduled_messages","args":[],"kwargs":{"limit":100}}'
```
