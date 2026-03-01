# TRACE-04: FlowCoordinatorAgent Decision Engine Trace

## 1. Entry Point: How the agent is triggered

### Celery Beat schedule
- `app/celery_app.py` schedules `send-daily-flow-questions` to task `app.tasks.flows.flow_tasks.process_daily_flows` at `08:00` Sao Paulo time.
- `process_daily_flows` (`app/tasks/flows/flow_tasks.py`) delegates to `process_daily_flows_async(limit=1000)`.

### Daily flow task execution path
1. `process_daily_flows_async()` loads active flows from `FlowStateRepository.get_active_flows(...)`.
2. It filters paused flows using `flow.state_data.get("paused")`.
3. It processes each patient via `_process_single_patient_flow_by_id(patient_id)` in `app/tasks/flows/batch_tasks.py`.
4. `_process_single_patient_flow_by_id` creates an isolated sync `Session` (`get_scoped_session`) and executes flow processing.
5. Message dispatch is done through `flow_engine` + scheduled messages pipeline, not through `FlowCoordinatorAgent`.

### Is `FlowCoordinatorAgent` invoked from this Celery task?
- No direct invocation found in `app/celery_app.py` or `app/tasks/flows/flow_tasks.py`.
- `FlowCoordinatorAgent` path exists as an agent-framework execution path (`process_task -> _process_daily_flow`), but it is not wired as a dedicated Celery beat task in current app-level schedule.

## 2. Execution Path: `FlowCoordinatorAgent._process_daily_flow()`

Method signature (effective):
- `FlowCoordinatorAgent._process_daily_flow(self, payload: Dict[str, Any]) -> Dict[str, Any>`
- Extracted payload inputs:
  - `patient_id = UUID(payload["patient_id"])`
  - `current_day = int(payload["current_day"])`

### Full call chain with handoffs

| Step | Caller | Callee | Inputs | Output |
|---|---|---|---|---|
| 1 | `FlowCoordinatorAgent._process_daily_flow` | `StateManager.build_flow_context` | `patient_id: UUID`, `current_day: int` | `FlowContext` |
| 2 | `FlowCoordinatorAgent._process_daily_flow` | `DecisionEngine.analyze_flow_situation` | `context: FlowContext` | `analysis: Dict[str, Any]` |
| 3 | `FlowCoordinatorAgent._process_daily_flow` | `DecisionEngine.make_flow_decision` | `context: FlowContext`, `analysis: Dict[str, Any]` | `decision: FlowDecision` |
| 4 | `FlowCoordinatorAgent._process_daily_flow` | `_execute_flow_decision` | `decision: FlowDecision`, `context: FlowContext` | `execution_result: Dict[str, Any]` |

### Decision dispatch mapping (`_execute_flow_decision`)
- `FlowDecision.CONTINUE_CURRENT` -> `_process_normal_flow(context)` -> `SequentialMessageHandler.send_day_messages(...)`
- `FlowDecision.ADVANCE_PHASE` -> `TransitionHandler.transition_flow_phase(context)`
- `FlowDecision.ADJUST_TIMING` -> `TransitionHandler.optimize_timing(context)`
- `FlowDecision.PERSONALIZE_CONTENT` -> `TransitionHandler.personalize_content(context)`
- `FlowDecision.ESCALATE_INTERVENTION` -> `_send_escalation_alert(context)`
- `FlowDecision.PAUSE_FLOW` -> `TransitionHandler.pause_flow(context)`
- `FlowDecision.RESUME_FLOW` -> `TransitionHandler.resume_flow(context)`

### Decision criteria (rule-based, deterministic)
`DecisionEngine.make_flow_decision` is deterministic and rule-based (no LLM in this module):
- High risk -> `ESCALATE_INTERVENTION`
- Low engagement -> `PERSONALIZE_CONTENT`
- Day transition boundary (`current_day == DAILY_FOLLOWUP_END_DAY`) -> `ADVANCE_PHASE`
- High progress + moderate engagement -> `ADJUST_TIMING`
- Moderate progress -> `PERSONALIZE_CONTENT`
- Otherwise -> `CONTINUE_CURRENT`

## 3. Data Shapes: `FlowContext` and `FlowDecision`

### `FlowContext` (`app/agents/patient/flow_coordinator/models.py`)
Fields populated by `StateManager.build_flow_context`:
- `patient_id: Optional[UUID]`
- `current_day: Optional[int]`
- `flow_state: Optional[PatientFlowState]`
- `patient_data: Optional[Patient]`
- `recent_interactions: List[Dict]`
- `mood_indicators: Dict[str, Any]`
- `adherence_metrics: Dict[str, float]`
- `risk_factors: List[str]`
- `knowledge_context: Dict[str, Any]`

### `FlowDecision` enum values
- `continue_current`
- `advance_phase`
- `adjust_timing`
- `personalize_content`
- `escalate_intervention`
- `pause_flow`
- `resume_flow`

### StateManager DB reads used to build `FlowContext`
- `PatientRepository.get(patient_id)` -> `context.patient_data`
- `FlowStateRepository.get_by_patient_id(patient_id)` -> first result into `context.flow_state`
- Recent messages query on `Message` table -> `context.recent_interactions`
- Quiz adherence query on `QuizSession` -> `quiz_completion_rate`
- Distinct message-active-days query (`func.count(distinct(date(...)))`) -> `scheduled_engagement_rate`
- Optional `KnowledgeGraph.get_patient_context(patient_id)` -> `context.knowledge_context`

