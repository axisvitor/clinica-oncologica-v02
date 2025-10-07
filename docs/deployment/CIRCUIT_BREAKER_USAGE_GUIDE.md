# Circuit Breaker Usage Guide

## Quick Reference

The circuit breaker protects your database from cascade failures by:
1. Tracking consecutive failures
2. Opening the circuit after threshold (default: 5 failures)
3. Rejecting requests when open (prevents database hammering)
4. Attempting recovery after timeout (default: 60 seconds)

## Basic Usage

### With Decorator (Recommended)

The `@with_db_retry` decorator automatically uses the circuit breaker:

```python
from app.utils.db_retry import with_db_retry
from sqlalchemy.orm import Session

# Async function
@with_db_retry(max_retries=3)
async def create_patient(db: Session, patient_data: dict):
    patient = Patient(**patient_data)
    db.add(patient)
    await db.commit()
    return patient

# Sync function
@with_db_retry(max_retries=3)
def get_patient(db: Session, patient_id: str):
    return db.query(Patient).filter(Patient.id == patient_id).first()
```

### Direct Circuit Breaker Usage

For advanced use cases, use the circuit breaker directly:

```python
from app.utils.db_retry import db_circuit_breaker

# Async operation
async def my_async_db_operation():
    async def operation():
        # Your database code here
        return await db.execute(query)

    return await db_circuit_breaker.acall(operation)

# Sync operation
def my_sync_db_operation():
    def operation():
        # Your database code here
        return db.execute(query)

    return db_circuit_breaker.call(operation)
```

## Configuration

### Decorator Parameters

```python
@with_db_retry(
    max_retries=3,          # Number of retry attempts (default: 3)
    base_delay=1.0,         # Initial delay between retries (default: 1.0s)
    max_delay=10.0,         # Maximum delay between retries (default: 10.0s)
    exponential_base=2.0,   # Exponential backoff multiplier (default: 2.0)
    jitter=True            # Add randomization to delays (default: True)
)
async def my_operation():
    pass
```

### Circuit Breaker Parameters

```python
from app.utils.db_retry import DatabaseCircuitBreaker

custom_breaker = DatabaseCircuitBreaker(
    failure_threshold=5,    # Failures before opening (default: 5)
    recovery_timeout=60     # Seconds before recovery attempt (default: 60)
)
```

## Circuit States

### CLOSED (Normal Operation)
- All requests pass through
- Failures are tracked
- Retries are attempted

### OPEN (Protection Mode)
- All requests are rejected immediately
- Database is protected from error storm
- No retry attempts made
- Error: "Circuit breaker is OPEN - database operations temporarily disabled"

### HALF_OPEN (Recovery Testing)
- First request after timeout is allowed
- Success → Circuit closes (back to normal)
- Failure → Circuit reopens (continue waiting)

## State Transitions

```
CLOSED ─[threshold failures]→ OPEN
  ↑                              ↓
  └────[success]────── HALF_OPEN ←┘
                          ↓
                   [recovery timeout]
```

## Examples

### Example 1: Simple Async Database Operation

```python
from app.utils.db_retry import with_db_retry
from sqlalchemy.orm import Session

@with_db_retry(max_retries=3, base_delay=0.5)
async def fetch_user_data(db: Session, user_id: str):
    """Fetch user data with automatic retry and circuit breaker"""
    user = await db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(f"User {user_id} not found")
    return user
```

### Example 2: Batch Operation with Custom Circuit Breaker

```python
from app.utils.db_retry import DatabaseCircuitBreaker
from sqlalchemy.exc import OperationalError

# Create custom circuit breaker for batch operations
batch_breaker = DatabaseCircuitBreaker(
    failure_threshold=3,     # Lower threshold for batch ops
    recovery_timeout=120     # Longer recovery time
)

async def batch_insert_patients(db: Session, patients: list):
    """Insert multiple patients with circuit breaker protection"""
    async def insert_batch():
        for patient_data in patients:
            patient = Patient(**patient_data)
            db.add(patient)
        await db.commit()

    try:
        return await batch_breaker.acall(insert_batch)
    except Exception as e:
        await db.rollback()
        raise
```

### Example 3: Handling Circuit Breaker Exceptions

```python
from app.utils.db_retry import with_db_retry

@with_db_retry(max_retries=3)
async def critical_operation(db: Session):
    """Operation with circuit breaker exception handling"""
    try:
        # Your database operation
        result = await db.execute(query)
        return result
    except Exception as e:
        if "Circuit breaker is OPEN" in str(e):
            # Circuit is open - database is unhealthy
            logger.error("Circuit breaker open - database unavailable")
            # Return cached data or fallback response
            return get_cached_fallback()
        else:
            # Other error - let it propagate
            raise
```

### Example 4: Manual Circuit Breaker Reset (Testing Only)

