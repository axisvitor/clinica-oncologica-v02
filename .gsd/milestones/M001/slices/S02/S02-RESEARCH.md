# Phase 51: Flow Recovery - Research

**Researched:** 2026-03-06
**Domain:** Celery periodic tasks, flow state machine, admin API endpoints, DLQ integration
**Confidence:** HIGH

## Summary

Phase 51 implements flow recovery for the WhatsApp patient flow pipeline. The Phase 50 work (now complete) hardened the pipeline against silent failures by adding mismatch recovery, send retries, follow-up retries, and config validation. Phase 51 builds on that foundation to detect flows that are *already* stuck (awaiting_response for too long) and either auto-recover them or give administrators manual tools.

The codebase already has substantial infrastructure that Phase 51 can leverage: (a) `FlowStateRepository.get_active_flows()` queries non-completed, non-deleted flows with fair ordering; (b) the `flags.is_awaiting_response()` helper normalizes truthy booleans from step_data; (c) `FlowManagementService.advance_patient_flow()` handles day advancement with optimistic locking; (d) the DLQ admin extensions at `/admin-ext/dlq/` provide a proven pattern for listing/retrying/discarding failed items; (e) the Celery Beat schedule in `celery_app.py` already has 38+ entries and the pattern for adding new periodic tasks is well-established.

The key implementation decisions center on: (1) how to identify stuck flows efficiently via a single SQL query rather than loading all active flows into memory; (2) how the auto-recovery logic decides between re-sending the last prompt vs. advancing the day; (3) where to surface failed flow operations -- reusing the existing DLQ table (which maps to `whatsapp_delivery_failures`) vs. creating a dedicated failed-flows query over `PatientFlowState.step_data`. The research below provides prescriptive guidance for each.

**Primary recommendation:** Add one new Celery Beat task (`detect_stuck_flows`) running every 15 minutes, one new service module (`app/services/flow/recovery.py`) containing both detection and auto-recovery logic, one new admin API router (`app/api/v2/routers/admin_extensions/flow_ops.py`) for manual flow control, and a failed-flow-operations query endpoint reading from `PatientFlowState.step_data` markers already placed by Phase 50.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RECV-01 | Stuck flow detector runs as periodic Celery Beat task, identifying flows with awaiting_response > configurable hours | Beat schedule pattern established; `PatientFlowState.step_data` contains `awaiting_response` and `last_interaction_at`; detection query uses SQL-level JSONB filtering |
| RECV-02 | Stuck flow auto-recovery attempts re-send of last prompt or day advance based on flow state analysis | Phase 50 created `retry_failed_flow_send` task and `advance_day_atomic()` helper; recovery service composes these |
| RECV-03 | Admin can manually reset, advance, or unstick a patient flow via dedicated API endpoint | `FlowManagementService.advance_patient_flow()` exists; admin auth pattern from `admin_extensions/` reusable |
| RECV-04 | Failed flow operations visible in admin via DLQ or dedicated failed-flows query | Phase 50 writes `delivery_failures`, `permanently_failed_at`, and `context_mismatch_count` into `step_data`; query endpoint aggregates these markers |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Celery | 5.x (existing) | Periodic stuck-flow detection task | Already sole task/scheduler provider; Beat schedule in celery_app.py |
| SQLAlchemy | 2.x (existing) | JSONB queries on PatientFlowState.step_data | Already used throughout; supports JSONB operators for efficient filtering |
| FastAPI | 0.100+ (existing) | Admin flow control API endpoints | Already the API framework; async session pattern established |
| Pydantic | 2.x (existing) | Request/response schemas for admin endpoints | Already used for all v2 schemas |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asgiref | existing | async_to_sync bridge in Celery tasks | Already used by send_retry and followup_retry tasks |
| redis-py | existing | Idempotency keys for recovery operations | Via `app.core.redis_manager.get_redis_manager()` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| JSONB step_data query | Dedicated stalled_flows table | Extra migration, extra write on every flow state change; step_data already has the markers from Phase 50 |
| Reuse DLQ table for flow failures | New flow_failures table | DLQ is message-centric (whatsapp_delivery_failures); flow-level failures are richer; query over step_data avoids new migration |

