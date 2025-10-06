# Wave 2 Phase 2 Endpoint Testing Guide

## Overview

This guide covers testing for the 4 new backend endpoints implemented in Wave 2 Phase 2:

1. **Admin System Stats** - GET `/api/v1/admin/system-stats`
2. **Analytics Treatment Distribution** - GET `/api/v1/analytics/treatment-distribution`
3. **Physician Risk Assessments** - GET `/api/v1/physician/risk-assessments`
4. **Medico Dashboard Stats** - GET `/api/v1/medico/dashboard-stats`

## Test Files Created

```
tests/
├── routes/
│   ├── test_admin_stats.py           # Admin system stats tests
│   ├── test_analytics_treatment.py   # Treatment distribution tests
│   ├── test_physician_risk.py        # Physician risk assessment tests (with performance benchmarks)
│   └── test_medico_stats.py          # Medico dashboard stats tests
└── conftest.py                        # Enhanced with new fixtures
```

## Quick Start

### Run All Wave 2 Endpoint Tests

```bash
# Navigate to backend directory
cd backend-hormonia

# Run all new endpoint tests
pytest tests/routes/test_admin_stats.py -v
pytest tests/routes/test_analytics_treatment.py -v
pytest tests/routes/test_physician_risk.py -v
pytest tests/routes/test_medico_stats.py -v
```

### Run All Tests at Once

```bash
# Run all Wave 2 tests in parallel
pytest tests/routes/test_admin_stats.py tests/routes/test_analytics_treatment.py tests/routes/test_physician_risk.py tests/routes/test_medico_stats.py -v
```

## Test Coverage

### Run with Coverage Report

```bash
# Generate HTML coverage report
pytest tests/routes/ \
  --cov=app/routes \
  --cov=app/services \
  --cov=app/api \
  --cov-report=html \
  --cov-report=term

# View coverage in browser
open htmlcov/index.html  # macOS
start htmlcov/index.html  # Windows
xdg-open htmlcov/index.html  # Linux
```

### Coverage Targets

- **Statements**: > 80%
- **Branches**: > 75%
- **Functions**: > 80%
- **Lines**: > 80%

## Performance Benchmarks

### Run Performance Tests Only

```bash
# Run all performance-related tests
pytest tests/routes/test_physician_risk.py -k "performance" -v

# Run scalability benchmarks
pytest tests/routes/test_physician_risk.py::TestPhysicianRiskBenchmarks -v --durations=10
```

### Performance Targets

| Endpoint | Patient Count | Target Time |
|----------|---------------|-------------|
| Physician Risk | 10 | < 50ms |
| Physician Risk | 25 | < 100ms |
| Physician Risk | 50 | < 200ms |
| Physician Risk | 100 | < 400ms |

## Test Categories by Endpoint

### 1. Admin System Stats (`test_admin_stats.py`)

**Coverage:**
- ✅ Authorization checks (admin-only access)
- ✅ System metrics collection (CPU, memory, disk)
- ✅ User metrics calculation by role
- ✅ Database connection stats
- ✅ Redis caching (30-second TTL)
- ✅ Error handling and edge cases

**Run:**
```bash
pytest tests/routes/test_admin_stats.py -v
```

### 2. Analytics Treatment Distribution (`test_analytics_treatment.py`)

**Coverage:**
- ✅ Valid period parameters (7d, 30d, 90d, all)
- ✅ Invalid period validation
- ✅ Response structure with chart-ready colors
- ✅ Percentage calculations (sum to 100%)
- ✅ Empty data handling
- ✅ Color assignment from mapping
- ✅ Sorting by count descending
- ✅ Doctor filtering
- ✅ Null treatment type exclusion
- ✅ Small category grouping

**Run:**
```bash
pytest tests/routes/test_analytics_treatment.py -v
```

### 3. Physician Risk Assessments (`test_physician_risk.py`)

**Coverage:**
- ✅ **CRITICAL**: Performance with 50 patients (< 200ms)
- ✅ Single patient filtering
- ✅ Risk score calculation accuracy
- ✅ N+1 query elimination (eager loading)
- ✅ Multiple alert severity levels
- ✅ Resolved alerts exclusion
- ✅ Empty patient list handling
- ✅ Scalability benchmarks (10, 25, 50, 100 patients)

**Run:**
```bash
pytest tests/routes/test_physician_risk.py -v

# Performance-focused run
pytest tests/routes/test_physician_risk.py -k "performance or benchmark" -v
```

### 4. Medico Dashboard Stats (`test_medico_stats.py`)

**Coverage:**
- ✅ New medico with no data (returns zeros, not errors)
- ✅ Accurate stats calculation
- ✅ Alert metrics by severity
- ✅ Engagement calculation (response rates)
- ✅ Today filtering
- ✅ Multi-medico isolation
- ✅ Null value handling
- ✅ Response time performance

