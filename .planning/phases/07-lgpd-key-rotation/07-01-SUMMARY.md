---
phase: 07-lgpd-key-rotation
plan: 01
subsystem: database
tags: [lgpd, encryption, celery, redis, python, aes-256-gcm, key-rotation]

# Dependency graph
requires:
  - phase: 03-operational-stability
    provides: UnifiedEncryptionService with field-level AES-256-GCM encryption for cpf/email/phone

provides:
  - lgpd.batch_reencrypt_patients Celery task with chunked processing and Redis idempotency
  - rotate_encryption_key() in-memory key rotation with clear delegation to Celery task
  - Test suite verifying idempotency, chunking, error resilience, and env-var key reading

affects: [key-rotation-ops, lgpd-compliance, celery-workers]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Env-var key injection: secrets read from os.environ inside task body, never passed as args"
    - "Redis idempotency set: lgpd:reencrypt:completed_ids:{job_id} with 7-day TTL"
    - "Chunked offset pagination: offset/limit loop with per-chunk commit, no full-table load"
    - "HASH_SALT invariant: explicitly documented as must NOT rotate alongside PHI_ENCRYPTION_KEY"

key-files:
  created:
    - backend-hormonia/app/tasks/lgpd/__init__.py
    - backend-hormonia/app/tasks/lgpd/reencrypt_patients.py
    - backend-hormonia/tests/tasks/test_reencrypt_patients.py
  modified:
    - backend-hormonia/app/celery_app.py
    - backend-hormonia/app/task_queue.py
    - backend-hormonia/app/services/encryption/service.py

key-decisions:
  - "Secrets injected via env var name args (not values) — prevents PHI appearing in Celery broker/result backend logs"
  - "has_more detection via last_batch_size == chunk_size after while loop exits — handles max_patients exact-boundary case"
  - "Per-patient errors counted and logged but do not abort batch — allows partial success and resume"
  - "rotate_encryption_key() only updates in-memory keys; delegates DB re-encryption to Celery task with explicit log message"

patterns-established:
  - "LGPD tasks: always use job_id-scoped Redis sets for idempotency, 7-day TTL"
  - "Key rotation: env-var name as task arg, value read inside task body"

requirements-completed: [LGPD-04]

# Metrics
duration: 7min
completed: 2026-02-23
---

# Phase 7 Plan 01: LGPD Key Rotation Summary

**LGPD batch re-encryption Celery task (lgpd.batch_reencrypt_patients) with chunked offset pagination, Redis job-scoped idempotency markers, and 6-test suite verifying safe resumable key rotation for patient CPF/email/phone PII fields.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-02-23T01:36:57Z
- **Completed:** 2026-02-23T01:44:21Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- New `app/tasks/lgpd/` package with `batch_reencrypt_patients` Celery task registered in both `celery_app.py` and `task_queue.py`
- Task reads PHI keys from env vars (not args), processes patients in configurable offset chunks, commits per chunk, marks processed patients in Redis with 7-day TTL so interrupted runs resume safely
- `UnifiedEncryptionService.rotate_encryption_key()` stub replaced with real in-memory key rotation that clearly delegates DB re-encryption to the Celery task
- 6 tests covering all ROADMAP success criteria including idempotency verification (`test_idempotency_skips_already_processed`)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create batch re-encryption Celery task module** - `67f036ad` (feat)
2. **Task 2: Register task and update rotate_encryption_key stub** - `3a450bf1` (feat)
3. **Task 3: Write idempotency and chunking test** - `6bb408b2` (test)

## Files Created/Modified

- `backend-hormonia/app/tasks/lgpd/reencrypt_patients.py` - Main Celery task with helpers for key derivation, per-patient re-encryption, and Redis idempotency
- `backend-hormonia/app/tasks/lgpd/__init__.py` - Package init re-exporting batch_reencrypt_patients
- `backend-hormonia/app/celery_app.py` - Added app.tasks.lgpd.reencrypt_patients to include list
- `backend-hormonia/app/task_queue.py` - Added app.tasks.lgpd.reencrypt_patients to _TASK_MODULES
- `backend-hormonia/app/services/encryption/service.py` - rotate_encryption_key() stub replaced with real in-memory rotation + delegation docs
- `backend-hormonia/tests/tasks/test_reencrypt_patients.py` - 6 tests for batch processing, idempotency, chunking, error resilience, env-var reading, has_more flag

## Decisions Made

- **Secrets never as task args:** `old_key_env_var` and `new_key_env_var` accept env var *names* only; the actual key values are read inside the task body via `os.environ`. This prevents PHI encryption keys from appearing in Celery broker queues or result backends.
- **has_more edge case fix:** After the while loop exits at `max_patients`, an extra check detects whether the last batch was full (`last_batch_size == chunk_size`); if so, `has_more` is set True to signal more records exist.
- **Per-patient error policy:** Errors are counted and logged with `exc_info=True` but do not abort the batch. The batch continues to the next patient. This matches the plan specification and allows safe partial-success runs.
- **rotate_encryption_key() scope:** Only updates in-memory `_keys["phi"]` and `_keys["quiz"]`, reinitializes algorithms/encryptors. Database re-encryption is explicitly documented as the Celery task's responsibility, with a log message guiding operators.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed has_more flag not set when max_patients reached with full batch**
- **Found during:** Task 3 (test execution)
- **Issue:** When `processed` reached exactly `max_patients` with a full last batch, the while loop exited via condition (not via internal break), leaving `has_more=False` despite more rows existing in the DB.
- **Fix:** Added `last_batch_size` tracking. After the while loop, if `processed >= max_patients` and `last_batch_size == chunk_size`, set `has_more = True`.
- **Files modified:** backend-hormonia/app/tasks/lgpd/reencrypt_patients.py
- **Verification:** `test_has_more_flag_when_max_patients_reached` now passes (was failing before fix).
- **Committed in:** `6bb408b2` (Task 3 commit)

**2. [Rule 1 - Bug] Patched self.update_state() in tests to prevent Celery backend error**
- **Found during:** Task 3 (first test run)
- **Issue:** `self.update_state()` inside bound Celery task fails in unit test context because there is no real Celery task ID (task_id=None), causing `ValueError: task_id must not be empty`.
- **Fix:** Added `patch.object(batch_reencrypt_patients, "update_state")` to each test that invokes the task.
- **Files modified:** backend-hormonia/tests/tasks/test_reencrypt_patients.py
- **Verification:** All 6 tests pass.
- **Committed in:** `6bb408b2` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered

None beyond the two auto-fixed bugs documented above.

## User Setup Required

None - no external service configuration required. The new env var `PHI_ENCRYPTION_KEY_PREVIOUS` is only needed when actively performing a key rotation (set to the old key, keep `PHI_ENCRYPTION_KEY` as the new key).

## Next Phase Readiness

- `lgpd.batch_reencrypt_patients` is fully operational and registered. Operators can invoke it with a unique `job_id` during a maintenance window to complete database re-encryption.
- HASH_SALT invariant is documented in both the task module and the `rotate_encryption_key()` docstring.
- LGPD-04 requirement satisfied: batch re-encryption task exists, is resumable via idempotency markers, and has a test verifying idempotency behavior.

---
*Phase: 07-lgpd-key-rotation*
*Completed: 2026-02-23*
