# Phase 19: Saga & Integrity Splits - Context

**Gathered:** 2026-02-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Deliver Phase 19 by splitting `saga/orchestrator.py`, `saga/compensation.py`, and `flow_integrity.py` into focused modules (target `<500` lines per file), while preserving current runtime behavior and caller compatibility through legacy-path shims.

</domain>

<decisions>
## Implementation Decisions

### Split Boundaries
- `saga/orchestrator`: split into orchestrator, step-executor, and metrics-focused modules.
- `saga/compensation`: split into compensation-chain logic and step-handler modules.
- `flow_integrity`: split into corruption-detection and recovery-action modules.
- Use `*_pkg` package structure for split modules, matching prior phase conventions.

### Compatibility Contract
- Keep backward compatibility at legacy import paths during Phase 19.
- Do not add deprecation warnings in this phase.

### Execution Sequencing
- Execute in this order: orchestrator -> compensation -> integrity.
- Keep commits atomic per split plan.
- Run quality gates per plan (not only at phase end).
- If a blocker appears and blocks the plan, fix it immediately and document the deviation.

### Validation and Evidence
- Require contract tests + targeted regressions + line-budget checks for each plan.
- Enforce `<500` lines per new split module file with no exceptions.
- Ensure coverage includes all three domains (orchestrator, compensation, integrity).
- Keep SUMMARY files detailed, including evidence, commands, deviations, and blockers.

### Claude's Discretion
- Runtime parity implementation details are delegated to Claude, with strict observable behavior parity as default.
- Public export strategy details are delegated to Claude, with explicit `__all__` whitelisting as default.

</decisions>

<specifics>
## Specific Ideas

- Keep this phase strictly focused on refactor/split scope with no new capability additions.
- Communication preference for this collaboration: Portuguese.

</specifics>

<deferred>
## Deferred Ideas

- Full migration to remove legacy shim paths and delete legacy compatibility code after downstream callers are migrated (future phase/backlog item).

</deferred>

---

*Phase: 19-saga-integrity-splits*
*Context gathered: 2026-02-26*
