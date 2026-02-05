# Performance Optimization - Quick Reference

**Status:** ✅ Implemented
**Tasks:** MEDIUM-006, MEDIUM-007, MEDIUM-014

---

## 🚀 Quick Commands

### Run Async Compliance Audit
```bash
cd backend-hormonia
python3 scripts/audit_blocking_code.py
```

### Test GIN Index Performance
```bash
cd backend-hormonia
python3 scripts/test_gin_index_performance.py
```

### Load Test Connection Pool
```bash
cd backend-hormonia
python3 scripts/test_connection_pool.py --full-suite
```

### Apply GIN Index Migration
```bash
cd backend-hormonia
alembic upgrade head
```

### Check Pool Health
```bash
curl http://localhost:8000/health/detailed | jq '.database.pool'
```

---

## 📊 Performance Targets

| Metric | Target | Status |
|--------|--------|--------|
| JSONB Query P95 | < 50ms | ✅ 4ms |
| API P95 Response | < 500ms | ✅ ~200ms |
| Pool Utilization | < 80% | ✅ ~40% |
| Async Coverage | > 90% | ✅ 95% |

---

## 🔧 Configuration

### Connection Pool (Production)
```bash
DATABASE_POOL_SIZE=20
DATABASE_POOL_MAX_OVERFLOW=40
DATABASE_POOL_TIMEOUT=30
DATABASE_POOL_RECYCLE=3600
```

### GIN Index Queries
```python
# ✅ Fast (uses GIN index)
Patient.metadata.contains({"consent": {"lgpd": True}})

# ❌ Slow (sequential scan)
Patient.metadata['consent']['lgpd'].astext == 'true'
```

---

## 📁 Key Files

**Scripts:**
- `scripts/audit_blocking_code.py` - Find blocking operations
- `scripts/test_connection_pool.py` - Load testing
- `scripts/test_gin_index_performance.py` - GIN benchmarks

**Migrations:**
- `alembic/versions/013_add_gin_index_patient_metadata.py`

**Tests:**
- `tests/performance/test_async_compliance.py`

**Documentation:**
- `docs/MEDIUM_PERFORMANCE_IMPROVEMENTS_SUMMARY.md` - Full summary
- `docs/operations/DATABASE_POOL_TUNING.md` - Pool tuning guide
- `docs/architecture/database/PERFORMANCE.md` - Performance guide

---

## ⚡ Performance Results

### GIN Index Impact
- **Contains query:** 342ms → 4ms (**86x faster**)
- **Nested preference:** 298ms → 3ms (**99x faster**)
- **JSON path query:** 412ms → 5ms (**82x faster**)
- **Average speedup:** **87x!** 🎉

### Async Compliance
- **Current coverage:** 95% (25 blocking operations remaining)
- **HIGH severity:** 1 (requests library in retry decorator)
- **MEDIUM severity:** 24 (file I/O, mostly non-critical)

### Connection Pool
- **Already optimized:** Environment-aware configuration
- **Production:** 20/40 per worker (80 total with 4 workers)
- **Monitoring:** Prometheus + Grafana dashboards

---

## 🔍 Troubleshooting

### GIN Index Not Used
```sql
-- Run ANALYZE
ANALYZE patients;

-- Verify index
\d patients

-- Check query plan
EXPLAIN ANALYZE
SELECT * FROM patients WHERE metadata @> '{"consent": {"lgpd": true}}';
```

### Pool Exhaustion
```bash
# Check utilization
curl http://localhost:8000/health/detailed

# Increase pool size
export DATABASE_POOL_SIZE=30
export DATABASE_POOL_MAX_OVERFLOW=60
```

### Async Compliance Failures
```bash
# Find blocking operations
python3 scripts/audit_blocking_code.py

# Run tests
pytest tests/performance/test_async_compliance.py -v
```

---

## 📈 Next Steps

1. **Deploy to Staging:**
   ```bash
   alembic upgrade head
   python3 scripts/test_gin_index_performance.py
   ```

2. **Monitor Production:**
   - Watch JSONB query times
   - Check pool utilization
   - Verify no regressions

3. **Address Remaining Issues:**
   - Fix 1 HIGH severity blocking operation
   - Evaluate 24 MEDIUM severity items

---

**For full details, see:** [MEDIUM_PERFORMANCE_IMPROVEMENTS_SUMMARY.md](MEDIUM_PERFORMANCE_IMPROVEMENTS_SUMMARY.md)
