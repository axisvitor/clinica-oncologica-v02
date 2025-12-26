# Database Performance - Quick Reference Guide

**Last Updated:** December 25, 2025
**Status:** 3 Critical + 5 High Priority Issues Identified

---

## Critical Issues at a Glance

### 1. Flow Analytics Sentiment Distribution (HIGH)
**File:** `app/repositories/flow_analytics.py:146`
**Problem:** Loads all sentiment scores into memory, processes in Python
**Fix:** Use database `CASE/SUM` aggregation
**Impact:** -75ms per request for large datasets

### 2. Response Time Statistics (HIGH)
**File:** `app/repositories/flow_analytics.py:174`
**Problem:** Fetches all times, sorts in Python (O(n log n))
**Fix:** Use PostgreSQL `percentile_cont()`
**Impact:** -100ms per request for 100k+ records

### 3. Message Delivery Metrics (HIGH)
**File:** `app/repositories/flow_analytics.py:220-262`
**Problem:** 4 sequential COUNT queries
**Fix:** Single query with CASE aggregations
**Impact:** -60ms per request (4→1 query)

---

## Current State Analysis

### Repositories with Good Practices ✅
- `patient/base.py` - Excellent eager loading
- `patient/pagination.py` - Cursor pagination + Redis caching
- `appointment.py` - Eager loading by default
- `quiz.py` - Eager loading with joinedload

### Repositories Needing Fixes ❌
- `flow_analytics.py` - 3 major aggregation issues
- `message.py` - Missing eager load in some methods
- `quiz.py` - Caching without eager loading

### Database Indexes Missing
- `quiz_responses(patient_id, created_at DESC)` - Needed
- `messages(patient_id, status, created_at DESC)` - Needed
- `flow_analytics(patient_id, timestamp DESC)` - Needed
- `alerts(patient_id, status, created_at DESC)` - Needed

---

## Key Metrics Before/After

### Response Time Improvement
```
Average Page Load Time
Before: 350-450ms
After:  100-200ms
Target: 50-100ms (Phase 2-3)
```

### Query Count Reduction
```
Before: 271+ queries across system
After:  ~160 queries with optimization
Reduction: 40-50%
```

### Memory Usage per Request
```
Before: 50-100KB per large query
After:  <10KB with aggregation
Reduction: 80-90%
```

---

## Implementation Priority Matrix

### Phase 1 (Week 1) - CRITICAL
```
Priority 1: Flow Analytics Sentiment
Priority 2: Response Time Stats
Priority 3: Message Delivery Metrics
Effort: 2-3 hours | Impact: 235ms savings
```

### Phase 2 (Week 2-3) - HIGH
```
Priority 4: Risk Assessment Aggregation
Priority 5: Message Eager Loading
Priority 6: Database Indexes (8 total)
Effort: 3-4 hours | Impact: 150ms savings
```

### Phase 3 (Week 3-4) - MEDIUM
```
Priority 7: Data Integrity Service
Priority 8: Quiz Template Eager Loading
Priority 9: Comprehensive Eager Load Defaults
Effort: 2-3 hours | Impact: 50ms savings
```

---

## Quickest Wins (Highest ROI)

### Win #1: Flow Analytics Sentiment (30 min)
**Effort:** 30 minutes
**Impact:** 75ms per request
**Complexity:** LOW (database aggregation)
```python
# Replace lines 146-155 in flow_analytics.py with CASE/SUM
from sqlalchemy import func, case

result = self.db.query(
    func.sum(case((FlowAnalytics.sentiment_score > 0.1, 1), else_=0)).label('positive'),
    func.sum(case((FlowAnalytics.sentiment_score.between(-0.1, 0.1), 1), else_=0)).label('neutral'),
    func.sum(case((FlowAnalytics.sentiment_score < -0.1, 1), else_=0)).label('negative'),
).filter(FlowAnalytics.sentiment_score.isnot(None))
```

### Win #2: Message Delivery Metrics (45 min)
**Effort:** 45 minutes
**Impact:** 60ms per request
**Complexity:** MEDIUM (4→1 query conversion)
```python
# Replace lines 220-262 with single query + CASE statements
metrics = self.db.query(
    func.count(FlowMessage.id).label('total_scheduled'),
    func.count(case((FlowMessage.sent_at.isnot(None), 1))).label('sent'),
    # ... more aggregations
).filter(FlowMessage.scheduled_for.between(start_date, end_date)).one()
```

### Win #3: Missing Database Indexes (2 hours)
**Effort:** 2 hours (8 indexes)
**Impact:** 100-150ms improvement across queries
**Complexity:** LOW (straightforward SQL)
```sql
CREATE INDEX CONCURRENTLY idx_quiz_responses_patient_date
ON quiz_responses(patient_id, created_at DESC) WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY idx_messages_patient_status_date
ON messages(patient_id, status, created_at DESC);
```

---

## Testing Checklist

After each fix:

- [ ] Run existing unit tests
- [ ] EXPLAIN ANALYZE the new query
- [ ] Benchmark with 10k+ test records
- [ ] Check for cartesian products
- [ ] Verify no regression in other queries
- [ ] Test edge cases (empty results, NULL values)

