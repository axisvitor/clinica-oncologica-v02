# Phase 31: Compensation Integrity — Research

**Researched:** 2026-03-01
**Domain:** Saga compensating transaction integrity (Python/SQLAlchemy/AsyncSession)
**Confidence:** HIGH — all findings derived from direct codebase inspection

---

## Summary

Phase 31 addresses four compensation-integrity requirements (COMP-01 through COMP-04) for the patient onboarding saga. The saga has three active forward steps and three compensation handlers. Direct code reading confirms the 1:1 step-to-handler mapping is complete today, the compensation sequence runs in strict reverse order (4→3→1), and idempotency guards using `step_data["compensated_steps"]` are present in every handler. The primary investigative work for this phase is verification, not correction: confirm the mapping is correct, confirm the transaction boundary model works as designed, and document any gaps found.

The transaction architecture has a deliberate two-transaction model. The forward execution path (steps 1–4) runs inside a single SQLAlchemy session that is committed atomically at the end. When the forward transaction fails, the orchestrator rolls it back and then creates a new `FAILED` saga record in a second transaction. Compensation then executes against that persisted FAILED record in its own transaction, committing as `COMPENSATED` or leaving as `FAILED` if compensation itself errors. This is the source of important boundary questions: what happens to partial DB writes (flushes) when the forward transaction rolls back, and whether the compensation commit is truly isolated from incomplete forward work.

Idempotency is implemented at the handler level via `step_data["compensated_steps"]` lists, which guards against double-execution. However, there is a gap: the `step_data` field is JSONB on the saga model, and its mutations during compensation are committed only once at the end of `_compensate_saga_internal`. If the process crashes after step 3 is compensated but before the final commit, re-running compensation starts fresh (step_data has no partial state). This is a known saga pattern risk worth documenting.

**Primary recommendation:** Verify COMP-01 through COMP-04 by static analysis and targeted unit tests — the existing code is structurally sound, but the verification artifacts (documented step-to-handler matrix, transaction boundary diagram, idempotency proof tests) do not yet exist as standalone artifacts.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| COMP-01 | Every saga step in steps.py has a matching compensation handler in compensation_handlers.py | Step/handler enumeration in Architecture Patterns section confirms 3 forward steps and 3 handlers. Gap analysis needed: step 2 (Firebase, deprecated) must be explicitly confirmed as intentionally uncompensated. |
| COMP-02 | Partial failure scenarios trigger correct rollback sequence in reverse execution order | `_compensate_saga_internal` in compensation.py reads `current_step` and executes handlers in order 4→3→1. Logic verified; plan task verifies edge cases: failure at step 1, at step 3, at step 4. |
| COMP-03 | Database transaction boundaries around saga steps verified (commit/rollback isolation) | Two-transaction model verified in orchestrator.py. Forward steps use flush-not-commit; rollback discards all intermediate work. Compensation has its own commit. Plan task: document boundary and check for partial-write leakage. |
| COMP-04 | Saga operations are idempotent (re-executing a step or compensation does not create duplicates) | Idempotency guards present in all three handlers via `compensated_steps` list in `step_data`. Forward idempotency guarded by `idempotency_key` checks and `IntegrityError` handling. Plan task: confirm guards are complete and test double-execution scenarios. |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.x (AsyncSession) | DB session management, flush/commit/rollback | Project canonical; all API routers use AsyncSession |
| pytest-asyncio | Current | Async test execution | `asyncio_mode = "auto"` in pyproject.toml |
| pytest | 7.0+ | Test framework | Configured in pyproject.toml |
| unittest.mock | stdlib | AsyncMock, MagicMock for DB/saga mocking | Used in all existing compensation tests |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| SQLite (in-memory) | stdlib | Test DB backend for unit tests | Existing conftest uses SQLite with compatibility shims for JSONB |
| MutableDict/MutableList (sqlalchemy.ext.mutable) | 2.x | JSONB mutation tracking on saga model | step_data and execution_log use these; must flag_modified when mutating nested dicts |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Direct code inspection for COMP-01 | Runtime enumeration test | Code inspection is deterministic and faster; runtime test confirms import path |
| MagicMock for DB in compensation tests | Full SQLite integration DB | Existing tests use MagicMock; unit scope is sufficient for COMP-02/04 verification |

