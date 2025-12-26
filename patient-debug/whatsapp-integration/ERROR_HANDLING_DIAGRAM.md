# WhatsApp Integration - Error Handling & Recovery Flow

## Error Handling Architecture

### 1. Message Delivery Error Flow

```
[Message Creation]
       │
       ├─> Create Message (status=PENDING)
       ├─> db.flush() (get ID without commit)
       │
       ▼
[Schedule Message]
       │
       ├─ SUCCESS? ──YES──> db.commit() ──> Message sent ✓
       │                         │
       │                         └─> Analytics tracking
       │                         └─> WebSocket broadcast
       │
       ├─ FAILURE?
       │     │
       │     ├─> db.rollback() (atomic safety)
       │     │
       │     ├─ Is Transient Error?
       │     │     │
       │     │     ├─ YES (connection, timeout, deadlock)
       │     │     │    │
       │     │     │    ├─> Retry attempt 2 (delay: 1s)
       │     │     │    ├─> Retry attempt 3 (delay: 2s)
       │     │     │    └─> Max retries (3) reached?
       │     │     │             │
       │     │     │             ├─ YES ──> Create FAILED record
       │     │     │             └─ NO  ──> Continue retrying
       │     │     │
       │     │     └─ NO (validation, not found, integrity)
       │     │          │
       │     │          └─> Immediate failure (no retry)
       │     │
       │     └─> Create audit trail:
       │           └─> Message (status=FAILED, metadata={error, attempts, ...})
```

### 2. Evolution API Failure Scenarios

#### Scenario A: API Temporarily Unavailable

```
[send_via_evolution() fails with ConnectionError]
       │
       ├─> Catch EvolutionAPIError
       ├─> Check retry_count < max_retries (5 for flow messages)
       │
       ├─ YES ──> Schedule retry with exponential backoff
       │          │
       │          ├─> Retry 1: now + 3 min (180s)
       │          ├─> Retry 2: now + 4.5 min (270s)
       │          ├─> Retry 3: now + 6.75 min (405s)
       │          ├─> Retry 4: now + 10.125 min (607.5s)
       │          └─> Retry 5: now + 15.2 min (911.25s)
       │
       └─ NO  ──> Mark message as FAILED
                  ├─> Update status
                  ├─> Store error in metadata
                  └─> Alert admin (TODO: implement alerting)
```

#### Scenario B: Instance Not Connected

```
[Evolution instance status check]
       │
       ├─> health_check() returns {"healthy": false, "connected": false}
       │
       ├─> OPTION 1: Queue message for later retry
       │     └─> Message stays in PENDING status
       │     └─> Celery task will retry every 30 seconds
       │
       ├─> OPTION 2: Fallback to SMS (future enhancement)
       │     └─> Not implemented yet
       │
       └─> OPTION 3: Notify admin to reconnect instance
             └─> Email/Slack alert (TODO)
```

### 3. Webhook Processing Errors

```
[POST /webhooks/whatsapp/evolution/{instance}]
       │
       ├─> Rate limit check (500/min per IP+instance)
       │     │
       │     ├─ EXCEEDED ──> HTTP 429 Too Many Requests
       │     │                └─> Evolution retries later
       │     │
       │     └─ OK ──> Continue
       │
       ├─> Idempotency check (Atomic Redis SET NX EX)
       │     │
       │     ├─ DUPLICATE ──> HTTP 200 OK (skip processing)
       │     │                └─> Log: "Duplicate event ignored"
       │     │
       │     └─ NEW ──> Continue
       │
       ├─> Parse webhook payload
       │     │
       │     ├─ INVALID ──> HTTP 400 Bad Request
       │     │              └─> Log error, return immediately
       │     │
       │     └─ VALID ──> Continue
       │
       ├─> Find patient by phone hash
       │     │
       │     ├─ NOT FOUND ──> Log warning, return 200 OK
       │     │                (Patient might not be registered)
       │     │
       │     └─ FOUND ──> Process message
       │
       ├─> Trigger flow engine (background task)
       │     │
       │     ├─ TASK FAILS ──> Log error (non-critical)
       │     │                 └─> Webhook still returns 200 OK
       │     │                 └─> Evolution won't retry
       │     │
       │     └─ TASK SUCCEEDS ──> AI processes response
       │
       └─> Return HTTP 200 OK (always, unless critical error)
```

### 4. Database Transaction Failures

