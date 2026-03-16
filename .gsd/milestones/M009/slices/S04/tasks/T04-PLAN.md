---
estimated_steps: 4
estimated_files: 2
---

# T04: Schedule parity verification + call site audit

**Slice:** S04 — Quiz/alert/follow-up/monitoring migradas + schedule completo
**Milestone:** M009

## Description

Create a verification script that proves 1:1 schedule parity between all 47 Celery beat_schedule entries and Taskiq schedule labels. Audit all `.delay()`/`.apply_async()` call sites to confirm external ones are migrated or marked `TODO(S05)`. This is the proof task for R082 (schedule parity) and R083 (call site migration).

## Steps

1. **Create `scripts/verify_schedule_parity.sh`**:
   - Extract all 47 beat_schedule entries from `app/celery_app.py` — capture the `"task":` value and schedule type/value for each entry.
   - Extract all `schedule=[...]` labels from all `app/tasks/*_taskiq.py` files — capture function name and schedule config.
   - Build a mapping from Celery task name → Taskiq function name (names differ: Celery uses dotted module path like `app.tasks.alerts.check_patient_alerts`, Taskiq uses function name `check_patient_alerts`).
   - Compare: for each beat_schedule entry, verify a matching Taskiq schedule label exists. Report matched/missing/extra.
   - Exit 0 if all 47 matched, exit 1 if any missing.

2. **Run the verification script and fix any gaps**:
   - If any beat_schedule entry is missing a Taskiq equivalent, identify which `*_taskiq.py` module should contain it and add the missing schedule label.
   - Verify the final count: 47/47 matched.

3. **Audit remaining call sites**:
   - Run `rg "\.delay\(|\.apply_async\(" --glob "*.py" --glob "!**/test*"` from `backend-hormonia/`.
   - Expected results: `.delay()` / `.apply_async()` should ONLY appear in:
     - `app/tasks/*.py` (Celery task modules — deleted in S05)
     - `app/celery_app.py` (Celery config — deleted in S05)
     - `app/domain/quizzes/.../trigger_service.py` (TODO(S05) per D010 — sync caller)
     - `app/services/flow/recovery.py` (TODO(S05) per D010 — sync caller)
   - If any OTHER file still has `.delay()` / `.apply_async()`, it's a missed call site — fix it.
   - Verify that trigger_service.py and recovery.py have `TODO(S05)` markers on their Celery dispatch lines.

4. **Count total `@broker.task` across all taskiq modules**:
   - `grep -rc "@broker.task" app/tasks/*_taskiq.py` should show ≥46 total tasks (9 messaging + 14 flows + 3 saga_retry + 4 audit + 2 lgpd + 2 reports + 3 saga_monitoring + 7 alerts + 3 webhook_dlq + 8 monitoring + 6 quiz_link + 8 quiz_flow + 3 follow_up = 72 tasks total, but some may be non-broker-task helpers).

## Must-Haves

- [ ] `scripts/verify_schedule_parity.sh` created and executable
- [ ] Script reports 47/47 beat_schedule entries matched to Taskiq schedule labels
- [ ] No external `.delay()` / `.apply_async()` call sites remain (except TODO(S05)-marked trigger_service.py and recovery.py)
- [ ] trigger_service.py and recovery.py have explicit `TODO(S05)` comments on Celery dispatch lines

## Verification

- `bash scripts/verify_schedule_parity.sh` exits 0 with all entries matched
- `rg "\.delay\(|\.apply_async\(" --glob "*.py" --glob "!app/tasks/*.py" --glob "!app/celery_app.py" --glob "!**/test*" backend-hormonia/ | grep -v "TODO(S05)" | wc -l` → 0
- `grep -rc "@broker.task" app/tasks/*_taskiq.py | awk -F: '{s+=$2}END{print "Total broker tasks:", s}'` confirms total

## Inputs

- `backend-hormonia/app/celery_app.py` — all 47 beat_schedule entries (lines 81-296)
- All `backend-hormonia/app/tasks/*_taskiq.py` files from T01, T02, T03 + S02/S03
- `backend-hormonia/app/domain/quizzes/integration/flow_integration/trigger_service.py` — TODO(S05) call site
- `backend-hormonia/app/services/flow/recovery.py` — TODO(S05) call site

## Expected Output

- `backend-hormonia/scripts/verify_schedule_parity.sh` — executable verification script
- Passing verification: 47/47 schedule parity, zero unresolved external call sites
