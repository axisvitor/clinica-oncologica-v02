# Phase 23: Service Migration - Context

**Gathered:** 2026-02-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate shared services that are invoked from API context so they accept `AsyncSession` and execute non-blocking DB operations, while services used exclusively by Celery remain on sync `Session`.

</domain>

<decisions>
## Implementation Decisions

### Caller compatibility contract
- Preserve existing service method behavior and external call expectations during migration.
- Avoid breaking argument names/order and returned data shapes at existing call sites.
- If async adaptation requires helper methods, keep compatibility wrappers so current callers continue to work.

### API and Celery coexistence policy
- Shared services invoked from API context become async-capable and accept `AsyncSession` via DI constructor pattern.
- Services exclusively used by Celery remain sync and continue using `Session`.
- For dual-use services, keep explicit async paths for API calls and sync-compatible paths for Celery workers; do not use event-loop bridging hacks in worker code.

### Error semantics and behavior parity
- Preserve current business validation behavior and error meanings while migrating DB access.
- Keep exception categories/messages stable unless a change is required to correct incorrect behavior.
- Prioritize behavior parity over style-only refactors in this phase.

### Rollout and acceptance strictness
- Migrate by service group (patient, quiz, analytics, communication, auth/session, infrastructure, `flow_monitoring_pkg`) with automated checks after each group.
- Consider each group complete only when API-context usage is non-blocking and group-level automated checks pass.
- End phase with cross-group verification focused on zero `MissingGreenlet` regressions in migrated service paths.

### Claude's Discretion
- Exact method naming for async/sync adapters and wrappers.
- Internal query refactor shape (`db.execute(select(...))` helper patterns) as long as behavior parity is preserved.
- Test file organization and fixture reuse strategy.

</decisions>

<specifics>
## Specific Ideas

- User delegated implementation decisions to Claude: "Te dou liberdade total para decidir o melhor pro sistema."
- Guiding principle for defaults: maximize API async safety and migration reliability while minimizing breaking changes for existing callers.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 23-service-migration*
*Context gathered: 2026-02-27*
