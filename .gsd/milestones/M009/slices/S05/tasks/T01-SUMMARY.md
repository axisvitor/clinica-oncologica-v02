---
id: T01
parent: S05
milestone: M009
provides:
  - app/tasks/helpers/ package with 9 domain helper modules (40+ functions/constants)
  - All 10 Taskiq modules import from helpers instead of Celery modules
key_files:
  - backend-hormonia/app/tasks/helpers/__init__.py
  - backend-hormonia/app/tasks/helpers/messaging_helpers.py
  - backend-hormonia/app/tasks/helpers/alerts_helpers.py
  - backend-hormonia/app/tasks/helpers/lgpd_helpers.py
  - backend-hormonia/app/tasks/helpers/reports_helpers.py
  - backend-hormonia/app/tasks/helpers/saga_helpers.py
  - backend-hormonia/app/tasks/helpers/follow_up_helpers.py
  - backend-hormonia/app/tasks/helpers/quiz_link_helpers.py
  - backend-hormonia/app/tasks/helpers/flow_helpers.py
  - backend-hormonia/app/tasks/helpers/quiz_flow_helpers.py
key_decisions:
  - flow_helpers.py consolidates helpers from 4 Celery sources (flow_automation, batch_tasks, send_retry, followup_retry) since flows_taskiq.py imports from all 4
  - _process_single_patient_flow was copied fully with all internal helpers (_is_flow_paused, _is_awaiting_response, _update_scheduling, _get_message_template_for_day, _normalize_template_day) since they are tightly coupled
  - Changed send_scheduled_message.delay() inside _process_single_patient_flow to use Taskiq dispatch (send_scheduled_message.kiq) since the helper now lives outside Celery context
patterns_established:
  - Helpers package convention: app/tasks/helpers/{domain}_helpers.py for shared pure functions
  - Internal helpers that call each other are co-located in the same helper module
observability_surfaces:
  - ast.parse() verification confirms all 13 Taskiq modules parse after import changes
  - AST scan confirms zero imports from Celery task modules in any *_taskiq.py file
duration: 20m
verification_result: passed
completed_at: 2026-03-16
blocker_discovered: false
---

# T01: Extract pure helpers from Celery modules into shared helper package

**Created `app/tasks/helpers/` package with 9 domain helper modules containing 40+ functions/constants, and rewired all 10 Taskiq module imports away from Celery sources.**

## What Happened

Extracted all pure helper functions and constants from Celery task modules into a new `app/tasks/helpers/` package. Each helper module corresponds to one or more Celery source files:

- **messaging_helpers.py** (3 helpers from messaging.py): `_build_idempotency_key`, `_compute_next_reminder_time`, `_schedule_next_reminder` + internal deps `_parse_time_str`, `_add_months`
- **alerts_helpers.py** (3 helpers from alerts.py): `_ALERT_METADATA_REDACTED_FIELDS`, `_sanitize_alert_metadata`, `_build_patient_context`
- **lgpd_helpers.py** (13 helpers from lgpd_tasks.py): Full normalization/sanitization/resolution chain including all internal deps
- **reports_helpers.py** (3 helpers from reports.py): `_get_system_actor_uuid`, `_sanitize_report_type`, `_build_safe_report_path`
- **saga_helpers.py** (2 helpers from saga_retry.py): `_calculate_exponential_backoff`, `_alert_admin_max_retries_exceeded` + `_send_admin_email_alert`
- **follow_up_helpers.py** (5 helpers from follow_up.py): Dedup constants + eligibility/DB helpers
- **quiz_link_helpers.py** (4 helpers from quiz_link_tasks.py): Sanitization + token fingerprinting
- **flow_helpers.py** (consolidated from 4 Celery sources): `flow_automation.py` (3), `batch_tasks.py` (full processing chain), `send_retry.py` (3), `followup_retry.py` (1)
- **quiz_flow_helpers.py** (5 helpers from quiz_flow/ subpackage): From cleanup_tasks, helpers, question_tasks, trigger_tasks

Updated all 10 Taskiq modules with 15 import statements redirected from Celery sources to `app.tasks.helpers.*`. This included both top-level imports and inline/lazy imports inside functions (e.g., `flows_taskiq.py` had lazy imports from `send_retry` and `followup_retry`).

