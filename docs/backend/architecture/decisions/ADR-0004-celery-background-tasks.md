# ADR-0004: Celery + Beat for Background Tasks

## Status

Accepted

Date: 2024-01-18

## Context

The Clínica Hormonia system requires robust background task processing for:
- **Email notifications**: Send quiz invitations, alerts, and reports asynchronously
- **WhatsApp messages**: Process Evolution API webhooks and send messages
- **Scheduled tasks**: Daily/weekly/monthly quiz scheduling, reminder notifications
- **Report generation**: Generate PDF reports without blocking API requests
- **Data processing**: Analyze quiz responses, calculate risk scores
- **Integration sync**: Sync with external systems (Evolution API, Firebase)
- **Cleanup jobs**: Archive old data, clear expired sessions

Requirements:
- Reliable task execution with retries
- Scheduled recurring tasks (cron-like)
- Task prioritization (urgent alerts vs. routine reports)
- Distributed execution across workers
- Monitoring and failure tracking
- Graceful error handling and dead letter queue

## Decision

We will use **Celery 5+ with Celery Beat** for all background task processing, using Redis as the broker and result backend.

Key components:
1. **Celery Workers**: Process async tasks (emails, WhatsApp, reports)
2. **Celery Beat**: Schedule recurring tasks (cron jobs)
3. **Redis Broker**: Task queue with persistence
4. **Redis Results**: Store task results with TTL
5. **Task priorities**: Separate queues for urgent/normal/low priority
6. **Retries**: Exponential backoff for failed tasks
7. **Monitoring**: Flower dashboard for task visibility

## Consequences

### Positive Consequences

- **Non-blocking API**: Long-running tasks don't block HTTP responses
- **Reliability**: Tasks survive worker crashes with Redis persistence
- **Scalability**: Add workers to increase throughput
- **Scheduling**: Cron-like scheduling with Beat
- **Retry logic**: Automatic retries with exponential backoff
- **Monitoring**: Flower provides real-time task visibility
- **Priority queues**: Critical tasks processed first
- **Distributed**: Tasks distributed across multiple workers
- **Error handling**: Dead letter queue for failed tasks

### Negative Consequences

- **Complexity**: Another service to manage and monitor
- **Debugging**: Async task debugging harder than synchronous code
- **State management**: Need to handle worker restarts gracefully
- **Memory usage**: Each worker consumes memory
- **Latency**: Tasks not instant (queue processing delay)

### Risks

- **Task loss**: Redis failure could lose queued tasks (mitigated with persistence)
- **Worker crashes**: Unhandled exceptions can crash workers
- **Queue buildup**: Slow tasks can cause queue backlog
- **Resource exhaustion**: Too many concurrent tasks can overwhelm resources
- **Beat single point**: Only one Beat instance should run (use locks)

## Alternatives Considered

### Alternative 1: Background Threads (asyncio)

**Description**: Use Python asyncio background tasks

**Pros**:
- No external dependencies
- Simple for basic tasks
- Lower latency

**Cons**:
- Not distributed (single process)
- Lost on restart
- No scheduling support
- Hard to monitor
- No priority queues
- Poor error handling

**Why rejected**: Cannot scale horizontally and lacks robustness

### Alternative 2: Apache Airflow

**Description**: Workflow orchestration platform

**Pros**:
- Powerful DAG-based workflows
- Rich UI and monitoring
- Complex dependency management
- Great for data pipelines

**Cons**:
- Overkill for our use case
- Heavy infrastructure
- Steep learning curve
- Higher operational cost
- Designed for batch processing, not real-time tasks

**Why rejected**: Too complex for our relatively simple task requirements

### Alternative 3: RabbitMQ + Custom Workers

**Description**: Build custom worker system with RabbitMQ

**Pros**:
- Full control over implementation
- Robust message broker
- Flexible routing

**Cons**:
- Reinventing the wheel
- More code to maintain
- No built-in scheduling
- No monitoring tools
- Team needs to build retry logic

**Why rejected**: Celery provides all needed features out of the box

### Alternative 4: AWS Lambda

**Description**: Serverless functions for background tasks

**Pros**:
- Auto-scaling
- No infrastructure management
- Pay per execution

**Cons**:
- Vendor lock-in
- Cold start latency
- 15-minute execution limit
- Complex local development
- Harder to debug
- Cost unpredictable at scale

**Why rejected**: Want to maintain infrastructure flexibility and avoid cold starts

## Implementation Notes

### Task Definition

