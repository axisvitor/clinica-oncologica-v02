# Phase 30, Plan 01 - Onboarding Path Trace

## Scope

- Requirement focus: TRACE-01
- Traced paths:
  - Path A: API onboarding with saga (`POST /api/v2/patients/` -> `OnboardingCoordinator` -> `SagaOrchestrator` -> `SagaStepExecutor` -> `PatientFlowService` -> `FlowCore.enroll_patient()`)
  - Path B: Standalone dispatcher enrollment (`FlowDispatcher.initialize_flow()` -> `PatientFlowService` -> `FlowCore.enroll_patient()`)
- Method: code-level handoff verification with parameter and return contract checks

## Contract Reconciliation Note (TRACE-01)

- Path A and Path B are independent execution paths in the current implementation.
- `FlowDispatcher` does not invoke `SagaOrchestrator` in production onboarding runtime wiring.
- TRACE-01 is satisfied by complete traceability and explicit comparison of both paths, not by direct runtime coupling between them.

## Section 1: Path A (Saga) Handoff Trace

### Handoff 1: API router -> onboarding factory

| Attribute | Value |
|---|---|
| Caller | `app/api/v2/routers/patients/crud.py:create_patient()` (line ~589, call at ~760) |
| Callee | `app/services/patient/onboarding_factory.py:get_onboarding_coordinator(db: Any, saga_orchestrator: Optional[SagaOrchestrator] = None) -> OnboardingCoordinator` |
| Parameters | `db=AsyncSession` -> expected `Any` (OK); `saga_orchestrator=SagaOrchestrator` -> expected `Optional[SagaOrchestrator]` (OK) |
| Return | `OnboardingCoordinator` -> assigned to `coordinator` and used for create call |
| Session | Caller uses `AsyncSession`; factory accepts `db: Any` |
| Status | OK (typing is permissive) |

### Handoff 2: API router -> coordinator create

| Attribute | Value |
|---|---|
| Caller | `app/api/v2/routers/patients/crud.py:create_patient()` (call at ~857) |
| Callee | `app/domain/patient/onboarding/coordinator.py:OnboardingCoordinator.create_patient(patient_data: PatientCreate, doctor_id: UUID, current_user: Optional[User] = None, idempotency_key: Optional[str] = None) -> Patient` |
| Parameters | `patient_data=PatientCreate` (OK), `doctor_id=UUID` (OK), `current_user=auth payload` (accepted by `Optional[User]/Any` use), `idempotency_key=Optional[str]` (OK) |
| Return | `Patient` -> assigned to `created`, then serialized by router |
| Session | Coordinator internally holds `self.db` from factory wiring |
| Status | OK |

### Handoff 3: coordinator -> integrity validation

| Attribute | Value |
|---|---|
| Caller | `app/domain/patient/onboarding/coordinator.py:create_patient()` (call at ~153) |
| Callee | `app/services/patient/integrity_service.py:PatientIntegrityService.validate_patient_data(patient_data: PatientCreate | PatientUpdate, doctor_id: Optional[UUID] = None, patient_id: Optional[UUID] = None, is_update: bool = False) -> Dict[str, Any]` |
| Parameters | `patient_data=PatientCreate` (OK), `doctor_id=UUID` (OK), `is_update=False` (OK) |
| Return | `Dict[str, Any]` of normalized data, but caller uses method for validation side effects only |
| Session | Integrity service is built with same `db` object from factory (`db: Any`) |
| Status | FINDING: return payload is ignored (validation-only usage) and `db` type is opaque |

### Handoff 4: coordinator -> saga orchestrator

| Attribute | Value |
|---|---|
| Caller | `app/domain/patient/onboarding/coordinator.py:create_patient()` (call at ~171) |
| Callee | `app/orchestration/saga_orchestrator/orchestrator.py:SagaOrchestrator.execute_patient_onboarding_saga(patient_data: PatientCreate, doctor_id: Optional[UUID] = None, current_user: Any = None, idempotency_key: Optional[str] = None) -> Optional[Patient]` |
| Parameters | `patient_data=PatientCreate` (OK), `doctor_id=UUID` (compatible with `Optional[UUID]`), `current_user` (OK for `Any`), `idempotency_key=Optional[str]` (OK) |
| Return | `Optional[Patient]` -> caller enforces non-null and raises validation error on `None` |
| Session | SagaOrchestrator constructed with API `AsyncSession`, typed as `Any` |
| Status | OK (runtime guarded by `if not patient`) |

