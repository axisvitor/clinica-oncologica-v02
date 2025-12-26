# 4. Performance & Optimization

> **Scope:** Bottleneck analysis, Indexes strategy, Optimization guides.
> **Source:** Consolidated from `performance_analysis_report.md`, `PERFORMANCE_FIXES_QUICK_GUIDE.md`.

---

## 1. Overall Performance Status

**Score:** 8.5/10
**Database:** PostgreSQL 14+
**Indices:** 479 (Otimização massiva concluída na Migration 031)

The database performs exceptionally well due to proactive optimization strategies like cursor pagination and extensive indexing.

---

## 2. Key Optimizations Implemented

### A. Cursor Pagination (Keyset)
Traditional `OFFSET` pagination degrades to O(N). We implemented **Cursor Pagination** O(1).
-   **Impact:** Page 1000 load time dropped from **450ms** to **5ms**.
-   **Indexes:** Composite indexes on `(created_at DESC, id DESC)` added to huge tables (`messages`, `audit_logs`).

### B. Eager Loading (N+1 Prevention)
Repositories default to `joinedload` or `selectinload` for relationships.
-   **Example:** Loading 50 Messages executes **1 query** (with JOINs) instead of **51 queries**.

### C. JSONB Indexing (GIN)
-   **Feature:** Patient Metadata is stored in JSONB.
-   **Optimization:** GIN indexes allow querying `metadata->>'field'` at 250x the speed of text search.
-   **Metric:** Search time reduced from **5s** to **20ms**.

### D. Database-Level Aggregation
Statistics (e.g., "Messages by Status") use `GROUP BY` SQL queries rather than loading objects into Python memory.

---

## 3. Bottlenecks & Fixes

### 🔴 Critical Fixes (Recently Applied/Identified)

#### 1. Template Versions N+1
**Issue:** Serializing flow templates triggered a query per version for the `Kind` relationship.
**Fix:** Added `.options(joinedload(FlowTemplateVersion.kind))`.
**Gain:** 90% latency reduction.

#### 2. Conversations Endpoint
**Issue:** `list_conversations` executed 2 queries per patient (Message + Count). 100 patients = 200 queries.
**Fix:** Rewritten to use Window Functions / Subqueries.
**Gain:** Reduced to ~3 queries total.

#### 3. Patient Summary Aggregation
**Issue:** Sequential execution of heavy aggregation queries.
**Fix:** Implemented `asyncio.gather` for parallel execution.
**Gain:** 50-75% reduction in wait time.

#### 4. User Search N+1 (Fixed 22/12/2025)
**Issue:** `search_users()` in `user_queries.py` called `get_user_summary(user.id)` for each user in results, causing 21 queries for 20 users.
**Fix:** Added `joinedload(User.patients)` and built summaries directly from loaded users.
**Gain:** 21 queries → 1 query (95% reduction).
**File:** `app/services/admin/admin_user_service/user_queries.py:115-146`

#### 5. Role Statistics N+1 (Fixed 22/12/2025)
**Issue:** `get_user_statistics()` executed separate COUNT query for each UserRole (5 queries).
**Fix:** Single `GROUP BY` query with `func.count(User.id)`.
**Gain:** 5 queries → 1 query (80% reduction).
**File:** `app/services/admin/admin_user_service/user_queries.py:172-184`

#### 6. Unbounded Queries (Fixed 22/12/2025)
**Issue:** 9 repository methods called `.all()` without LIMIT, risking memory exhaustion.
**Fix:** Added LIMIT clauses (50-500 depending on use case).
**Files:** `alert.py`, `consent.py`, `appointment.py`, `notification.py`

---

## 4. Indexing Strategy

### Standard Indexes
-   **PK/FK:** All Primary and Foreign keys indexed.
-   **Status:** Low-cardinality fields (Enum) indexed for filtering.

### Composite Indexes
Used for frequent multi-column filters.
-   `idx_patient_phone_doctor`: `(phone, doctor_id)` -> Fast lookup for "Does this patient exist for this doctor?".
-   `idx_messages_patient_status`: `(patient_id, status)` -> Fast "Unread messages for patient".

### Partial Indexes
Used to reduce index size and maintenance cost.
-   `email IS NOT NULL`: Only indexes rows where email exists.
-   `deleted_at IS NULL`: Optimizes the common "Active records" query path.

---

## 5. Performance Monitoring

### Recommended Metrics to Watch
1.  **Slow Queries:** Monitor `pg_stat_statements` for queries > 100ms.
2.  **Connection Pool:** Ensure `Active < Pool Size`. (Alert at >90% utilization).
3.  **Index Usage:** Periodically check for unused indexes using `pg_stat_user_indexes`.
4.  **Bloat:** Monitor table bloat on high-churn tables like `messages`.

### Tuning Parameters
-   `statement_timeout`: Set to 30s (Prod) to prevent runaway queries.
-   `pool_recycle`: 3600s to prevent stale connection issues.