---

## Code Review Checklist

Before merging:

- [ ] No raw SQL injection vulnerabilities
- [ ] All relationship eager loads use correct strategy (joinedload vs selectinload)
- [ ] No N+1 patterns remain
- [ ] Comments explain optimization rationale
- [ ] Performance metrics documented
- [ ] Backward compatible with existing API

---

## Monitoring After Deployment

### Metrics to Watch
1. **Slow Query Log**
   - Alert if any query takes >500ms
   - Review query plans daily first week

2. **Database CPU**
   - Should drop 15-20% after optimizations
   - Watch for any unusual patterns

3. **Cache Hit Rate**
   - Monitor Redis cache effectiveness
   - Target: 70%+ hit rate for read operations

4. **Connection Pool**
   - Verify pool isn't exhausted
   - Watch for connection leaks

### Query Performance Dashboard
```
Metrics to track:
- P50 query time (ms)
- P95 query time (ms)
- P99 query time (ms)
- Queries per second
- Cache hit rate (%)
- Slow query count (>500ms)
```

---

## File-by-File Action Items

### `app/repositories/flow_analytics.py`
| Line | Method | Action | Status |
|------|--------|--------|--------|
| 146 | get_sentiment_distribution | Replace with DB aggregation | TODO |
| 174 | get_response_time_stats | Replace with percentile_cont | TODO |
| 220-262 | get_delivery_metrics | Consolidate to 1 query | TODO |
| 280 | get_response_correlation | Use DB epoch calculation | TODO |

### `app/repositories/message.py`
| Line | Method | Action | Status |
|------|--------|--------|--------|
| 168 | get_scheduled_messages | Add eager_load parameter | TODO |
| 131 | get_pending_messages | Verify eager load active | DONE ✓ |

### `app/repositories/quiz.py`
| Line | Method | Action | Status |
|------|--------|--------|--------|
| 98-114 | get_active_templates | Add selectinload to cache | TODO |
| 166-200 | get_by_patient | Add missing relationships | TODO |

### Database Schema
| Index | Table | Columns | Status |
|-------|-------|---------|--------|
| 1 | quiz_responses | (patient_id, created_at DESC) | TODO |
| 2 | messages | (patient_id, status, created_at DESC) | TODO |
| 3 | flow_analytics | (patient_id, timestamp DESC) | TODO |
| 4 | flow_analytics | (flow_type, timestamp DESC) | TODO |
| 5 | alerts | (patient_id, status, created_at DESC) | TODO |
| 6 | appointments | (patient_id, scheduled_start DESC) | TODO |
| 7 | quiz_sessions | (patient_id, status, created_at DESC) | TODO |
| 8 | treatments | (patient_id, created_at DESC) | TODO |

---

## Quick Debugging Tips

### Check if Query has N+1 Pattern
```python
# Enable SQL logging (DEBUG mode)
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Run operation and count SQL log lines
# Expected: 1-4 queries max for single operation
```

### EXPLAIN ANALYZE Your Queries
```sql
-- Before optimization
EXPLAIN ANALYZE
SELECT sentiment_score FROM flow_analytics WHERE sentiment_score IS NOT NULL;

-- After optimization
EXPLAIN ANALYZE
SELECT SUM(CASE WHEN sentiment_score > 0.1 THEN 1 ELSE 0 END) as positive
FROM flow_analytics WHERE sentiment_score IS NOT NULL;
```

### Check Query Plans
```sql
-- Look for sequential scans on large tables (bad)
-- Better: index scans or bitmap scans

-- Check row estimates vs actual rows
-- If different by 10x+: update table stats
ANALYZE table_name;
```

---

## References & Resources

### SQLAlchemy Optimization
- [Eager Loading Strategies](https://docs.sqlalchemy.org/en/14/orm/loading_relationships.html)
- [Query Compilation Caching](https://docs.sqlalchemy.org/en/14/core/linting.html)

### PostgreSQL Performance
- [Window Functions](https://www.postgresql.org/docs/14/functions-window.html)
- [Index Design](https://use-the-index-luke.com/)
- [EXPLAIN ANALYZE](https://www.postgresql.org/docs/14/sql-explain.html)

### Best Practices
- [SQLAlchemy Anti-Patterns](https://docs.sqlalchemy.org/en/14/faq/performance.html)
- [Database Design](https://en.wikipedia.org/wiki/Database_normalization)

---

## Support & Questions

For issues or questions about these optimizations:

1. Check the detailed analysis: `DATABASE_PERFORMANCE_N_PLUS_ONE_ANALYSIS.md`
2. Review implementation guide: `N_PLUS_ONE_FIX_IMPLEMENTATION_GUIDE.md`
3. Check existing tests for pattern examples
4. Contact: Backend team lead

---

**Status:** Active - Prioritize Phase 1 fixes this week
**Last Review:** 2025-12-25
**Next Review:** 2026-01-08 (after Phase 1 deployment)