### Handoff 5: orchestrator -> step 1 create patient

| Attribute | Value |
|---|---|
| Caller | `app/orchestration/saga_orchestrator/orchestrator.py:execute_patient_onboarding_saga()` (call at ~149) |
| Callee | `app/orchestration/saga_orchestrator/steps.py:SagaStepExecutor.step_create_patient(saga: PatientOnboardingSaga, patient_data: PatientCreate, doctor_id: Optional[UUID] = None, idempotency_key: Optional[str] = None) -> Patient` |
| Parameters | `saga=PatientOnboardingSaga` (OK), `patient_data=PatientCreate` (OK), `doctor_id=Optional[UUID]` (OK), `idempotency_key=Optional[str]` (OK) |
| Return | `Patient` -> assigned to local `patient`; orchestrator aborts on falsy result |
| Session | Step executor stores `db: Any` from orchestrator |
| Status | OK |

### Handoff 6: orchestrator -> step 2 initialize flow

| Attribute | Value |
|---|---|
| Caller | `app/orchestration/saga_orchestrator/orchestrator.py:execute_patient_onboarding_saga()` (call at ~160) |
| Callee | `app/orchestration/saga_orchestrator/steps.py:SagaStepExecutor.step_initialize_flow(saga: PatientOnboardingSaga, patient: Patient, current_user: Any, idempotency_key: Optional[str] = None) -> None` |
| Parameters | `saga=PatientOnboardingSaga` (OK), `patient=Patient` (OK), `current_user=Any` (OK), `idempotency_key=Optional[str]` (OK) |
| Return | `None` -> caller uses completion/failure semantics only |
| Session | Step executor still uses orchestrator `db: Any` |
| Status | OK |

### Handoff 7: step 2 -> PatientFlowService.initialize_default_flow

| Attribute | Value |
|---|---|
| Caller | `app/orchestration/saga_orchestrator/steps.py:step_initialize_flow()` (call at ~354) |
| Callee | `app/services/patient/flow_service.py:PatientFlowService.initialize_default_flow(patient: Patient, current_user_id: Optional[UUID] = None, auto_commit: bool = True) -> Optional[PatientFlowState]` |
| Parameters | `patient=Patient` (OK), `current_user_id=Optional[UUID]` (OK), `auto_commit=False` (explicit saga/UoW mode, OK) |
| Return | `Optional[PatientFlowState]` -> caller branches on `None` to log skip reasons |
| Session | Service initialized with saga `db` object (`Any`, runtime is API `AsyncSession`) |
| Status | FINDING: method uses `self.db.commit()`/`self.db.flush()` without `await` in an async function |

### Handoff 8: PatientFlowService -> FlowCore enrollment

| Attribute | Value |
|---|---|
| Caller | `app/services/patient/flow_service.py:initialize_default_flow()` (call at ~104) |
| Callee | `app/services/flow/core/operations.py:FlowCoreOperationsMixin.enroll_patient(patient_id: UUID, flow_type: FlowType = FlowType.ONBOARDING, auto_commit: bool = True) -> PatientFlowState` |
| Parameters | `patient_id=patient.id (UUID)` (OK), `flow_type=FlowType` (OK), `auto_commit=False` on saga path (OK) |
| Return | `PatientFlowState` -> used to populate patient metadata and propagated back |
| Session | `FlowCoreOperationsMixin` expects async-style `db.execute/commit/flush/refresh`; runtime alignment depends on `db` object passed into engine |
| Status | OK |

### Handoff 9: step 2 -> PatientFlowService.activate_patient

| Attribute | Value |
|---|---|
| Caller | `app/orchestration/saga_orchestrator/steps.py:step_initialize_flow()` (call at ~385) |
| Callee | `app/services/patient/flow_service.py:PatientFlowService.activate_patient(patient_id: UUID, auto_commit: bool = True) -> Optional[Patient]` |
| Parameters | `patient_id=UUID` (OK), `auto_commit=False` (OK) |
| Return | `Optional[Patient]` -> return value ignored by caller |
| Session | Callee delegates to sync `PatientRepository(self.db).get_by_id(...)`/`update(...)` |
| Status | FINDING: async path depends on sync repository API (`self.db.query(...)`), while saga is invoked from API `AsyncSession` path |

