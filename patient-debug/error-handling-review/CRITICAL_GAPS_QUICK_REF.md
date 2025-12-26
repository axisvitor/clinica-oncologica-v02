# Critical Error Handling Gaps - Quick Reference

## 🚨 P0 - Fix Immediately (This Week)

### 1. Silent Message Send Failures
**File**: `backend-hormonia/app/orchestration/saga_orchestrator.py:409-458`

**Issue**: Welcome messages fail silently without alerting anyone.

**Current Code**:
```python
try:
    success = await self.whatsapp_service.send_message(message)
except Exception as send_exc:
    logger.warning(f"Welcome message send failed (non-fatal): {send_exc}")

# Saga completes even if message failed
saga.status = SagaStatus.STEP_4_MESSAGE_SENT
```

**Fix**:
```python
try:
    success = await self.whatsapp_service.send_message(message)
    if not success:
        # Add to retry queue
        await self.message_retry_queue.enqueue(message.id, retry_count=0)

        # Alert if retries exhausted
        if message.retry_count >= MAX_RETRIES:
            alert_ops_team(
                title="Welcome message failed after max retries",
                patient_id=str(patient.id),
                severity="medium"
            )
except Exception as send_exc:
    logger.error(f"Message send failed: {send_exc}", exc_info=True)
    await self.message_retry_queue.enqueue(message.id, retry_count=0)
```

---

### 2. Task Failures Not Alerted
**File**: `backend-hormonia/app/tasks/follow_up.py:190-197`

**Issue**: Follow-up tasks fail silently after max retries.

**Current Code**:
```python
except Exception as e:
    logger.error(f"Error in task: {e}", exc_info=True)
    if self.request.retries < self.max_retries:
        raise self.retry(exc=e)
    return self.create_error_result(str(e))
```

**Fix**:
```python
except Exception as e:
    logger.error(f"Error in task: {e}", exc_info=True)
    if self.request.retries < self.max_retries:
        raise self.retry(exc=e)

    # Alert after max retries
    alert_ops_team(
        title="Follow-up task failed after max retries",
        details={
            "task_id": self.request.id,
            "task_name": self.name,
            "error": str(e),
            "retry_count": self.request.retries
        },
        severity="high"
    )

    return self.create_error_result(str(e))
```

---

### 3. Cache Invalidation Failures Not Monitored
**File**: `backend-hormonia/app/services/patient/crud_service.py:182-188`

**Issue**: Cache failures are logged but not tracked with metrics.

**Current Code**:
```python
try:
    asyncio.run(self._cache_invalidation.invalidate_entity(...))
except Exception as cache_error:
    self._logger.warning(f"Cache invalidation failed: {cache_error}")
```

**Fix**:
```python
from app.metrics import cache_invalidation_failures

try:
    asyncio.run(self._cache_invalidation.invalidate_entity(...))
except Exception as cache_error:
    self._logger.warning(
        f"Cache invalidation failed for patient {patient_id}: {cache_error}",
        exc_info=True
    )

    # Track metric
    cache_invalidation_failures.labels(entity="patient").inc()

    # Alert if failure rate > 10%
    if self._cache_failure_rate() > 0.10:
        alert_ops_team(
            title="High cache invalidation failure rate",
            details={"failure_rate": self._cache_failure_rate()},
            severity="medium"
        )
```

---

### 4. Standardize Cache Error Logging
**Files**: Multiple (crud_service.py, crud.py, etc.)

**Issue**: Cache failures logged at different levels (DEBUG, WARNING).

**Fix**: Update all cache error logging to WARNING:
```python
# BEFORE (inconsistent)
logger.debug(f"Cache check failed: {e}")  # ❌
logger.warning(f"Cache invalidation failed: {e}")  # ✅

# AFTER (consistent)
logger.warning(f"Cache operation failed: {e}", exc_info=True)  # ✅
metrics.increment("cache.operation.failed")
```

---

## 🔴 P1 - High Priority (This Month)

### 5. HTTP Retry Transport
**File**: `backend-hormonia/app/integrations/evolution/client.py`

**Add**:
```python
from httpx_retry import AsyncRetryTransport

retry_transport = AsyncRetryTransport(
    max_retries=3,
    backoff_factor=0.5,
    status_forcelist=[502, 503, 504, 429],
    retry_on_exceptions=[httpx.ConnectTimeout, httpx.ReadTimeout]
)

self.client = httpx.AsyncClient(
    transport=retry_transport,
    timeout=httpx.Timeout(timeout, connect=10.0),
    headers=headers
)
```

---

### 6. Error Context in Repository
**File**: `backend-hormonia/app/repositories/patient/base.py:179-181`

