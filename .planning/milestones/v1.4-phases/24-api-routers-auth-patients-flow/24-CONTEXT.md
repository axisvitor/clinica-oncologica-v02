# Phase 24: API Routers - Auth / Patients / Flow - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate auth, user, patient, physician, and flow router groups to AsyncSession-based dependencies and async-safe handler execution, while preserving endpoint contracts (paths/methods and response schemas) across the API surface.

</domain>

<decisions>
## Implementation Decisions

### API compatibility boundary
- Keep contract stability as default: same endpoints, same request/response schema shape.
- If status-code inconsistencies are found, correct them in this phase instead of deferring.
- Contract-preserving corrections are allowed; no endpoint removals or renames.

### Router migration order
- Migrate in this sequence: auth/users/roles -> patients/physicians -> flow routers.
- Sequence decision is locked; execution strategy inside each group is flexible.

### Regression evidence expectations
- Validate all changed endpoints in each router group (not only critical endpoints).
- Auth/users/roles validation must include full group behavior, including role/permission routes.
- Patients/physicians validation must include import/export routes.
- Deliver automated validation plus a short per-group summary of what was verified.

### Issue handling during migration
- If an issue is outside direct async migration scope, defer it to a dedicated later phase.
- If an issue blocks AsyncSession migration, apply the minimum fix needed to unblock and continue.

### Claude's Discretion
- Error response text and strictness policy details, as long as endpoint contracts remain stable.
- Whether optional new response fields are introduced (if any, they must not break existing schema guarantees).
- Delivery granularity inside each group and strict gating behavior between groups.
- Detailed definition of "group complete" checkpoints.
- Preference for local hotfix vs broader cleanup when both are viable.
- Format/detail level for tracking deferred issues found during migration.

</decisions>

<specifics>
## Specific Ideas

No specific external references were requested. Focus is contract-safe AsyncSession migration with clear evidence per router group.

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope.

</deferred>

---

*Phase: 24-api-routers-auth-patients-flow*
*Context gathered: 2026-02-27*
