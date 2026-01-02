# Load Testing Guide

This guide explains how to run load tests for Backend Hormonia using Locust.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running Tests](#running-tests)
- [Test Scenarios](#test-scenarios)
- [Interpreting Results](#interpreting-results)
- [Troubleshooting](#troubleshooting)
- [CI/CD Integration](#cicd-integration)

---

## Prerequisites

### Required Software

- Python 3.11+
- Locust 2.x
- Backend Hormonia running (local or staging)

### System Requirements

**Minimum:**
- 2 CPU cores
- 4 GB RAM
- Network access to backend

**Recommended:**
- 4+ CPU cores
- 8+ GB RAM
- Low-latency network

---

## Installation

### 1. Install Locust

```bash
# Using pip
pip install locust

# Or with specific version
pip install locust==2.20.0

# Verify installation
locust --version
```

### 2. Navigate to Test Directory

```bash
cd backend-hormonia/locust
```

### 3. Verify Configuration

```bash
# Check if locustfile.py exists
ls -la locustfile.py

# Make scenarios.sh executable
chmod +x scenarios.sh
```

---

## Running Tests

### Quick Start (Smoke Test)

```bash
# Run smoke test (10 users, 1 minute)
./scenarios.sh smoke
```

### Interactive Mode (Web UI)

```bash
# Start Locust web UI
locust -f locustfile.py --host=http://localhost:8000

# Open browser to: http://localhost:8089
# Set users and spawn rate in UI
```

### Headless Mode (Automated)

```bash
# Load test: 100 users, 5 minutes
locust -f locustfile.py \
  --host=http://localhost:8000 \
  --headless \
  -u 100 \
  -r 10 \
  --run-time 5m \
  --html reports/load-test.html \
  --csv reports/load-test
```

### Using Scenarios Script

```bash
# Run all predefined scenarios
./scenarios.sh all

# Run specific scenario
./scenarios.sh load      # Normal load test
./scenarios.sh stress    # Stress test
./scenarios.sh spike     # Spike test
./scenarios.sh soak      # Endurance test
```

---

## Test Scenarios

### 1. Smoke Test
**Purpose:** Quick validation
**Users:** 10
**Duration:** 1 minute

```bash
./scenarios.sh smoke
```

**Use when:**
- Testing after deployment
- Quick sanity check
- CI/CD pipeline

---

### 2. Load Test
**Purpose:** Normal operational load
**Users:** 100
**Duration:** 5 minutes

```bash
./scenarios.sh load
```

**Use when:**
- Baseline performance testing
- Before major releases
- Monthly performance reviews

---

### 3. Stress Test
**Purpose:** High load testing
**Users:** 500
**Duration:** 10 minutes

```bash
./scenarios.sh stress
```

**Use when:**
- Testing scalability
- Finding breaking points
- Capacity planning

---

### 4. Spike Test
**Purpose:** Sudden traffic spike
**Users:** 1000 (rapid ramp-up)
**Duration:** 3 minutes

```bash
./scenarios.sh spike
```

**Use when:**
- Testing resilience
- Auto-scaling validation
- Disaster recovery testing

---

### 5. Soak Test
**Purpose:** Long-term stability
**Users:** 50
**Duration:** 30 minutes

```bash
./scenarios.sh soak
```

**Use when:**
- Checking for memory leaks
- Database connection leaks
- Long-running stability

---

## Custom Test Configuration

### Custom User Count and Duration

```bash
locust -f locustfile.py \
  --host=http://localhost:8000 \
  --headless \
  -u 250 \        # 250 concurrent users
  -r 25 \         # Spawn 25 users/second
  --run-time 10m  # Run for 10 minutes
```

### Test Specific User Class

```bash
# Only test patient onboarding
locust -f locustfile.py \
  --host=http://localhost:8000 \
  --headless \
  -u 100 \
  --run-time 5m \
  PatientOnboardingUser
```

### Environment-Specific Testing

```bash
# Test against staging
export LOCUST_HOST=https://staging-api.hormonia.com.br
./scenarios.sh load

# Test against production (use with caution!)
export LOCUST_HOST=https://api.hormonia.com.br
./scenarios.sh smoke  # Only smoke test in production
```

---

## Interpreting Results

### HTML Report

After each test, open the HTML report:

```bash
# Open in browser
open reports/load-test.html

# Or view in terminal
cat reports/load-test_stats.csv
```

### Key Metrics

#### Response Time Percentiles

```
p50 (median):    87ms   ✅ Good
p95:            245ms   ✅ Good
p99:            478ms   ✅ Acceptable
Max:           1234ms   ⚠️  Check outliers
```

**Interpretation:**
- **p50 < 100ms:** Excellent
- **p95 < 300ms:** Good
- **p99 < 500ms:** Acceptable
- **Max < 2000ms:** No critical issues

#### Throughput

```
Requests/second: 207
Total requests:  62,185
Duration:        5 minutes
```

**Targets:**
- **> 100 req/s:** Minimum acceptable
- **> 500 req/s:** Production-ready
- **> 1000 req/s:** High-performance

#### Error Rate

```
Total requests: 62,185
Failures:           12
Error rate:      0.02%
```

**Thresholds:**
- **< 0.1%:** Excellent
- **< 1%:** Acceptable
- **> 1%:** Needs investigation
- **> 5%:** Critical issue

### CSV Analysis

```bash
# View summary statistics
head -20 reports/load-test_stats.csv

# Check failure details
cat reports/load-test_failures.csv

# Analyze response time distribution
cat reports/load-test_stats_history.csv
```

---

## Common Issues and Solutions

### Issue 1: High Error Rate

**Symptoms:**
- Error rate > 1%
- Many 500/503 responses

**Causes:**
- Database connection pool exhausted
- Memory issues
- Rate limiting triggered

**Solutions:**
```bash
# Check database connections
psql -c "SELECT count(*) FROM pg_stat_activity;"

# Check memory usage
docker stats

# Review logs
docker logs backend-hormonia --tail 100
```

---

### Issue 2: Slow Response Times

**Symptoms:**
- p95 > 500ms
- Increasing response times

**Causes:**
- Slow database queries
- No caching
- CPU bottleneck

**Solutions:**
```bash
# Enable query logging
export SQLALCHEMY_ECHO=true

# Check slow queries
psql -c "SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"

# Profile CPU
py-spy top -- python -m uvicorn app.main:app
```

---

### Issue 3: Connection Errors

**Symptoms:**
- ConnectionError in Locust
- DNS resolution failures

**Causes:**
- Backend not running
- Firewall blocking
- Wrong host URL

**Solutions:**
```bash
# Test connectivity
curl -I http://localhost:8000/api/v2/health

# Check DNS
nslookup api.hormonia.com.br

# Verify backend is running
docker ps | grep backend-hormonia
```

---

## CI/CD Integration

### GitHub Actions

The load test workflow runs automatically:

```yaml
# .github/workflows/load-test.yml
on:
  schedule:
    - cron: '0 2 * * 0'  # Every Sunday at 2 AM
  workflow_dispatch:     # Manual trigger
```

### Manual Trigger

```bash
# Using gh CLI
gh workflow run load-test.yml -f scenario=smoke

# View results
gh run list --workflow=load-test.yml
```

### Performance Gates in CI

Tests fail if metrics exceed thresholds:

```yaml
- p95 > 500ms → ❌ FAIL
- Error rate > 0.1% → ❌ FAIL
- Throughput < 100 req/s → ❌ FAIL
```

---

## Best Practices

### 1. Start Small

```bash
# Always start with smoke test
./scenarios.sh smoke

# Then gradually increase load
./scenarios.sh load
./scenarios.sh stress
```

### 2. Monitor During Tests

```bash
# Terminal 1: Run load test
./scenarios.sh load

# Terminal 2: Watch metrics
watch -n 1 'docker stats --no-stream'

# Terminal 3: Monitor logs
docker logs -f backend-hormonia
```

### 3. Test Realistic Scenarios

- Use production-like data
- Simulate real user behavior
- Test with actual API keys (staging)
- Include think time between requests

### 4. Document Results

After each test run:

```bash
# Save results with timestamp
mkdir -p results/$(date +%Y%m%d_%H%M%S)
cp reports/* results/$(date +%Y%m%d_%H%M%S)/

# Add notes
echo "Load test after deployment v1.2.3" > results/$(date +%Y%m%d_%H%M%S)/NOTES.txt
```

---

## Advanced Usage

### Distributed Load Testing

Run Locust across multiple machines:

```bash
# Master node
locust -f locustfile.py --master

# Worker nodes
locust -f locustfile.py --worker --master-host=192.168.1.100
```

### Custom User Behavior

Edit `locustfile.py` to add new user classes:

```python
class CustomUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def custom_workflow(self):
        # Your custom logic here
        pass
```

### Performance Profiling

```bash
# Profile Locust itself
py-spy record -o profile.svg -- locust -f locustfile.py --headless -u 100 -t 60s

# Generate flame graph
open profile.svg
```

---

## Resources

### Documentation

- [Locust Documentation](https://docs.locust.io/)
- [Load Testing Best Practices](https://docs.locust.io/en/stable/writing-a-locustfile.html)
- [Backend Hormonia Performance Guide](./LOAD_TEST_BENCHMARKS.md)

### Tools

- **Grafana:** Real-time monitoring during tests
- **Prometheus:** Metrics collection
- **New Relic/Datadog:** APM integration

### Support

- **Slack:** #performance-testing
- **Email:** backend-team@hormonia.com.br
- **On-call:** See PagerDuty rotation

---

## Appendix

### Locust CLI Reference

```bash
# Common options
-f, --locustfile    Locust file to use
--host              Target host
-u, --users         Number of concurrent users
-r, --spawn-rate    Users spawned per second
-t, --run-time      Test duration (e.g., 5m, 1h)
--headless          Run without web UI
--html              Generate HTML report
--csv               Generate CSV reports
```

### Environment Variables

```bash
LOCUST_HOST              # Target host URL
LOCUST_USERS             # Number of users
LOCUST_SPAWN_RATE        # Spawn rate
LOCUST_RUN_TIME          # Test duration
LOCUST_HEADLESS          # Headless mode (true/false)
```

---

**Last Updated:** 2025-01-16
**Version:** 1.0.0
**Maintained by:** Backend Performance Team
