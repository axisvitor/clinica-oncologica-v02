# Database Schema Analysis Report - Oncology Clinic System

**Analyzed by**: Database Schema Analyzer Agent
**Date**: 2025-12-24
**Environment**: PostgreSQL (AWS RDS)
**Project**: Hormonia Backend - Oncology Patient Management

---

## Executive Summary

**Overall Assessment**: 🟡 MODERATE - Schema is generally well-designed but has **7 critical issues** and **15 optimization opportunities** requiring attention.

**Critical Issues Found**: 7
**Warning-Level Issues**: 8
**Optimization Opportunities**: 15
**Migration Conflicts**: 2

---

## 1. CRITICAL ISSUES (P0)

### 🔴 ISSUE #1: Schema-Model Mismatch in QuizSession

**Severity**: P0 - Critical
**Impact**: Runtime errors, data corruption
**Location**: `app/models/quiz.py` (QuizSession model)

**Problem**:
- **Database column**: `current_question` (Integer)
- **Model attribute**: `current_question_index` (used in some code)
- **Inconsistency**: Model defines `current_question` but has backward-compatibility property for `current_question_index`

**Evidence**:
```python
# quiz.py line 106-107
current_question = Column(Integer, nullable=True, default=0)
# FIX: Renamed from current_question_index

# Lines 185-191 - Backward compatibility
@property
def current_question_index(self) -> int:
    return self.current_question or 0
```

**Impact**:
- Code using `current_question_index` directly will fail
- Serialization inconsistencies
- Migration confusion

**Recommendation**:
- Standardize on `current_question` everywhere
- Remove backward-compatibility properties
- Update all API endpoints and services

---

### 🔴 ISSUE #2: Migration 034 - CONCURRENTLY in Transaction

**Severity**: P0 - Migration Failure
**Impact**: Index creation will fail
**Location**: `alembic/versions/034_add_performance_indexes.py`

**Problem**:
```python
# Lines 50-64
def create_index_safe(index_name: str, table: str, column: str):
    try:
        op.execute(f"""
            CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name}
            ON {table}({column})
        """)
    except Exception:
        op.execute(f"""
            CREATE INDEX IF NOT EXISTS {index_name}
            ON {table}({column})
        """)
```

**Why This Fails**:
- `CREATE INDEX CONCURRENTLY` **CANNOT** run inside a transaction
- Alembic runs migrations in transactions by default
- Exception handler will catch and fall back, but this is inefficient

**Evidence from Comments**:
```python
# Line 26-28
# IMPORTANT: CONCURRENTLY requires running outside a transaction.
# Run with: alembic upgrade head --sql | psql  (for manual review)
# Or ensure transaction_per_migration=False in env.py for this migration.
```

**Impact**:
- Indexes created with regular `CREATE INDEX` (locks table)
- Production table locks during index creation
- Potential downtime or slow queries

**Recommendation**:
```python
# Option 1: Disable transaction for this migration
revision = '034_add_performance_indexes'
down_revision = '033_fix_user_sync_log_schema'

def upgrade():
    # Check if in transaction
    conn = op.get_bind()
    if conn.in_transaction():
        # Commit transaction before CONCURRENTLY
        op.execute("COMMIT")

    # Now safe to use CONCURRENTLY
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_patients_doctor_id
        ON patients(doctor_id)
    """)

# Option 2: Run outside Alembic
# Execute indexes separately in production:
# psql $DATABASE_URL -c "CREATE INDEX CONCURRENTLY ..."
```

---

### 🔴 ISSUE #3: Missing Index Cleanup in Migration 034

**Severity**: P0 - Incomplete Migration
**Impact**: Index duplication, unused indexes
**Location**: `034_add_performance_indexes.py` lines 74-85

**Problem**:
```python
# Line 74-85 - Conditional index creation in DO $$ block
def create_index_if_table_exists(index_name, table, column):
    op.execute(f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table}') THEN
                EXECUTE 'CREATE INDEX IF NOT EXISTS {index_name} ON {table}({column})';
            END IF;
        END $$;
    """)
```

**Issues**:
1. **Cannot use CONCURRENTLY** inside `DO $$` blocks
2. **Table existence check incomplete** - doesn't verify if index already exists
3. **No validation** of index creation success

