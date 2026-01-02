# PERFORMANCE QUICK FIX CHECKLIST

**Priority:** 🔴 Critical | ⚠️ High | 🟡 Medium | 🟢 Low
**Effort:** S (Small <4h) | M (Medium 1-2d) | L (Large 3-5d)

---

## 🔴 CRITICAL - Fix This Week

### 1. [ ] Fix Blocking Operations in Async Code
- **Priority:** 🔴 Critical
- **Effort:** S (3-4 hours)
- **Impact:** 8-10x throughput improvement
- **Files:**
  - `app/services/notification_service.py`
  - `app/utils/whatsapp_queue.py`
  - `app/orchestration/saga_orchestrator.py`
  - `app/core/distributed_lock.py`

**Action Items:**
```bash
# 1. Find all instances
grep -rn "time\.sleep" app/ --include="*.py" | grep "async def"

# 2. Replace pattern
# Before: time.sleep(5)
# After: await asyncio.sleep(5)

# 3. Test
python -m pytest tests/performance/test_async_blocking.py
```

**Validation:**
- [ ] No `time.sleep()` in async functions
- [ ] Load test shows 8-10x improvement
- [ ] No event loop warnings in logs

---

### 2. [ ] Implement Cache Invalidation
- **Priority:** 🔴 Critical
- **Effort:** M (1 day)
- **Impact:** Data consistency, +10-15% cache hit rate
- **Files:**
  - `app/repositories/patient.py`
  - `app/repositories/message.py`
  - `app/services/cache/invalidation/`

**Action Items:**
```python
# Add to each repository's update/delete methods
def _invalidate_caches(self, entity_id: UUID, cache_type: str):
    if not self.redis:
        return

    patterns = [
        f"{cache_type}:detail:{entity_id}",
        f"{cache_type}:list:*",
        f"{cache_type}:count:*",
    ]

    for pattern in patterns:
        keys = self.redis.keys(pattern)
        if keys:
            self.redis.delete(*keys)
```

**Validation:**
- [ ] Update patient → cache cleared
- [ ] List shows fresh data immediately
- [ ] No stale data reports from QA

---

## ⚠️ HIGH PRIORITY - Next Sprint

### 3. [ ] Add Query Limits to Services
- **Priority:** ⚠️ High
- **Effort:** S (4 hours)
- **Impact:** Memory safety, prevents OOM
- **Files:**
  - `app/services/risk_assessment_service.py` (Line 201)
  - `app/services/flow_dashboard.py` (Line 546)
  - `app/services/data_integrity_monitoring.py` (Line 282)

**Action Items:**
```python
# Replace this pattern
for alert in alerts_query.all():  # ❌

# With this
BATCH_SIZE = 100
offset = 0
while True:
    batch = alerts_query.limit(BATCH_SIZE).offset(offset).all()
    if not batch:
        break
    for alert in batch:
        process_alert(alert)
    offset += BATCH_SIZE
```

**Validation:**
- [ ] Memory usage stable with 10,000+ records
- [ ] No OOM errors in staging
- [ ] Performance tests pass

---

### 4. [ ] Optimize Connection Pool
- **Priority:** ⚠️ High
- **Effort:** S (2-3 hours)
- **Impact:** Eliminates pool exhaustion errors
- **File:** `app/core/database.py`

**Action Items:**
```python
# Current (Lines 52-66)
pool_size=50,
max_overflow=20,

# Change to dynamic sizing
import os
workers = int(os.getenv('WEB_CONCURRENCY', '4'))
pool_size = max(50, workers * 10)  # 10 per worker
max_overflow = pool_size // 3  # 33% buffer
```

**Validation:**
- [ ] No "pool exhausted" errors in logs
- [ ] Load test with 200 concurrent users passes
- [ ] Pool metrics show <80% utilization

---

## 🟡 MEDIUM PRIORITY - Ongoing Improvements

### 5. [ ] Background Jobs for Slow Operations
- **Priority:** 🟡 Medium
- **Effort:** M (2 days)
- **Impact:** 95% faster perceived response time
- **Endpoints:**
  - POST `/patients/{id}/summary` (AI generation 2-5s)
  - POST `/messages/validate` (integrity check 0.5-2s)
  - POST `/reports/generate` (large reports 1-3s)

**Action Items:**
```python
# Convert to Celery task
@celery_app.task(name="generate_patient_summary")
def generate_patient_summary_task(patient_id: str):
    # Heavy processing
    return result

# API endpoint returns immediately
@router.post("/patients/{id}/summary")
async def request_summary(patient_id: UUID):
    task = generate_patient_summary_task.delay(str(patient_id))
    return {"task_id": task.id, "status": "processing"}
```

