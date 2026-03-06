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

## Milestone: v1.6 — WuzAPI Migration

**Shipped:** 2026-03-03
**Phases:** 7 | **Plans:** 21
**Timeline:** 2 days (2026-03-01 -> 2026-03-03)

### What Was Built

- WuzAPI client with token auth, retries, rate limiting, circuit breaker, and media encoding
- Webhook stack with raw-body HMAC, Redis idempotency, LGPD opt-out, and LID DLQ routing
- Full outbound migration to WuzAPI with Evolution code tombstoned across Stack A/Stack B
- Regression gates for webhook fixtures, STOP-to-send-guard E2E, and source-level Evolution import checks
- Audit findings closed: webhook secret alignment and explicit HTTP 501 for unsupported contacts sync

### What Worked

- **Hard-cut strategy** — No dual-provider transition period reduced surface area and eliminated provider-selection logic
- **Phase structure** — Foundation (33) -> Webhook (34) -> Config (35) -> Outbound (36) -> Cleanup (37) -> Tests (38) -> Polish (39) was clean dependency ordering
- **Source-level import checks** — Evolution import blocker CI guard prevents regression from accidental re-introduction

### What Was Inefficient

- **Audit findings after completion** — Phase 39 polish (settings secret consistency + contacts sync 501) could have been caught during plan-check
- **No formal milestone audit before v1.6** — Audit file was created retroactively

### Key Lessons

1. Hard-cut provider migrations are cleaner than dual-mode transitions when the old provider is fully isolated
2. Source-level CI guards (import blockers) are the most reliable regression prevention for tombstoned code
3. Post-completion polish phases (39) consistently surface 1-2 findings that initial plans miss

### Cost Observations

- Sessions: ~8-10 across 2 days
- Notable: Mostly mechanical migration — pattern from v1.2 LangGraph tombstone applied to Evolution

---

## Milestone: v1.7 — Frontend Quality & ADK Integration

**Shipped:** 2026-03-05
**Phases:** 4 | **Plans:** 20
**Timeline:** 2 days (2026-03-03 -> 2026-03-05)

### What Was Built

- OTel instrumentation removed to unblock ADK dependency resolution in Python 3.13
- Google ADK integrated with PIISafeADKWrapper, FunctionTool + Runner dispatch, and CI guards
- Admin SPA quality hardened: Evolution remnants removed, TanStack Query polling, Prettier/ESLint stabilized
- Quiz interface quality at parity: Next 15 + ESLint 9, MSW v2, strict schema-boundary typing, green gates

### What Worked

- **Backend-then-frontend ordering** — Phases 40-41 (backend ADK) then 42-43 (frontend quality) avoided cross-domain conflicts
- **Tooling decisions made once** — ESLint 9 flat config pattern established in admin SPA (42), then mirrored to quiz (43) without redesign
- **PIISafeADKWrapper contract** — Mirroring PIISafeAgent contract for ADK made the wrapper predictable and testable

### What Was Inefficient

- **No milestone audit** — Skipped audit before completion; gap was documented but not formally verified
- **Phase 42 checkpoint overhead** — Required explicit user approval signals for checkpoint closure, adding prompts

### Key Lessons

1. When removing a dependency (OTel) to unblock another (ADK), handle the removal as a distinct phase before integration
2. Frontend quality phases benefit from shared tooling decisions — ESLint/Prettier config should be established once
3. PIISafe wrapper pattern is reusable: PIISafeAgent (v1.2) -> PIISafeADKWrapper (v1.7) -> future wrappers

### Cost Observations

- Sessions: ~8-10 across 2 days
- Notable: Frontend phases (42-43) were slower per plan due to complex build tooling decisions

---

## Milestone: v1.8 — ADK Stability & Error Hardening

**Shipped:** 2026-03-06
**Phases:** 6 | **Plans:** 11
**Timeline:** 2 days (2026-03-05 -> 2026-03-06)

### What Was Built

- ADK runtime controls: per-invocation timeout, LLM budget, explicit cancellation, bounded session state with Redis-first metadata store
- Pre-tool safety guardrails: `before_tool_callback` blocks unsafe calls before side effects; operator policy metadata immutable in tool dispatch
- Deterministic error classification: every ADK failure maps to exactly one of `timeout`, `policy_block`, `tool_error`, `upstream_error`
- ADK observability: Prometheus latency/throughput/in-flight metrics + structured invocation logs
- ADK CI smoke gate: oncology tool trajectory coverage blocks deploy on regressions
- Gap closure (Phases 48-49): Phase 44 verification closeout + real google-adk runner conditional smoke tests

