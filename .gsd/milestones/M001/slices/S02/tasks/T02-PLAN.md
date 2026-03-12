# T02: Admin flow operations and failed-op visibility

**Slice:** S02 — **Milestone:** M001

## Description

Give administrators manual flow control tools and failed-operations visibility.

Purpose: When auto-recovery is insufficient or operators need to intervene directly, they need API endpoints to reset, advance, or unstick specific patient flows. They also need to see which flows have experienced failures (delivery failures, mismatch resets) to triage proactively.

Output: `flow_ops.py` admin router with 4 endpoints, Pydantic schemas, router registration, and full test coverage.

## Must-Haves

- [ ] "An admin can reset a specific patient flow to clear awaiting_response and mismatch counters via POST /admin-ext/flow-ops/{patient_id}/reset"
- [ ] "An admin can advance a specific patient flow to the next day via POST /admin-ext/flow-ops/{patient_id}/advance"
- [ ] "An admin can unstick a specific patient flow by clearing stuck state and recovery counters via POST /admin-ext/flow-ops/{patient_id}/unstick"
- [ ] "An admin can view failed flow operations (delivery failures, mismatch resets) via GET /admin-ext/flow-ops/failed"
- [ ] "All admin flow operations are audit-logged via AuditService"

## Files

- `backend-hormonia/app/api/v2/routers/admin_extensions/flow_ops.py`
- `backend-hormonia/app/api/v2/routers/admin_extensions/__init__.py`
- `backend-hormonia/app/schemas/v2/admin_extensions.py`
- `backend-hormonia/tests/unit/api/test_admin_flow_ops.py`
