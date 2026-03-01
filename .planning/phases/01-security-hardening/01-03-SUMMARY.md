---
phase: 01-security-hardening
plan: 03
subsystem: config
tags: [pydantic, settings, validation, model_validator, security, debug, startup]

# Dependency graph
requires: []
provides:
  - "BaseAppSettings.validate_debug_flag: @model_validator blocking APP_ENABLE_DEBUG=True in production/staging"
  - "tests/test_settings_validation.py: 10 tests covering SEC-04 debug flag guardrail"
affects:
  - "02-lgpd-compliance"
  - "Any phase that reads BaseAppSettings in production deployments"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "@model_validator(mode='after') for startup security guardrail in BaseAppSettings"
    - "Direct BaseAppSettings import in tests to bypass module-level Settings() instantiation"

key-files:
  created:
    - "backend-hormonia/tests/test_settings_validation.py"
  modified:
    - "backend-hormonia/app/config/settings/base.py"
    - "backend-hormonia/tests/config/test_production_config.py"

key-decisions:
  - "Placed validate_debug_flag in BaseAppSettings (not SecuritySettings) so ALL Settings subclasses inherit the guard without requiring SecuritySettings"
  - "Blocked both 'production' and 'prod' (short alias) and 'staging' — mirrors real-world deployment naming conventions"
  - "Tests import BaseAppSettings directly from base module to avoid triggering module-level Settings() instantiation"

patterns-established:
  - "Startup guardrail pattern: @model_validator(mode='after') raises ValueError to block dangerous config combos before the app accepts traffic"
  - "Test isolation pattern: import from app.config.settings.base (not app.config.settings) to test BaseAppSettings in isolation"

requirements-completed:
  - SEC-04

# Metrics
duration: 6min
completed: 2026-02-22
---

# Phase 1 Plan 03: Debug Flag Startup Guardrail Summary

**Pydantic @model_validator(mode='after') in BaseAppSettings blocks startup when APP_ENABLE_DEBUG=True in production/staging, with 10 tests covering all environment combinations**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-22T16:33:46Z
- **Completed:** 2026-02-22T16:39:42Z
- **Tasks:** 2
- **Files modified:** 3 (base.py modified, test_settings_validation.py created, test_production_config.py auto-fixed)

## Accomplishments

- Added `validate_debug_flag` `@model_validator(mode="after")` to `BaseAppSettings` that raises `ValueError` at startup when `APP_ENABLE_DEBUG=True` in `production`, `prod`, or `staging` environments
- Created `tests/test_settings_validation.py` with 10 test cases covering the full SEC-04 requirement: production blocked, staging blocked, prod-alias blocked, development allowed, dev-alias allowed, test allowed, testing-alias allowed, debug=false-in-production allowed, and error message verification
- Auto-fixed existing `test_production_debug_false` in `tests/config/test_production_config.py` whose regex `"APP_ENABLE_DEBUG must be False"` no longer matched after our new validator fires first with `"APP_ENABLE_DEBUG=True is not allowed"`

## Task Commits

Each task was committed atomically:

1. **Task 1: Add validate_debug_flag model_validator to BaseAppSettings** - `befb78ee` (feat)
2. **Task 2: Add tests for debug flag validation in production settings** - `9cb162e7` (test)

**Plan metadata:** (see final docs commit)

## Files Created/Modified

- `backend-hormonia/app/config/settings/base.py` - Added `validate_debug_flag` `@model_validator(mode="after")` after field definitions; raises `ValueError` for production/staging, warns for unknown environments, passes silently for development/test
- `backend-hormonia/tests/test_settings_validation.py` - New file: 10 tests covering all SEC-04 scenarios (prod/staging/prod-alias blocked; dev/dev-alias/test/testing-alias allowed; debug=false OK; error message check)
- `backend-hormonia/tests/config/test_production_config.py` - Auto-fixed: `match="APP_ENABLE_DEBUG must be False"` → `match="APP_ENABLE_DEBUG=True is not allowed"` to align with new validator

## Decisions Made

- `validate_debug_flag` lives in `BaseAppSettings` (not `SecuritySettings`) so every Settings subclass inherits the guard without needing to explicitly inherit from SecuritySettings
- Both `"production"` and `"prod"` (short alias) and `"staging"` are blocked — mirrors real-world CI/CD naming where `prod` is a common short form
- Tests use `from app.config.settings.base import BaseAppSettings` (direct module import) rather than `from app.config.settings import BaseAppSettings` to avoid triggering the module-level `settings = Settings()` call in `__init__.py`
- Validator follows the exact same `@model_validator(mode="after")` pattern as `validate_secret_key` in `SecuritySettings` for consistency

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_production_debug_false regex mismatch in existing test**
- **Found during:** Task 1 verification (running existing tests after adding the validator)
- **Issue:** `tests/config/test_production_config.py::test_production_debug_false` used `match="APP_ENABLE_DEBUG must be False"` — the old error message from the non-validator `validate_production_config()` method. Our new `@model_validator` fires earlier at pydantic validation time with a different message: `"APP_ENABLE_DEBUG=True is not allowed in 'production' environment."`. The existing test failed with regex mismatch.
- **Fix:** Updated the `match=` string to `"APP_ENABLE_DEBUG=True is not allowed"` — still correctly tests the same behavior (ValueError on production+debug=true), now matching the actual error message.
- **Files modified:** `backend-hormonia/tests/config/test_production_config.py`
- **Verification:** All 3 tests in `test_production_config.py` pass (confirmed with pytest run)
- **Committed in:** `befb78ee` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 x Rule 1 - Bug)
**Impact on plan:** Auto-fix necessary for test suite correctness. The test was testing the right behavior (ValueError on production+debug=true) but with the wrong expected message after our new validator replaced the earlier message source. No scope creep.

## Issues Encountered

- The plan's inline verification script `APP_ENVIRONMENT=production APP_ENABLE_DEBUG=true python3 -c "from app.config.settings.base import BaseAppSettings; ..."` showed an exit code 1 because the module import path goes through `app/config/__init__.py` which has a module-level `settings = Settings()` that immediately fails with our validator. This is the CORRECT behavior — the application refuses to start. The test strategy used `BaseAppSettings` directly imported from `app.config.settings.base` to test in isolation without triggering the full Settings instantiation.

## User Setup Required

None - no external service configuration required. This is a startup guardrail — it only affects deployments that incorrectly set `APP_ENABLE_DEBUG=True` in production/staging environments.

## Next Phase Readiness

- SEC-04 requirement complete: `APP_ENABLE_DEBUG=True` is now blocked at startup in production/staging
- All 13 related tests pass (10 new + 3 existing)
- Phase 1 Plan 3 of 3 complete — Phase 1 (Security Hardening) execution finished

---
*Phase: 01-security-hardening*
*Completed: 2026-02-22*