**Installation:**
```bash
# No new dependencies — all tools already in project
cd backend-hormonia && pip install -e ".[dev]"
```

---

## Architecture Patterns

### Current Saga Step → Handler Mapping

This is the authoritative step-to-handler mapping extracted from code reading:

```
Forward Steps (steps.py — SagaStepExecutor):
  Step 1: step_create_patient()    → current_step=1, status=STEP_1_PATIENT_CREATED
  Step 2: [Firebase — DEPRECATED]  → current_step=2, status=STEP_2_FIREBASE_USER_CREATED  ← SKIPPED
  Step 3: step_initialize_flow()   → current_step=3, status=STEP_3_FLOW_INITIALIZED
  Step 4: step_send_welcome_message() → current_step=4, status=STEP_4_MESSAGE_SENT

Compensation Handlers (compensation_handlers.py):
  compensate_message()   ← compensates step 4 (mark messages CANCELLED)
  compensate_flow()      ← compensates step 3 (delete PatientFlowState records)
  compensate_patient()   ← compensates step 1 (hard-delete Patient record)
  [Step 2 deprecated]    ← explicitly SKIPPED in _compensate_saga_internal (comment at line 125)
```

**COMP-01 finding:** The 1:1 mapping is satisfied for active steps. Step 2 (Firebase) is deprecated and explicitly skipped with a code comment. This is intentional, not a gap. The plan needs to verify this claim with a static assertion.

### Compensation Sequence Pattern (COMP-02)

`_compensate_saga_internal` in `compensation.py` determines which handlers to run by checking `saga.current_step >= N`:

```python
# Source: backend-hormonia/app/orchestration/saga_orchestrator/compensation.py lines 106-134
if saga.current_step >= 4:
    await self._compensate_step_with_retry(saga, 4, "compensate_message", ...)
if saga.current_step >= 3:
    await self._compensate_step_with_retry(saga, 3, "compensate_flow", ...)
# Step 2 deprecated — skipped
if saga.current_step >= 1 and saga.patient_id:
    await self._compensate_step_with_retry(saga, 1, "compensate_patient", ...)
```

Execution order: 4 → 3 → 1 (reverse of forward: 1 → 3 → 4). This is correct.

Edge cases to verify in plans:
- `current_step=1` (patient created, failed before flow): only compensate_patient runs
- `current_step=3` (flow created, failed before message): compensate_flow + compensate_patient run
- `current_step=4` (all steps, failed after message): all three handlers run
- `current_step=0` (failed before any step): no handlers run (patient_id guard)

### Transaction Boundary Pattern (COMP-03)

```
Forward Transaction (single commit):
  db.add(saga)           → flush
  step_create_patient()  → flush (db.flush, NOT commit)
  step_initialize_flow() → flush
  step_send_welcome_message() → flush
  saga.status = COMPLETED
  await self._db_commit()   ← ONE commit for all forward work

On Forward Failure:
  await self._db_rollback()  ← ALL forward flushes discarded
  failure_saga = PatientOnboardingSaga(...)
  db.add(failure_saga)
  await self._db_commit()    ← Second tx: persist FAILED record only

Compensation Transaction (separate commit):
  saga.status = COMPENSATING
  compensate_message()   → modifies Message.status in memory
  compensate_flow()      → db.delete(flow_states) in memory
  compensate_patient()   → db.delete(patient) in memory
  saga.status = COMPENSATED
  await self._db_commit()    ← Third tx: commit all compensation deletions
```

