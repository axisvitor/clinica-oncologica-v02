# Retrospective

Living retrospective document. Updated after each milestone completion.

---

## Milestone: v1.4 — AsyncSession & Test Stability

**Shipped:** 2026-02-28
**Phases:** 9 | **Plans:** 54
**Timeline:** 3 days (2026-02-26 → 2026-02-28)

### What Was Built

- Fixed alerts.type column mapping, unblocking the test suite
- Established async DI foundation (get_async_db, DualSessionMixin, async engine, CI guard)
- Migrated 3 critical services (data_integrity, flow_alerts, flow_dashboard) from sync to async-safe
- Migrated all 7 shared service groups to support AsyncSession from API context
- Converted all 46+ API router files across 9 groups to AsyncSession — zero Depends(get_db) remaining
- Stabilized test fixtures with SyncToAsyncSessionAdapter supporting full AsyncSession contract
- Closed audit gaps with Phase 28 (adapter wrappers + enhanced_reports.py migration)

### What Worked

- **Phase dependency ordering** — Schema fix (Phase 20) → Foundation (21) → Services (22-23) → Routers (24-26) → Tests (27) → Gap closure (28) was exactly the right execution order. No backtracking.
- **Source-level regression tests** — Using importlib/inspect to assert async patterns avoided coupling to live DB fixtures. Fast, deterministic, catches import-level regressions.
- **Dual-mode DI pattern** — Session|AsyncSession constructor typing allowed services to work with both API (async) and Celery (sync) callers without code duplication.
- **Audit-driven gap closure** — Running `/gsd:audit-milestone` before completion surfaced real gaps (adapter wrappers, enhanced_reports.py) that would have been missed.
- **Wave-based plan execution** — Phases with 9-16 plans (23, 26) executed smoothly because dependency ordering was pre-planned.

### What Was Inefficient

- **14 unchecked ROADMAP checkboxes** — Plans had SUMMARY files but ROADMAP.md checkboxes weren't updated, creating doc inconsistency the audit flagged.
- **Stale VERIFICATION.md for Phase 21** — Run too early (before downstream phases completed), producing a misleading 0/4 score that required manual analysis during audit.
- **Phase 24 grew from 6 to 7 plans** — Gap closure plan 24-07 was needed because flow_templates.py verification was missed in initial scope.
- **Phase 27 gap closure (plans 27-05, 27-06)** — Pagination test and literal token issues required two additional plans. Could have been caught in initial plan-check.

### Patterns Established

- **Inlined async SQL in routers** — When sync repositories can't accept AsyncSession, inline the SQL in the router handler. Repos stay sync for Celery compat.
- **Awaitable-resolution helpers** — `_resolve(result)` pattern handles both sync return values and coroutines, enabling Session|AsyncSession dual paths.
- **Test adapter explicit wrappers** — Never rely on __getattr__ for awaitable methods. Always implement explicit async wrappers (delete, add, scalars, get, begin_nested).
- **Source-level regression lock** — Assert module source code doesn't contain banned patterns (db.query, Depends(get_db)) instead of running live tests.

### Key Lessons

1. Run VERIFICATION after all gap closure plans, not just after the initial execution wave.
2. Keep ROADMAP.md checkboxes in sync with SUMMARY file creation — automate or add to phase completion checklist.
3. Milestone audit is valuable even for seemingly complete milestones — it found 2 real code gaps and 2 doc inconsistencies.
4. Async migration is systematic, not creative — the pattern (select/execute, awaitable resolution, regression test) repeats identically across 54 plans.

### Cost Observations

- Sessions: ~15-20 across 3 days
- Largest phase: Phase 26 (16 plans, largest single phase in project history)
- Smallest phase: Phase 20 (1 plan, surgical schema fix)

---

## Milestone: v1.5 — Saga Orchestrator Deep Dive

**Shipped:** 2026-03-01
**Phases:** 4 | **Plans:** 14
**Timeline:** 2 days (2026-02-28 → 2026-03-01)

### What Was Built

