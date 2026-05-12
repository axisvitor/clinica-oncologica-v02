---
id: T01
parent: S01
milestone: M013
key_files:
  - backend-hormonia/app/integrations/whatsapp/api/routes.py
  - backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py
key_decisions:
  - Used the existing canonical `get_current_active_admin` dependency instead of introducing any new auth scheme.
  - Kept `/api/v2/whatsapp/health` on the public router and moved all management endpoints to an included auth-gated sub-router.
duration: 
verification_result: passed
completed_at: 2026-05-12T17:24:09.449Z
blocker_discovered: false
---

# T01: Gated WhatsApp management routes behind the canonical admin-session dependency while keeping `/api/v2/whatsapp/health` public.

**Gated WhatsApp management routes behind the canonical admin-session dependency while keeping `/api/v2/whatsapp/health` public.**

## What Happened

Refactored `app.integrations.whatsapp.api.routes` to keep the existing `/whatsapp` router as the public surface and add an auth-gated `management_router` using `Depends(get_current_active_admin)`. All management route decorators were moved to the management sub-router, then included into the public router after endpoint definitions, so anonymous and non-admin callers are rejected before message-service dependencies, direct queue construction, or database-backed handlers execute. Added focused integration coverage for representative WhatsApp management operations, explicit public-health behavior, non-admin rejection, and an admin-positive mocked send operation. The tests install sentries for `get_message_service`, `MessageQueue`, and `get_async_db` to prove auth ordering, and they attach valid CSRF double-submit tokens for unsafe POSTs so middleware does not mask route-level auth behavior.

## Verification

Ran the focused WhatsApp management auth test file. The exact task command using `python` could not run in this environment because `python` is not installed (exit 127), so I reran the same pytest target with `python3`; all four focused tests passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python3 -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py -q` | 0 | ✅ pass | 26170ms |

## Deviations

Used `python3` for verification because the environment has no `python` executable. Added test-local CSRF token setup for POST requests so the route auth dependency, rather than CSRF middleware, is the exercised rejection point.

## Known Issues

None.

## Files Created/Modified

- `backend-hormonia/app/integrations/whatsapp/api/routes.py`
- `backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py`
