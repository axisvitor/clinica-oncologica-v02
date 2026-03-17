---
estimated_steps: 5
estimated_files: 20
---

# T01: Extract pure helpers from Celery modules into shared helper package

**Slice:** S05 — Celery removal + bridge cleanup
**Milestone:** M009

## Description

10 Taskiq modules import ~40+ helper functions/constants from Celery task modules that will be deleted in T03. If we delete those Celery files first, every Taskiq task breaks at import time. This task creates `app/tasks/helpers/` package with per-domain helper modules, copies the pure helper functions from Celery sources, and rewires all Taskiq module imports.

This is the **hard prerequisite** for the entire slice. Nothing else can proceed until this is done.

## Steps

1. **Create `app/tasks/helpers/__init__.py`** — Empty package init (just a docstring).

2. **Create per-domain helper modules** — For each Taskiq module that imports from a Celery module, create a corresponding helper file and copy the imported helpers:

   | Helper Module | Source Celery Module | Helpers to Copy |
   |---|---|---|
   | `messaging_helpers.py` | `app/tasks/messaging.py` | `_build_idempotency_key`, `_compute_next_reminder_time`, `_schedule_next_reminder` |
   | `alerts_helpers.py` | `app/tasks/alerts.py` | `_ALERT_METADATA_REDACTED_FIELDS`, `_sanitize_alert_metadata`, `_build_patient_context` |
   | `lgpd_helpers.py` | `app/tasks/lgpd_tasks.py` | `_is_patient_context`, `_normalize_action`, `_normalize_data_category`, `_normalize_fields_accessed`, `_normalize_legal_basis`, `_normalize_optional_text`, `_normalize_purpose`, `_normalize_resource_type`, `_resolve_patient_identifier`, `_resolve_patient_uuid`, `_safe_parse_uuid`, `_sanitize_additional_data`, `_SENSITIVE_DATA_CATEGORIES` |
   | `reports_helpers.py` | `app/tasks/reports.py` | `_build_safe_report_path`, `_get_system_actor_uuid`, `_sanitize_report_type` |
   | `saga_helpers.py` | `app/tasks/saga_retry.py` | `_calculate_exponential_backoff`, `_alert_admin_max_retries_exceeded` |
   | `follow_up_helpers.py` | `app/tasks/follow_up.py` | `FOLLOW_UP_DEDUP_WINDOW_SECONDS`, `FOLLOW_UP_DEDUP_LOCK_SECONDS`, `_get_last_follow_up_sent_at_db`, `_is_follow_up_eligible`, `_update_patient_last_message_sent_at` |
   | `quiz_link_helpers.py` | `app/tasks/quiz_link_tasks.py` | `_sanitize_dlq_record`, `_sanitize_error_message`, `_sanitize_limit`, `_token_fingerprint` |
   | `flow_helpers.py` | `app/tasks/flow_automation.py` + `app/tasks/flows/batch_tasks.py` | `_determine_template_for_patient`, `_get_reminder_message`, `_is_auto_resume_due`, `_process_single_patient_flow_by_id` |
   | `quiz_flow_helpers.py` | `app/tasks/quiz_flow/cleanup_tasks.py` + `helpers.py` + `question_tasks.py` + `trigger_tasks.py` | `_sanitize_max_age_hours`, `_notify_providers_of_quiz_completion`, `_parse_uuid`, `_sanitize_hours_before_expiry`, `_sanitize_limit` (note: different from quiz_link's `_sanitize_limit`) |

   For each helper:
   - Open the Celery source file
   - Find the function/constant definition
   - Copy it into the new helper module INCLUDING all its imports (inspect what the function uses: logging, uuid, datetime, ORM models, etc.)
   - Do NOT copy any Celery-specific imports (celery, celery_app, etc.)
   - If a helper calls another helper from the same source file, copy both

   **IMPORTANT constraints:**
   - `_process_single_patient_flow_by_id` from `batch_tasks.py` is a complex async function with its own DB session management and imports. Copy it fully with all its internal helper calls (`_is_flow_paused`, `_is_awaiting_response`, `_process_single_patient_flow`, `get_db` from `batch_tasks.py`). If these are too entangled, alternatively just inline the import in `flows_taskiq.py` but update it to import from `helpers/flow_helpers.py`.
   - `_notify_providers_of_quiz_completion` from `quiz_flow/helpers.py` — check what it imports and copy those deps too.
   - Some helpers may have DB session parameters (sync ORM) — that's fine, copy as-is. These are still "pure" in the sense that they don't depend on Celery runtime.

3. **Update all Taskiq module imports** — For each of the 10 Taskiq modules that imports from a Celery module, change the import source:

   | Taskiq Module | Old Import | New Import |
   |---|---|---|
   | `messaging_taskiq.py` | `from app.tasks.messaging import ...` | `from app.tasks.helpers.messaging_helpers import ...` |
   | `alerts_taskiq.py` | `from app.tasks.alerts import ...` | `from app.tasks.helpers.alerts_helpers import ...` |
   | `lgpd_taskiq.py` | `from app.tasks.lgpd_tasks import ...` | `from app.tasks.helpers.lgpd_helpers import ...` |
   | `reports_taskiq.py` | `from app.tasks.reports import ...` | `from app.tasks.helpers.reports_helpers import ...` |
   | `saga_retry_taskiq.py` | `from app.tasks.saga_retry import ...` | `from app.tasks.helpers.saga_helpers import ...` |
   | `follow_up_taskiq.py` | `from app.tasks.follow_up import ...` | `from app.tasks.helpers.follow_up_helpers import ...` |
   | `quiz_link_taskiq.py` | `from app.tasks.quiz_link_tasks import ...` | `from app.tasks.helpers.quiz_link_helpers import ...` |
   | `flows_taskiq.py` | `from app.tasks.flow_automation import ...` AND `from app.tasks.flows.batch_tasks import ...` | `from app.tasks.helpers.flow_helpers import ...` |
   | `quiz_flow_taskiq.py` | `from app.tasks.quiz_flow.cleanup_tasks import ...` etc. | `from app.tasks.helpers.quiz_flow_helpers import ...` |

   Note: `audit_taskiq.py`, `monitoring_taskiq.py`, `webhook_dlq_taskiq.py`, `saga_monitoring_taskiq.py` do NOT import from Celery modules — no changes needed.

4. **Verify each Taskiq module parses** — Run `ast.parse()` on all 13 `*_taskiq.py` files after import changes.

5. **Verify no Taskiq module imports from Celery task modules** — AST scan all `*_taskiq.py` files: zero `from app.tasks.messaging import`, `from app.tasks.alerts import`, etc. Only `from app.tasks.helpers.*` and `from app.tasks.taskiq_base import` and `from app.tasks.*_taskiq import` are allowed.

## Must-Haves

- [ ] `app/tasks/helpers/` package exists with `__init__.py` and 9 domain helper modules
- [ ] All ~40+ helper functions/constants copied with their dependencies (imports they need)
- [ ] All 10 Taskiq modules updated to import from `app.tasks.helpers.*`
- [ ] All 13 `*_taskiq.py` modules pass `ast.parse()` after changes
- [ ] Zero imports from Celery task modules in any `*_taskiq.py` file

## Verification

```bash
# 1. All 13 Taskiq modules parse
python3 -c "
import ast, glob, sys
errors = []
for f in glob.glob('backend-hormonia/app/tasks/*_taskiq.py'):
    try:
        ast.parse(open(f).read())
    except SyntaxError as e:
        errors.append(f'{f}: {e}')
if errors:
    print('FAIL:', errors)
    sys.exit(1)
print(f'PASS — {len(glob.glob(\"backend-hormonia/app/tasks/*_taskiq.py\"))} Taskiq modules parse OK')
"

# 2. Zero imports from Celery task modules in Taskiq files
python3 -c "
import ast, glob, sys
CELERY_MODULES = {
    'app.tasks.messaging', 'app.tasks.alerts', 'app.tasks.monitoring',
    'app.tasks.flow_automation', 'app.tasks.follow_up', 'app.tasks.lgpd_tasks',
    'app.tasks.quiz_link_tasks', 'app.tasks.reports', 'app.tasks.saga_monitoring',
    'app.tasks.saga_retry', 'app.tasks.webhook_dlq', 'app.tasks.audit_cleanup',
    'app.tasks.flows.batch_tasks', 'app.tasks.flows.flow_tasks',
    'app.tasks.flows.send_retry', 'app.tasks.flows.stuck_detection',
    'app.tasks.flows.monitoring', 'app.tasks.flows.monthly_tasks',
    'app.tasks.flows.cleanup_tasks', 'app.tasks.flows.followup_retry',
    'app.tasks.quiz_flow.cleanup_tasks', 'app.tasks.quiz_flow.helpers',
    'app.tasks.quiz_flow.question_tasks', 'app.tasks.quiz_flow.response_tasks',
    'app.tasks.quiz_flow.trigger_tasks',
}
errors = []
for f in glob.glob('backend-hormonia/app/tasks/*_taskiq.py'):
    tree = ast.parse(open(f).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in CELERY_MODULES:
            errors.append(f'{f}:{node.lineno}: from {node.module}')
if errors:
    print('FAIL — Celery module imports in Taskiq files:')
    for e in errors: print(f'  {e}')
    sys.exit(1)
print('PASS — Zero Celery module imports in Taskiq files')
"

# 3. Helper modules exist and parse
python3 -c "
import ast, glob, sys
helpers = [h for h in glob.glob('backend-hormonia/app/tasks/helpers/*.py') if '__pycache__' not in h and '__init__' not in h]
if len(helpers) < 9:
    print(f'FAIL — expected >=9 helper modules, found {len(helpers)}: {helpers}')
    sys.exit(1)
for f in helpers:
    try: ast.parse(open(f).read())
    except SyntaxError as e:
        print(f'FAIL: {f}: {e}')
        sys.exit(1)
print(f'PASS — {len(helpers)} helper modules parse OK')
"
```

## Inputs

- All 13 `*_taskiq.py` modules in `backend-hormonia/app/tasks/` — each has import lines from Celery modules that need to be redirected
- The Celery source modules from which helpers are imported (read these to extract helper function code)

## Expected Output

- `backend-hormonia/app/tasks/helpers/__init__.py` — package init
- `backend-hormonia/app/tasks/helpers/messaging_helpers.py` — 3 helpers from messaging.py
- `backend-hormonia/app/tasks/helpers/alerts_helpers.py` — 3 helpers from alerts.py
- `backend-hormonia/app/tasks/helpers/lgpd_helpers.py` — 13 helpers from lgpd_tasks.py
- `backend-hormonia/app/tasks/helpers/reports_helpers.py` — 3 helpers from reports.py
- `backend-hormonia/app/tasks/helpers/saga_helpers.py` — 2 helpers from saga_retry.py
- `backend-hormonia/app/tasks/helpers/follow_up_helpers.py` — 5 helpers from follow_up.py
- `backend-hormonia/app/tasks/helpers/quiz_link_helpers.py` — 4 helpers from quiz_link_tasks.py
- `backend-hormonia/app/tasks/helpers/flow_helpers.py` — 4 helpers from flow_automation.py + batch_tasks.py
- `backend-hormonia/app/tasks/helpers/quiz_flow_helpers.py` — 5 helpers from quiz_flow/ subpackage
- All 10 Taskiq modules with updated import paths