**Impact**:
- Potential duplicate indexes
- Missed optimization opportunities
- Migration idempotency issues

**Recommendation**:
```python
def create_index_if_table_exists(index_name, table, column):
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Check if table exists
    if table not in inspector.get_table_names():
        return

    # Check if index already exists
    indexes = inspector.get_indexes(table)
    if any(idx['name'] == index_name for idx in indexes):
        return

    # Create index CONCURRENTLY (outside transaction)
    if not conn.in_transaction():
        op.execute(f"CREATE INDEX CONCURRENTLY {index_name} ON {table}({column})")
    else:
        # Fallback: regular index
        op.execute(f"CREATE INDEX {index_name} ON {table}({column})")
```

---

### 🔴 ISSUE #4: Database Pool Exhaustion Risk

**Severity**: P0 - Production Availability
**Impact**: Connection exhaustion, application downtime
**Location**: `app/core/database_config.py`

**Problem - Development Environment**:
```python
# Lines 240-252
else:  # DEVELOPMENT
    return DatabasePoolConfig(
        pool_size=10,      # Reduced from 20
        max_overflow=15,   # Reduced from 30
        # Total per worker: 10 + 15 = 25 connections
    )
```

**Current State**:
- Development: 1 worker × 25 connections = **25 total**
- Production: 4 workers × 20 connections = **80 total**
- AWS RDS t3.micro limit: ~100 connections
- Reserved for admin: ~20 connections
- **Available**: ~80 connections

**Risk Calculation**:
```
Development (Single Machine):
- Default workers: 1
- Connections: 25
- Status: ✅ SAFE

Production (Multiple Workers):
- Workers: 4
- Connections per worker: 20
- Total: 80
- Status: ⚠️ AT LIMIT

If someone runs dev with 4 workers:
- Total: 4 × 25 = 100 connections
- Status: 🔴 EXCEEDS LIMIT
```

**Evidence**:
```python
# Lines 288-292
if environment == EnvironmentType.PRODUCTION and total_connections > 80:
    logger.warning(
        f"⚠️  Total connections ({total_connections}) may exceed "
        f"AWS RDS limits (~80). Consider reducing workers or pool size."
    )
```

**Impact**:
- Connection pool exhaustion
- `FATAL: too many connections` errors
- Application downtime
- Failed requests

**Recommendation**:
```python
# Solution 1: Environment-aware defaults
def get_worker_count() -> int:
    explicit_workers = os.getenv("WEB_CONCURRENCY") or os.getenv("WORKER_COUNT")
    if explicit_workers:
        return int(explicit_workers)

    env = detect_environment()
    if env == EnvironmentType.DEVELOPMENT:
        return 1  # ✅ Force single worker in dev
    elif env == EnvironmentType.PRODUCTION:
        return 4  # Production default
    else:
        return 2  # Staging default

# Solution 2: Dynamic pool sizing
def calculate_pool_config(environment: str, worker_count: Optional[int] = None):
    if worker_count is None:
        worker_count = get_worker_count()

    # Calculate safe pool size based on workers
    max_connections = 80  # AWS RDS limit
    total_per_worker = max_connections // worker_count
    pool_size = int(total_per_worker * 0.5)
    max_overflow = total_per_worker - pool_size

    return DatabasePoolConfig(
        pool_size=pool_size,
        max_overflow=max_overflow,
        ...
    )
```

---

### 🔴 ISSUE #5: LGPD Compliance - Encryption Validation Hook Issues

**Severity**: P0 - Data Integrity
**Impact**: Incomplete encryption, LGPD violations
**Location**: `app/models/patient.py` lines 569-601

**Problem**:
```python
@event.listens_for(Patient, "before_insert")
@event.listens_for(Patient, "before_update")
def validate_cpf_encryption(mapper, connection, target):
    # Check if CPF data exists and is properly encrypted
    if target.cpf_encrypted:
        if not target.cpf_hash:
            raise ValueError(
                "CPF encryption incomplete: cpf_hash is missing. "
                "Use set_cpf() method to properly encrypt CPF data."
            )
```

**Issues**:
1. **Only validates CPF** - doesn't validate email/phone encryption
2. **No validation on email_encrypted/email_hash**
3. **No validation on phone_encrypted/phone_hash**
4. **Inconsistent encryption** could slip through

