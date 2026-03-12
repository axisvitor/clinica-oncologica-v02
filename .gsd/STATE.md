# GSD State

**Active Milestone:** M003 — Structural Refactor And Dead-Code Cleanup
**Active Slice:** None
**Phase:** ready-for-slice-planning
**Requirements Status:** 6 active · 12 validated · 7 deferred · 8 out of scope

## Milestone Registry
- ✅ **M001:** Bulletproof Flow Pipeline
- ✅ **M002:** First-Party Authentication Cutover
- 🔄 **M003:** Structural Refactor And Dead-Code Cleanup

## Recent Decisions
- M003 starts with evidence-first hotspot inventory and dead-code guardrails.
- Backend auth/session is the first hotspot attack zone; frontend api-client/type surface follows.
- Remove obsolete compatibility only when deadness is proven; otherwise isolate and justify it.
- Visible contract drift is out of scope for this milestone.

## Blockers
- None

## Next Action
Plan S01: Evidence Map And Cleanup Guardrails.
