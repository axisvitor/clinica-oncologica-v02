# Phase 30: Flow Integration Trace - Research

**Researched:** 2026-02-28
**Domain:** Python async flow tracing -- patient onboarding execution path from API entry through saga orchestration
**Confidence:** HIGH

---

## Summary

Phase 30 is a code tracing and verification phase. The goal is to follow the complete patient onboarding execution path from the `FlowDispatcher.initialize_flow()` entry point through `EnhancedFlowEngine`, `FlowCore`, to `SagaOrchestrator`, and verify that every handoff in this chain is wired correctly with no broken links. Additionally, the pause/resume semantics, cancel flow path, and `FlowCoordinatorAgent` decision-to-saga data flow must be traced and verified.

This research has read every file in the chain and pre-identified the actual call graph, pause/resume state machine, cancel path logic, and agent-to-saga data flow. Key finding: the flow chain has TWO distinct execution paths -- (A) the API onboarding path via `patients/crud.py -> OnboardingCoordinator -> SagaOrchestrator`, and (B) the daily flow execution path via `FlowCoordinatorAgent -> SequentialMessageHandler`. The saga is ONLY invoked in path (A) for patient creation. Path (B) does NOT use the saga at all. This distinction is critical for correctly scoping TRACE-04.

A significant finding is that there are TWO separate pause implementations with DIFFERENT state keys: `FlowManagementService.pause_patient_flow()` sets `state_data["paused"] = True`, while `TransitionHandler.pause_flow()` (agent path) sets `state_data["flow_paused"] = True`. The Celery Beat `process_daily_flows` task only checks `state_data.get("paused")`, NOT `state_data.get("flow_paused")`. This means agent-initiated pauses may NOT block daily flow processing -- a potential correctness issue that tracing should document.

**Primary recommendation:** Trace each path by reading the code call-by-call, documenting every handoff (caller -> callee -> parameter types -> return types), and flagging any broken links, type mismatches, or state inconsistencies. This is a read-and-document phase, not a fix-everything phase -- fixes belong in Phase 31+ or get deferred.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TRACE-01 | Full patient onboarding path traced from FlowDispatcher.initialize_flow() through EnhancedFlowEngine, FlowCore, to SagaOrchestrator execution | Complete call graph pre-mapped: `FlowDispatcher -> PatientFlowService -> FlowCore.enroll_patient()` AND `patients/crud.py -> OnboardingCoordinator -> SagaOrchestrator.execute_patient_onboarding_saga()`. Both paths documented with file locations. |
| TRACE-02 | Pause/resume semantics verified through split flow management code (management/pause_resume.py) | Three separate pause paths identified: (1) `FlowManagementService.pause_patient_flow()` via API, (2) `FlowCore.pause_patient_flow()` via FlowCore transitions, (3) `TransitionHandler.pause_flow()` via agent. State key divergence (`paused` vs `flow_paused`) pre-identified. Auto-resume via Celery Beat documented. |
| TRACE-03 | Cancel flow path verified: revocation of queued work, state cleanup, and saga compensation triggered correctly | Cancel path in `pause_resume.py:cancel_patient_flow()` pre-read: revokes Celery tasks, marks messages CANCELLED, sets flow status "cancelled". CRITICAL FINDING: cancel does NOT trigger saga compensation -- cancel operates on flow state only, saga compensation is triggered only on saga failure during patient creation. |
| TRACE-04 | FlowCoordinatorAgent decision engine interaction with saga verified for correct data flow | Agent path traced: `FlowCoordinatorAgent._process_daily_flow() -> DecisionEngine -> _execute_flow_decision()`. This path does NOT invoke SagaOrchestrator -- it calls `SequentialMessageHandler.send_day_messages()` for message dispatch and `TransitionHandler` for state changes. The agent-saga "interaction" is INDIRECT: agent manages flow state that was originally created by the saga during onboarding. |
</phase_requirements>

---

## Standard Stack

