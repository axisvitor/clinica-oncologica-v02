# Phase 30, Plan 02 - Pause/Resume/Cancel Trace

## Scope

- Requirement focus: TRACE-02, TRACE-03
- This document traces pause and resume semantics first, then cancel semantics.
- Task 1 output covers the three pause paths, auto-resume wiring, and pause guard coverage.

## Contract Reconciliation Note (TRACE-03)

- Cancel behavior in the traced flow path is message/task cleanup plus flow-state transition to cancelled.
- Saga compensation is triggered by saga failure handling in the onboarding orchestrator lifecycle.
- Cancel does not trigger saga compensation; TRACE-03 is satisfied by verifiable cancel semantics plus an explicit compensation boundary.

## Section 1: Pause Path Trace (TRACE-02)

### Path 1: API/FlowManagement pause (`FlowManagementPauseResumeMixin.pause_patient_flow`)

- File: `app/services/flow/management/pause_resume.py`
- Signature:
  - `pause_patient_flow(patient_id: UUID, reason: Optional[str] = None, duration_hours: Optional[int] = None, user_id: UUID = None) -> FlowPauseResponse`
- Active-flow lookup:
  - `flow_state = self.flow_repo.get_active_flow(patient_id)`
- State writes:
  - `state_data["paused"] = True`
  - `state_data["pause_reason"] = reason or "Manual pause by healthcare provider"`
  - `state_data["paused_at"] = now`
  - Optional: `state_data["paused_by"] = str(user_id)`
  - Optional: `state_data["auto_resume_at"] = now + duration_hours`
- Status write:
  - `flow_state.status = "paused"`
  - `flow_state.last_interaction_at = now`
- Persistence mode:
  - Sync ORM path with `self.db.commit()`
- Additional behavior:
  - Idempotent re-pause branch executes when `state_data.get("paused")` is already true.
  - Re-pause refreshes `pause_reason`, `paused_at`, and optionally `auto_resume_at`.

### Path 2: FlowCore pause (`FlowCoreTransitionsMixin.pause_patient_flow`)

- File: `app/services/flow/core/transitions.py`
- Signature:
  - `pause_patient_flow(patient_id: UUID, reason: str = None) -> dict[str, Any]`
- Active-flow lookup:
  - `await _get_flow_state_by_status(patient_id, "active")`
- State writes:
  - `state_data["paused"] = True`
  - `state_data["pause_reason"] = reason or "Manual pause"`
  - `state_data["paused_at"] = now`
  - `state_data["paused_by_step"] = flow_state.current_step`
- Status write:
  - `flow_state.status = "paused"`
- Persistence mode:
  - Async path with optimistic lock via `await _commit_flow_state_with_lock(...)`
- Additional behavior:
  - Emits flow-state change events through `flow_broadcaster`.

### Path 3: Agent pause (`TransitionHandler.pause_flow`)

- File: `app/agents/patient/flow_coordinator/transition_handler.py`
- Signature:
  - `pause_flow(context: FlowContext)`
- State writes:
  - `state_data["flow_paused"] = True`
  - `state_data["paused_at"] = now`
  - `state_data["paused_by"] = agent_id`
  - `state_data["pause_reason"] = "patient_request_or_medical_indication"`
- Status write:
  - No write to `flow_state.status`
- Persistence mode:
  - Sync session commit with `self.db_session.commit()`
- Additional behavior:
  - Emits structured log event with `transition_type = "pause"`.

### Side-by-side pause comparison

| Attribute | API/FlowManagement | FlowCore | Agent/TransitionHandler |
|---|---|---|---|
| State key | `state_data["paused"]` | `state_data["paused"]` | `state_data["flow_paused"]` |
| Status field | Sets `status = "paused"` | Sets `status = "paused"` | Not changed |
| Auto-resume write | Yes (`auto_resume_at` when `duration_hours`) | No explicit write in pause method | No |
| Daily-flow pause filter compatibility | Yes | Yes | No (filter checks `paused`) |
| DB mode | Sync commit (`self.db.commit`) | Async optimistic lock commit | Sync session commit |

## Section 2: Resume and Auto-Resume Trace (TRACE-02)

### Manual resume behavior

#### API/FlowManagement resume (`FlowManagementPauseResumeMixin.resume_patient_flow`)