**Key finding:** Forward step flushes use `_db_flush()`, not commit. If the overall forward transaction fails, `_db_rollback()` discards all flushed-but-uncommitted writes. This is the correct pattern — no partial writes should leak across step boundaries within the forward path.

**Risk to investigate:** The `_db_flush()` calls inside steps silently swallow flush errors (wrapped in try/except with `logger.warning`). If a flush fails but the exception is swallowed, the saga's `current_step` counter may be ahead of what was actually persisted, leading to compensation running more handlers than needed. This is a correctness concern for COMP-03 and COMP-04.

### Idempotency Pattern (COMP-04)

Forward idempotency (step re-execution safety):
```python
# step_create_patient: IntegrityError → raises ValidationError (duplicate CPF/phone/email)
# step_initialize_flow: checks for existing PatientFlowState before creating
# step_send_welcome_message: checks for existing Message with matching saga_id + idempotency_key
```

Compensation idempotency:
```python
# All three handlers in compensation_handlers.py use:
compensated_steps = saga.step_data.get("compensated_steps", []) if saga.step_data else []
if "message" in compensated_steps:  # or "flow" or "patient"
    return  # Already compensated, skip
```

**Risk:** `compensated_steps` is written to `saga.step_data` in memory during `_compensate_saga_internal`, and only committed at the very end. If the process crashes between compensating step 3 and committing, the `compensated_steps` list in the DB is empty. A second compensation run will re-execute all handlers. For `compensate_message` (mark CANCELLED — no-op if already CANCELLED due to the `Message.status != CANCELLED` filter) this is safe. For `compensate_flow` (delete flow states — no-op if already deleted) this is safe. For `compensate_patient` (delete patient — no-op if not found) this is safe. The DB-level operations are idempotent even without the in-memory guard.

### Anti-Patterns to Avoid

- **Do not add new steps to steps.py without adding a corresponding handler to compensation_handlers.py.** There is no automated enforcement of this constraint; Phase 31 should add a static check.
- **Do not commit inside individual step methods.** Steps use flush-only; one commit per saga execution. Adding a mid-step commit would break the Unit-of-Work pattern.
- **Do not catch and swallow exceptions silently in compensation handlers.** All handlers must re-raise after logging so the retry loop in `_compensate_step_with_retry` can count attempts.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Step → handler mapping enforcement | Custom registry class | Static test that enumerates step methods vs handler functions | Simpler, zero runtime overhead, existing test pattern |
| Idempotency tracking | New JSONB schema or Redis key | Existing `step_data["compensated_steps"]` | Already implemented and DB-backed |
| Transaction isolation testing | Full integration DB with real Postgres | MagicMock + AsyncMock unit tests covering commit/rollback calls | Existing test suite uses this pattern; sufficient for COMP-03 verification |

**Key insight:** This phase is verification-first. The compensation machinery is largely implemented. Plans should produce verification artifacts (documented matrix, targeted tests) rather than new implementations.

---

## Common Pitfalls

### Pitfall 1: Assuming flush = commit for transaction boundary analysis
**What goes wrong:** A reviewer concludes that step 1's `db.flush()` persists data permanently, missing the fact that the enclosing rollback wipes it.
**Why it happens:** SQLAlchemy flush is visible within the session but not committed to DB.
**How to avoid:** Document explicitly that all forward-path flushes are within a single uncommitted transaction.
**Warning signs:** Test asserting that a Patient row exists after a saga step fails.

### Pitfall 2: Missing step numbering gap (step 2)
**What goes wrong:** COMP-01 is marked incomplete because step 2 has no handler.
**Why it happens:** The SagaStatus enum still has `STEP_2_FIREBASE_USER_CREATED` and `current_step=2` appears in resume logic.
**How to avoid:** Confirm the code comment at compensation.py:125 ("Step 2 deprecated — skipped") as the authoritative documentation of this gap. The plan must document this explicitly.
**Warning signs:** An automated step-count check that treats step 2 as an active step.

