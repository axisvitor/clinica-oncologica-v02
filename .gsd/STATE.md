# GSD State

**Active Milestone:** M002 — First-Party Authentication Cutover
**Active Slice:** S02 — Account Recovery And Migration
**Active Task:** not started — awaiting S02 planning/execution
**Phase:** S01 is complete and locally verified. The backend now has first-party local login, canonical DB+Redis session issuance, session-backed protected-route auth, verify-session, logout invalidation, and stable auth diagnostics.

## Recent Decisions
- M002 remains a hard cut: shipped staff auth must end without Firebase Auth runtime dependence.
- Preserve Redis + HttpOnly cookie sessions; replace the identity provider, not the session model.
- M002/S01 makes `user_id` the canonical session identity; `firebase_uid` is compatibility-only metadata.
- M002/S01 exposes canonical authenticated-user routes under `/api/v2/users/*` and keeps `/api/v2/auth/*` as a hidden legacy alias during the transition.
- M002/S01 keeps auth failures inspectable with stable error codes plus `request_id` or debug-step diagnostics while redacting secrets.

## Blockers
- No active blocker for S01.
- Remaining milestone work is now in later slices: password reset / first-access migration, frontend + realtime cutover, and final Firebase Auth runtime cleanup.

## Next Action
Start S02 and ship the recovery/migration contract:
- `POST /api/v2/auth/password/reset-request`
- `POST /api/v2/auth/password/reset-confirm`
- admin-created account first-access compatibility with the new local auth/session core