**Installation:**
No new packages required. All dependencies are already in the project.

## Architecture Patterns

### Recommended Project Structure
```
backend-hormonia/app/
  services/flow/
    recovery.py               # NEW: StuckFlowDetector + FlowAutoRecovery service
  tasks/flows/
    stuck_detection.py         # NEW: Celery Beat task wrapping the detection service
  api/v2/routers/
    admin_extensions/
      flow_ops.py              # NEW: Admin flow control endpoints
  schemas/v2/
    admin_extensions.py        # MODIFY: Add FlowOps schemas
  config/settings/
    tasks.py                   # MODIFY: Add STUCK_FLOW_* settings
```

### Pattern 1: Stuck Flow Detection via JSONB Query
**What:** A periodic Celery task queries `patient_flow_states` for rows where `step_data->>'awaiting_response'` is truthy AND `last_interaction_at` is older than the configurable threshold, directly in SQL.
**When to use:** Every 15 minutes via Beat schedule.
**Example:**
```python
# Source: Existing codebase pattern from FlowStateRepository + Phase 50 flags
from sqlalchemy import text, and_, or_
from app.models.flow import PatientFlowState
from app.models.patient import Patient

STUCK_FLOW_THRESHOLD_HOURS = int(os.getenv("TASK_STUCK_FLOW_THRESHOLD_HOURS", "4"))

def find_stuck_flows(db, threshold_hours: int = STUCK_FLOW_THRESHOLD_HOURS) -> list:
    cutoff = now_sao_paulo() - timedelta(hours=threshold_hours)
    return (
        db.query(PatientFlowState)
        .join(Patient)
        .filter(
            PatientFlowState.completed_at.is_(None),
            Patient.deleted_at.is_(None),
            # JSONB truthy check for awaiting_response
            PatientFlowState.step_data["awaiting_response"].astext.in_(
                ["true", "True", "1", "yes"]
            ),
            # Stuck longer than threshold
            or_(
                PatientFlowState.last_interaction_at < cutoff,
                PatientFlowState.last_interaction_at.is_(None),
            ),
        )
        .order_by(PatientFlowState.last_interaction_at.asc().nullsfirst())
        .limit(100)  # Safety cap per cycle
        .all()
    )
```

### Pattern 2: Auto-Recovery Decision Logic
**What:** For each stuck flow, analyze `step_data` to decide recovery action: re-send last prompt (if `day_complete` is False) or advance day (if `day_complete` is True but `day_advance_verified` is False).
**When to use:** Called by the detector for each identified stuck flow.
**Example:**
```python
# Source: Phase 50 step_data structure from 50-01/50-03 summaries
def determine_recovery_action(step_data: dict) -> str:
    if step_data.get("day_complete"):
        if not step_data.get("day_advance_verified"):
            return "advance_day"
        return "resend_prompt"  # day complete + verified but still waiting = stuck
    return "resend_prompt"  # not day_complete = waiting for response = re-send
```

### Pattern 3: Admin Flow Control API (follows admin_extensions pattern)
**What:** Dedicated router under `/admin-ext/flow-ops/` with endpoints: POST `/{patient_id}/reset`, POST `/{patient_id}/advance`, POST `/{patient_id}/unstick`. Uses same auth, rate-limiting, caching, and audit patterns as the DLQ admin router.
**When to use:** When auto-recovery fails or operator needs manual intervention.
**Example:**
```python
# Source: admin_extensions/dlq.py pattern
@router.post("/{patient_id}/unstick")
@limiter.limit("30/minute")
async def unstick_patient_flow(
    request: Request,
    patient_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    # Clear awaiting_response, reset mismatch counters
    # Log action via AuditService
    ...
```

### Pattern 4: Failed Flow Operations Query (no new table)
**What:** Query `PatientFlowState` rows that have `delivery_failures`, `permanently_failed_at`, or `last_mismatch_reset_at` markers in step_data. These markers were placed by Phase 50.
**When to use:** Admin wants to see which flows have experienced failures.
**Example:**
```python
# Source: Phase 50 send_retry.py + sequential_response_gate.py
def find_failed_flow_operations(db, limit=50):
    return (
        db.query(PatientFlowState)
        .join(Patient)
        .filter(
            Patient.deleted_at.is_(None),
            or_(
                PatientFlowState.step_data.has_key("delivery_failures"),
                PatientFlowState.step_data.has_key("last_mismatch_reset_at"),
            ),
        )
        .order_by(PatientFlowState.updated_at.desc())
        .limit(limit)
        .all()
    )
```