## Verification

```
# Task verification — all 3 checks pass:
PASS — 13 Taskiq modules parse OK
PASS — Zero Celery module imports in Taskiq files
PASS — 9 helper modules parse OK

# Slice verification — checks applicable to T01:
V2 PASS — 13 Taskiq modules parse OK
V6 PASS — 47 schedule labels preserved
V7 PASS — 10 helper modules parse OK (9 domain + __init__.py)

# Remaining slice checks (expected to fail until T02-T04):
V1 (zero Celery imports in app/) — not yet, Celery sources still exist
V3 (requirements.txt clean) — not yet
V4 (key Celery files deleted) — not yet
V5 (Celery directories deleted) — not yet
V8 (no TODO(S05)) — not yet
V9 (tasks/__init__.py clean) — not yet
```

## Diagnostics

- If a helper import fails at runtime, the structured `log_task_error` in each Taskiq task emits the `ImportError` traceback to stdout/Sentry
- To verify helper coverage: `python3 -c "import ast, glob; ..."`  AST scan on all `*_taskiq.py` files (see task plan verification scripts)
- To check specific helper: `python3 -c "from app.tasks.helpers.{domain}_helpers import {func}; print('OK')"`

## Deviations

- **flow_helpers.py is larger than planned**: Plan listed 4 helpers from `flow_automation.py` + `batch_tasks.py`. Actual imports in `flows_taskiq.py` also included 3 helpers from `send_retry.py` and 1 from `followup_retry.py` (discovered via AST scan). All consolidated into `flow_helpers.py`.
- **_process_single_patient_flow fully extracted with full dep chain**: The plan noted this might be "too entangled". It was manageable — copied the full async processing pipeline including `_process_single_patient_flow`, `_get_message_template_for_day`, `_update_scheduling`, and `_normalize_template_day`. Changed one `send_scheduled_message.delay()` call to `send_scheduled_message.kiq()` for Taskiq compatibility.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/tasks/helpers/__init__.py` — Package init with docstring
- `backend-hormonia/app/tasks/helpers/messaging_helpers.py` — 5 helpers from messaging.py
- `backend-hormonia/app/tasks/helpers/alerts_helpers.py` — 3 helpers from alerts.py
- `backend-hormonia/app/tasks/helpers/lgpd_helpers.py` — 13+ helpers from lgpd_tasks.py
- `backend-hormonia/app/tasks/helpers/reports_helpers.py` — 3 helpers from reports.py
- `backend-hormonia/app/tasks/helpers/saga_helpers.py` — 3 helpers from saga_retry.py
- `backend-hormonia/app/tasks/helpers/follow_up_helpers.py` — 6 helpers from follow_up.py
- `backend-hormonia/app/tasks/helpers/quiz_link_helpers.py` — 4 helpers from quiz_link_tasks.py
- `backend-hormonia/app/tasks/helpers/flow_helpers.py` — 15+ helpers from 4 Celery sources
- `backend-hormonia/app/tasks/helpers/quiz_flow_helpers.py` — 5 helpers from quiz_flow/ subpackage
- `backend-hormonia/app/tasks/alerts_taskiq.py` — Import updated to helpers.alerts_helpers
- `backend-hormonia/app/tasks/flows_taskiq.py` — 3 import statements updated (top-level + 2 inline)
- `backend-hormonia/app/tasks/follow_up_taskiq.py` — Import updated to helpers.follow_up_helpers
- `backend-hormonia/app/tasks/lgpd_taskiq.py` — Import updated to helpers.lgpd_helpers
- `backend-hormonia/app/tasks/messaging_taskiq.py` — Import updated to helpers.messaging_helpers
- `backend-hormonia/app/tasks/quiz_flow_taskiq.py` — Import updated to helpers.quiz_flow_helpers
- `backend-hormonia/app/tasks/quiz_link_taskiq.py` — Import updated to helpers.quiz_link_helpers
- `backend-hormonia/app/tasks/reports_taskiq.py` — Import updated to helpers.reports_helpers
- `backend-hormonia/app/tasks/saga_retry_taskiq.py` — Import updated to helpers.saga_helpers
- `.gsd/milestones/M009/slices/S05/S05-PLAN.md` — T01 marked done, added diagnostic check to observability