### Core

| Component | Version | Purpose | Why Standard |
|-----------|---------|---------|--------------|
| Python | 3.12 | Runtime | Project baseline |
| SQLAlchemy | existing | ORM (AsyncSession for API, sync Session for Celery) | Dual-session pattern established in v1.4 |
| pytest + pytest-asyncio | 8.3.4 | Test framework | pyproject.toml: `asyncio_mode = "auto"` |
| Celery + Celery Beat | existing | Task queue + scheduled auto-resume | `resume_paused_flows` runs hourly |

### Supporting

| Component | Purpose | When to Use |
|-----------|---------|-------------|
| `app.core.distributed_lock.acquire_lock` | Distributed locking | Saga execution, saga resume, saga compensation |
| `app.utils.timezone.now_sao_paulo` | Timezone-aware timestamps | All state_data timestamps |

### No New Dependencies

This is a tracing/verification phase. No new packages are needed.

---

## Architecture Patterns

### The Complete Onboarding Call Graph (TRACE-01)

Two entry paths to patient enrollment exist:

#### Path A: API Patient Creation (Primary -- uses Saga)

```
API: POST /api/v2/patients/
  -> app/api/v2/routers/patients/crud.py (line ~756)
     -> SagaOrchestrator(db=db, redis_client=..., evolution_client=...)
     -> get_onboarding_coordinator(db, saga_orchestrator)
     -> coordinator.create_patient(patient_data, doctor_id, current_user, idempotency_key)
        -> OnboardingCoordinator.create_patient()  [coordinator.py:124]
           -> integrity_service.validate_patient_data()           # Step 1: Validate
           -> saga_orchestrator.execute_patient_onboarding_saga() # Step 2: Saga
              -> SagaOrchestrator.execute_patient_onboarding_saga() [orchestrator.py:85]
                 -> acquire_lock("saga:onboarding:{doctor}:{phone_hash}")
                 -> Create PatientOnboardingSaga record
                 -> step_executor.step_create_patient()     [steps.py:152]  -> Patient DB record
                 -> step_executor.step_initialize_flow()    [steps.py:298]
                    -> flow_service.initialize_default_flow()
                       -> PatientFlowService.initialize_default_flow() [flow_service.py:68]
                          -> _select_flow_type(patient) -> FlowType.ONBOARDING
                          -> flow_engine.enroll_patient(patient_id, flow_type)
                             -> FlowCore.enroll_patient() [operations.py:99]
                                -> Create PatientFlowState record
                    -> flow_service.activate_patient()
                       -> PatientFlowService.activate_patient() [flow_service.py:169]
                 -> step_executor.step_send_welcome_message() [steps.py:421]
                    -> message_service.schedule_message()   -> Message record (PENDING)
                 -> Commit or Compensate on failure
```

#### Path B: FlowDispatcher (Standalone enrollment -- NO saga)

```
FlowDispatcher.initialize_flow(patient, user_id)  [dispatcher.py:66]
  -> PatientFlowService(db).initialize_default_flow(patient, user_id)  [flow_service.py:68]
     -> _select_flow_type(patient) -> FlowType
     -> flow_engine.enroll_patient(patient_id, flow_type)
        -> FlowCore.enroll_patient() [operations.py:99]
           -> Create PatientFlowState record (with auto_commit=True)
     -> activate flow in patient metadata
```

**Key distinction:** `FlowDispatcher` does NOT use the saga. It calls `PatientFlowService` directly for enrollment. The saga path is ONLY invoked via `patients/crud.py -> OnboardingCoordinator`.

#### Path C: Daily Flow Execution (NO saga, uses agent)