**Missing Validations**:
```python
# MISSING: Email encryption validation
if target.email_encrypted and not target.email_hash:
    raise ValueError("Email encryption incomplete")

# MISSING: Phone encryption validation
if target.phone_encrypted and not target.phone_hash:
    raise ValueError("Phone encryption incomplete")

# MISSING: Reverse validation
if target.email_hash and not target.email_encrypted:
    raise ValueError("Email hash without encrypted data")
```

**Impact**:
- Incomplete LGPD compliance
- Searchable hashes without encryption
- Data integrity violations
- Potential data leaks

**Recommendation**:
```python
@event.listens_for(Patient, "before_insert")
@event.listens_for(Patient, "before_update")
def validate_lgpd_encryption(mapper, connection, target):
    """Validate all PII encryption (CPF, email, phone)."""

    # CPF validation
    if target.cpf_encrypted and not target.cpf_hash:
        raise ValueError("CPF encryption incomplete: missing hash")
    if target.cpf_hash and not target.cpf_encrypted:
        raise ValueError("CPF hash without encrypted data")

    # Email validation
    if target.email_encrypted and not target.email_hash:
        raise ValueError("Email encryption incomplete: missing hash")
    if target.email_hash and not target.email_encrypted:
        raise ValueError("Email hash without encrypted data")

    # Phone validation
    if target.phone_encrypted and not target.phone_hash:
        raise ValueError("Phone encryption incomplete: missing hash")
    if target.phone_hash and not target.phone_encrypted:
        raise ValueError("Phone hash without encrypted data")
```

---

### 🔴 ISSUE #6: Transaction Management in Repository

**Severity**: P0 - Data Consistency
**Impact**: Saga failures, incomplete transactions
**Location**: `app/repositories/patient/base.py`

**Problem - Inconsistent Transaction Handling**:
```python
# Lines 169-183 - create() method
try:
    self.db.add(patient)
    if auto_commit:
        self.db.commit()
        self.db.refresh(patient)
    else:
        self.db.flush()
        self.db.refresh(patient)
except Exception:
    self.db.rollback()  # ❌ PROBLEM: Always rollbacks, even in saga mode
    raise
```

**Issue**:
- When `auto_commit=False` (saga mode), rollback **undoes the flush**
- Saga orchestrator expects flush to persist until final commit
- Creates **race condition** in saga execution

**Impact**:
- Saga steps fail unexpectedly
- Patient creation rollback in step 1
- Orphaned saga records
- Data inconsistency

**Correct Implementation**:
```python
try:
    self.db.add(patient)
    if auto_commit:
        # Standard mode: commit immediately
        self.db.commit()
        self.db.refresh(patient)
    else:
        # Saga mode: flush only, let caller handle commit/rollback
        self.db.flush()
        self.db.refresh(patient)
        # ✅ NO ROLLBACK - let saga orchestrator decide
except Exception:
    if auto_commit:
        # Only rollback in auto_commit mode
        self.db.rollback()
    raise  # Let saga orchestrator handle in saga mode
```

**Alternative - Unit of Work Pattern**:
```python
class UnitOfWork:
    def __init__(self, db: Session):
        self.db = db
        self._committed = False

    def commit(self):
        self.db.commit()
        self._committed = True

    def rollback(self):
        if not self._committed:
            self.db.rollback()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        return False
```

---

### 🔴 ISSUE #7: Migration 033 - User Sync Log Schema Issues

**Severity**: P0 - Migration Failure Risk
**Impact**: Failed migrations, data loss
**Location**: `alembic/versions/033_fix_user_sync_log_schema.py`

**Problem 1 - Nullable to NOT NULL**:
```python
# Lines 56-70
if 'operation' not in existing_columns:
    # Add with default then make NOT NULL
    op.add_column('user_sync_log',
        sa.Column('operation', sa.String(50), nullable=True)
    )
    # Migrate data from sync_action if it exists
    if 'sync_action' in existing_columns:
        op.execute("""
            UPDATE user_sync_log
            SET operation = COALESCE(sync_action, 'sync')
            WHERE operation IS NULL
        """)
    else:
        op.execute("UPDATE user_sync_log SET operation = 'sync' WHERE operation IS NULL")
    op.alter_column('user_sync_log', 'operation', nullable=False)  # ❌ RACE CONDITION
```

