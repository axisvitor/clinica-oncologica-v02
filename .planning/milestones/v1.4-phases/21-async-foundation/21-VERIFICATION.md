---
phase: 21-async-foundation
verified: 2026-02-27T00:06:44Z
status: gaps_found
score: 0/4 must-haves verified
gaps:
  - truth: "All API routers declare AsyncSession as their session dependency type (no router imports get_db for request handling)"
    status: failed
    reason: "Large portions of API routers still import and use sync get_db."
    artifacts:
      - path: "backend-hormonia/app/api/v2"
        issue: "90 matches for `from app.database import get_db`; many handlers still use `Depends(get_db)`"
    missing:
      - "Migrate all router DB dependencies from `get_db`/`Session` to `get_async_db`/`AsyncSession`"
      - "Remove remaining sync `get_db` imports from API router modules"
  - truth: "Every service consumed by an API router has a corresponding async factory function in dependencies/"
    status: failed
    reason: "Only three async factories exist and they are not adopted by API routers."
    artifacts:
      - path: "backend-hormonia/app/dependencies/patient_services.py"
        issue: "Factory exists but no router usage found"
      - path: "backend-hormonia/app/dependencies/flow_services.py"
        issue: "Factories exist but no router usage found"
      - path: "backend-hormonia/app/api"
        issue: "Many routers still use sync service dependencies (e.g., get_patient_service, get_flow_management_service)"
    missing:
      - "Add async factories for all router-consumed services"
      - "Wire routers to async factories instead of sync service providers"
  - truth: "Services shared between API and Celery accept either Session or AsyncSession via a DI constructor pattern without branching logic in business code"
    status: failed
    reason: "DualSessionMixin exists but is not adopted by shared services; async methods still contain sync ORM calls."
    artifacts:
      - path: "backend-hormonia/app/core/database/dual_session.py"
        issue: "No service inheritance/usage found outside package exports"
      - path: "backend-hormonia/app/services/data_integrity_monitoring.py"
        issue: "Contains TODO(async-migration) and sync `self.db.query(...)` inside async methods"
      - path: "backend-hormonia/app/services/flow_alerts.py"
        issue: "Contains TODO(async-migration) and sync `self.db.query(...)` inside async methods"
    missing:
      - "Migrate shared services to constructor signatures supporting Session | AsyncSession"
      - "Adopt DualSessionMixin (or equivalent) in shared services and replace sync calls in async code paths"
---

# Phase 21: Async Foundation Verification Report

**Phase Goal:** The DI infrastructure is in place so that all API routers can use get_async_db, all services have async factory functions, and dual-mode session support exists for services shared between API and Celery — without breaking any Celery worker paths.
**Verified:** 2026-02-27T00:06:44Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | All API routers declare `AsyncSession` and avoid `get_db` | ✗ FAILED | `backend-hormonia/app/api/v2` has 90 `from app.database import get_db` matches; many handlers still `Depends(get_db)` |
| 2 | Every API-consumed service has an async factory in `dependencies/` | ✗ FAILED | Only 3 async factories are defined in `backend-hormonia/app/dependencies/patient_services.py` and `backend-hormonia/app/dependencies/flow_services.py`; no router usage found |
| 3 | Celery tasks stay sync with no worker-path regressions | ? UNCERTAIN | `backend-hormonia/scripts/check_async_isolation.py` passes and catches synthetic violations (exit codes `1/0/1/0`), but full Celery integration run for `MissingGreenlet` was not executed |
| 4 | Shared API/Celery services support `Session | AsyncSession` via DI pattern | ✗ FAILED | `DualSessionMixin` exists but no service adopts it; `backend-hormonia/app/services/data_integrity_monitoring.py` and `backend-hormonia/app/services/flow_alerts.py` still contain `TODO(async-migration)` + sync `self.db.query(...)` in async methods |