- Preconditions:
  - Active flow exists (`get_active_flow`).
  - `state_data.get("paused")` must be true.
- State writes:
  - `state_data["paused"] = False`
  - `state_data["resumed_at"] = now`
  - Optional: `state_data["resumed_by"] = str(user_id)`
  - `state_data.pop("auto_resume_at", None)`
- Status write:
  - `flow_state.status = "active"`
- Persistence mode:
  - Sync `self.db.commit()`.

#### FlowCore resume (`FlowCoreTransitionsMixin.resume_patient_flow`)

- Preconditions:
  - Paused flow exists (`await _get_flow_state_by_status(patient_id, "paused")`).
- State writes:
  - `state_data["paused"] = False`
  - `state_data["resumed_at"] = now`
  - `state_data.pop("auto_resume_at", None)`
  - `state_data["resumed"] = {...}` snapshot with pause metadata
- Status write:
  - `flow_state.status = "active"`
- Persistence mode:
  - Async optimistic lock commit + broadcast.

#### Agent resume (`TransitionHandler.resume_flow`)

- State writes:
  - `state_data["flow_paused"] = False`
  - `state_data["resumed_at"] = now`
  - `state_data["resumed_by"] = agent_id`
- Status write:
  - No `flow_state.status = "active"` write.

### Auto-resume mechanism (`resume_paused_flows` -> `resume_patient_flow`)

- Beat schedule source:
  - File: `app/celery_app.py`
  - Entry: `"resume-paused-flows"`
  - Task: `"app.tasks.flow_automation.resume_paused_flows"`
  - Frequency: `3600.0` seconds (hourly)
- Task implementation source:
  - File: `app/tasks/flow_automation.py`
  - Task function: `resume_paused_flows`
- Query criteria inside task:
  - `pfs.status = 'paused'`
  - `pfs.state_data->>'auto_resume_at' IS NOT NULL`
  - `(pfs.state_data->>'auto_resume_at')::timestamptz <= NOW()`
- Action path:
  - Builds `FlowManagementService(db)`
  - Calls `await mgmt_service.resume_patient_flow(patient_id=flow_row.patient_id)`

## Section 3: Pause Guard Coverage

- Task-level guard location:
  - File: `app/tasks/flows/flow_tasks.py`
  - Function: `process_daily_flows_async`
  - Guard expression: `if flow.state_data and flow.state_data.get("paused")`
- Effect:
  - API and FlowCore pauses are filtered out before daily dispatch.
  - Agent pause (`flow_paused`) is not filtered by this guard.
- Guard gap:
  - `SequentialMessageHandler.send_day_messages()` does not implement an independent pause check.
  - Pause enforcement currently depends on callers applying the task-level filter.

## Section 4: Findings From Pause/Resume Trace

### Finding A: Dual pause key divergence

- Severity: MEDIUM
- Evidence:
  - API/FlowCore use `state_data["paused"]` and set `status = "paused"`.
  - Agent TransitionHandler uses `state_data["flow_paused"]` and leaves status unchanged.
- Impact:
  - Agent-paused flows can bypass `process_daily_flows_async` pause filter.
  - Agent-paused flows do not satisfy auto-resume task criteria (`status = 'paused'` + `auto_resume_at`).

### Finding B: Pause guard is centralized and not defense-in-depth

- Severity: MEDIUM
- Evidence:
  - Guard exists in `process_daily_flows_async` only.
  - Sequential message dispatch path does not apply an independent pause gate.
- Impact:
  - Any direct dispatch path that skips task-level filtering can send messages for paused flows.

## Section 5: Cancel Path Trace (TRACE-03)

### Cancel API wiring

| Layer | File | Method | What it does |
|---|---|---|---|
| API endpoint | `app/api/v2/routers/flows.py` | `cancel_patient_flow(...)` | Exposes `POST /{patient_id}/cancel` and delegates to `FlowService` |
| API facade | `app/services/flow_service.py` | `FlowService.cancel_patient_flow(...)` | Delegates to `self.flow_management.cancel_patient_flow(...)` and maps response to `FlowCancelV2Response` |
| Management implementation | `app/services/flow/management/pause_resume.py` | `FlowManagementPauseResumeMixin.cancel_patient_flow(...)` | Cancels outbound messages, revokes Celery tasks, updates flow state to cancelled |

