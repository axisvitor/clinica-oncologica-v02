# GSD State

**Active Milestone:** M004 — Convergência Canônica de Runtime
**Active Slice:** S02 — Backend auth/sessão convergido para identidade canônica
**Phase:** planning
**Requirements Status:** 7 active · 18 validated · 7 deferred · 11 out of scope

## Milestone Registry
- ✅ **M001:** Bulletproof Flow Pipeline
- ✅ **M002:** First-Party Authentication Cutover
- ✅ **M003:** Structural Refactor And Dead-Code Cleanup
- 🔄 **M004:** Convergência Canônica de Runtime
- ⬜ **M005:** M005
- ⬜ **M006:** M006

## Recent Decisions
- S01 pins approved runtime-residue hotspots by explicit file anchors in `runtime-residue-allowlist.json`; hotspot moves must update the boundary intentionally.
- S01 boundary shrinkage is only complete when the allowlist, research, summary, and UAT move together with green verifier output.

## Blockers
- None

## Next Action
- Start `/gsd auto` from `docs-refactor-py313`; the next unit should be `plan-slice M004/S02`, which will create/check out `gsd/M004/S02` and use the S01 guardrail pack as input.