### Pitfall 3: Conflating step number with SagaStatus enum ordinal
**What goes wrong:** Plan logic uses `current_step >= 2` to trigger flow compensation when it should be `>= 3`.
**Why it happens:** SagaStatus has steps 1, 2, 3, 4 in the enum but step 2 is deprecated. The `current_step` field tracks 0, 1, 3, 4 in practice (step_initialize_flow sets current_step=3, not 2).
**How to avoid:** Verify by tracing what value `current_step` takes after each step method — it is explicitly assigned in the step body, not auto-incremented.
**Warning signs:** Compensation not running for a saga at current_step=3.

### Pitfall 4: step_data flush-swallowing masking incorrect current_step
**What goes wrong:** A step sets `saga.current_step = 3` and calls flush, but flush silently fails; current_step is 3 in memory but not in DB. Compensation uses the in-memory value, which may be wrong after a crash recovery.
**Why it happens:** All flush calls in steps.py are wrapped in `try/except` that only logs a warning and continues.
**How to avoid:** This is a pre-existing architectural trade-off (fail-fast on flush would block onboarding). Document as a known compensator risk: the step counter is best-effort in crash scenarios.
**Warning signs:** A saga shows current_step=4 in DB but no patient record exists after compensation.

### Pitfall 5: compensate_flow deleting flow states that belong to other sagas
**What goes wrong:** If a patient has multiple saga attempts, `compensate_flow` deletes ALL PatientFlowState records for that patient_id, not just those created by this saga.
**Why it happens:** The query in `compensate_flow` filters only by `patient_id`, not by saga_id.
**How to avoid:** Investigate whether a patient can have multiple saga attempts simultaneously (the distributed lock on `saga:onboarding:{doctor}:{phone_hash}` prevents this for the same phone). Document as verified-safe or flag as risk.
**Warning signs:** Patient with two saga records; second saga's flow state deleted by first saga's compensation.

---

## Code Examples

### Forward Transaction — Single Commit Pattern
```python
# Source: backend-hormonia/app/orchestration/saga_orchestrator/orchestrator.py lines 147-220
try:
    patient = await self.step_executor.step_create_patient(...)   # flush only
    await self.step_executor.step_initialize_flow(...)             # flush only
    await self.step_executor.step_send_welcome_message(...)        # flush only
    saga.status = SagaStatus.COMPLETED
    await self._db_commit()   # SINGLE commit for all forward work
except Exception as e:
    await self._db_rollback()  # Wipes ALL forward flushes
    # ... create failure_saga record in new transaction ...
```

### Compensation Reverse-Order Pattern
```python
# Source: backend-hormonia/app/orchestration/saga_orchestrator/compensation.py lines 104-134
if saga.current_step >= 4:
    await self._compensate_step_with_retry(saga, 4, "compensate_message",
                                           self._compensate_message, ...)
if saga.current_step >= 3:
    await self._compensate_step_with_retry(saga, 3, "compensate_flow",
                                           self._compensate_flow, ...)
if saga.current_step >= 1 and saga.patient_id:
    await self._compensate_step_with_retry(saga, 1, "compensate_patient",
                                           self._compensate_patient, ...)
```

### Idempotency Guard Pattern (replicated in all three handlers)
```python
# Source: backend-hormonia/app/orchestration/saga_orchestrator/compensation_handlers.py lines 100-109
compensated_steps = (
    saga.step_data.get("compensated_steps", []) if saga.step_data else []
)
if "message" in compensated_steps:  # or "flow" / "patient"
    logger.info(f"Saga {saga.id}: Message compensation already done, skipping")
    return
```

