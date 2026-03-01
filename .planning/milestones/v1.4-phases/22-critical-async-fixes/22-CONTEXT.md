# Phase 22: Critical Async Fixes - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Repair the three highest-priority production bugs where async methods call sync DB operations in `data_integrity_monitoring`, `flow_alerts`, and `flow_dashboard_pkg`. Eliminate `MissingGreenlet` under async load. Keep Celery sync paths unchanged and out of scope.

</domain>

<decisions>
## Implementation Decisions

### Failure behavior in async paths
- Apply strict async-safe DB access in targeted methods (`await db.execute(select(...))`) with no sync ORM calls in async methods.
- Do not hide real DB failures with silent fallbacks; preserve existing API/service error semantics.
- Treat `MissingGreenlet` as a defect to eliminate, not a recoverable runtime condition.

### Behavior compatibility policy
- Preserve existing request/response contracts and business behavior for affected endpoints/services.
- Limit changes to async-safety and session-type compatibility; avoid feature or payload changes.
- Use minimal-risk refactoring: replace sync query primitives with async equivalents while keeping method responsibilities intact.

### Fix scope within touched modules
- Mandatory scope for this phase:
  - `app/services/data_integrity_monitoring.py` (all 5 async methods)
  - `app/services/flow_alerts.py` (all 5 async methods)
  - `app/services/flow_dashboard_pkg/service.py` (mixin/session hierarchy accepting `AsyncSession`)
- If nearby async paths in these same modules still use sync DB operations, fix them in this phase to prevent immediate relapse.
- Do not expand to unrelated modules; capture anything else as deferred for later phases.

### Definition of done and proof level
- Required proof includes targeted automated tests covering repaired async paths in all three modules.
- Required runtime evidence: async load scenarios exercising these paths log zero `MissingGreenlet` exceptions.
- Required code-level validation: no `db.query()` (or equivalent sync DB operations) remain inside async execution paths of these modules.
- Required regression guard: Celery worker sync paths continue functioning without async-session regressions.

### Claude's Discretion
- Exact query composition details (`select`, joins, helper extraction) as long as behavior and contracts remain unchanged.
- Test implementation details (fixtures, stubs, and load harness shape) as long as verification is automated and reproducible.
- Minor internal cleanup strictly tied to async-safety readability may be included when it lowers risk.

</decisions>

<specifics>
## Specific Ideas

- User directive: "realizar as acoes mais corretas e profissionais possiveis" (delegate decision quality to Claude).
- Prioritize production safety, deterministic verification, and low-regression execution.

</specifics>

<deferred>
## Deferred Ideas

- Any broader service/router migration beyond the three target modules belongs to subsequent roadmap phases (23+).
- Any new feature behavior (new endpoints, payload changes, new analytics capabilities) is out of scope for Phase 22.

</deferred>

---

*Phase: 22-critical-async-fixes*
*Context gathered: 2026-02-26*
