# Database Issues - Quick Reference Card

**Generated:** 2025-12-24 | **Analyst:** Code Analyzer Agent

---

## 🔴 CRITICAL - Fix Immediately

### SAGA-001: Transaction Integrity Bug
**Impact:** Race conditions, orphaned patient records

```python
# ❌ CURRENT (BROKEN):
# app/repositories/patient/base.py:171-174
def create(self, obj_in: Dict[str, Any], auto_commit: bool = True):
    self.db.add(patient)
    if auto_commit:
        self.db.commit()  # ← COMMITS BEFORE SAGA COMPLETES!

# ✅ FIX:
# app/orchestration/saga_orchestrator.py
async def execute_saga(saga):
    patient = repo.create(data, auto_commit=False)  # NO COMMIT
    flow = await init_flow(patient, auto_commit=False)
    msg = await send_message(patient, auto_commit=False)

    db.commit()  # SINGLE COMMIT AT END
    saga.status = COMPLETED
```

**Files to Fix:**
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/orchestration/saga_orchestrator.py`
- `/mnt/c/Meu Projetos/clinica-oncologica-v02-1/backend-hormonia/app/repositories/patient/base.py`

**Priority:** P0 - Must fix before production

---

## 🟠 HIGH - Fix This Sprint

### FK-001: Missing passive_deletes
**Impact:** N+1 queries on patient deletion (50-80% slower)

```python
# ❌ CURRENT:
# app/models/alert.py:77
patient = relationship("Patient", back_populates="alerts")

# ✅ FIX:
patient = relationship("Patient", back_populates="alerts", passive_deletes=True)
```

**Apply to these relationships:**
1. `app/models/alert.py:77` - Alert.patient
2. `app/models/alert.py:78` - Alert.acknowledged_by_user
3. `app/models/quiz.py:278` - QuizResponse.patient
4. `app/models/quiz.py:279` - QuizResponse.quiz_template
5. `app/models/user.py:80-113` - All User relationships

**Priority:** P1 - Performance optimization

---

### RACE-001: Idempotency Gap
**Impact:** Duplicate patient creation errors under concurrent load

```python
# ✅ FIX:
# app/api/v2/routers/patients/crud.py
async def create_patient(data, db):
    key = generate_idempotency_key(data)

    # Check existing
    existing = repo.get_by_idempotency_key(key)
    if existing:
        return existing

    try:
        patient = repo.create({...data, "idempotency_key": key})
        db.commit()
        return patient
    except IntegrityError:
        db.rollback()
        # Race: another request won
        return repo.get_by_idempotency_key(key)
```

**Priority:** P1 - User experience

---

## 🟡 MEDIUM - Next Sprint

### IDX-002: Missing Composite Index

```sql
-- Add to new migration:
CREATE INDEX idx_patient_flow_states_patient_status
  ON patient_flow_states(patient_id, status);
```

**Use Case:**
```sql
SELECT * FROM patient_flow_states
WHERE patient_id = ? AND status = 'active';
```

**Priority:** P2 - Performance improvement

---

## ✅ What's Working Well

1. **LGPD Compliance** - Full encryption, plaintext dropped
2. **Indexing Strategy** - Comprehensive coverage on patients table
3. **Eager Loading** - Good N+1 prevention with selectinload/joinedload
4. **Connection Pooling** - Well-configured (20 base, 30 overflow)
5. **Unique Constraints** - Proper partial indexes for soft deletes

---

## 📊 Schema Health Summary

| Aspect | Status | Notes |
|---|---|---|
| LGPD Compliance | ✅ Excellent | Migration 030 complete |
| Indexes | ✅ Good | Minor composite index missing |
| Relationships | ⚠️ Needs Fix | passive_deletes missing |
| Transactions | 🔴 Critical | Saga pattern broken |
| Uniqueness | ✅ Excellent | Hash-based constraints work |
| Performance | ✅ Good | Eager loading well implemented |

---

## 🎯 Action Items

**Today:**
- [ ] Fix SAGA-001 transaction management
- [ ] Add passive_deletes to 7 relationships

**This Week:**
- [ ] Implement idempotency retry logic
- [ ] Test saga rollback scenarios

**Next Sprint:**
- [ ] Add composite index migration
- [ ] Limit message eager loading to recent N

---

## 📁 Key Files

**Models:**
- `app/models/patient.py` - Core entity
- `app/models/patient_onboarding_saga.py` - Saga tracking
- `app/models/alert.py`, `app/models/quiz.py`, `app/models/user.py` - Need passive_deletes

**Repositories:**
- `app/repositories/patient/base.py` - CRUD (needs auto_commit fix)
- `app/repositories/patient/eager_loading.py` - N+1 prevention

**Orchestration:**
- `app/orchestration/saga_orchestrator.py` - Transaction coordinator

**Migrations:**
- `alembic/versions/034_add_performance_indexes.py` - Latest
- `alembic/versions/030_drop_plaintext_email_phone.py` - LGPD

---

**Full Report:** `docs/patient-debug/DATABASE_ANALYSIS.md`