### Anti-Patterns to Avoid
- **Loading all active flows into Python to filter stuck ones:** Use SQL-level JSONB filtering instead. The repository already queries up to 5000 rows for daily processing; the stuck detector must be more surgical.
- **Modifying PatientFlowState without optimistic locking:** Phase 50 established the `version` column pattern. All writes to step_data in recovery must check the version.
- **Creating a new DB migration for a stalled_flows table:** The step_data JSONB already contains all markers. A dedicated table would require writes on every flow state change and a new migration.
- **Using `redis.keys()` anywhere:** Project rule -- always use `scan_iter(match=..., count=100)`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Day advancement with locking | Custom step_data writes | `advance_day_atomic()` from `management/advancement.py` | Phase 50 already handles optimistic locking, version bumps, verification markers |
| Message re-send | Custom WhatsApp call | `retry_failed_flow_send` Celery task from `tasks/flows/send_retry.py` | Handles idempotency, backoff, permanent failure bookkeeping |
| Admin auth + rate-limiting | Custom auth check | `get_admin_user` + `@limiter.limit()` from `admin_extensions/dependencies.py` | Proven pattern used by DLQ, audit endpoints |
| Audit logging | Custom DB writes | `AuditService` + `log_admin_extension_action()` from admin_extensions | HIPAA/LGPD compliance already handled |
| Bool flag checking | Custom truthy parsing | `is_awaiting_response()` from `services/flow/flags.py` | Handles string coercion edge cases |
| Async-to-sync bridge in Celery | Custom event loop | `asgiref.sync.async_to_sync` or `app.utils.async_helpers.run_async_in_sync` | Already established by existing Celery tasks |

**Key insight:** Phase 50 laid the groundwork by placing structured markers (delivery_failures, mismatch counters, day_advance_verified) into step_data. Phase 51 reads and acts on these markers rather than building new tracking infrastructure.

## Common Pitfalls

### Pitfall 1: JSONB Boolean Comparison in SQLAlchemy
**What goes wrong:** `step_data->>'awaiting_response'` returns a string, not a Python bool. Filtering with `== True` produces no results.
**Why it happens:** PostgreSQL JSONB text extraction always returns strings.
**How to avoid:** Use `.astext.in_(["true", "True", "1", "yes"])` or cast with `cast(... , Boolean)`. The `flags.is_awaiting_response()` helper handles this in Python, but SQL queries need explicit string matching.
**Warning signs:** Detector reports 0 stuck flows when you know some exist.

### Pitfall 2: Race Condition Between Detector and Incoming Response
**What goes wrong:** The detector flags a flow as stuck and initiates recovery at the exact moment the patient responds. Both the recovery and the response handler modify step_data.
**Why it happens:** Two concurrent writers on the same PatientFlowState row.
**How to avoid:** (1) Use optimistic locking via the `version` column; (2) In the recovery task, re-check `awaiting_response` immediately before acting; (3) Use Redis idempotency key `recovery:{flow_state_id}` with short TTL to prevent double-recovery.
**Warning signs:** Patient receives duplicate messages or flow state corruption.

### Pitfall 3: Celery Task Using Detached SQLAlchemy Objects
**What goes wrong:** If the detector loads PatientFlowState objects and passes them to recovery tasks, the objects become detached from the session.
**Why it happens:** Celery tasks run in separate processes; SQLAlchemy objects are session-bound.
**How to avoid:** Pass only `flow_state_id` (UUID) to the recovery task. The task opens its own `get_scoped_session()` and re-queries. This is the pattern used by `send_retry.py` and `followup_retry.py`.
**Warning signs:** `DetachedInstanceError` in Celery worker logs.