```
[Database Operation]
       │
       ├─ SQLAlchemyError (connection lost, deadlock, etc.)
       │     │
       │     ├─> db.rollback() immediately
       │     ├─> Log error with full traceback
       │     │
       │     ├─ Retry? (attempt < max_retries)
       │     │     │
       │     │     ├─ YES ──> Wait (exponential backoff)
       │     │     │          └─> Retry transaction
       │     │     │
       │     │     └─ NO  ──> Raise exception
       │     │                └─> Celery task fails
       │     │                └─> Task will be retried by Celery
       │     │
       │     └─ IntegrityError (unique constraint, foreign key)
       │           │
       │           └─> Check if race condition
       │                 │
       │                 ├─ Idempotency key conflict?
       │                 │    └─> Return existing message ID
       │                 │
       │                 └─ Other constraint?
       │                      └─> Log error, raise exception
```

### 5. Retry Policy Matrix

| Message Type | Max Retries | Base Delay | Backoff Factor | Max Total Time |
|--------------|-------------|------------|----------------|----------------|
| Flow Message | 5 | 180s (3min) | 1.5 | ~30 minutes |
| Quiz Message | 3 | 300s (5min) | 2.0 | ~25 minutes |
| Default | 3 | 300s (5min) | 2.0 | ~25 minutes |
| Urgent/Alert | 5 | 60s (1min) | 1.5 | ~10 minutes |

**Calculation Example (Flow Message):**
```
Attempt 1: Immediate
Attempt 2: 180s later (3 min)
Attempt 3: 180 * 1.5 = 270s later (4.5 min)
Attempt 4: 180 * 1.5² = 405s later (6.75 min)
Attempt 5: 180 * 1.5³ = 607.5s later (10.125 min)

Total max time: 3 + 4.5 + 6.75 + 10.125 = ~24.4 minutes
```

### 6. Failure Recovery Procedures

#### Recovery 1: Stuck PENDING Messages

**Detection:**
```sql
-- Find messages stuck in PENDING for >1 hour
SELECT id, patient_id, created_at, message_metadata->'error' as error
FROM messages
WHERE status = 'PENDING'
AND created_at < NOW() - INTERVAL '1 hour'
ORDER BY created_at;
```

**Recovery:**
```python
# Celery task: retry_pending_welcome_messages
# Runs every 10 minutes (see celery_app.py)

@shared_task(name="retry_pending_welcome_messages")
def retry_pending_welcome_messages(limit=50, min_age_minutes=5, max_age_hours=24):
    """Retry messages stuck in PENDING status."""

    # Find stuck messages
    stuck_messages = (
        db.query(Message)
        .filter(
            Message.status == MessageStatus.PENDING,
            Message.created_at < datetime.now() - timedelta(minutes=min_age_minutes),
            Message.created_at > datetime.now() - timedelta(hours=max_age_hours),
        )
        .limit(limit)
        .all()
    )

    # Retry each message
    for message in stuck_messages:
        try:
            await whatsapp_service.send_message(message)
        except Exception as e:
            logger.error(f"Retry failed for message {message.id}: {e}")
```

#### Recovery 2: Evolution Instance Reconnection

**Detection:**
```python
# Health check endpoint
health_status = await evolution_client.health_check()

if not health_status["healthy"]:
    # Instance not connected
    logger.error("Evolution instance not connected!")

    # Option 1: Scan QR code manually
    qr_code = await evolution_client.get_qr_code()

    # Option 2: Restart instance (if auto-reconnect enabled)
    await evolution_client.restart_instance()
```

**Manual Steps:**
1. Check Evolution API logs: `docker logs evolution-api-container`
2. Get QR code: `curl http://localhost:8080/instance/qrcode/meuwhatsapp`
3. Scan QR code with WhatsApp
4. Verify connection: `curl http://localhost:8080/instance/connectionState/meuwhatsapp`

#### Recovery 3: Failed Saga Transactions

**Detection:**
```sql
-- Find failed sagas (patient onboarding, etc.)
SELECT id, saga_type, current_step, state_data->'error' as error
FROM patient_onboarding_sagas
WHERE status = 'failed'
AND created_at > NOW() - INTERVAL '24 hours';
```