**Run:**
```bash
pytest tests/routes/test_medico_stats.py -v
```

## Test Fixtures

### Available Fixtures (in `conftest.py`)

```python
# Database fixtures
db_session              # Synchronous DB session
async_db_session        # Async DB session
empty_db               # Empty database for edge cases

# Authentication fixtures
doctor_a_credentials   # Doctor A credentials + JWT
doctor_b_credentials   # Doctor B credentials + JWT
admin_credentials      # Admin credentials + JWT
medico_credentials     # Medico credentials + JWT
physician_credentials  # Physician credentials + JWT
expired_token_credentials  # Expired token for auth failures

# Helper fixtures
auth_headers          # Function to create auth headers
set_rls_context       # Set RLS context for testing
http_client           # Async HTTP client for API testing
```

## Advanced Testing

### Test with Specific Database

```bash
# Use custom database URL
DATABASE_URL=postgresql://user:pass@localhost/test_db pytest tests/routes/ -v
```

### Test with Verbose SQL Logging

```bash
# Enable SQL echo for debugging
SQLALCHEMY_ECHO=true pytest tests/routes/test_physician_risk.py -v
```

### Test with Coverage Threshold

```bash
# Fail if coverage below 80%
pytest tests/routes/ --cov --cov-fail-under=80
```

## Debugging Failed Tests

### Run Single Test

```bash
# Run specific test function
pytest tests/routes/test_analytics_treatment.py::TestTreatmentDistribution::test_percentage_calculation -v
```

### Run with Debug Output

```bash
# Show print statements and full output
pytest tests/routes/test_physician_risk.py -v -s

# Show local variables on failure
pytest tests/routes/test_admin_stats.py -v -l
```

### Run with PDB Debugger

```bash
# Drop into debugger on failure
pytest tests/routes/test_medico_stats.py --pdb
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Wave 2 Endpoint Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.13'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio

      - name: Run Wave 2 endpoint tests
        run: |
          pytest tests/routes/test_admin_stats.py \
                 tests/routes/test_analytics_treatment.py \
                 tests/routes/test_physician_risk.py \
                 tests/routes/test_medico_stats.py \
                 --cov --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Test Data Cleanup

Tests use transactions that rollback automatically. No manual cleanup needed.

```python
# Automatic cleanup via conftest.py
@pytest.fixture
def db_session(test_engine):
    connection = test_engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()  # Auto-cleanup
    connection.close()
```

## Expected Test Results

### All Tests Passing

```
tests/routes/test_admin_stats.py .................. [ 25%]
tests/routes/test_analytics_treatment.py ........... [ 50%]
tests/routes/test_physician_risk.py ................ [ 75%]
tests/routes/test_medico_stats.py .................. [100%]

===================== 78 passed in 12.34s ======================
```

### With Coverage

```
Name                                 Stmts   Miss  Cover
--------------------------------------------------------
app/services/analytics.py              245     18    93%
app/api/v1/enhanced_analytics.py       156     12    92%
app/routes/admin.py                     89      8    91%
app/routes/physician.py                 112     11    90%
--------------------------------------------------------
TOTAL                                  602     49    92%
```

## Troubleshooting

### Issue: Import Errors

**Solution:** Ensure Python path includes backend directory
```bash
export PYTHONPATH=$PYTHONPATH:$(pwd)
pytest tests/routes/ -v
```

### Issue: Database Connection Errors

**Solution:** Check DATABASE_URL and database is running
```bash
# Check database
psql $DATABASE_URL -c "SELECT 1"

# Use test database
DATABASE_URL=postgresql://localhost/test_db pytest -v
```

### Issue: Redis Connection Errors

**Solution:** Mock Redis or start Redis server
```bash
# Install fakeredis for tests
pip install fakeredis

# Or start Redis
docker run -d -p 6379:6379 redis:latest
```

## Performance Monitoring

### Track Test Duration

```bash
# Show 10 slowest tests
pytest tests/routes/ -v --durations=10

# Show all test durations
pytest tests/routes/ -v --durations=0
```

### Profile Tests

```bash
# Install pytest-profiling
pip install pytest-profiling

# Run with profiling
pytest tests/routes/test_physician_risk.py --profile
```

## Next Steps

1. **Implement Endpoints**: If tests are failing with 404, implement the actual endpoints
2. **Increase Coverage**: Add more edge case tests
3. **Add Integration Tests**: Test with real frontend requests
4. **Performance Tuning**: Optimize queries based on benchmark results
5. **Add E2E Tests**: Test full user workflows with Playwright

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/14/orm/session_transaction.html)