```
Celery Beat: process_daily_flows [flow_tasks.py]
  -> Query active PatientFlowState records
  -> Filter out paused flows (checks state_data.get("paused"))
  -> For each active flow:
     -> SequentialMessageHandler.send_day_messages()
        -> _flow_functions.run_flow_message()

FlowCoordinatorAgent._process_daily_flow() [coordinator.py:168]
  -> state_manager.build_flow_context()
  -> decision_engine.analyze_flow_situation()
  -> decision_engine.make_flow_decision()
  -> _execute_flow_decision()
     -> _process_normal_flow() -> SequentialMessageHandler.send_day_messages()
     OR transition_handler.pause_flow() / resume_flow() / etc.
```

### Pause/Resume State Machine (TRACE-02)

#### Three Pause Paths (CRITICAL DIVERGENCE)

| Path | Code Location | Sets | Checks |
|------|--------------|------|--------|
| API pause | `FlowManagementPauseResumeMixin.pause_patient_flow()` | `state_data["paused"] = True`, `status = "paused"` | `state_data.get("paused")` |
| FlowCore pause | `FlowCoreTransitionsMixin.pause_patient_flow()` | `state_data["paused"] = True`, `status = "paused"` | -- |
| Agent pause | `TransitionHandler.pause_flow()` | `state_data["flow_paused"] = True` | Does NOT set `status = "paused"` |

**FINDING:** Agent `TransitionHandler.pause_flow()` uses key `"flow_paused"`, NOT `"paused"`. It also does NOT change `flow_state.status` to `"paused"`. This means:
- The Celery Beat `process_daily_flows` task checks `state_data.get("paused")` -- it will NOT see agent-initiated pauses.
- The `resume_paused_flows` task queries `WHERE status = 'paused' AND state_data->>'auto_resume_at' IS NOT NULL` -- agent pauses that don't set status to "paused" will NOT be auto-resumed.

**Pause State Transitions:**

```
Active Flow:
  state_data: {} or {"paused": false}
  status: "active"

After API/FlowCore Pause:
  state_data: {"paused": true, "pause_reason": "...", "paused_at": "...", "auto_resume_at": "..."}
  status: "paused"

After Resume:
  state_data: {"paused": false, "resumed_at": "..."}
  status: "active"

After Auto-Resume (Celery Beat):
  Same as manual resume -- called via FlowManagementService.resume_patient_flow()
```

**Auto-Resume Mechanism:**
1. `pause_patient_flow()` accepts `duration_hours` parameter
2. If provided, `auto_resume_at = now + timedelta(hours=duration_hours)` is stored in `state_data`
3. Celery Beat task `resume_paused_flows` runs hourly
4. Queries flows where `status = 'paused' AND state_data->>'auto_resume_at' <= NOW()`
5. Calls `FlowManagementService.resume_patient_flow()` for each

**Message dispatch guard:** The `process_daily_flows` task filters out paused flows: `if flow.state_data and flow.state_data.get("paused")`. The `_flow_functions.py` and `SequentialMessageHandler` do NOT independently check pause status -- the guard is at the Celery task level only.

### Cancel Flow Path (TRACE-03)

```
API: POST /api/v2/flows/{patient_id}/cancel
  -> FlowService.cancel_patient_flow()  [flow_service.py:255]
     -> flow_management.cancel_patient_flow()
        -> FlowManagementPauseResumeMixin.cancel_patient_flow()  [pause_resume.py:200]
           1. Get active flow state from flow_repo
           2. Query pending/scheduled/queued outbound messages for patient
           3. For each message:
              a. Set status = CANCELLED
              b. If message_metadata has celery_task_id: revoke via AsyncResult.revoke()
           4. Update flow_state:
              - status = "cancelled"
              - completed_at = now
              - state_data["paused"] = False
              - state_data["cancelled"] = True
              - state_data["auto_resume_at"] removed
              - state_data tracks messages_cancelled count and tasks_revoked count
           5. Commit
```

**CRITICAL FINDING:** Cancel does NOT trigger saga compensation. The cancel path operates purely on `PatientFlowState` and `Message` records. Saga compensation is invoked ONLY during `SagaOrchestrator.execute_patient_onboarding_saga()` when a step fails (see `orchestrator.py:273-286`). The cancel operation is independent of the saga lifecycle.