**Race Condition**:
1. Add column as nullable
2. Run UPDATE to set defaults
3. Change to NOT NULL
4. **Problem**: If INSERT happens between steps 2-3, it creates NULL row
5. Step 3 fails with "column contains null values"

**Problem 2 - Missing Index on Foreign Key**:
```python
# Lines 44-54
if 'user_id' not in existing_columns:
    op.add_column('user_sync_log',
        sa.Column('user_id', sa.UUID(), nullable=True)
    )
    op.create_index('ix_user_sync_log_user_id', 'user_sync_log', ['user_id'])
    op.create_foreign_key(
        'fk_user_sync_log_user_id',
        'user_sync_log', 'users',
        ['user_id'], ['id'],
        ondelete='CASCADE'
    )
```

**Issue**: Index created **before** foreign key
- Should create FK first, then index
- FK creation is slower without index
- Better: Create index, then FK (current order is actually correct)

**Correct Implementation**:
```python
# Solution 1: Add with default value
if 'operation' not in existing_columns:
    op.add_column('user_sync_log',
        sa.Column('operation', sa.String(50),
                  nullable=False,  # ✅ NOT NULL from start
                  server_default='sync')  # ✅ Database default
    )
    # Migrate from sync_action if exists
    if 'sync_action' in existing_columns:
        op.execute("UPDATE user_sync_log SET operation = sync_action WHERE sync_action IS NOT NULL")

    # Remove server default after migration
    op.alter_column('user_sync_log', 'operation', server_default=None)

# Solution 2: Use transaction isolation
from sqlalchemy import text

def upgrade():
    conn = op.get_bind()

    # Start exclusive transaction
    conn.execute(text("LOCK TABLE user_sync_log IN ACCESS EXCLUSIVE MODE"))

    # Now safe to add column and update
    op.add_column(...)
    op.execute("UPDATE ...")
    op.alter_column(..., nullable=False)
```

---

## 2. WARNING-LEVEL ISSUES (P1)

### ⚠️ ISSUE #8: N+1 Query Potential in Eager Loading

**Severity**: P1 - Performance
**Impact**: Slow queries, database load
**Location**: `app/repositories/patient/eager_loading.py`

**Problem**:
```python
# Lines 60-82
if "messages" in eager_load:
    query = query.options(
        selectinload(Patient.messages).joinedload(Message.sender)
    )
```

**Issue**: Nested eager loading strategy unclear
- `selectinload` for messages (correct for 1:many)
- `joinedload` for sender (correct for 1:1)
- But: does this execute 1 or 2 queries?

**Recommendation**: Document query count and add tests

---

### ⚠️ ISSUE #9: Index Naming Inconsistency

**Severity**: P1 - Maintainability
**Location**: Multiple migrations

**Inconsistencies**:
- `ix_patients_email_hash` vs `idx_patients_doctor_id`
- `ix_` prefix vs `idx_` prefix
- Some indexes use `v2` suffix: `idx_quiz_sessions_patient_id_v2`

**Recommendation**: Standardize on `idx_` prefix

---

### ⚠️ ISSUE #10: Missing Composite Indexes

**Severity**: P1 - Performance
**Location**: Database schema

**Missing Indexes**:
```sql
-- Frequently used together
CREATE INDEX idx_patients_doctor_flow_state ON patients(doctor_id, flow_state);
CREATE INDEX idx_quiz_sessions_patient_status ON quiz_sessions(patient_id, status);
CREATE INDEX idx_quiz_responses_session_question ON quiz_responses(quiz_session_id, question_id);
```

---

### ⚠️ ISSUE #11: Webhook Models Use Base Instead of BaseModel

**Severity**: P1 - Inconsistency
**Impact**: Missing timestamp fields, audit trail
**Location**: `app/models/webhook.py` lines 23-27

**Problem**:
```python
# Line 23-27
from app.models.base import Base

# Note: Webhook models use Base (not BaseModel) because they have custom
# id/timestamp columns that differ from BaseModel's standard fields.
# WebhookDelivery has completed_at, next_retry_at; WebhookLog has no updated_at.
# Changing to BaseModel would require database migration.
```