```python
@celery_app.task(bind=True, max_retries=3, default_retry_delay=300)
def send_quiz_email(self, patient_id: str, quiz_id: str):
    try:
        patient = get_patient(patient_id)
        quiz = get_quiz(quiz_id)

        send_email(
            to=patient.email,
            subject=f"Monthly Quiz: {quiz.title}",
            template="quiz_invitation",
            context={"patient": patient, "quiz": quiz}
        )

        log_email_sent(patient_id, quiz_id)

    except SMTPException as exc:
        # Retry on temporary email failures
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    except Exception as exc:
        # Log permanent failures
        log_task_failure(self.request.id, str(exc))
        raise
```

### Scheduled Tasks (Beat)

```python
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    'send-monthly-quiz': {
        'task': 'tasks.send_monthly_quiz',
        'schedule': crontab(day_of_month='1', hour='9', minute='0'),
        'args': (),
    },
    'cleanup-expired-sessions': {
        'task': 'tasks.cleanup_sessions',
        'schedule': crontab(hour='2', minute='0'),  # Daily at 2 AM
        'args': (),
    },
    'generate-weekly-reports': {
        'task': 'tasks.generate_reports',
        'schedule': crontab(day_of_week='monday', hour='8', minute='0'),
        'args': (),
    },
}
```

### Priority Queues

```python
# Define queues with priorities
celery_app.conf.task_routes = {
    'tasks.send_urgent_alert': {'queue': 'urgent'},
    'tasks.send_email': {'queue': 'normal'},
    'tasks.generate_report': {'queue': 'low'},
}

# Start workers with specific queues
# Worker 1: celery -A app worker -Q urgent,normal,low
# Worker 2: celery -A app worker -Q urgent,normal
# Worker 3: celery -A app worker -Q low
```

### Error Handling

```python
@celery_app.task(bind=True, max_retries=5)
def process_whatsapp_webhook(self, webhook_data: dict):
    try:
        # Idempotency check
        idempotency_key = webhook_data.get('id')
        if redis.exists(f"processed:{idempotency_key}"):
            return {"status": "already_processed"}

        # Process webhook
        result = handle_webhook(webhook_data)

        # Mark as processed
        redis.setex(f"processed:{idempotency_key}", 86400, "1")

        return result

    except NetworkError as exc:
        # Retry on network errors with exponential backoff
        raise self.retry(exc=exc, countdown=min(2 ** self.request.retries * 60, 3600))
    except ValidationError as exc:
        # Don't retry validation errors, send to DLQ
        send_to_dead_letter_queue(webhook_data, str(exc))
        raise
```

### Monitoring Configuration

```python
# Flower dashboard
celery -A app flower --port=5555

# Prometheus metrics
celery_app.conf.worker_send_task_events = True
celery_app.conf.task_send_sent_event = True
```

### Worker Configuration

```bash
# Production worker setup
celery -A app worker \
  --loglevel=info \
  --concurrency=4 \
  --max-tasks-per-child=1000 \
  --time-limit=3600 \
  --soft-time-limit=3300 \
  -Q urgent,normal,low

# Beat scheduler (single instance)
celery -A app beat \
  --loglevel=info \
  --pidfile=/var/run/celerybeat.pid
```

### Deployment Strategy

1. ✅ Celery 5+ installed with Redis broker
2. ✅ Beat scheduler for recurring tasks
3. ✅ Priority queues configured
4. ✅ Retry logic with exponential backoff
5. ✅ Flower monitoring dashboard
6. ✅ Docker containers for workers and beat
7. 🔄 Prometheus metrics integration
8. 🔄 Dead letter queue for failed tasks
9. 🔄 Auto-scaling based on queue depth

## References

- [Celery Documentation](https://docs.celeryproject.org/)
- [Celery Best Practices](https://docs.celeryproject.org/en/stable/userguide/tasks.html#best-practices)
- [Flower Monitoring](https://flower.readthedocs.io/)
- [Task Queue Patterns](https://www.enterpriseintegrationpatterns.com/patterns/messaging/)
- [Redis as Celery Broker](https://docs.celeryproject.org/en/stable/getting-started/backends-and-brokers/redis.html)

## Metadata

- **Author**: Backend Team
- **Reviewers**: Infrastructure Team, DevOps Team
- **Last Updated**: 2024-01-18
- **Related ADRs**: ADR-0003 (Redis), ADR-0001 (FastAPI), ADR-0005 (Evolution API)
- **Tags**: backend, async, infrastructure, scalability, celery