**Celery task revocation:** Uses `AsyncResult(task_id).revoke(terminate=False)` -- soft revocation (task will not execute if still queued, but will not be forcefully terminated if already running).

### FlowCoordinatorAgent Decision-to-Saga Data Flow (TRACE-04)

The FlowCoordinatorAgent does NOT directly invoke the SagaOrchestrator. The relationship is:

1. **Saga creates the initial flow state** during patient onboarding:
   - `SagaOrchestrator -> SagaStepExecutor.step_initialize_flow() -> PatientFlowService -> FlowCore.enroll_patient()` creates `PatientFlowState`

2. **Agent reads and modifies the flow state** created by the saga:
   - `FlowCoordinatorAgent._process_daily_flow() -> StateManager.build_flow_context()` reads `PatientFlowState`
   - `DecisionEngine` analyzes the flow context and makes a `FlowDecision`
   - `TransitionHandler` executes state changes on `PatientFlowState`

3. **Data flow (indirect):**
   ```
   Saga (writes) -> PatientFlowState DB record <- (reads) Agent
   ```

The agent receives:
- `patient_id` from task payload
- `current_day` from task payload
- `FlowContext` built from DB state (patient record, flow state, adherence metrics, interactions)

The agent does NOT pass data back to the saga. The saga is a one-time onboarding operation; the agent manages the ongoing flow lifecycle.

### Anti-Patterns to Watch For

- **Dual pause keys:** `state_data["paused"]` vs `state_data["flow_paused"]` -- tracing should flag this divergence clearly.
- **Sync DB calls in async context:** Already fixed in Phase 29 for SagaOrchestrator (db_adapter mixin), but `PatientFlowService.delete_flow()` still uses sync `self.db.query()` -- this is the saga compensation path.
- **Missing pause guard in _flow_functions:** Neither `_flow_functions.py` nor `SequentialMessageHandler` checks pause status. If called directly (bypassing Celery task filter), messages will be sent to paused flows.
- **Cancel does not check saga state:** If a patient was mid-saga (theoretically impossible since saga runs in a single request), cancel would not compensate the saga.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Call graph visualization | Custom AST parser | Manual code-reading with grep/read tools | Call graph is ~8 functions deep; manual tracing is faster and more accurate |
| State machine validation | Formal state machine framework | Document expected transitions and verify in code | State machine is simple (active/paused/cancelled/completed) |
| Type checking across handoffs | Runtime type assertions | Read type hints and verify manually | This is a tracing phase, not a runtime validation phase |

---

## Common Pitfalls

### Pitfall 1: Assuming FlowDispatcher is the Saga Entry Point

**What goes wrong:** The requirement says "trace from FlowDispatcher.initialize_flow() through EnhancedFlowEngine, FlowCore, to SagaOrchestrator." This implies FlowDispatcher calls the saga.
**Why it happens:** FlowDispatcher is named as the "entry point" but it actually delegates to `PatientFlowService` which calls `FlowCore.enroll_patient()` -- no saga involved.
**How to avoid:** Trace BOTH paths: (A) the saga path via `patients/crud.py -> OnboardingCoordinator -> SagaOrchestrator` and (B) the standalone `FlowDispatcher -> PatientFlowService -> FlowCore` path. Document that the saga entry is path (A), not FlowDispatcher.
**Warning signs:** If the trace document says "FlowDispatcher calls SagaOrchestrator", the trace is wrong.

### Pitfall 2: Confusing Three Pause Implementations

**What goes wrong:** There are THREE places that implement pause logic with subtly different state key names and behaviors.
**Why it happens:** The code was split across v1.3 (management mixins) and the agent system has its own pause via TransitionHandler.
**How to avoid:** Trace each pause path separately and compare the state keys and status changes side-by-side.
**Warning signs:** Test that checks `state_data.get("paused")` passes but agent-paused flows still receive messages.

