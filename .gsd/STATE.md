# GSD State

**Active Milestone:** M002 — First-Party Authentication Cutover
**Active Slice:** None — roadmap ready
**Active Task:** None
**Phase:** Planning ready

## Recent Decisions
- M002 is a hard cut: shipped staff auth must not depend on Firebase Auth runtime paths.
- Preserve Redis + HttpOnly cookie sessions; replace the identity provider, not the session model.
- Standardize login on email only.
- Keep account provisioning admin-driven.
- Existing users regain access through reset / first-access email flows.

## Blockers
- None

## Next Action
Read `.gsd/milestones/M002/M002-ROADMAP.md` and decompose S01 into a slice plan with context-window-sized tasks.
