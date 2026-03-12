# T01: Stuck flow detection and auto-recovery

**Slice:** S02 — **Milestone:** M001

## Description

Detect stuck patient flows automatically and recover them via periodic Celery Beat task.

Purpose: Patients whose flows are stuck in `awaiting_response` for hours are currently invisible. This plan adds a periodic detector that finds them and attempts auto-recovery (re-send prompt or advance day) before the patient or operator notices.

Output: `recovery.py` service module with detection + recovery logic, `stuck_detection.py` Celery task, Beat schedule entry, and configurable settings. Fully tested.

## Must-Haves

- [ ] "A periodic Celery Beat task runs every 15 minutes and identifies patient flows stuck in awaiting_response longer than a configurable threshold"
- [ ] "Stuck flows are automatically recovered by re-sending the last prompt or advancing the day, based on the flow's current step_data state"
- [ ] "Auto-recovery is bounded: after 3 recovery attempts per flow, the flow is flagged for manual intervention instead of retried endlessly"
- [ ] "Recovery operations are idempotent: a concurrent patient response does not cause duplicate messages or state corruption"

## Files

- `backend-hormonia/app/services/flow/recovery.py`
- `backend-hormonia/app/tasks/flows/stuck_detection.py`
- `backend-hormonia/app/tasks/flows/__init__.py`
- `backend-hormonia/app/config/settings/tasks.py`
- `backend-hormonia/app/celery_app.py`
- `backend-hormonia/tests/unit/tasks/test_stuck_detection.py`
- `backend-hormonia/tests/unit/services/flow/test_flow_recovery.py`
