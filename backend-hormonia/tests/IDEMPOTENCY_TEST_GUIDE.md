# Idempotency Test Execution Guide

## Quick Start

```bash
# Run all idempotency tests
cd backend-hormonia
pytest tests/unit/coordination/test_saga_idempotency.py \
       tests/integration/test_saga_concurrency.py -v

# Run with coverage report
pytest tests/unit/coordination/test_saga_idempotency.py \
       tests/integration/test_saga_concurrency.py \
       --cov=app.coordination.saga_orchestrator \
       --cov-report=html \
       --cov-report=term

# View coverage report
open htmlcov/index.html
```

## Test Categories

### 1. Unit Tests (Fast - ~10 seconds)

**File:** `tests/unit/coordination/test_saga_idempotency.py`

```bash
# Run all unit tests
pytest tests/unit/coordination/test_saga_idempotency.py -v

# Run specific test
pytest tests/unit/coordination/test_saga_idempotency.py::TestSagaIdempotency::test_duplicate_saga_execution_prevented -v

# Run with detailed output
pytest tests/unit/coordination/test_saga_idempotency.py -vv -s
```

**What's Tested:**
- Duplicate saga execution prevention
- Email/phone uniqueness validation
- Step-level idempotency
- Message deduplication
- Redis cache behavior
- Flow state idempotency

### 2. Integration Tests (Slower - ~30-60 seconds)

**File:** `tests/integration/test_saga_concurrency.py`

```bash
# Run all integration tests
pytest tests/integration/test_saga_concurrency.py -v

# Run specific load test
pytest tests/integration/test_saga_concurrency.py::TestConcurrentSagaExecution::test_stress_test_50_concurrent_sagas -v

# Run with performance timing
pytest tests/integration/test_saga_concurrency.py -v --durations=10
```

**What's Tested:**
- 10-50 concurrent saga executions
- Race condition prevention
- Database deadlock prevention
- Transaction isolation
- Load/stress testing

## Test Fixtures Required

### Database Setup
```bash
# Create test database
createdb hormonia_test

# Run migrations
alembic upgrade head
```

### Redis Setup
```bash
# Start Redis (or use mock)
redis-server

# Or use Docker
docker run -d -p 6379:6379 redis:7-alpine
```

### Environment Variables
```bash
# Set test environment
export TESTING=true
export DATABASE_URL="postgresql://user:pass@localhost/hormonia_test"
export REDIS_URL="redis://localhost:6379/0"
```

## Common Test Scenarios

### Scenario 1: Verify Duplicate Prevention

```bash
# Test that duplicate patient data doesn't create duplicates
pytest tests/unit/coordination/test_saga_idempotency.py::TestSagaIdempotency::test_duplicate_saga_execution_prevented -v
```

**Expected:** ✅ PASS - Only 1 patient created

### Scenario 2: Verify Race Conditions

```bash
# Test 10 concurrent registrations
pytest tests/integration/test_saga_concurrency.py::TestConcurrentSagaExecution::test_10_concurrent_patient_registrations -v
```

**Expected:** ✅ PASS - No deadlocks, 1 patient created

### Scenario 3: Stress Test

```bash
# Test 50 concurrent sagas
pytest tests/integration/test_saga_concurrency.py::TestConcurrentSagaExecution::test_stress_test_50_concurrent_sagas -v
```

**Expected:** ✅ PASS - 10 unique patients, no crashes

### Scenario 4: Message Idempotency

```bash
# Test WhatsApp message deduplication
pytest tests/unit/coordination/test_saga_idempotency.py::TestSagaIdempotency::test_message_idempotency -v
```

**Expected:** ✅ PASS - Message sent only once

## Debugging Failures

### Test Fails: "Duplicate Patient Created"

**Cause:** Idempotency logic not working

**Debug:**
```bash
# Run with verbose output
pytest tests/unit/coordination/test_saga_idempotency.py::TestSagaIdempotency::test_duplicate_saga_execution_prevented -vv -s

# Check database state
psql hormonia_test -c "SELECT id, email, phone FROM patients;"
```

**Fix:** Verify email/phone uniqueness constraints in database

### Test Fails: "Deadlock Detected"

**Cause:** Database locking issue under concurrent load

**Debug:**
```bash
# Run with detailed traceback
pytest tests/integration/test_saga_concurrency.py -vv --tb=long

# Check PostgreSQL logs
tail -f /var/log/postgresql/postgresql-*.log | grep deadlock
```

**Fix:** Review transaction isolation level, add SELECT FOR UPDATE

### Test Fails: "Redis Connection Error"