- Saga orchestrator modules verified async-safe with dual-session DB adapters and SagaDBAdapterMixin extraction
- Two onboarding paths independently traced end-to-end across 15+ handoffs with contract verification
- Pause/resume/cancel semantics traced with dual pause-key divergence documented
- Compensation integrity proven: step mapping, reverse-order rollback (4->3->1), transaction boundaries, idempotency
- 40+ new tests covering happy path, compensation, timeout/concurrency/retry, shim contracts, flow lifecycle
- Documentation-code contract parity enforced through gap closure plans (30-04, 32-05)

### What Worked

- **Review-first, test-second approach** — Phases 29-30 audited and traced before Phases 31-32 wrote tests. Tests targeted real contracts, not assumptions.
- **Static source verification tests** — Pattern from v1.4 extended to compensation integrity: asserting source code patterns (flush-only, rollback-before-failure) without DB fixtures.
- **Gap closure as standard practice** — Plans 30-04 and 32-05 closed contract-documentation drift proactively without scope creep.
- **Contract-reconciliation pattern** — When trace findings diverged from roadmap/requirements wording, updated the docs to match implementation truth instead of forcing runtime rewiring.
- **Mock-driven saga tests** — MagicMock DB with model-keyed query routing gave deterministic unit-level saga coverage without requiring integration database.

### What Was Inefficient

- **No milestone audit ran** — Unlike v1.4, v1.5 completed without a formal `/gsd:audit-milestone`. All requirements were checked off and phases complete, so risk was low, but the pattern should be maintained.
- **32-05 gap closure was avoidable** — Plan 32-02 narrative used soft-delete language while production handler uses hard-delete. Catching this during plan-check would have saved a gap closure plan.
- **gsd-tools path mismatch** — Every executor bootstrap hit a `$HOME/.claude/...` vs repo-local path issue. Minor but repeated across all phases.

### Patterns Established

- **Dual-session DB adapter mixin** — Extract async/sync DB helpers into inherited mixin to keep orchestrator modules within LOC budgets.
- **Handoff trace documentation** — Every integration trace records caller, callee signature, parameter compatibility, return usage, session type.
- **Compensation contract tests** — Active forward steps mapped to callable handlers; deprecated steps documented with source assertions.
- **Model-keyed mock_db.query** — Side effects keyed on queried model class allow realistic per-handler query results.

### Key Lessons

1. Review/audit milestones benefit from tracing before testing — trace findings inform test design.
2. Contract-reconciliation (updating docs to match implementation) is safer than forcing implementation changes to match docs.
3. Plan narrative language matters — soft-delete vs hard-delete drift caused an extra gap closure plan. Plan-check should catch semantic mismatches.
4. Milestone was the most efficient yet (7 plans/day average) because scope was focused: review, trace, test — no new features to design.

### Cost Observations

- Sessions: ~5-8 across 2 days
- Largest phase: Phase 32 (5 plans, test coverage)
- Smallest phase: Phase 31 (2 plans, surgical compensation verification)
- Notable: Most plans were documentation/test-only — minimal production code changes

---

## Cross-Milestone Trends

| Metric | v1.0 | v1.1 | v1.2 | v1.3 | v1.4 | v1.5 |
|--------|------|------|------|------|------|------|
| Phases | 5 | 4 | 4 | 6 | 9 | 4 |
| Plans | 13 | 10 | 16 | 31 | 54 | 14 |
| Days | 1 | 1 | 1 | 2 | 3 | 2 |
| Plans/day | 13 | 10 | 16 | 15.5 | 18 | 7 |
| Net LOC | -9,314 | +4,664 | +7,680 | +5,472 | +20,503 | +7,166 |
| Commits | 38 | 30+ | 72 | 123 | 199 | 53 |
| Had audit? | No | No | No | No | Yes | No |
| Gap closure plans | 0 | 0 | 0 | 0 | 2 | 2 |

**Observations:**
- Plans/day dropped in v1.5 (7 vs 18) because plans were audit/trace-heavy, not mechanical migration patterns like v1.4
- v1.5 produced +7k LOC almost entirely in documentation and tests — zero new production features
- Gap closure plans (30-04, 32-05) continue as a healthy pattern for catching contract drift
- Cumulative: 32 phases, 138 plans across 6 milestones in 8 days
- Review/audit milestones (v1.5) are inherently slower in plans/day but produce high-value verification artifacts

---
*Created: 2026-02-28 after v1.4 milestone*
*Updated: 2026-03-01 after v1.5 milestone*