### What Worked

- **Audit-driven gap closure** — Running `/gsd:audit-milestone` found 4 requirement gaps (ADK-09/10 orphaned, ADK-11/12 human_needed), which led to targeted Phases 48-49 instead of vague rework
- **Conditional real-runner testing** — `skipif(not HAS_ADK)` keeps local dev green while CI smoke-adk provides real coverage
- **Deterministic error taxonomy** — Establishing `policy_block`/`tool_error`/`upstream_error` early (Phase 45) made observability (Phase 46) and smoke (Phase 47) trivial to wire
- **Fast plans** — Average plan execution was ~12 min; Phase 45 P02 took only 7 min because runtime already had the right structure from P01

### What Was Inefficient

- **Phase 44 missing VERIFICATION.md** — Caused an audit gap_found and required an extra Phase 48 just to create the verification artifact. Should have been created during Phase 44 execution.
- **Phase 45 verification left at human_needed** — Required Phase 49 to promote to passed. Could have been addressed sooner if real-runner tests were scoped into Phase 45 planning.
- **Stale VALIDATION.md in Phases 46-47** — VALIDATION.md remained draft/Wave 0 even after VERIFICATION.md passed. Low impact but clutters audit.

### Patterns Established

- **Verification artifacts are mandatory at phase completion** — Phase 44's missing VERIFICATION.md caused a gap closure phase. Future phases must include verification as part of execution, not as an afterthought.
- **Conditional smoke tests** — `skipif(not HAS_ADK)` pattern allows external-dependency tests to live in the main test suite while only executing in CI environments that have the dependency.
- **Audit -> gap closure -> complete** — The three-step pattern (`/gsd:audit-milestone` -> `/gsd:plan-milestone-gaps` -> `/gsd:complete-milestone`) is now the standard milestone completion flow.

### Key Lessons

1. Missing verification artifacts create audit gaps that cost more to fix retroactively than to create during execution.
2. Deterministic error taxonomy should be established before observability instrumentation — makes metric labels and log schemas trivial.
3. Gap closure phases (48-49) were small and fast because audit precisely identified what was missing.
4. The most efficient milestone yet by plan duration (~12 min average) because the ADK runtime was already well-structured from v1.7.

### Cost Observations

- Sessions: ~3-4 across 2 days
- Notable: Most focused milestone — 11 plans in 2 days, all backend, zero frontend work
- Smallest net LOC among recent milestones (+8,028) reflecting hardening/testing focus over new features

---

## Cross-Milestone Trends

| Metric | v1.0 | v1.1 | v1.2 | v1.3 | v1.4 | v1.5 | v1.6 | v1.7 | v1.8 |
|--------|------|------|------|------|------|------|------|------|------|
| Phases | 5 | 4 | 4 | 6 | 9 | 4 | 7 | 4 | 6 |
| Plans | 13 | 10 | 16 | 31 | 54 | 14 | 21 | 20 | 11 |
| Days | 1 | 1 | 1 | 2 | 3 | 2 | 2 | 2 | 2 |
| Plans/day | 13 | 10 | 16 | 15.5 | 18 | 7 | 10.5 | 10 | 5.5 |
| Net LOC | -9,314 | +4,664 | +7,680 | +5,472 | +20,503 | +7,166 | +9,340 | +4,873 | +8,028 |
| Commits | 38 | 30+ | 72 | 123 | 199 | 53 | 99 | 85 | 12 |
| Had audit? | No | No | No | No | Yes | Yes | Yes | No | Yes |
| Gap closure plans | 0 | 0 | 0 | 0 | 2 | 2 | 1 | 0 | 2 |

**Observations:**
- Cumulative: 49 phases, 190 plans across 9 milestones in 13 days
- v1.8 had the lowest plans/day (5.5) but highest per-plan efficiency (~12 min average) — hardening work has fewer plans but each requires careful design
- Gap closure via audit continues to be a standard pattern (v1.4, v1.5, v1.6, v1.8)
- v1.8 had the lowest commit count (12) reflecting focused, targeted changes rather than broad migrations
- The audit -> gap closure -> complete flow is now the established milestone completion pattern
- ADK module matured from 0 LOC (pre-v1.7) to ~2,319 LOC across 2 milestones with full safety/observability/CI coverage

---
*Created: 2026-02-28 after v1.4 milestone*
*Updated: 2026-03-06 after v1.8 milestone*