### Handoff 10: orchestrator -> step 3 welcome message

| Attribute | Value |
|---|---|
| Caller | `app/orchestration/saga_orchestrator/orchestrator.py:execute_patient_onboarding_saga()` (call at ~169) |
| Callee | `app/orchestration/saga_orchestrator/steps.py:SagaStepExecutor.step_send_welcome_message(saga: PatientOnboardingSaga, patient: Patient, idempotency_key: Optional[str] = None) -> None` |
| Parameters | `saga=PatientOnboardingSaga` (OK), `patient=Patient` (OK), `idempotency_key=Optional[str]` (OK) |
| Return | `None` -> caller treats this step as best-effort (non-fatal failure path) |
| Session | Uses same saga `db` object; idempotency check uses async select helper |
| Status | OK |

### Handoff 11: step 3 -> MessageService.schedule_message

| Attribute | Value |
|---|---|
| Caller | `app/orchestration/saga_orchestrator/steps.py:step_send_welcome_message()` (call at ~521) |
| Callee | `app/domain/messaging/core/message_service/service.py:MessageService.schedule_message(patient_id: UUID, content: str, scheduled_for: datetime, message_type: MessageType = MessageType.TEXT, message_metadata: Optional[Dict[str, Any]] = None, auto_commit: bool = True) -> Message` |
| Parameters | `patient_id=UUID` (OK), `content=str` (OK), `scheduled_for=datetime` (OK), `message_type=MessageType.TEXT` (OK), `message_metadata=dict` (OK), `auto_commit=False` (OK) |
| Return | `Message` -> assigned to `message` and logged |
| Session | Sync `schedule_message` is called from async step; no `await` required because callee is synchronous |
| Status | OK |

## Section 2: Path B (FlowDispatcher) Handoff Trace

### Handoff 12: caller -> FlowDispatcher.initialize_flow

| Attribute | Value |
|---|---|
| Caller | External caller of `FlowDispatcher` facade (`app/services/dispatcher.py` usage contract at lines ~48-50) |
| Callee | `app/services/dispatcher.py:FlowDispatcher.initialize_flow(patient: Patient, current_user_id: Optional[UUID] = None, auto_commit: bool = True) -> Optional[PatientFlowState]` |
| Parameters | `patient=Patient` (required), `current_user_id=Optional[UUID]` (optional), `auto_commit=True` default |
| Return | `Optional[PatientFlowState]` |
| Session | `FlowDispatcher` accepts `Session | AsyncSession` at construction |
| Status | OK |

### Handoff 13: FlowDispatcher -> PatientFlowService.initialize_default_flow

| Attribute | Value |
|---|---|
| Caller | `app/services/dispatcher.py:initialize_flow()` (call at ~104) |
| Callee | `app/services/patient/flow_service.py:PatientFlowService.initialize_default_flow(...) -> Optional[PatientFlowState]` |
| Parameters | `patient=Patient` (OK), `current_user_id=Optional[UUID]` (OK), `auto_commit` forwarded as-is (default `True`) |
| Return | `Optional[PatientFlowState]` -> returned directly by dispatcher |
| Session | Delegates same DB handle passed to dispatcher |
| Status | OK |

### Handoff 14: PatientFlowService -> engine enrollment

| Attribute | Value |
|---|---|
| Caller | `app/services/patient/flow_service.py:initialize_default_flow()` |
| Callee | `FlowCoreOperationsMixin.enroll_patient(patient_id: UUID, flow_type: FlowType = FlowType.ONBOARDING, auto_commit: bool = True) -> PatientFlowState` |
| Parameters | `patient_id=UUID` (OK), `flow_type=FlowType` (OK), `auto_commit=True` on dispatcher default path |
| Return | `PatientFlowState` |
| Session | Commit boundary is inside `enroll_patient()` when `auto_commit=True` |
| Status | OK |

### Handoff 15: FlowCore enrollment -> persistence side effects