### Pitfall 3: Expecting Cancel to Trigger Saga Compensation

**What goes wrong:** TRACE-03 success criteria says "cancel flow triggers saga compensation." The actual code does NOT trigger saga compensation from the cancel path.
**Why it happens:** Cancel operates on `PatientFlowState` and `Message` records. The saga is a one-time onboarding transaction that runs to completion or compensates inline.
**How to avoid:** Document that cancel and saga compensation are independent operations. The success criteria "verifiable by inspecting cancel path logic" means inspecting the code and documenting what cancel actually does -- not asserting that it calls saga compensation.
**Warning signs:** Attempting to add saga compensation to the cancel path would be scope creep -- cancel happens AFTER onboarding is complete.

### Pitfall 4: Missing Sync-to-Async Issues in PatientFlowService

**What goes wrong:** `PatientFlowService.delete_flow()` uses `self.db.query(PatientFlowState)` (sync) and `self.db.delete(state)` (sync). If called with AsyncSession (from API path), this will fail.
**Why it happens:** `delete_flow()` was not migrated to async in v1.4.
**How to avoid:** Document this as a finding during the trace. It is called from `compensation_handlers.compensate_flow()` which receives an AsyncSession -- this is a potential bug in the compensation path.
**Warning signs:** `AttributeError: 'AsyncSession' object has no attribute 'query'` during saga compensation.

---

## Code Examples

### Tracing a Handoff (pattern for TRACE-01)

```python
# Pattern: verify each handoff by reading both sides

# CALLER: orchestrator.py:160
await self.step_executor.step_initialize_flow(
    saga, patient, current_user, idempotency_key=idempotency_key
)

# CALLEE: steps.py:298
async def step_initialize_flow(
    self,
    saga: PatientOnboardingSaga,
    patient: Patient,
    current_user: Any,
    idempotency_key: Optional[str] = None,
) -> None:

# VERIFY: parameter count matches, types are compatible
# saga: PatientOnboardingSaga -- OK (caller passes saga which is this type)
# patient: Patient -- OK (caller passes patient from step_create_patient result)
# current_user: Any -- OK (caller passes current_user from API)
# idempotency_key: Optional[str] -- OK (caller passes from outer scope)
```

### Verifying Pause State Transition

```python
# API pause sets these keys:
flow_state.state_data["paused"] = True
flow_state.state_data["pause_reason"] = reason
flow_state.state_data["paused_at"] = now_sao_paulo().isoformat()
flow_state.status = "paused"

# Agent pause sets DIFFERENT keys:
context.flow_state.state_data["flow_paused"] = True
context.flow_state.state_data["paused_at"] = now_sao_paulo().isoformat()
# Does NOT set flow_state.status = "paused"

# Celery Beat only checks:
if flow.state_data and flow.state_data.get("paused"):  # Misses agent pauses!
```

### Cancel Path Message Revocation

```python
# pause_resume.py:228-245
from celery.result import AsyncResult
from app.celery_app import celery_app as celery_instance

for message in pending_messages:
    message.status = MessageStatus.CANCELLED
    task_id = message.message_metadata.get("celery_task_id") if message.message_metadata else None
    if task_id:
        AsyncResult(task_id, app=celery_instance).revoke(terminate=False)
        revoked_count += 1
```

---

## Pre-Identified Issues (Findings to Document During Trace)

### Issue 1: Dual Pause State Key Divergence

| Attribute | API/FlowCore Path | Agent Path |
|-----------|-------------------|------------|
| State key | `state_data["paused"]` | `state_data["flow_paused"]` |
| Status field | `status = "paused"` | NOT changed |
| Auto-resume support | Yes (`auto_resume_at`) | No |
| Blocks daily flow? | Yes (Celery task filter) | No (filter checks `"paused"` not `"flow_paused"`) |

**Severity:** MEDIUM -- agent-initiated pauses may not block message dispatch.
**Recommendation:** Document as finding. Fix belongs in Phase 31+ or a follow-up.