**Replace**:
```python
# BEFORE (generic)
except Exception:
    self.db.rollback()
    raise

# AFTER (specific)
from sqlalchemy.exc import IntegrityError, OperationalError
from app.exceptions import DatabaseError

except IntegrityError as e:
    self.db.rollback()
    logger.error(f"Integrity constraint violated: {e}", exc_info=True)
    if "phone_hash" in str(e):
        raise DatabaseError("Patient with this phone already exists") from e
    raise DatabaseError("Data constraint violated") from e

except OperationalError as e:
    self.db.rollback()
    logger.error(f"Database operation failed: {e}", exc_info=True)
    raise DatabaseError("Database temporarily unavailable") from e

except Exception as e:
    self.db.rollback()
    logger.error(f"Unexpected database error: {e}", exc_info=True)
    raise
```

---

### 7. Circuit Breaker Configuration
**File**: `backend-hormonia/app/services/flow/errors/handler.py:577`

**Replace**:
```python
# BEFORE (hardcoded)
if breaker["failures"] >= 5:
    breaker["state"] = "open"

# AFTER (configurable)
threshold = self.config.circuit_breaker.get(
    operation,
    default_threshold=5
)
if breaker["failures"] >= threshold:
    breaker["state"] = "open"
    logger.warning(
        f"Circuit breaker opened for {operation}",
        extra={"failures": breaker["failures"], "threshold": threshold}
    )
```

---

## 🟡 P2 - Medium Priority (This Quarter)

### 8. Timeline API Partial Data Warning
**File**: `backend-hormonia/app/api/v2/routers/patients/flow.py:368`

**Replace**:
```python
# BEFORE (silent failure)
except Exception as e:
    logger.warning(f"Could not fetch saga events: {e}")

# AFTER (warn user)
warnings = []
try:
    sagas = db.query(PatientOnboardingSaga)...
except Exception as e:
    logger.warning(f"Could not fetch saga events: {e}", exc_info=True)
    warnings.append("Saga events unavailable")

return {
    "patient_id": patient_id,
    "events": events,
    "warnings": warnings  # ← Add this
}
```

---

### 9. Specific Error Messages
**File**: `backend-hormonia/app/api/v2/routers/patients/crud.py:490`

**Replace**:
```python
# BEFORE (generic)
if not updated_patient:
    raise HTTPException(status_code=500, detail="Failed to update patient")

# AFTER (specific)
ERROR_MESSAGES = {
    "constraint_violation": "Patient with this phone already exists",
    "database_unavailable": "System temporarily unavailable",
    "validation_failed": "Invalid patient data",
}

if not updated_patient:
    error_type = getattr(e, "error_type", "unknown")
    detail = ERROR_MESSAGES.get(error_type, "Failed to update patient")
    raise HTTPException(status_code=500, detail=detail)
```

---

### 10. Redis Fallback Metrics
**File**: `backend-hormonia/app/tasks/follow_up.py:76`

**Add**:
```python
from app.metrics import redis_fallback_count

except Exception as e:
    logger.warning(f"Redis unavailable, using in-memory: {e}")
    redis_fallback_count.labels(operation="get_pending_actions").inc()

    # Alert if Redis down > 10 minutes
    if self._redis_downtime() > timedelta(minutes=10):
        alert_ops_team(
            title="Redis unavailable - using fallback",
            details={"downtime_minutes": self._redis_downtime().total_seconds() / 60},
            severity="medium"
        )
```

---

## 📊 Metrics to Add

```python
# app/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# Error metrics
patient_errors_total = Counter(
    "patient_operations_errors_total",
    "Total patient operation errors",
    ["operation", "error_type", "severity"]
)

# Cache metrics
cache_invalidation_failures = Counter(
    "cache_invalidation_failures_total",
    "Cache invalidation failures",
    ["entity"]
)

cache_operation_duration = Histogram(
    "cache_operation_duration_seconds",
    "Cache operation duration"
)

# Message metrics
message_send_failures = Counter(
    "whatsapp_message_send_failures_total",
    "WhatsApp message send failures",
    ["reason"]
)

# Saga metrics
saga_compensation_failures = Counter(
    "saga_compensation_failures_total",
    "Saga compensation failures",
    ["step"]
)

# Redis metrics
redis_fallback_count = Counter(
    "redis_fallback_total",
    "Redis fallback operations",
    ["operation"]
)
```

---

## 🚨 Alerts to Create