**Recovery:**
```python
# Celery task: scan_and_retry_failed_sagas
# Runs every 5 minutes (see celery_app.py)

@shared_task(name="app.tasks.saga_retry.scan_and_retry_failed_sagas")
def scan_and_retry_failed_sagas():
    """Retry failed sagas with retry policy."""

    failed_sagas = (
        db.query(PatientOnboardingSaga)
        .filter(
            PatientOnboardingSaga.status == 'failed',
            PatientOnboardingSaga.retry_count < 3,
        )
        .all()
    )

    for saga in failed_sagas:
        try:
            saga_orchestrator.retry_saga(saga.id)
        except Exception as e:
            logger.error(f"Saga retry failed: {e}")
```

### 7. Circuit Breaker Pattern (Future Enhancement)

**Proposed Implementation:**

```python
class CircuitBreaker:
    """
    Prevent cascading failures when Evolution API is down.

    States:
    - CLOSED: Normal operation
    - OPEN: API failing, requests blocked
    - HALF_OPEN: Testing if API recovered
    """

    def __init__(self, failure_threshold=5, timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.state = "CLOSED"
        self.last_failure_time = None
        self.timeout = timeout

    async def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            # Check if timeout elapsed
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker: OPEN -> HALF_OPEN")
            else:
                raise CircuitBreakerOpen("Evolution API circuit breaker is open")

        try:
            result = await func(*args, **kwargs)

            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failure_count = 0
                logger.info("Circuit breaker: HALF_OPEN -> CLOSED")

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"
                logger.error(f"Circuit breaker: {self.state} (failures: {self.failure_count})")

            raise
```

**Usage:**

```python
circuit_breaker = CircuitBreaker(failure_threshold=5, timeout=60)

async def send_message_with_circuit_breaker(phone, message):
    try:
        return await circuit_breaker.call(
            evolution_client.send_text_message,
            phone,
            message
        )
    except CircuitBreakerOpen:
        # Fallback: Queue for later
        await queue_message_for_retry(phone, message)
```

### 8. Dead Letter Queue (DLQ) Processing

**Current Implementation:**

```python
# Celery task: process_whatsapp_dlq
# Runs every 10 minutes (see celery_app.py)

@shared_task(name="app.tasks.messaging.process_whatsapp_dlq")
def process_whatsapp_dlq(limit=50):
    """
    Process messages from Dead Letter Queue.

    DLQ contains:
    - Messages that failed max retries
    - Messages with permanent errors (validation, etc.)
    - Messages older than 24 hours
    """

    dlq_messages = (
        db.query(Message)
        .filter(
            Message.status == MessageStatus.FAILED,
            Message.message_metadata.contains({"dlq": True}),
        )
        .limit(limit)
        .all()
    )

    for message in dlq_messages:
        # Analyze failure reason
        error = message.message_metadata.get("error", "")

        # Decide recovery action
        if "patient not found" in error.lower():
            # Skip, patient deleted
            logger.warning(f"DLQ: Patient not found for message {message.id}")
            continue

        elif "invalid phone" in error.lower():
            # Update patient phone, retry
            logger.warning(f"DLQ: Invalid phone for message {message.id}")
            # TODO: Notify admin to update patient phone
            continue

        else:
            # Generic failure, retry one more time
            try:
                await whatsapp_service.send_message(message)
                logger.info(f"DLQ: Successfully retried message {message.id}")
            except Exception as e:
                logger.error(f"DLQ: Final failure for message {message.id}: {e}")
                # Move to permanent DLQ (TODO: implement)
```

---

## Monitoring & Alerting

### Critical Alerts (PagerDuty/Slack)

1. **Evolution API Down:**
   - Trigger: `health_check()` fails for >5 minutes
   - Action: Alert on-call engineer

2. **High Message Failure Rate:**
   - Trigger: >10% of messages FAILED in last hour
   - Action: Alert team, check Evolution connection

3. **Webhook Processing Errors:**
   - Trigger: >50 webhook errors in 10 minutes
   - Action: Check webhook endpoint, Evolution config

4. **Celery Workers Down:**
   - Trigger: No active workers for >2 minutes
   - Action: Restart workers, alert DevOps

### Warning Alerts (Email/Slack)

1. **Messages Stuck in PENDING:**
   - Trigger: >100 messages PENDING for >30 minutes
   - Action: Check Evolution API, retry tasks

2. **Elevated Retry Rate:**
   - Trigger: >5% of messages require retry
   - Action: Investigate Evolution API performance

3. **Idempotency Cache Misses:**
   - Trigger: Redis connection issues
   - Action: Check Redis health, restart if needed

---

**Documentation Generated:** 2025-12-24 05:35 UTC