### Existing Test Pattern for Compensation Verification
```python
# Source: backend-hormonia/tests/services/test_saga_compensation.py lines 346-355
async def test_compensate_saga_internal_all_steps_succeed(self, compensator, mock_saga, mock_db):
    compensator._compensate_step_with_retry = AsyncMock()
    await compensator._compensate_saga_internal(mock_saga)
    # Should call compensation for steps 4, 3, 1 (step 2 is skipped)
    assert compensator._compensate_step_with_retry.call_count == 3
    mock_db.commit.assert_called_once()
    assert mock_saga.status == SagaStatus.COMPENSATED
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Monolithic saga_orchestrator.py | Split into orchestrator.py, steps.py, compensation.py, compensation_handlers.py, persistence.py, types.py, exceptions.py, metrics.py, db_adapter.py | v1.3 (2026-02-24) | Modules are focused; LOC contracts enforced (<500 lines each) |
| Firebase step 2 active | Step 2 deprecated, skipped in compensation | Before v1.5 | compensation_handlers.py has no step-2 handler; orchestrator explicitly skips it |
| Sync Session only | Dual-mode: AsyncSession (API) + sync Session (Celery) | v1.4 (2026-02-26) | `_db_flush`, `_db_execute` etc. use `inspect.isawaitable` branching |
| Patient repo for all DB ops | Inlined async-safe queries in steps.py and compensation_handlers.py | v1.4 | Direct SQLAlchemy queries; patient_repo kept for backward compat only |

**Deprecated/outdated:**
- `SagaStatus.IN_PROGRESS`: alias for STARTED, kept for DB compatibility
- `SagaStatus.STEP_2_FIREBASE_USER_CREATED`: kept in enum for DB compatibility, never set by active code
- `PatientRepository` in compensation: present in `SagaCompensator.__init__` signature but unused (inlined queries in handlers)

---

## Open Questions

1. **Does the distributed lock prevent concurrent compensation for the same saga?**
   - What we know: `compensate_saga()` acquires `saga:compensate:{saga.id}` lock before proceeding.
   - What's unclear: If compensation is triggered twice simultaneously (e.g., two retries), the second caller gets `LockAcquisitionError` and raises `SagaCompensationError`. Is this caller's FAILED record now stuck?
   - Recommendation: Verify in plan that the lock semantics are correct and that a stuck-at-COMPENSATING saga can be manually recovered.

2. **Can a patient have multiple active saga records?**
   - What we know: The onboarding lock `saga:onboarding:{doctor}:{phone_hash}` prevents concurrent *new* saga creation for the same phone+doctor pair. But the lock TTL is 300s and resume path has its own lock.
   - What's unclear: If a saga is in FAILED state and admin triggers `resume_saga`, can a new onboarding saga for the same patient be initiated concurrently?
   - Recommendation: Document as informational finding; confirm whether `compensate_flow` deleting all patient flow states is safe given this.

3. **Is `step_data["compensated_steps"]` mutation properly tracked by SQLAlchemy MutableDict?**
   - What we know: `step_data` is `MutableDict.as_mutable(JSONB)`. When we do `saga.step_data = {**(saga.step_data or {}), "compensated_steps": [...]}`, we reassign the entire dict, which SQLAlchemy tracks as a modification.
   - What's unclear: If compensation crashes after modifying in memory but before commit, does the `compensated_steps` list persist?
   - Recommendation: Confirm via test that re-running compensation after a simulated crash still produces correct final state (all DB operations are idempotent even without the guard).

---

## Validation Architecture

The `workflow.nyquist_validation` config value is not set (only `workflow.research`, `workflow.plan_check`, `workflow.verifier` are present). The config does NOT include `nyquist_validation`, so this section is intentionally abbreviated.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.0+ with pytest-asyncio |
| Config file | `backend-hormonia/pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `cd backend-hormonia && python -m pytest tests/services/test_saga_compensation.py -x -q` |
| Full saga suite | `cd backend-hormonia && python -m pytest tests/orchestration/ tests/services/test_saga_compensation.py tests/unit/orchestration/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | Test File Exists? |
|--------|----------|-----------|-------------------|------------------|
| COMP-01 | Every step in steps.py has a handler in compensation_handlers.py | unit (static) | `pytest tests/unit/orchestration/test_saga_compensation_integrity.py::test_every_step_has_handler -x` | No — Wave 0 gap |
| COMP-02 | Triggering compensation at step N runs handlers in reverse N→1 order | unit | `pytest tests/unit/orchestration/test_saga_compensation_integrity.py::test_compensation_reverse_order -x` | No — Wave 0 gap |
| COMP-03 | Forward steps use flush-only; failure triggers rollback; compensation has its own commit | unit | `pytest tests/unit/orchestration/test_saga_compensation_integrity.py::test_transaction_boundaries -x` | No — Wave 0 gap |
| COMP-04 | Re-executing any step or handler twice produces same final state | unit | `pytest tests/unit/orchestration/test_saga_compensation_integrity.py::test_idempotency_forward_steps tests/unit/orchestration/test_saga_compensation_integrity.py::test_idempotency_compensation_handlers -x` | No — Wave 0 gap |

**Note:** Some sub-scenarios for COMP-02 and COMP-04 are already covered in `tests/services/test_saga_compensation.py`. New tests should complement, not duplicate.

### Sampling Rate
- **Per task commit:** `cd backend-hormonia && python -m pytest tests/unit/orchestration/test_saga_compensation_integrity.py -x -q`
- **Per wave merge:** `cd backend-hormonia && python -m pytest tests/orchestration/ tests/services/test_saga_compensation.py tests/unit/orchestration/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/unit/orchestration/test_saga_compensation_integrity.py` — covers COMP-01, COMP-02, COMP-03, COMP-04
- [ ] Shared fixtures for saga/db mocks already exist in `tests/fixtures/saga_fixtures.py` and `tests/services/test_saga_compensation.py` — reuse, do not duplicate

---

## Sources

### Primary (HIGH confidence)
- Direct code reading: `backend-hormonia/app/orchestration/saga_orchestrator/steps.py` — forward step implementations
- Direct code reading: `backend-hormonia/app/orchestration/saga_orchestrator/compensation_handlers.py` — compensation handler implementations
- Direct code reading: `backend-hormonia/app/orchestration/saga_orchestrator/compensation.py` — SagaCompensator orchestration and reverse-order logic
- Direct code reading: `backend-hormonia/app/orchestration/saga_orchestrator/orchestrator.py` — transaction boundary (flush vs commit), failure path, compensation trigger
- Direct code reading: `backend-hormonia/app/orchestration/saga_orchestrator/db_adapter.py` — dual-session adapter
- Direct code reading: `backend-hormonia/app/models/patient_onboarding_saga.py` — saga model, step_data MutableDict, current_step semantics
- Direct code reading: `backend-hormonia/app/models/enums.py` — SagaStatus enum, deprecated step 2
- Direct code reading: `backend-hormonia/tests/services/test_saga_compensation.py` — existing compensation test patterns
- Direct code reading: `backend-hormonia/tests/unit/orchestration/test_saga_compensation_split_contract.py` — split contract tests
- Direct code reading: `backend-hormonia/pyproject.toml` — pytest configuration

### Secondary (MEDIUM confidence)
- `.planning/REQUIREMENTS.md` — COMP-01 through COMP-04 requirement descriptions
- `.planning/STATE.md` — project decisions from phases 29-30 confirming dual-session architecture
- `.planning/phases/30-flow-integration-trace/30-VERIFICATION.md` — Phase 30 anti-pattern finding (flow_service.py async commit without await) that may interact with saga step boundary analysis

### Tertiary (LOW confidence)
- None — all findings are directly from code reading

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed in pyproject.toml and existing code
- Architecture: HIGH — all patterns read directly from production source files
- Pitfalls: HIGH (structural) / MEDIUM (crash-recovery scenarios) — structural pitfalls from code reading; crash-recovery risk extrapolated from code structure
- Test map: HIGH — existing test files confirmed, new file identified as Wave 0 gap

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (stable code; no fast-moving dependencies)