**Score:** 0/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `backend-hormonia/app/core/database/async_engine.py` | Canonical async engine/session/get_async_db | ✓ VERIFIED | Exists, substantive, exported and shimmed via `backend-hormonia/app/database.py` |
| `backend-hormonia/app/core/database/dual_session.py` | DualSessionMixin helpers for sync/async branching | ⚠️ ORPHANED | Exists and substantive, but no service adoption detected |
| `backend-hormonia/app/core/database/__init__.py` | Re-export async infra + DualSessionMixin | ✓ VERIFIED | Exports present and importable |
| `backend-hormonia/app/database.py` | Backward-compatible async shim, sync code untouched | ✓ VERIFIED | Async section is shim import from canonical module |
| `backend-hormonia/scripts/check_async_isolation.py` | CI guard for task async DB leakage | ✓ VERIFIED | Exists, scans `app/tasks`, and correctly fails/passes on synthetic tests |
| `backend-hormonia/app/dependencies/patient_services.py` | Async patient-domain factory | ⚠️ ORPHANED | Exists and re-exported, but not consumed by routers |
| `backend-hormonia/app/dependencies/flow_services.py` | Async flow-domain factories | ⚠️ ORPHANED | Exists and re-exported, but not consumed by routers |
| `backend-hormonia/app/dependencies/__init__.py` | Re-exports async factories and canonical get_async_db | ✓ VERIFIED | Re-exports present alongside sync dependencies |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `backend-hormonia/app/core/database/async_engine.py` | `backend-hormonia/app/database.py` | Shim re-export of async symbols | ✓ WIRED | `app/database.py` imports `get_async_db`, `get_async_engine`, `get_async_session_factory`, `AsyncSessionLocal` from canonical module |
| `backend-hormonia/app/core/database/dual_session.py` | `backend-hormonia/app/services/data_integrity_monitoring.py` | Service inheritance + helper usage | ✗ NOT_WIRED | No `DualSessionMixin` usage outside `app/core/database` package |
| `backend-hormonia/scripts/check_async_isolation.py` | `backend-hormonia/app/tasks/` | Recursive task scan and violation detection | ✓ WIRED | Uses `tasks_dir.rglob("*.py")`; runtime check returns clean on baseline and fails on injected violations |
| `backend-hormonia/scripts/check_async_isolation.py` | `backend-hormonia/scripts/check_agent_run_calls.py` | Same lint-script structure | ✓ WIRED | Matching docstring/comment skipping and deterministic exit-code behavior |
| `backend-hormonia/app/dependencies/patient_services.py` | `backend-hormonia/app/core/database/async_engine.py` | `Depends(get_async_db)` injection | ✓ WIRED | Imports canonical `get_async_db` from `app.core.database` |
| `backend-hormonia/app/dependencies/flow_services.py` | `backend-hormonia/app/core/database/async_engine.py` | `Depends(get_async_db)` injection | ✓ WIRED | Imports canonical `get_async_db` from `app.core.database` |
| `backend-hormonia/app/dependencies/*_services.py` | API routers | Async factory adoption in handlers | ✗ NOT_WIRED | No router references to `get_async_data_integrity_service`, `get_async_flow_alerts_service`, or `get_async_flow_analytics_service` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| FOUND-01 | 21-01, 21-03 | All API routers use `get_async_db`/`AsyncSession` instead of `get_db` | ✗ BLOCKED | 90 `from app.database import get_db` matches remain under `backend-hormonia/app/api/v2` |
| FOUND-02 | 21-03 | Async factory functions exist in `dependencies/` for all API-consumed services | ✗ BLOCKED | Only three async factories exist; routers still depend on many sync service providers |
| FOUND-03 | 21-02 | Celery tasks remain sync with no worker-path regression | ? NEEDS HUMAN | Static checks pass (`check_async_isolation.py`, task scan), but full Celery integration validation for zero `MissingGreenlet` not executed |
| FOUND-04 | 21-01, 21-03 | Shared services accept `Session` or `AsyncSession` via DI constructor pattern | ✗ BLOCKED | `DualSessionMixin` not adopted; shared services still run sync ORM calls in async methods |

Orphaned requirement IDs for Phase 21: none (all `FOUND-01..FOUND-04` are declared in phase plan frontmatter).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| `backend-hormonia/app/services/data_integrity_monitoring.py` | 183 | `TODO(async-migration)` + sync `self.db.query(...)` in async flow | 🛑 Blocker | Shared service not async-safe, blocks FOUND-04 outcome |
| `backend-hormonia/app/services/flow_alerts.py` | 34 | `TODO(async-migration)` + sync `self.db.query(...)` in async flow | 🛑 Blocker | Shared service not async-safe, blocks FOUND-04 outcome |
| `backend-hormonia/app/core/database/dual_session.py` | 18 | Implemented but not adopted by services | ⚠️ Warning | Foundation exists but goal-level behavior is not wired |

### Human Verification Required

### 1. Celery Integration MissingGreenlet Check

**Test:** Run Celery worker integration paths that execute representative tasks (messaging, flow, quiz) under normal workload.
**Expected:** Zero `MissingGreenlet` errors and no async DB dependency leakage in worker logs.
**Why human:** Requires runtime process orchestration and behavioral verification not provable from static code scan alone.

### Gaps Summary

Phase 21 delivered core infrastructure artifacts (canonical async DB module, shim exports, async isolation script, and initial async factories), but the phase goal is not achieved at outcome level. The repository still has broad sync router dependencies (`get_db`), async factory coverage is incomplete and currently unwired to routers, and shared services have not adopted the dual-mode session pattern. Celery static guardrails are in place and functioning, but full runtime worker-path verification remains pending.

---

_Verified: 2026-02-27T00:06:44Z_
_Verifier: Claude (gsd-verifier)_
