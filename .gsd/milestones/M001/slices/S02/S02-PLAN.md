# S02: Flow Recovery

**Goal:** Detect stuck patient flows automatically and recover them via periodic Celery Beat task.
**Demo:** Detect stuck patient flows automatically and recover them via periodic Celery Beat task.

## Must-Haves


## Tasks

- [x] **T01: Stuck flow detection and auto-recovery** `est:15m`
  - Detect stuck patient flows automatically and recover them via periodic Celery Beat task.

Purpose: Patients whose flows are stuck in `awaiting_response` for hours are currently invisible. This plan adds a periodic detector that finds them and attempts auto-recovery (re-send prompt or advance day) before the patient or operator notices.

Output: `recovery.py` service module with detection + recovery logic, `stuck_detection.py` Celery task, Beat schedule entry, and configurable settings. Fully tested.
- [x] **T02: Admin flow operations and failed-op visibility** `est:6 min`
  - Give administrators manual flow control tools and failed-operations visibility.

Purpose: When auto-recovery is insufficient or operators need to intervene directly, they need API endpoints to reset, advance, or unstick specific patient flows. They also need to see which flows have experienced failures (delivery failures, mismatch resets) to triage proactively.

Output: `flow_ops.py` admin router with 4 endpoints, Pydantic schemas, router registration, and full test coverage.

## Files Likely Touched

- `backend-hormonia/app/services/flow/recovery.py`
- `backend-hormonia/app/tasks/flows/stuck_detection.py`
- `backend-hormonia/app/tasks/flows/__init__.py`
- `backend-hormonia/app/config/settings/tasks.py`
- `backend-hormonia/app/celery_app.py`
- `backend-hormonia/tests/unit/tasks/test_stuck_detection.py`
- `backend-hormonia/tests/unit/services/flow/test_flow_recovery.py`
- `backend-hormonia/app/api/v2/routers/admin_extensions/flow_ops.py`
- `backend-hormonia/app/api/v2/routers/admin_extensions/__init__.py`
- `backend-hormonia/app/schemas/v2/admin_extensions.py`
- `backend-hormonia/tests/unit/api/test_admin_flow_ops.py`