## 4. Saga-Agent Relationship (indirect via `PatientFlowState`)

- The saga writes flow state during onboarding:
  - `SagaStepExecutor.step_initialize_flow(...)` in `app/orchestration/saga_orchestrator/steps.py`
  - Calls `PatientFlowService.initialize_default_flow(...)`
  - Which calls `flow_engine.enroll_patient(...)` to create `PatientFlowState`
- The agent reads and updates that state later:
  - `StateManager.build_flow_context(...)` reads `PatientFlowState`
  - `TransitionHandler` updates state according to `FlowDecision`

Key relationship:

`SagaOrchestrator (onboarding write)` -> `PatientFlowState (DB)` <- `FlowCoordinatorAgent (daily read/write)`

There is no direct `FlowCoordinatorAgent -> SagaOrchestrator` call in this path.

### Field-by-field data integrity (`PatientFlowState`)

`PatientFlowState` is created in `FlowCoreOperationsMixin.enroll_patient` (called by saga step `step_initialize_flow`).

| PatientFlowState field (model) | Set by saga/onboarding path | Read by agent path | Status |
|---|---|---|---|
| `patient_id` | Yes (`enroll_patient(patient_id=...)`) | Yes (`FlowStateRepository.get_by_patient_id(patient_id)` filter) | OK |
| `flow_template_version_id` | Yes (`active_version.id`) | Indirectly via `flow_state` object carried in `FlowContext` | OK |
| `current_step` | Yes (`current_step=1`) | Yes via alias `flow_state.current_day` / `context.current_day` use | OK |
| `status` | Implicit default lifecycle state at creation (`active` path assumptions in repo/tasks) | Yes, indirectly in task-level filtering and state transitions | OK |
| `step_data` (`state_data` alias) | Yes (`enrollment_date`, `ai_enabled`, `personalization_level`) | Yes (`state_data` in transition and pause logic) | OK |
| `flow_metadata` | Optional; later can include saga idempotency key in step 2 | Not required for current decision logic | OK |
| `started_at` | Yes (`start_dt`) | Indirectly through flow lifecycle computations | OK |
| `completed_at` | Not set at creation | Used later by lifecycle transitions (not required by agent decision engine input) | OK |
| `next_scheduled_at` | Not set at creation | Used by flow automation scheduling, not by `DecisionEngine` directly | OK |
| `last_interaction_at` | Not set at creation | Used downstream by automation, not required by `DecisionEngine` directly | OK |

Integrity conclusion:
- Every field required by `StateManager.build_flow_context` and subsequent `DecisionEngine`/`TransitionHandler` paths is present from onboarding initialization plus normal runtime updates.
- No hard mismatch found where agent requires a field that the onboarding saga path fails to initialize.

### Session type analysis

- Saga side (`SagaStepExecutor` + onboarding path) runs with `AsyncSession` in API request context (`steps.py` imports `AsyncSession` and async `select` execution paths).
- Agent side (`FlowCoordinatorAgent`, `StateManager`, `TransitionHandler`) is typed and constructed with sync `Session` in worker/agent context.
- The relationship is time-separated:
  1. Saga initializes patient + flow during onboarding transaction.
  2. Agent reads/updates `PatientFlowState` later during daily processing.
- No direct concurrent saga/agent access is implied by this chain; they are decoupled by persisted DB state.

### Agent registration / invocation finding

- Search in `app/celery_app.py` for `FlowCoordinatorAgent|flow_coordinator`: no matches.
- Search in `app/tasks/**/*.py`: only `app/tasks/flows/batch_tasks.py` imports flow coordinator constants (`MONTHLY_CYCLE_*`), not the `FlowCoordinatorAgent` class.
- Conclusion: current beat/task wiring does not directly instantiate `FlowCoordinatorAgent`; its execution path is an available agent-framework path, while scheduled daily processing uses flow task + batch handlers.

## 5. Findings

1. **Session type concern confirmed**
   - `FlowCoordinatorAgent` is constructed with sync `sqlalchemy.orm.Session`.
   - `_process_normal_flow` uses `SequentialMessageHandler(self.db_session)` and includes an inline note that this path should migrate to `AsyncSession` in follow-up.
   - This is a known mixed-session concern for agent path execution.

2. **Pause key divergence cross-reference**
   - `TransitionHandler.pause_flow` sets `state_data["flow_paused"]`.
   - `process_daily_flows_async` filters using `state_data.get("paused")`.
   - This divergence is consistent with prior trace findings in `backend-hormonia/docs/traces/30-02-pause-resume-cancel-trace.md`.

3. **Agent invocation mechanism clarified**
   - Celery beat path is `process_daily_flows` -> batch flow processor.
   - No beat schedule entry directly targets `FlowCoordinatorAgent` class methods.
   - Agent path appears to be available through agent messaging/task orchestration rather than current beat wiring.

4. **Data flow from payload to action is unbroken**
   - `patient_id/current_day` payload -> `FlowContext` -> `analysis` -> `FlowDecision` -> `TransitionHandler`/`SequentialMessageHandler` execution.
   - Caller/callee boundaries and returned structures are explicit and consistent.