### Issue 2: PatientFlowService.delete_flow() Uses Sync DB

```python
# flow_service.py:341-366
async def delete_flow(self, patient_id: UUID) -> bool:
    flow_states = (
        self.db.query(PatientFlowState)        # SYNC -- will fail with AsyncSession
        .filter(PatientFlowState.patient_id == patient_id)
        .all()
    )
    for state in flow_states:
        self.db.delete(state)                    # SYNC
    self.db.commit()                             # SYNC
```

Called from: `compensation_handlers.compensate_flow()` which receives AsyncSession from the saga's db parameter.

**Severity:** MEDIUM -- compensation path for flow deletion may fail with AsyncSession.
**Note:** `compensation_handlers.compensate_flow()` actually uses `await db.execute(select(...))` pattern with AsyncSession. Need to verify if `delete_flow()` is actually called or if compensation inlines its own async deletion.

### Issue 3: Cancel Does NOT Trigger Saga Compensation

The success criteria says "cancel flow triggers saga compensation." The code shows cancel operates independently:
- Cancel modifies `PatientFlowState` (status, state_data)
- Cancel marks messages as CANCELLED and revokes Celery tasks
- Cancel does NOT touch `PatientOnboardingSaga` records
- Saga compensation is only triggered inline during `execute_patient_onboarding_saga()` failure

**Severity:** Informational -- this is by design, not a bug. The saga is a one-time operation.

### Issue 4: SequentialMessageHandler Has No Pause Guard

`_flow_functions.py` and `SequentialMessageHandler.send_day_messages()` do not check `state_data.paused` before sending messages. The pause guard is ONLY in the Celery Beat task `process_daily_flows`.

**Severity:** LOW -- if `send_day_messages` is called directly (e.g., from FlowCoordinatorAgent), it will send to paused flows. However, the agent path builds a FlowContext and could theoretically check pause status in the decision engine.

---

## File Inventory for Tracing

### TRACE-01: Onboarding Path Files

| File | Role in Chain | LOC |
|------|--------------|-----|
| `app/api/v2/routers/patients/crud.py` | API entry point; creates SagaOrchestrator | ~900 |
| `app/services/patient/onboarding_factory.py` | Wires OnboardingCoordinator with all deps | 103 |
| `app/domain/patient/onboarding/coordinator.py` | Orchestrates validation + saga call | 204 |
| `app/orchestration/saga_orchestrator/orchestrator.py` | Saga main class; 3-step execution | 475 |
| `app/orchestration/saga_orchestrator/steps.py` | Step implementations (create patient, init flow, send message) | 585 |
| `app/services/patient/flow_service.py` | PatientFlowService (init flow, activate, delete) | 367 |
| `app/services/flow/core/operations.py` | FlowCore.enroll_patient() | 340 |
| `app/services/dispatcher.py` | FlowDispatcher (standalone, no saga) | 139 |
| `app/services/enhanced_flow_engine_pkg/service.py` | EnhancedFlowEngine (inherits FlowCore) | 120 |
| `app/services/flow/core/service.py` | FlowCore composed class | 28 |

### TRACE-02: Pause/Resume Files

| File | Role | LOC |
|------|------|-----|
| `app/services/flow/management/pause_resume.py` | API pause/resume/cancel (FlowManagementService mixin) | 290 |
| `app/services/flow/core/transitions.py` | FlowCore pause/resume (EnhancedFlowEngine path) | 262 |
| `app/agents/patient/flow_coordinator/transition_handler.py` | Agent pause/resume | 194 |
| `app/tasks/flow_automation.py` | Celery Beat auto-resume task | 635 |
| `app/tasks/flows/flow_tasks.py` | process_daily_flows (pause filter) | ~200 |

### TRACE-03: Cancel Path Files