### Pitfall 4: Admin Endpoint Using Sync Session
**What goes wrong:** Admin endpoint calls `FlowManagementService` which uses sync `Session`, but the router provides `AsyncSession`.
**Why it happens:** `FlowManagementService.__init__` takes a `FlowStateRepository(db)` where `db` is `Session`. Admin routers use `get_async_db`.
**How to avoid:** Use `db.run_sync(lambda sync_db: ...)` to bridge, or write async-native queries for the admin endpoints (as done in the DLQ admin router).
**Warning signs:** `greenlet_spawn` errors or `MissingGreenlet` exceptions.

### Pitfall 5: Recovery Triggering Infinite Loop
**What goes wrong:** Auto-recovery re-sends a prompt, which sets `awaiting_response = True`. Next detector cycle finds it stuck again (if patient doesn't respond within threshold) and re-sends again.
**Why it happens:** No limit on recovery attempts per flow.
**How to avoid:** Track `recovery_attempts` in step_data. After N attempts (e.g., 3), stop auto-recovery and flag the flow for manual intervention. Also set `last_recovery_at` timestamp and skip flows recovered within the current threshold window.
**Warning signs:** Patient receives the same question repeatedly; step_data shows growing recovery_attempts.

## Code Examples

Verified patterns from the existing codebase:

### Celery Beat Task Registration
```python
# Source: celery_app.py lines 81-292
celery_app.conf.beat_schedule["detect-stuck-flows"] = {
    "task": "app.tasks.flows.stuck_detection.detect_stuck_flows",
    "schedule": 900.0,  # Every 15 minutes
}
```

### Celery Task with Scoped Session (sync)
```python
# Source: tasks/flows/send_retry.py
@celery_app.task(
    bind=True,
    base=FlowTaskBase,
    name="app.tasks.flows.stuck_detection.detect_stuck_flows",
    max_retries=1,
    acks_late=True,
    reject_on_worker_lost=True,
)
def detect_stuck_flows(self) -> dict[str, Any]:
    with get_scoped_session() as db:
        # Query stuck flows
        # Attempt recovery for each
        # Return summary
        ...
```

### Admin Extension Endpoint Pattern
```python
# Source: admin_extensions/dlq.py
from .dependencies import get_admin_user, log_admin_extension_action
from .utils import ...  # serialize helpers

router = APIRouter()

@router.post("/{patient_id}/unstick", ...)
@limiter.limit("30/minute")
async def unstick_flow(
    request: Request,
    patient_id: UUID,
    db: AsyncSession = Depends(get_async_db),
    admin_user: User = Depends(get_admin_user),
    context: RequestContext = Depends(get_request_context),
):
    # 1. Find active flow
    # 2. Clear awaiting_response, reset counters
    # 3. Commit with version bump
    # 4. Audit log
    # 5. Invalidate cache
    ...
```

### Optimistic Lock Write Pattern
```python
# Source: management/advancement.py advance_day_atomic()
expected_version = getattr(flow_state, "version", 0)
version_result = db.execute(
    select(PatientFlowState.version).filter(PatientFlowState.id == flow_state.id)
)
current_version = version_result.scalar_one_or_none()
if current_version != expected_version:
    raise FlowStateConflictError("Concurrent flow update detected")
flow_state.version = expected_version + 1
db.commit()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Silent waiting on context mismatch | Counter-based reset after 3 mismatches | Phase 50 (50-01) | Flows auto-unstick from correlation failures |
| Silent message send failure | Celery retry with exponential backoff | Phase 50 (50-02) | Failed sends get 3 retries before permanent failure |
| Silent follow-up drop | Background retry via Celery task | Phase 50 (50-03) | Deferred follow-ups never silently disappear |
| Unverified day advancement | Atomic advance with optimistic lock | Phase 50 (50-03) | Day completion is verified, not assumed |
| No flow stall visibility | *Phase 51 adds periodic detection* | Phase 51 | Flows stuck > threshold are automatically found |

**Deprecated/outdated:**
- `AutomatedRecoveryService`: Exists at `app/services/automated_recovery_pkg/` but is a general-purpose system recovery tool (DB, Redis, queues). It does NOT specifically handle stuck patient flows. Phase 51 creates flow-specific recovery that is simpler and more targeted.

## Open Questions

1. **Configurable threshold default value**
   - What we know: The threshold must be configurable via environment variable.
   - What's unclear: Whether 4 hours is appropriate for oncology patient flows (where patients may respond next day).
   - Recommendation: Default to 4 hours for stall detection, but only auto-recover after 8 hours. Make both configurable: `TASK_STUCK_FLOW_DETECT_HOURS=4` and `TASK_STUCK_FLOW_RECOVER_HOURS=8`.

2. **Recovery action for completed-day flows**
   - What we know: `day_complete=True` + `day_advance_verified=False` means advancement failed.
   - What's unclear: Whether re-running `advance_day_atomic()` is safe in auto-recovery (it requires a valid db session and template lookup).
   - Recommendation: For auto-recovery, advance day using `FlowManagementService.advance_patient_flow()` which has all validation. If it fails, flag for manual intervention.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x with pytest-asyncio (asyncio_mode=auto) |
| Config file | `backend-hormonia/pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `cd backend-hormonia && python -m pytest tests/unit/tasks/ -x -q` |
| Full suite command | `cd backend-hormonia && python -m pytest tests/unit/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RECV-01 | Periodic task finds flows stuck in awaiting_response > threshold | unit | `pytest tests/unit/tasks/test_stuck_detection.py -x` | Wave 0 |
| RECV-02 | Auto-recovery re-sends prompt or advances day based on state | unit | `pytest tests/unit/services/flow/test_flow_recovery.py -x` | Wave 0 |
| RECV-03 | Admin can reset/advance/unstick flow via API | unit | `pytest tests/unit/api/test_admin_flow_ops.py -x` | Wave 0 |
| RECV-04 | Failed flow operations queryable by admin | unit | `pytest tests/unit/api/test_admin_flow_ops.py::test_list_failed_ops -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `cd backend-hormonia && python -m pytest tests/unit/tasks/test_stuck_detection.py tests/unit/services/flow/test_flow_recovery.py -x -q`
- **Per wave merge:** `cd backend-hormonia && python -m pytest tests/unit/ -x -q`
- **Phase gate:** Full unit suite green before verify-work

### Wave 0 Gaps
- [ ] `tests/unit/tasks/test_stuck_detection.py` -- covers RECV-01 (detector finds stuck flows, respects threshold, handles empty results)
- [ ] `tests/unit/services/flow/test_flow_recovery.py` -- covers RECV-02 (resend vs advance decision, recovery attempt tracking, max recovery limit)
- [ ] `tests/unit/api/test_admin_flow_ops.py` -- covers RECV-03, RECV-04 (unstick, advance, reset endpoints; failed ops query)

## Sources

### Primary (HIGH confidence)
- `backend-hormonia/app/celery_app.py` -- Beat schedule pattern, 38+ existing periodic tasks
- `backend-hormonia/app/tasks/flows/send_retry.py` -- Celery task pattern with scoped session, retry, permanent failure
- `backend-hormonia/app/tasks/flows/followup_retry.py` -- Follow-up retry pattern
- `backend-hormonia/app/services/flow/management/advancement.py` -- `advance_day_atomic()` with optimistic locking
- `backend-hormonia/app/services/flow/sequential_response_gate.py` -- Mismatch recovery, step_data markers
- `backend-hormonia/app/services/flow/flags.py` -- `is_awaiting_response()` boolean coercion
- `backend-hormonia/app/models/flow.py` -- `PatientFlowState` model with step_data JSONB, version column
- `backend-hormonia/app/api/v2/routers/admin_extensions/dlq.py` -- Admin endpoint pattern (auth, rate-limit, audit, cache invalidation)
- `backend-hormonia/app/repositories/flow.py` -- `FlowStateRepository.get_active_flows()` query pattern
- `backend-hormonia/app/config/settings/tasks.py` -- Environment variable configuration pattern

### Secondary (MEDIUM confidence)
- Phase 50 summaries (50-01 through 50-04) -- Documented step_data markers and established patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- patterns copied directly from existing codebase (send_retry, admin_extensions/dlq)
- Pitfalls: HIGH -- identified from real codebase patterns (JSONB types, session management, optimistic locking)

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable -- internal codebase patterns, no external dependency risk)