| Attribute | Value |
|---|---|
| Caller | `app/services/flow/core/operations.py:enroll_patient()` |
| Callee | SQLAlchemy persistence (`self.db.add(flow_state)` + `await self.db.commit()` or `await self.db.flush()`) |
| Parameters | New `PatientFlowState` with template version, day/step metadata |
| Return | `PatientFlowState` refreshed from DB |
| Session | Async DB contract assumed (`await self.db.execute/commit/flush/refresh`) |
| Status | OK |

### FlowDispatcher usage audit (Task 2)

Search scope requested by plan: `backend-hormonia/app/**/*.py`.

| Location | Observed usage | Classification | Reachability |
|---|---|---|---|
| `app/services/dispatcher.py` | `FlowDispatcher` class definition and internal logging strings | Production source definition | Reachable only if instantiated by another module |
| `app/dependencies/service_dependencies.py` | `get_flow_service()` returns `services.flow_service` (dispatcher from provider) | Production DI wiring | Potentially reachable, but no endpoint import/use found |
| `app/service_provider.py` | Lazy property constructs `FlowDispatcher(self.db)` | Production service container wiring | Potentially reachable, but no consuming call sites found |
| `app/services/flow/__init__.py` | Docstring examples for `FlowDispatcher` and `initialize_flow()` | Documentation/example text | Not executable runtime path |

Additional checks:

- `\.initialize_flow\(` search in `backend-hormonia/app` only matched `dispatcher.py` and `services/flow/__init__.py` examples.
- `Depends(get_flow_service)` search in `backend-hormonia/app` returned no matches.
- Full repository search (`backend-hormonia/**/*.py`) found concrete runtime invocations only in tests:
  - `tests/integration/test_flow_consolidation.py`
  - `tests/unit/services/test_communication_services_async.py`

Verdict:

- In current app-layer production code, no active entrypoint calls `FlowDispatcher.initialize_flow()` directly.
- `FlowDispatcher` appears to be retained for compatibility/DI surface and test coverage, with no confirmed production invocation path.

### EnhancedFlowEngine inheritance chain verification

From `app/services/enhanced_flow_engine_pkg/service.py`:

```text
EnhancedFlowEngine
  -> FlowOrchestrationMixin
  -> FlowResponseMixin
  -> FlowConversationMixin
  -> FlowCore
```

From `app/services/flow/core/service.py`:

```text
FlowCore
  -> FlowCoreTransitionsMixin
  -> FlowCoreTemplateBindingMixin
  -> FlowCoreOperationsMixin
```

Enrollment method ownership:

- `enroll_patient()` is implemented in `FlowCoreOperationsMixin` (`app/services/flow/core/operations.py`).
- `EnhancedFlowEngine` inherits this method through `FlowCore` and is therefore the concrete callee used by `PatientFlowService.initialize_default_flow()`.

## Section 3: Findings Summary

1. `db: Any`/mixed session typing across saga and flow services obscures whether each handoff is sync `Session` or `AsyncSession`.
2. `PatientFlowService.initialize_default_flow()` is async but calls `self.db.commit()`/`self.db.flush()` without `await`.
3. `PatientFlowService.activate_patient()` (async) delegates to sync `PatientRepository` methods that rely on `self.db.query(...)`.
4. `OnboardingCoordinator.__init__` types `db: Session` while API path injects `AsyncSession`.
5. `FlowDispatcher` has no confirmed production caller in `backend-hormonia/app`; usages are DI wiring, class/docs references, and tests.

## Section 4: Path Comparison (A vs B)

| Dimension | Path A (Saga onboarding) | Path B (FlowDispatcher standalone) |
|---|---|---|
| Entry point | `POST /api/v2/patients/` router | `FlowDispatcher.initialize_flow()` facade |
| Coordination layer | `OnboardingCoordinator` + `SagaOrchestrator` + `SagaStepExecutor` | `FlowDispatcher` + `PatientFlowService` |
| Transaction style | Multi-step saga with deferred commit/compensation behavior | Single enrollment call, default `auto_commit=True` |
| Side effects in scope | Create patient, initialize flow, schedule welcome message | Initialize flow only |
| Failure model | Saga state tracking and compensation attempt | Direct exception surface from service/engine |
| Session contract | Heavily mixed (`AsyncSession` at API, several `db: Any` hops) | Depends on dispatcher caller; API call sites not yet confirmed here |