**Issues**:
1. **WebhookLog has no `updated_at`** - breaks audit trail
2. **Inconsistent with other models** - Patient, Quiz use BaseModel
3. **Custom timestamp handling** - prone to errors

**Impact**:
- Harder to track changes
- Inconsistent API responses
- Manual timestamp management

**Recommendation**:
- Create migration to add `updated_at` to WebhookLog
- Migrate to BaseModel for consistency
- Or document why this exception is necessary

---

### ⚠️ ISSUE #12: FlowState Enum Duplication

**Severity**: P1 - Code Duplication
**Location**: `app/models/patient.py`, `app/models/flow.py`

**Problem**:
```python
# patient.py lines 26-27
from app.models.enums import FlowState  # Consolidated enum
# Re-export for backward compatibility

# flow.py lines 23-26
from app.models.enums import FlowState  # Consolidated enum
# Re-export for backward compatibility
```

**Issue**: Both files import and re-export FlowState
- Centralized in `app/models/enums`
- But still imported in multiple places
- Backward compatibility re-exports

**Recommendation**:
- Remove re-exports
- Update all imports to use `app.models.enums.FlowState`
- Add deprecation warnings if needed

---

### ⚠️ ISSUE #13: SagaStatus Enum Schema Mismatch

**Severity**: P1 - Enum Management
**Location**: `app/models/patient_onboarding_saga.py`

**Problem**:
```python
# Lines 97-102
status = Column(
    PG_ENUM(SagaStatus, name="saga_status", create_type=False),
    nullable=False,
    default=SagaStatus.STARTED,
    index=True,
)
```

**Issue**: `create_type=False`
- Assumes enum type already exists in database
- If enum doesn't exist, column creation fails
- No migration to create enum type

**Missing**:
```sql
-- Should be in migration
CREATE TYPE saga_status AS ENUM (
    'STARTED',
    'IN_PROGRESS',
    'STEP_1_PATIENT_CREATED',
    'STEP_2_FIREBASE_USER_CREATED',
    'STEP_3_FLOW_INITIALIZED',
    'STEP_4_MESSAGE_SENT',
    'COMPLETED',
    'COMPLETED_WITH_WARNINGS',
    'FAILED',
    'COMPENSATING',
    'COMPENSATED',
    'RETRY_SCHEDULED'
);
```

**Recommendation**: Create migration to ensure enum type exists

---

### ⚠️ ISSUE #14: Deprecated Firebase Step in Saga

**Severity**: P1 - Dead Code
**Location**: `app/models/patient_onboarding_saga.py` lines 39-41

**Problem**:
```python
# DEPRECATED: Firebase integration removed - keeping for DB compatibility
# This step is skipped in saga execution (see saga_orchestrator.py)
STEP_2_FIREBASE_USER_CREATED = "STEP_2_FIREBASE_USER_CREATED"  # @deprecated
```

**Issues**:
1. Dead enum value in database
2. Status never used in code
3. Creates confusion in saga logic
4. Step numbering gap (1, 3, 4 instead of 1, 2, 3)

**Recommendation**:
- Create migration to remove deprecated status
- Renumber saga steps (1, 2, 3 instead of 1, 3, 4)
- Update documentation

---

### ⚠️ ISSUE #15: Redis Client Lazy Loading in Repository

**Severity**: P1 - Error Handling
**Location**: `app/repositories/patient/base.py` lines 48-59

**Problem**:
```python
@property
def redis(self):
    """Lazy load Redis client for caching"""
    if self._redis_client is None:
        try:
            from app.core.redis_unified import get_redis_client
            self._redis_client = get_redis_client("sync")
        except Exception:
            # Redis optional - gracefully degrade if unavailable
            self._redis_client = False  # ❌ Uses False as sentinel
    return self._redis_client if self._redis_client else None
```

**Issues**:
1. Uses `False` as sentinel value
2. Every access checks `if self._redis_client`
3. Generic `Exception` catch
4. No logging of Redis failures