```python
from app.utils.db_retry import reset_circuit_breaker

# Only use in tests or manual recovery scenarios
reset_circuit_breaker()
logger.info("Circuit breaker manually reset to CLOSED state")
```

## Monitoring

### Check Circuit Breaker Status

```python
from app.utils.db_retry import db_circuit_breaker

# Log current status
logger.info(f"Circuit state: {db_circuit_breaker.state}")
logger.info(f"Failure count: {db_circuit_breaker.failure_count}")
logger.info(f"Last failure: {db_circuit_breaker.last_failure_time}")
```

### Add Custom Metrics

```python
from app.utils.db_retry import db_circuit_breaker
import prometheus_client

# Export metrics to Prometheus
circuit_state_gauge = prometheus_client.Gauge(
    'db_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)'
)

state_map = {"closed": 0, "open": 1, "half_open": 2}
circuit_state_gauge.set(state_map[db_circuit_breaker.state])
```

## Best Practices

### DO ✅
- Use `@with_db_retry` decorator for all database operations
- Let the circuit breaker handle transient errors automatically
- Monitor circuit breaker state in production
- Set appropriate thresholds based on your traffic patterns
- Use async variants (`acall()`) for async operations

### DON'T ❌
- Don't manually reset circuit breaker in production
- Don't bypass circuit breaker for critical operations
- Don't set threshold too low (causes false positives)
- Don't set recovery timeout too short (prevents proper recovery)
- Don't use sync `call()` for async functions (will fail)

## Troubleshooting

### Circuit Opens Frequently
**Symptom**: Circuit breaker opens often
**Solutions**:
- Increase `failure_threshold` (default: 5)
- Increase `max_retries` on decorator (default: 3)
- Check database health and connectivity
- Review database connection pool settings

### Circuit Never Opens
**Symptom**: Circuit stays CLOSED despite errors
**Causes**:
- Using wrong method (sync `call()` for async function)
- Errors not being caught (check exception types)
- Custom error handling preventing propagation

**Solution**: Ensure using correct circuit breaker method:
```python
# For async functions, use acall()
await db_circuit_breaker.acall(async_func)

# For sync functions, use call()
db_circuit_breaker.call(sync_func)
```

### Circuit Stays Open Too Long
**Symptom**: Circuit doesn't recover
**Solutions**:
- Decrease `recovery_timeout` (default: 60s)
- Check if underlying issue is resolved
- Manually reset if needed (testing only): `reset_circuit_breaker()`

## Error Messages

### "Circuit breaker is OPEN - database operations temporarily disabled"
- **Meaning**: Too many failures detected, circuit protecting database
- **Action**: Wait for recovery timeout, or check database health
- **Duration**: Default 60 seconds before recovery attempt

### "Integrity error in {function_name}"
- **Meaning**: Data constraint violation (unique key, foreign key, etc.)
- **Action**: Fix data issue, operation won't be retried
- **Note**: Circuit breaker doesn't track these (not transient)

## Testing

### Unit Tests Example

```python
import pytest
from app.utils.db_retry import DatabaseCircuitBreaker, reset_circuit_breaker
from sqlalchemy.exc import OperationalError

class TestMyDatabaseOperation:
    def setup_method(self):
        # Reset circuit breaker before each test
        reset_circuit_breaker()

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failures(self):
        breaker = DatabaseCircuitBreaker(failure_threshold=3)

        async def failing_op():
            raise OperationalError("DB error", None, None)

        # Fail 3 times to open circuit
        for i in range(3):
            with pytest.raises(OperationalError):
                await breaker.acall(failing_op)

        assert breaker.state == "open"

        # Next call should be rejected
        with pytest.raises(Exception, match="Circuit breaker is OPEN"):
            await breaker.acall(failing_op)
```

## Migration Guide

If you have existing database code without circuit breaker:

### Before (Without Circuit Breaker)
```python
async def get_patient(db: Session, patient_id: str):
    return await db.query(Patient).filter(Patient.id == patient_id).first()
```

### After (With Circuit Breaker)
```python
from app.utils.db_retry import with_db_retry

@with_db_retry(max_retries=3)
async def get_patient(db: Session, patient_id: str):
    return await db.query(Patient).filter(Patient.id == patient_id).first()
```

That's it! Just add the decorator.

## Additional Resources

- **Fix Documentation**: `docs/deployment/P1-2_CIRCUIT_BREAKER_FIX.md`
- **Summary**: `docs/deployment/CIRCUIT_BREAKER_FIX_SUMMARY.md`
- **Tests**: `tests/unit/utils/test_db_circuit_breaker.py`
- **Verification**: `tests/unit/utils/test_circuit_breaker_verification.py`

## Support

For issues or questions:
1. Check circuit breaker state: `db_circuit_breaker.state`
2. Review logs for failure patterns
3. Run verification tests: `pytest tests/unit/utils/test_circuit_breaker_verification.py -v -s`
4. Consult documentation above
