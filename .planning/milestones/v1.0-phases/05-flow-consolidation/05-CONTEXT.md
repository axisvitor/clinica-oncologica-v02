# Phase 5: Flow Consolidation - Context

**Gathered:** 2026-02-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Eliminate the dual flow system that causes silent divergence of patient state. Choose one canonical system, implement a FlowDispatcher facade with feature-flag routing, decommission the losing system, and write integration tests covering the unified flow + alert pipeline end-to-end. This phase delivers the full lifecycle: facade + routing + tests + decommission -- not just setup.

</domain>

<decisions>
## Implementation Decisions

### Canonical system choice
- Claude's discretion: analyze both systems (production flow_core.py day-based vs QW-021 manager.py step-based) and recommend based on code quality, production usage, migration risk, and data model maturity
- Claude's discretion: evaluate whether any concepts from the losing system are worth preserving
- Claude's discretion: determine if data migration between systems is needed

### Migration strategy
- Feature flag routes by patient type: new patients go to canonical system immediately, existing patients stay on current system until migrated
- All patients should eventually be migrated to the canonical system, even mid-flow
- Claude's discretion: routing audit logging during transition period
- Claude's discretion: timeline for full decommission

### Decommissioning
- Full code deletion of the losing system -- not tombstoned (breaking from project's tombstone pattern for this case)
- Decommissioning happens within Phase 5, not deferred to a later phase
- Claude's discretion: whether callers go through FlowDispatcher or import canonical directly
- Claude's discretion: database table/column cleanup for losing system artifacts

### Integration testing
- Tests must run against real PostgreSQL (not mocked/in-memory)
- Claude's discretion: which patient flow scenarios to cover (onboarding, mid-flow, completion, edge cases)
- Claude's discretion: whether alert pipeline is included per FLOW-03 requirement scope
- No specific edge cases mandated -- Claude identifies them from the flow state model

### Claude's Discretion
- Which flow system is canonical (production vs QW-021) -- based on analysis of both
- Whether to port concepts from losing system
- FlowDispatcher as temporary migration tool vs permanent facade
- Data parity investigation and migration needs
- Routing audit logging during transition
- Import path for callers (dispatcher vs direct canonical)
- Database artifact cleanup for losing system
- Critical patient scenarios for integration tests
- Alert pipeline inclusion scope for FLOW-03
- Edge case identification from flow state model

</decisions>

<specifics>
## Specific Ideas

- New-vs-existing patient routing for feature flag (not percentage-based ramp)
- Full deletion over tombstoning for the decommissioned system
- Complete lifecycle in one phase: no "set up now, remove later" split
- Real PostgreSQL for integration tests -- no mocking the database layer

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 05-flow-consolidation*
*Context gathered: 2026-02-22*