### Cancel execution sequence

1. **Input contract**
   - Current implementation accepts `patient_id` and optional `user_id`.
   - No `reason` argument is accepted in this method today.

2. **Flow lookup**
   - Retrieves active flow with `self.flow_repo.get_active_flow(patient_id)`.
   - Raises `FlowStateNotFoundError` when no active flow exists.

3. **Cancelable outbound message query**
   - Builds cancellable statuses as `[PENDING, SCHEDULED]` and adds `QUEUED` if available.
   - Queries messages by:
     - `Message.patient_id == patient_id`
     - `Message.status.in_(cancellable_statuses)`
     - `Message.direction == MessageDirection.OUTBOUND`

4. **Message status mutation and Celery revoke**
   - For each matched message:
     - sets `message.status = MessageStatus.CANCELLED`
     - reads `message.message_metadata.get("celery_task_id")`
     - calls `AsyncResult(task_id, app=celery_instance).revoke(terminate=False)` when task id exists
   - Soft revoke semantics (`terminate=False`):
     - queued task: prevented from future execution
     - running task: not force-killed

5. **Flow state cleanup and cancellation metadata**
   - `flow_state.status = "cancelled"`
   - `flow_state.completed_at = now`
   - `flow_state.last_interaction_at = now`
   - `state_data["paused"] = False`
   - `state_data["cancelled"] = True`
   - `state_data["cancelled_at"] = now.isoformat()`
   - `state_data["cancelled_by"] = str(user_id) if user_id else None`
   - `state_data["messages_cancelled"] = len(pending_messages)`
   - `state_data["tasks_revoked"] = revoked_count`
   - `state_data.pop("auto_resume_at", None)`

6. **Commit behavior**
   - Increments optimistic version (`flow_state.version = expected_version + 1`).
   - Executes one `self.db.commit()` after message and flow mutations.
   - Returns summary payload with cancellation timestamp, message count, and revoke count.

## Section 6: Cancel vs Saga Compensation Independence

### Verified compensation trigger boundary

- Compensation engine location:
  - `app/orchestration/saga_orchestrator/compensation.py`
  - `SagaCompensator.compensate_saga(...)` handles rollback for onboarding saga failures.
- Trigger point:
  - `app/orchestration/saga_orchestrator/orchestrator.py`
  - In `execute_patient_onboarding_saga(...)` exception path, orchestrator persists failed saga and then calls `await self.compensator.compensate_saga(failure_saga)`.
- Cancel path relation:
  - `cancel_patient_flow(...)` in `pause_resume.py` does not import or call saga orchestrator/compensator.
  - Cancel mutates runtime flow/message data only; it does not query or mutate `PatientOnboardingSaga` records.

### Informational finding: cancel does not trigger saga compensation

- Severity: INFO
- Statement:
  - Cancel and saga compensation are independent operations by design.
  - Saga compensation is for onboarding transaction failure.
  - Cancel is a post-onboarding runtime operation for active flow/message cleanup.

### Open-question resolution: `compensation_handlers.compensate_flow()` DB pattern

- File reviewed: `app/orchestration/saga_orchestrator/compensation_handlers.py`
- Answer:
  - `compensate_flow()` does **not** call `PatientFlowService.delete_flow()`.
  - It performs inline deletion:
    - `select(PatientFlowState).filter(PatientFlowState.patient_id == saga.patient_id)`
    - `await _db_delete(db, flow_state)` for each returned row
- DB mode behavior:
  - `_db_execute` and `_db_delete` support both sync-like and async sessions.
  - Compensation path is therefore insulated from the sync `self.db.query()` implementation in `PatientFlowService.delete_flow()`.

## Section 7: Additional Findings

### Finding C: Cancel input contract divergence from planned expectation

- Severity: LOW
- Observation:
  - Plan context expected optional cancel `reason`, but implementation currently accepts only `patient_id` and optional `user_id`.
- Impact:
  - Cancellation rationale is not captured in flow state by this method.

### Finding D: Cancel cleanup aligns with auto-resume safeguards

- Severity: INFO
- Observation:
  - Cancel clears `auto_resume_at`, flips `paused` to false, and sets status to `cancelled`.
- Impact:
  - Cancelled flows are naturally excluded from auto-resume query criteria (`status = 'paused'` + due `auto_resume_at`).