```yaml
# alerts/patient_workflows.yml
groups:
  - name: patient_workflows
    rules:
      # P0 Alerts
      - alert: MessageSendFailuresHigh
        expr: rate(message_send_failures_total[5m]) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High WhatsApp message failure rate"

      - alert: TaskFailuresAfterRetry
        expr: increase(celery_task_failures_after_max_retries[5m]) > 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Celery task failed after max retries"

      # P1 Alerts
      - alert: CacheInvalidationFailing
        expr: rate(cache_invalidation_failures_total[10m]) > 0.1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Cache invalidation failure rate > 10%"

      - alert: SagaCompensationFailed
        expr: increase(saga_compensation_failures_total[5m]) > 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "Saga compensation failed - manual intervention required"

      # P2 Alerts
      - alert: RedisUnavailable
        expr: rate(redis_fallback_total[10m]) > 0
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Redis unavailable, using fallback"
```

---

## 📝 Logging Standards

### Create: `docs/logging-standards.md`

```markdown
# Logging Standards

## Levels

### DEBUG
- Cache hits/misses
- Query details
- Performance metrics
- Internal state changes

### INFO
- Successful operations
- Patient state changes
- Flow transitions
- Integration calls (success)

### WARNING
- Retryable failures
- Fallback operations triggered
- Cache failures
- Rate limiting triggered
- Degraded service mode

### ERROR
- Operation failures affecting users
- Database errors
- External service failures
- Data validation failures
- Security violations

### CRITICAL
- System failures requiring immediate action
- Data corruption detected
- Saga compensation failures
- Circuit breaker opened for critical path

## Context Requirements

All logs must include:
- Operation name
- User/patient ID (if applicable)
- Request ID (for tracing)
- Error type (for errors)
- Duration (for operations)

Example:
```python
logger.error(
    f"Failed to update patient {patient_id}",
    exc_info=True,
    extra={
        "operation": "update_patient",
        "patient_id": str(patient_id),
        "request_id": request.id,
        "error_type": type(e).__name__,
        "duration_ms": duration.total_seconds() * 1000
    }
)
```

## Cache-Specific

- Connection failures: **WARNING**
- Operation failures: **WARNING** (with metric)
- Cache miss: **DEBUG**
- Cache hit: **DEBUG**

## External Service

- Request start: **INFO**
- Request success: **INFO** (with duration)
- Transient failure: **WARNING** (with retry count)
- Permanent failure: **ERROR**

## Saga Pattern

- Saga start: **INFO**
- Step success: **INFO**
- Step failure: **ERROR** (with compensation plan)
- Compensation success: **WARNING**
- Compensation failure: **CRITICAL**
```

---

## 🧪 Tests to Add

### Priority Test Scenarios

```python
# tests/error_handling/test_critical_paths.py

@pytest.mark.asyncio
async def test_message_failure_alerts_team():
    """P0: Message failures after retries should alert ops team"""
    with patch('app.alerts.alert_ops_team') as mock_alert:
        # Simulate message send failure
        mock_whatsapp.send_message.return_value = False

        # Run saga
        await orchestrator.execute_patient_onboarding_saga(...)

        # Should alert after max retries
        assert mock_alert.called
        assert "Welcome message failed" in mock_alert.call_args[1]["title"]

@pytest.mark.asyncio
async def test_cache_failure_doesnt_break_update():
    """P1: Cache failures shouldn't prevent patient updates"""
    with patch('app.cache.invalidate_entity', side_effect=RedisError()):
        # Should succeed despite cache failure
        patient = await crud_service.update_patient(patient_id, data)
        assert patient.name == data.name

@pytest.mark.asyncio
async def test_redis_fallback_tracked():
    """P2: Redis fallbacks should be tracked with metrics"""
    from app.metrics import redis_fallback_count

    with patch('app.redis.get', side_effect=RedisError()):
        initial_count = redis_fallback_count._value.get()

        # Execute task
        await execute_pending_follow_ups()

        # Should increment metric
        assert redis_fallback_count._value.get() > initial_count

def test_timeline_api_warns_on_partial_data():
    """P2: Timeline API should warn when saga data unavailable"""
    with patch('db.query', side_effect=Exception("Saga unavailable")):
        response = client.get(f"/api/v2/patients/{patient_id}/timeline")

        data = response.json()
        assert "warnings" in data
        assert "Saga events unavailable" in data["warnings"]
```

---

## 📚 Documentation to Create

1. **Logging Standards**: `docs/logging-standards.md` (see above)
2. **Error Handling Guide**: `docs/error-handling-guide.md`
3. **Alerting Runbook**: `docs/alerting-runbook.md`
4. **Monitoring Dashboard**: Grafana dashboard JSON
5. **Incident Response**: `docs/incident-response.md`

---

**Last Updated**: 2025-12-24
**Next Review**: Weekly until P0 fixed, then monthly
