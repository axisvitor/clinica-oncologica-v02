# Phase 10: Preparation & Scope - Context

**Gathered:** 2026-02-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Prepare the codebase for Pydantic AI agent implementation: audit all LangGraph/LangChain imports across the codebase, install pydantic-ai-slim without dependency conflicts, and delete the consensus system (confirmed dead code with zero production callers). The 5 existing DDD service "agents" in `app/agents/` are annotated or reorganized to avoid confusion with real Pydantic AI agents coming in Phase 11.

</domain>

<decisions>
## Implementation Decisions

### Consensus Deletion Pattern
- **Delete completo** — remove files from repository entirely (not tombstone pattern)
- Delete all associated test files — no @pytest.skip stubs
- Remove unused agent IDs from `app/agents/base.py` (ALERT_ANALYZER_ID, PATIENT_MONITOR_ID etc. — only those exclusively used by consensus)
- Adjust `flow_coordinator` to remove consensus imports and calls cleanly (not stub/mock)
- Files to delete: `app/ai/langgraph/consensus.py`, `app/agents/patient/flow_coordinator/consensus_manager.py`, and any tests for these

### ADK Deferral
- **Do NOT design for ADK compatibility** — Pydantic AI pure, no future-proofing for ADK
- ADK deferred to v1.3 due to 3 irresolvable dependency conflicts (OTel cap, FastAPI bundling, Pydantic 2.11+ failures)
- Track ADK issue #3615 (google-adk-core lightweight install) for v1.3 readiness

### Dependency Management
- Single `requirements.txt` file (no dev/prod/test split)
- pydantic-ai and LangGraph coexist during migration phases 10-12
- LangGraph packages removed at end of Phase 12

### Claude's Discretion
- **Agent identity handling**: Whether to rename `app/agents/` DDD services, annotate them, or restructure — Claude evaluates naming confusion risk and chooses the least-disruptive approach
- **Timing of agent reorganization**: Phase 10 or Phase 11 — Claude picks based on what minimizes churn
- **message_composer classification**: Whether it stays as DDD service or migrates to AI agent — Claude evaluates based on its actual LLM usage pattern
- **New Pydantic AI agents directory**: `app/ai/agents/` vs `app/agents/ai/` vs other — Claude picks based on existing codebase patterns
- **ADK deferral documentation location**: PROJECT.md Key Decisions, REQUIREMENTS.md, or both
- **ADK tracking mechanism**: STATE.md pending todo, MILESTONES.md note, or other
- **Dependency coexistence strategy**: How to manage pydantic-ai + LangGraph side-by-side safely
- **pydantic-ai version pinning**: `>=1.63.0,<2.0.0` vs exact pin vs other — Claude picks the safest strategy given v2 breaking changes planned for April 2026

</decisions>

<specifics>
## Specific Ideas

- User explicitly said "nao gostei da forma que trabalha" about LangGraph — the migration is motivated by dissatisfaction with the framework's overhead, not a bug
- User chose "estrutura de agentes" as the attraction to new frameworks — they value clean agent cooperation patterns
- User wants the system to "realmente aja da forma correta e sem erros" — reliability is the priority over features
- The project name "Hormonia" implies harmony — the user wants smooth, well-orchestrated flows

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-preparation-scope*
*Context gathered: 2026-02-23*