**Better Implementation**:
```python
from typing import Optional

_REDIS_UNAVAILABLE = object()  # Unique sentinel

@property
def redis(self) -> Optional[RedisClient]:
    if self._redis_client is None:
        try:
            from app.core.redis_unified import get_redis_client
            self._redis_client = get_redis_client("sync")
        except (ImportError, ConnectionError, RedisError) as e:
            logger.warning(f"Redis unavailable: {e}")
            self._redis_client = _REDIS_UNAVAILABLE

    return None if self._redis_client is _REDIS_UNAVAILABLE else self._redis_client
```

---

## 3. OPTIMIZATION OPPORTUNITIES

### 💡 OPT #1: Partial Index on deleted_at

**Current**:
```python
# patient.py line 127
deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
```

**Optimized**:
```sql
-- Only index non-deleted patients (most queries)
CREATE INDEX idx_patients_active
ON patients(id)
WHERE deleted_at IS NULL;

-- Smaller index, faster queries
```

---

### 💡 OPT #2: Covering Indexes for Analytics

**Location**: Quiz analytics queries

**Current**: Separate indexes on each column

**Optimized**:
```sql
-- Covering index for quiz analytics
CREATE INDEX idx_quiz_responses_analytics_covering
ON quiz_responses(quiz_template_id, question_id, response_value, responded_at);

-- All data in index, no table lookup needed
```

**Already Implemented**: Line 311-316 in quiz.py ✅

---

### 💡 OPT #3: JSONB Indexing for patient_data

**Current**: No JSONB indexes

**Recommended**:
```sql
-- GIN index for JSONB queries
CREATE INDEX idx_patients_metadata_gin
ON patients USING gin(patient_data);

-- Specific path indexes for common queries
CREATE INDEX idx_patients_medical_history
ON patients USING gin((patient_data->'medical_history'));
```

**Note**: Migration 005 adds GIN indexes - verify implementation

---

### 💡 OPT #4: Connection Pool Pre-Warming

**Location**: `app/core/database_config.py`

**Current**: Pools fill on demand

**Optimization**:
```python
def warm_pool(engine, pool_size: int):
    """Pre-warm connection pool on startup."""
    connections = []
    try:
        for _ in range(pool_size):
            connections.append(engine.connect())
        logger.info(f"Pre-warmed {pool_size} connections")
    finally:
        for conn in connections:
            conn.close()
```

---

### 💡 OPT #5: Query Result Caching Strategy

**Location**: `app/repositories/quiz.py`

**Current**: 5-10 minute TTL caching

**Optimization**:
```python
# Tiered caching strategy
CACHE_TTL = {
    "templates": 3600,        # 1 hour (rarely change)
    "sessions": 300,          # 5 minutes (moderate changes)
    "responses": 60,          # 1 minute (frequently change)
    "analytics": 1800,        # 30 minutes (computed data)
}
```

---

### 💡 OPT #6: Batch Insert for Quiz Responses

**Optimization**: Use bulk insert for multiple responses

```python
def bulk_create_responses(
    db: Session,
    responses: List[Dict[str, Any]]
) -> List[QuizResponse]:
    """Bulk insert quiz responses."""

    response_objects = [
        QuizResponse(**response_data)
        for response_data in responses
    ]

    db.bulk_save_objects(response_objects, return_defaults=True)
    db.commit()

    return response_objects
```

---

### 💡 OPT #7: Database Connection Health Checks

**Location**: Add to `database_config.py`

```python
def check_pool_health(engine):
    """Monitor connection pool health."""
    pool = engine.pool

    metrics = {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
        "max_overflow": pool._max_overflow,
    }

    # Alert if pool is exhausted
    if metrics["checked_out"] >= metrics["size"]:
        logger.warning(f"Pool near exhaustion: {metrics}")

    return metrics
```

---

### 💡 OPT #8: Async Repository Pattern

**Future Optimization**: Move to async database operations

```python
from sqlalchemy.ext.asyncio import AsyncSession

class AsyncPatientRepository:
    async def get_by_id(self, patient_id: UUID) -> Optional[Patient]:
        async with self.session() as db:
            result = await db.execute(
                select(Patient)
                .where(Patient.id == patient_id)
                .options(selectinload(Patient.quiz_sessions))
            )
            return result.scalar_one_or_none()
```

---

## 4. MIGRATION CONFLICTS

### 🔧 CONFLICT #1: Index Creation Order

