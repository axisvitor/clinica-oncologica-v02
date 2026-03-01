# Cloud Run Configuration

Cloud Run service definitions for the Hormonia backend.

## Files
- `Dockerfile`: Container image for API, worker, and beat services.
- `service-api.yaml`: API service configuration (Cloud Run).
- `service-whatsapp-worker.yaml`: WhatsApp webhook worker service.

## Architecture
- **Task Queue**: Celery with Dragonfly (Redis-compatible) as broker/backend.
- **Scheduler**: Celery Beat (all periodic tasks defined in `app/celery_app.py`).
- **Local Dev**: Use `docker-compose.yml` in the backend root for Dragonfly + Worker + Beat.

## Notes
- Cloud Tasks and Cloud Scheduler were removed. All background jobs use Celery + Dragonfly.
- Dragonfly is a drop-in Redis replacement (same protocol, same `redis://` URL).
- Worker and Beat services run alongside the API (Railway or Cloud Run).
