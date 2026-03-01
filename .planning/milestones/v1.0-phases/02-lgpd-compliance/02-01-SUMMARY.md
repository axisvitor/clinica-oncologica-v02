---
phase: 02-lgpd-compliance
plan: 01
subsystem: patient-audit
tags: [lgpd, compliance, audit, database, soft-delete]
dependency_graph:
  requires: []
  provides: [PatientDeletionAudit model, lgpd01 migration, delete_patient audit hook]
  affects: [app/services/patient/crud_service.py, app/api/v2/routers/patients/crud.py]
tech_stack:
  added: [PatientDeletionAudit SQLAlchemy model, PostgreSQL RULE immutability pattern]
  patterns: [append-only audit table, PostgreSQL RULE for immutability, merge migration for dual-head Alembic state]
key_files:
  created:
    - backend-hormonia/app/models/patient_deletion_audit.py
    - backend-hormonia/alembic/versions/lgpd01_add_patient_deletion_audit.py
  modified:
    - backend-hormonia/app/models/__init__.py
    - backend-hormonia/app/services/patient/crud_service.py
    - backend-hormonia/app/api/v2/routers/patients/crud.py
    - backend-hormonia/tests/services/patient/test_crud_service.py
decisions:
  - "No FK from patient_deletion_audit to patients.id — audit row must survive hard-deletion of the patient"
  - "PostgreSQL RULE objects (not triggers) used for immutability — RULEs intercept at rewrite level and cannot be bypassed by superusers the way triggers can"
  - "Merge migration pattern (down_revision as tuple) chosen because codebase had two existing Alembic heads (015_rename_upload_metadata, a9c4e1d2b7f0)"
  - "PatientDeletionAudit import placed inside delete_patient() body — avoids circular import risk"
  - "deletion_reason defaults to 'Admin deletion via API' when caller omits it — backward compatible"
metrics:
  duration: "~12 min"
  completed: "2026-02-22"
  tasks_completed: 2
  files_modified: 6
---

# Phase 2 Plan 1: LGPD Patient Deletion Audit — Summary

**One-liner:** Immutable PostgreSQL audit table for LGPD Art. 16/18 compliance, written atomically inside the soft-delete transaction with PostgreSQL RULE objects blocking UPDATE/DELETE.

## What Was Built

### PatientDeletionAudit Model

New SQLAlchemy model at `backend-hormonia/app/models/patient_deletion_audit.py`:

- Columns: `id` (UUID PK), `patient_id` (UUID, NOT NULL, indexed), `deleted_by_user_id` (UUID, nullable), `deleted_by_email` (String 255, nullable), `deletion_reason` (Text, nullable), `patient_name_hash` (String 64, SHA-256 of patient name — NOT plaintext), `deleted_at` (DateTime tz-aware, NOT NULL)
- No FK to `patients.id` by design — audit row survives even if patient row is hard-deleted
- Composite indexes: `idx_pda_patient_deleted_at`, `idx_pda_deleted_at`, `idx_pda_patient_id`
- Helper: `PatientDeletionAudit.hash_name(name)` static method for consistent SHA-256 hashing

### Alembic Migration

`backend-hormonia/alembic/versions/lgpd01_add_patient_deletion_audit.py`:

- Merge migration: `down_revision = ("015_rename_upload_metadata", "a9c4e1d2b7f0")` — merges both Alembic heads into a single chain for future LGPD migrations
- Creates `patient_deletion_audit` table with all required columns
- Creates 3 indexes (patient_id, patient_id+deleted_at composite, deleted_at)
- Creates two PostgreSQL RULE objects for immutability:
  - `patient_deletion_audit_no_update` — blocks all UPDATE operations
  - `patient_deletion_audit_no_delete` — blocks all DELETE operations
- `downgrade()` drops rules first, then indexes, then table

### Service Hook in delete_patient()

`backend-hormonia/app/services/patient/crud_service.py`:

- `delete_patient()` now accepts keyword-only optional params: `performed_by_user_id`, `performed_by_email`, `deletion_reason`
- All params are `Optional` with `None` defaults — fully backward compatible with existing callers
- PatientDeletionAudit INSERT is the **first operation** in the transaction block (line 278), before `patient.deleted_at` is set (line 293)
- `hashlib` added to stdlib imports at module level

### Router User Context

`backend-hormonia/app/api/v2/routers/patients/crud.py`:

- `delete_patient` endpoint now extracts `performer_uuid` (from `user_id_str`) and `performer_email` (from `current_user`) before calling the service
- Handles both dict and model-instance user representations
- Passes `performed_by_user_id` and `performed_by_email` to service

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test assertion too strict after audit record was added**

- **Found during:** Task 2 verification
- **Issue:** `test_delete_patient_success` asserted `mock_db_session.add.assert_called_once_with(sample_patient)`. After adding the LGPD audit INSERT, `session.add()` is now called twice — first for `PatientDeletionAudit`, then for `patient`. The test failed.
- **Fix:** Updated assertion to `assert_any_call(sample_patient)` and `call_count >= 2`, with a docstring explaining the expected two-call behavior.
- **Files modified:** `tests/services/patient/test_crud_service.py`
- **Commit:** 829860e6

**2. [Rule 3 - Blocking] Two Alembic heads existed**

- **Found during:** Task 1 migration creation
- **Issue:** Running `python3` to discover Alembic heads revealed two heads: `015_rename_upload_metadata` and `a9c4e1d2b7f0`. Setting `down_revision` to a single head would leave the other branch disconnected.
- **Fix:** Used Alembic merge pattern: `down_revision = ("015_rename_upload_metadata", "a9c4e1d2b7f0")` — standard Alembic tuple syntax that merges both branches.
- **Files modified:** `lgpd01_add_patient_deletion_audit.py` (created)
- **Commit:** eb32da58

## Verification Results

| Check | Result |
|-------|--------|
| `from app.models.patient_deletion_audit import PatientDeletionAudit` | PASS |
| Migration has `CREATE TABLE` + `CREATE RULE` | PASS |
| Migration has valid `revision` and `down_revision` | PASS |
| Audit INSERT line (278) < soft-delete line (293) | PASS |
| `grep "PatientDeletionAudit" crud_service.py` | PASS |
| `grep "performed_by" crud.py` | PASS |
| `pytest tests/services/patient/test_crud_service.py` | PASS (48/48) |
| `pytest tests/services/patient/ tests/unit/api/v2/` | PASS (99/99) |

## Commits

| Task | Hash | Message |
|------|------|---------|
| Task 1: Model + Migration | eb32da58 | feat(02-01): add PatientDeletionAudit model and Alembic migration |
| Task 2: Service hook + Router | 829860e6 | feat(02-01): hook PatientDeletionAudit into delete_patient() and router |

## Self-Check: PASSED