| File | Role | LOC |
|------|------|-----|
| `app/services/flow/management/pause_resume.py` | cancel_patient_flow() implementation | 290 |
| `app/api/v2/routers/flows.py` | API endpoint wiring | ~1200 |
| `app/services/flow_service.py` | FlowService facade delegation | ~300 |
| `app/orchestration/saga_orchestrator/compensation.py` | SagaCompensator (NOT called by cancel) | 255 |
| `app/orchestration/saga_orchestrator/compensation_handlers.py` | Individual compensation handlers | 344 |

### TRACE-04: Agent Decision Engine Files

| File | Role | LOC |
|------|------|-----|
| `app/agents/patient/flow_coordinator/coordinator.py` | FlowCoordinatorAgent main class | 402 |
| `app/agents/patient/flow_coordinator/decision_engine.py` | DecisionEngine (flow decisions) | 207 |
| `app/agents/patient/flow_coordinator/transition_handler.py` | TransitionHandler (state changes) | 194 |
| `app/agents/patient/flow_coordinator/state_manager.py` | StateManager (context building) | ~200 |
| `app/agents/patient/flow_coordinator/models.py` | FlowContext, FlowDecision models | ~100 |

---

## Plan Split Recommendation

### Plan 30-01: Trace Full Onboarding Path (TRACE-01)

Trace the complete onboarding call chain from `patients/crud.py` through `OnboardingCoordinator -> SagaOrchestrator -> SagaStepExecutor -> PatientFlowService -> FlowCore.enroll_patient()`. Also trace the standalone `FlowDispatcher -> PatientFlowService` path. Document every handoff with:
- Caller file + line
- Callee file + method signature
- Parameter types passed vs expected
- Return type
- Any broken links or type mismatches

### Plan 30-02: Trace Pause/Resume and Cancel Semantics (TRACE-02, TRACE-03)

Trace all three pause paths and the cancel path. Document:
- State key divergence (`paused` vs `flow_paused`)
- Pause guard coverage (which callers check pause before dispatch)
- Auto-resume mechanism (Celery Beat -> FlowManagementService)
- Cancel path: message revocation, state cleanup
- Whether cancel interacts with saga compensation (answer: no)
- Whether messages are blocked during pause (answer: only via Celery task filter)

### Plan 30-03: Trace Agent Decision Engine Data Flow (TRACE-04)

Trace the `FlowCoordinatorAgent._process_daily_flow()` path:
- How FlowContext is built from DB state
- What data the DecisionEngine receives
- How decisions map to actions (TransitionHandler, SequentialMessageHandler)
- The indirect relationship: saga creates flow state, agent manages it afterward
- Data integrity: does the agent have all context it needs?
- Session type concern: agent uses sync Session (db_session) but handler may need AsyncSession

---

## Existing Test Coverage

| Test File | What It Covers | Relevant to |
|-----------|---------------|-------------|
| `tests/unit/services/test_flow_cancel.py` | 5 tests: cancel state, cancel messages, revoke tasks, override pause, not found | TRACE-03 |
| `tests/unit/tasks/test_auto_resume_flows.py` | 4 tests: expired resume, future skip, indefinite skip, conflict handling | TRACE-02 |
| `tests/orchestration/test_saga_orchestrator.py` | Saga happy path and compensation | TRACE-01 |
| `tests/services/test_saga_compensation.py` | Compensation handler tests | TRACE-03 |
| `tests/unit/orchestration/test_saga_module_audit.py` | Export/type audit | TRACE-01 (Phase 29) |

---

## Open Questions

1. **Does `compensation_handlers.compensate_flow()` call `PatientFlowService.delete_flow()` or inline its own async deletion?**
   - What we know: `compensation_handlers.py` receives AsyncSession and uses `await db.execute(select(...))`. `PatientFlowService.delete_flow()` uses sync `self.db.query()`.
   - What's unclear: Whether `compensate_flow()` delegates to `delete_flow()` or inlines the deletion.
   - Recommendation: Read `compensation_handlers.py:compensate_flow()` during plan execution.