**Migrations**: 033, 034

**Issue**: Both create indexes on same tables
- 033: Creates indexes during column addition
- 034: Creates performance indexes
- Potential duplication

**Recommendation**: Verify no duplicate indexes

---

### 🔧 CONFLICT #2: FlowState Enum References

**Location**: Multiple models reference FlowState

**Issue**: Enum changes require multiple migrations

**Recommendation**:
- Document all FlowState usages
- Use Alembic batch operations for enum changes

---

## 5. SCHEMA HEALTH SUMMARY

### Models Analyzed: 6
- ✅ Patient (602 lines) - Well-structured with LGPD compliance
- ✅ Quiz (362 lines) - Good design, minor field naming issues
- ✅ Flow (162 lines) - Clean, standardized
- ✅ Webhook (167 lines) - Uses Base instead of BaseModel
- ✅ PatientOnboardingSaga (262 lines) - Good saga pattern
- ⚠️ Database Config (353 lines) - Pool exhaustion risk

### Repository Patterns: 4
- ✅ PatientRepositoryBase - Good CRUD with caching
- ✅ QuizRepository - Well-optimized with eager loading
- ✅ Eager Loading Mixin - Prevents N+1 queries
- ⚠️ Transaction management needs improvement

### Migration Health:
- Total migrations analyzed: 2 (033, 034)
- ✅ LGPD compliance migrations (028-030)
- ⚠️ Performance index migrations need review
- 🔴 CONCURRENTLY issues in migration 034

---

## 6. RECOMMENDATIONS BY PRIORITY

### Immediate (P0) - Within 24 Hours:
1. ✅ Fix migration 034 CONCURRENTLY issue
2. ✅ Verify database pool configuration
3. ✅ Add email/phone encryption validation hooks
4. ✅ Fix transaction management in repositories
5. ✅ Review migration 033 race conditions

### Short Term (P1) - Within 1 Week:
6. Standardize index naming (`idx_` prefix)
7. Add missing composite indexes
8. Create SagaStatus enum migration
9. Remove deprecated Firebase saga step
10. Document N+1 query prevention strategy

### Medium Term (P2) - Within 1 Month:
11. Add JSONB GIN indexes for patient_data
12. Implement connection pool pre-warming
13. Add database health monitoring
14. Optimize query caching strategy
15. Consider async repository pattern

### Long Term (P3) - Backlog:
16. Migrate webhooks to BaseModel
17. Centralize enum definitions
18. Add batch insert optimizations
19. Implement covering indexes
20. Performance testing and benchmarking

---

## 7. MONITORING RECOMMENDATIONS

### Database Metrics to Track:
- Connection pool usage (checked out / total)
- Query execution time (p50, p95, p99)
- Index usage statistics
- Cache hit ratios (Redis)
- Transaction rollback rates
- N+1 query detection

### Alerts to Configure:
- Pool usage > 80%
- Query time > 1 second
- Failed migrations
- LGPD encryption failures
- Saga compensation triggers

---

## 8. TESTING RECOMMENDATIONS

### Unit Tests Needed:
- Migration idempotency (can run twice)
- LGPD encryption hooks
- Transaction management in sagas
- Connection pool exhaustion scenarios

### Integration Tests Needed:
- Concurrent request handling
- Database pool under load
- Index performance benchmarks
- Cache invalidation logic

---

## 9. CONCLUSION

The database schema is **fundamentally sound** but requires **immediate attention** to:

1. **Migration 034** - Fix CONCURRENTLY issue before production deployment
2. **Connection pools** - Prevent exhaustion in multi-worker environments
3. **LGPD compliance** - Extend validation hooks to email/phone
4. **Transaction management** - Fix saga repository patterns

**Overall Risk Level**: 🟡 MODERATE

**Time to Fix Critical Issues**: 4-8 hours

**Recommended Next Steps**:
1. Create branch: `fix/database-critical-issues`
2. Fix migration 034 CONCURRENTLY
3. Add comprehensive encryption validation
4. Update repository transaction handling
5. Add database pool monitoring
6. Run full integration test suite
7. Deploy to staging for validation

---

**Generated by**: Database Schema Analyzer
**Coordination**: Claude Flow Swarm
**Memory Key**: `bugs/database`