**Validation:**
- [ ] Endpoint returns <100ms
- [ ] Tasks complete successfully in background
- [ ] Status polling works correctly

---

### 6. [ ] Response Field Selection
- **Priority:** 🟡 Medium
- **Effort:** M (1 day)
- **Impact:** 60-80% smaller responses
- **Files:** All API routers

**Action Items:**
```python
@router.get("/patients/{id}")
async def get_patient(
    patient_id: UUID,
    fields: Optional[List[str]] = Query(None)
):
    patient = patient_repo.get_by_id(patient_id)

    if fields:
        return {k: getattr(patient, k) for k in fields}

    return PatientResponse.from_orm(patient)
```

**Validation:**
- [ ] `?fields=id,name` returns only those fields
- [ ] Response size reduced 60-80%
- [ ] API docs updated

---

## 📊 MONITORING SETUP

### 7. [ ] Add Performance Tracking
- **Priority:** ⚠️ High
- **Effort:** S (4 hours)
- **File:** `app/core/database.py`, `app/main.py`

**Action Items:**
```python
# Query performance tracking (database.py)
@event.listens_for(engine, "before_cursor_execute")
def track_query_start(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault('query_start_time', []).append(time.time())

@event.listens_for(engine, "after_cursor_execute")
def track_query_end(conn, cursor, statement, parameters, context, executemany):
    duration = time.time() - conn.info['query_start_time'].pop()
    if duration > 1.0:  # Slow query threshold
        logger.warning(f"Slow query: {duration:.3f}s - {statement[:200]}")

# Endpoint performance (main.py)
@app.middleware("http")
async def track_performance(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    if duration > 1.0:
        logger.warning(f"Slow endpoint: {request.url.path} - {duration:.3f}s")

    response.headers["X-Process-Time"] = str(duration)
    return response
```

**Validation:**
- [ ] Slow queries logged (>1s)
- [ ] Slow endpoints logged (>1s)
- [ ] Dashboard shows metrics

---

### 8. [ ] Load Testing Suite
- **Priority:** 🟡 Medium
- **Effort:** M (1 day)
- **Directory:** `tests/performance/`

**Action Items:**
```python
# tests/performance/test_patient_endpoints.py
async def test_patient_list_load():
    async with AsyncClient(base_url=BASE_URL) as client:
        start = time.time()
        tasks = [client.get("/api/v2/patients") for _ in range(100)]
        responses = await asyncio.gather(*tasks)
        duration = time.time() - start

        assert all(r.status_code == 200 for r in responses)
        assert duration < 10, f"100 requests took {duration}s"
```

**Validation:**
- [ ] 100 concurrent requests <10s
- [ ] No connection pool errors
- [ ] Memory usage stable

---

## 🎯 SUCCESS METRICS

Track these metrics weekly:

| Metric | Baseline | Target | Current |
|--------|----------|--------|---------|
| **Patient List (First)** | 300ms | 150ms | ___ |
| **Patient List (Cached)** | 150ms | 80ms | ___ |
| **Name Search** | 50ms | 5-10ms | ___ |
| **Concurrent Users** | 50 | 250-500 | ___ |
| **Error Rate** | 2% | <0.5% | ___ |
| **Cache Hit Rate** | 70% | 80-85% | ___ |
| **P95 Response Time** | 800ms | 400ms | ___ |
| **Memory Usage** | 2GB | 1.2GB | ___ |

---

## 🚀 DEPLOYMENT CHECKLIST

Before deploying performance fixes:

- [ ] **Code Review:** All changes peer-reviewed
- [ ] **Unit Tests:** 100% pass rate
- [ ] **Integration Tests:** All critical paths tested
- [ ] **Load Tests:** 100 concurrent users, no errors
- [ ] **Staging Validation:** 24h soak test successful
- [ ] **Rollback Plan:** Documented and tested
- [ ] **Monitoring:** Alerts configured for regressions
- [ ] **Documentation:** Performance docs updated

---

## 📞 ESCALATION PATH

If performance issues persist:

1. **Immediate (<15min):** Check monitoring dashboard
2. **Within 1 hour:** Review application logs
3. **Within 4 hours:** Database query analysis
4. **Within 8 hours:** Involve infrastructure team
5. **Critical:** Scale horizontally (add workers)

---

## 📚 REFERENCE DOCUMENTS

- **Full Analysis:** `docs/performance/DEEP_PERFORMANCE_ANALYSIS.md`
- **Database Docs:** `docs/database/README.md`
- **API Docs:** `docs/api/`
- **Monitoring:** Internal dashboard (link TBD)

---

**Last Updated:** 2025-12-02
**Next Review:** 2025-12-09 (after Week 1 fixes)
**Owner:** Backend Performance Team