2. **Is the `TransitionHandler.pause_flow()` "flow_paused" key actually used in production?**
   - What we know: The agent code sets `state_data["flow_paused"] = True` but the daily task filter checks `state_data.get("paused")`.
   - What's unclear: Whether `FlowCoordinatorAgent` is actively invoked in production (it requires sync Session from the legacy agent framework).
   - Recommendation: Check if the agent is registered in Celery Beat or if it's only invoked via the agent messaging system.

3. **Is `FlowDispatcher` still used anywhere as an entry point?**
   - What we know: `FlowDispatcher` is defined but the primary enrollment path goes through `patients/crud.py -> OnboardingCoordinator -> SagaOrchestrator`.
   - What's unclear: Whether any other code path still calls `FlowDispatcher.initialize_flow()`.
   - Recommendation: Grep for `FlowDispatcher` usage during plan execution.

---

## Sources

### Primary (HIGH confidence)

- Direct file inspection -- all files in the flow chain read in full during research:
  - `app/services/dispatcher.py` (FlowDispatcher)
  - `app/services/enhanced_flow_engine_pkg/service.py` (EnhancedFlowEngine)
  - `app/services/flow/core/service.py` (FlowCore)
  - `app/services/flow/core/operations.py` (FlowCoreOperationsMixin)
  - `app/services/flow/core/transitions.py` (FlowCoreTransitionsMixin)
  - `app/services/patient/flow_service.py` (PatientFlowService)
  - `app/services/patient/onboarding_factory.py` (factory)
  - `app/domain/patient/onboarding/coordinator.py` (OnboardingCoordinator)
  - `app/orchestration/saga_orchestrator/orchestrator.py` (SagaOrchestrator)
  - `app/orchestration/saga_orchestrator/steps.py` (SagaStepExecutor)
  - `app/orchestration/saga_orchestrator/compensation.py` (SagaCompensator)
  - `app/orchestration/saga_orchestrator/db_adapter.py` (SagaDBAdapterMixin)
  - `app/services/flow/management/pause_resume.py` (pause/resume/cancel)
  - `app/services/flow/management/service.py` (FlowManagementService)
  - `app/agents/patient/flow_coordinator/coordinator.py` (FlowCoordinatorAgent)
  - `app/agents/patient/flow_coordinator/decision_engine.py` (DecisionEngine)
  - `app/agents/patient/flow_coordinator/transition_handler.py` (TransitionHandler)
  - `app/tasks/flow_automation.py` (Celery Beat auto-resume)
  - `app/tasks/flows/flow_tasks.py` (daily flow processing)
  - `app/api/v2/routers/patients/crud.py` (API entry point)
  - `app/api/v2/routers/flows.py` (flow API endpoints)
  - `app/services/flow_service.py` (FlowService facade)
  - `app/services/flow/sequential_message_handler_pkg/sequencing.py` (message dispatch)
- Phase 29 RESEARCH.md and VERIFICATION.md -- saga module audit findings
- `.planning/REQUIREMENTS.md` -- TRACE-01 through TRACE-04 definitions
- `.planning/ROADMAP.md` -- Phase 30 success criteria

### Secondary (MEDIUM confidence)

- `.planning/STATE.md` -- v1.3 split decisions and v1.4 async migration context

### Tertiary (LOW confidence)

- None -- all findings are from direct codebase inspection.

---

## Metadata

**Confidence breakdown:**
- Onboarding path (TRACE-01): HIGH -- complete call graph pre-mapped from code
- Pause/resume semantics (TRACE-02): HIGH -- all three paths read, state key divergence confirmed
- Cancel path (TRACE-03): HIGH -- full cancel implementation read, Celery revocation logic traced
- Agent-saga data flow (TRACE-04): HIGH -- agent code read, saga relationship clarified as indirect

**Research date:** 2026-02-28
**Valid until:** 2026-03-28 (stable codebase, no external dependencies to track)