**Cause:** Redis not running or not accessible

**Debug:**
```bash
# Check Redis status
redis-cli ping

# Run tests with Redis mock
pytest tests/unit/coordination/test_saga_idempotency.py -v
```

**Fix:** Start Redis or use mock in tests

## Performance Benchmarks

Expected performance targets:

| Test Type | Count | Expected Time | Max Time |
|-----------|-------|---------------|----------|
| Unit tests | 9 | 5-10s | 15s |
| Integration (10 concurrent) | 1 | 10-20s | 30s |
| Integration (20 concurrent) | 1 | 15-25s | 40s |
| Stress test (50 concurrent) | 1 | 30-45s | 60s |
| **Total** | 17 | ~60s | 120s |

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Idempotency Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: hormonia_test
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Run idempotency tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost/hormonia_test
          REDIS_URL: redis://localhost:6379/0
          TESTING: true
        run: |
          pytest tests/unit/coordination/test_saga_idempotency.py \
                 tests/integration/test_saga_concurrency.py \
                 --cov=app.coordination.saga_orchestrator \
                 --cov-report=xml \
                 --cov-report=term

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Monitoring in Production

### Key Metrics to Track

1. **Duplicate Rate**
   ```python
   # Monitor saga duplicate attempts
   saga_duplicate_attempts = Counter('saga_duplicate_attempts_total')
   saga_duplicate_prevented = Counter('saga_duplicate_prevented_total')
   ```

2. **Redis Cache Hit Rate**
   ```python
   # Monitor cache effectiveness
   idempotency_cache_hits = Counter('idempotency_cache_hits_total')
   idempotency_cache_misses = Counter('idempotency_cache_misses_total')
   ```

3. **Concurrent Saga Rate**
   ```python
   # Monitor concurrent execution
   concurrent_sagas = Gauge('concurrent_sagas')
   max_concurrent_sagas = Gauge('max_concurrent_sagas')
   ```

### Alerts

```yaml
# Prometheus alerts
groups:
  - name: idempotency
    rules:
      - alert: HighDuplicateAttemptRate
        expr: rate(saga_duplicate_attempts_total[5m]) > 10
        for: 5m
        annotations:
          summary: High rate of duplicate saga attempts

      - alert: LowCacheHitRate
        expr: rate(idempotency_cache_hits_total[5m]) / rate(idempotency_cache_misses_total[5m]) < 0.8
        for: 10m
        annotations:
          summary: Idempotency cache hit rate below 80%
```

## Troubleshooting Guide

### Issue: Tests Pass Locally, Fail in CI

**Cause:** Environment differences (database, Redis, timing)

**Solution:**
1. Check CI environment variables
2. Verify database/Redis connectivity
3. Increase timeout values for CI
4. Check for timing-dependent assertions

### Issue: Flaky Concurrent Tests

**Cause:** Race conditions in test setup/teardown

**Solution:**
1. Use proper async fixtures
2. Add database cleanup between tests
3. Use unique test data per test
4. Check for shared state between tests

### Issue: Memory/Connection Leaks

**Cause:** Database connections not closed properly

**Solution:**
1. Use pytest fixtures with proper cleanup
2. Check for unclosed sessions
3. Monitor connection pool usage
4. Add connection leak detection

## Best Practices

1. **Run Before Every Commit**
   ```bash
   pytest tests/unit/coordination/test_saga_idempotency.py -v
   ```

2. **Run Full Suite Before PR**
   ```bash
   pytest tests/unit/coordination/test_saga_idempotency.py \
          tests/integration/test_saga_concurrency.py -v
   ```

3. **Monitor Test Performance**
   ```bash
   pytest --durations=10
   ```

4. **Keep Tests Fast**
   - Mock external services
   - Use in-memory databases where possible
   - Parallelize independent tests

5. **Maintain 100% Coverage**
   ```bash
   pytest --cov=app.coordination.saga_orchestrator \
          --cov-report=html \
          --cov-fail-under=95
   ```

## Resources

- **Test Files:**
  - `/tests/unit/coordination/test_saga_idempotency.py`
  - `/tests/integration/test_saga_concurrency.py`

- **Fixtures:**
  - `/tests/fixtures/saga_fixtures.py`

- **Implementation:**
  - `/app/coordination/saga_orchestrator.py`

- **Documentation:**
  - `/docs/operations/SAGA_IDEMPOTENCY_TESTS_IMPLEMENTATION.md`

---

**Need Help?** Check the full implementation guide in `/docs/operations/SAGA_IDEMPOTENCY_TESTS_IMPLEMENTATION.md`
