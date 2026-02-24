# Phase 13: SDK Migration & Cleanup - Context

**Gathered:** 2026-02-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Eliminate the last LangChain reference in the entire backend. GeminiClient migrates from ChatGoogleGenerativeAI to the google-genai SDK directly, Celery tasks use agent.run_sync() to bridge async, and zero LangChain imports remain anywhere in the codebase. This is the final phase of the AI Framework Migration milestone.

</domain>

<decisions>
## Implementation Decisions

### Migration cutover strategy
- Hard-switch to google-genai SDK — no gradual toggle, the legacy code path is removed entirely
- Remove the GeminiDomainClient shim layer — direct google-genai calls, no abstraction layer
- Remove AI_FRAMEWORK setting and its env var entry completely (not tombstoned, not deprecated — deleted)
- Adapt the full 50-scenario regression suite to target google-genai SDK directly (no trimming)

### Celery async bridge
- Use run_sync() everywhere — every Celery task calling an AI agent wraps with run_sync(), no event loop management in workers
- Scope limited to Celery-to-agent bridge only — the broader sync-in-async migration (42 methods, 8 files) is a separate future effort
- Keep existing Celery retry configuration unchanged (autoretry_for, max_retries, backoff) — run_sync() is just the execution wrapper
- Validate both FastAPI (async native) and Celery (run_sync) paths after SDK swap

### Cleanup scope & completeness
- Remove ALL langchain-* packages from production, dev, and test requirements — clean dependency tree
- Full config cleanup: .env.example, docker-compose, deployment configs, documentation — nothing left behind
- Permanent test assertion that greps codebase for langchain/langgraph imports and fails if any found

### Rollback & safety net
- Include a staging smoke test checklist before production deploy (deploy staging, trigger each AI agent type, verify output quality)
- Milestone (AI Framework Migration) is complete after Phase 13 is validated — no additional monitoring phase

### Claude's Discretion
- Tombstone files from earlier phases: keep or delete based on whether any imports still reference tombstoned paths
- Rollback strategy: Claude determines best approach (likely git revert to pre-Phase 13 given the hard-switch decision)
- Production confidence bar: Claude defines based on system error monitoring and staging smoke test results

</decisions>

<specifics>
## Specific Ideas

- The 50-scenario regression suite from Phase 11 is the primary validation tool — adapt it, don't replace it
- The broader sync-in-async migration (42 methods across 8 files with TODO(async-migration) annotations) is explicitly out of scope
- Staging smoke test should cover all four AI agent types (Sentiment, Humanize, Variation, Empathy)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-sdk-migration-cleanup*
*Context gathered: 2026-02-24*
