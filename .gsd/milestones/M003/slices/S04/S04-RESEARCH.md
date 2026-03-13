# M003 / S04 — Research

**Date:** 2026-03-13

## Summary

S04 owns **R036** directly and supports **R034, R035, R037, R038, and R039**. In the current repo state, the main surprise is that **S04 is already materially executed**: the strongest frontend compat residues are gone, the backend auth dependency surface is already pruned, `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all` is green, and the slice already has a real manifest/summary/UAT pack instead of placeholders.

That changes the research posture. This is **not** a blank “what should S04 do?” investigation anymore. The useful S04 research outcome is to document the **actual cleanup boundary now present in the repo**:
- **already removed:** `frontend-hormonia/src/lib/api.ts`, `frontend-hormonia/src/lib/types/api.ts`, `frontend-hormonia/src/hooks/use-quiz-session.ts`, plus the dead backend auth export surface (`verify_firebase_token`, `get_doctor_user`, `get_current_user_websocket`)
- **intentionally retained:** `backend-hormonia/app/routers/auth_session.py`, `firebase_uid` compatibility paths, and the bearer-token fallback in `get_current_user()`
- **not yet missing for S04, but still missing for the milestone:** the integrated cross-surface smoke owned by S05

So the real S04 recommendation is: **treat the slice as closed unless scope is explicitly widened**. If anyone wants to continue deleting compatibility residue from here, they must open a new proof cycle around the retained islands instead of assuming they are just dead leftovers.

## Requirement Targeting

### Slice ownership / support

- **Owns: R036 — Obsolete compatibility layers are removed or tightly isolated**
  - Current status from live repo reads: satisfied at the S04 boundary level. Dead frontend aliases/hooks are deleted; dead backend auth exports are absent; live compatibility islands are explicit.
- **Supports: R034 — Critical hotspots stay reduced instead of regrowing compat sludge**
  - Current status: supported. `backend-hormonia/app/dependencies/auth_dependencies.py` is down to **675 lines** and the deleted compat files remain at **0 lines** in the living verifier.
- **Supports: R035 — Dead-code removal is evidence-based**
  - Current status: supported. The repo now uses a combination of negative contract tests, a cleanup manifest, and the S01 evidence-map gate instead of prose-only claims.
- **Supports: R037 — Visible contracts remain stable during cleanup**
  - Current status: supported, but final proof still belongs to S05. The retained auth/session compatibility islands are the main constraint here.
- **Supports: R038 — Codebase becomes safer to change in practice**
  - Current status: supported. Canonical-vs-legacy ownership is clearer now than in S01.
- **Supports: R039 — Structural cleanup leaves strong proof**
  - Current status: supported at slice level via the manifest, contract tests, and verifier; milestone-close cross-surface proof still belongs to S05.

## Recommendation

### Recommended posture for S04 now

1. **Do not reopen S04 as if the cleanup work were still pending.**
   - The strongest proven-dead targets are already removed.
   - The verifier and handoff artifacts already reflect the post-cleanup state.

2. **Use S04 as a boundary artifact for S05, not as a new implementation queue.**
   - Start from:
     - `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md`
     - `.gsd/milestones/M003/slices/S04/S04-SUMMARY.md`
     - `.gsd/milestones/M003/slices/S04/S04-UAT.md`
     - `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`

3. **If scope is widened, treat the remaining compat islands as a new research problem.**
   - `backend-hormonia/app/routers/auth_session.py`
   - `firebase_uid` compatibility reads/writes
   - bearer-token fallback in `backend-hormonia/app/dependencies/auth_dependencies.py::get_current_user()`

4. **Do not delete retained islands on grep counts alone.**
   - The repo still contains large amounts of `firebase_uid` test/docs/schema residue.
   - Raw repo mentions are not equivalent to current runtime necessity.

## Key Findings And Surprises

### 1) S04 is already closed in the current repo state

Current slice artifacts are real, not placeholders:
- `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md`
- `.gsd/milestones/M003/slices/S04/S04-SUMMARY.md`
- `.gsd/milestones/M003/slices/S04/S04-UAT.md`
- `.gsd/milestones/M003/slices/S04/tasks/T01-SUMMARY.md`
- `.gsd/milestones/M003/slices/S04/tasks/T02-SUMMARY.md`
- `.gsd/milestones/M003/slices/S04/tasks/T03-SUMMARY.md`

That is a meaningful contrast with the preloaded S02/S03 placeholder summaries.

### 2) The frontend dead-code targets are really gone

Live existence check:
- `frontend-hormonia/src/lib/api.ts` → missing
- `frontend-hormonia/src/lib/types/api.ts` → missing
- `frontend-hormonia/src/hooks/use-quiz-session.ts` → missing

The current S01 verifier also reports:
- `frontend.legacy_types.lines=0`
- `frontend.legacy_types.imports=0`
- `frontend.legacy_api.lines=0`
- `frontend.legacy_api.imports=0`
- `frontend.use_quiz_session.lines=0`

And the negative boundary test now pins that absence:
- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts`

### 3) The backend auth export cleanup is also already landed

Current public dependency surface reads show these names are absent from the public auth package surface:
- `verify_firebase_token`
- `get_doctor_user`
- `get_current_user_websocket`

The current proof is intentionally negative:
- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` asserts those exports stay absent
- `backend-hormonia/tests/services/websocket/test_connection_manager.py` now treats `firebase` / `auto` websocket auth modes as explicitly unsupported

This is important: the remaining work was not runtime cleanup, but **stale proof cleanup**.

### 4) `auth_session.py` is still mounted and still live

This is the main constraint against overreaching S04.

`backend-hormonia/app/core/router_registry.py` still mounts:
- `from app.routers.auth_session import router as auth_session`
- `app.include_router(auth_session, tags=["Session Authentication"])`

And `backend-hormonia/app/routers/auth_session.py` still:
- exposes `/session/*`
- reads/writes `firebase_uid`
- rebuilds permissions/session payloads in a legacy-oriented shape
- remains **731 lines** long in the live verifier

So even if the frontend no longer uses the root `/session/*` path as the happy path, the backend router is still not proven dead.

### 5) `firebase_uid` is still a live compatibility substrate, not just dead historical residue

This was the biggest live-code constraint found in the current repo.

Examples:
- `backend-hormonia/app/dependencies/auth_role_dependencies.py` prefers canonical `id` / `user_id`, but still falls back to `firebase_uid` when canonical IDs are absent
- `backend-hormonia/app/api/v2/routers/auth.py` still persists `user_payload["firebase_uid"] = user.firebase_uid` into the canonical cache entry
- `backend-hormonia/app/routers/auth_session.py` still depends on `firebase_uid` heavily
- multiple compatibility helpers in `app/api/v2/*shared*` still preserve `firebase_uid`-based access patterns

So `firebase_uid` should be described as **compatibility data that still has live readers/writers**, not as dead code.

### 6) The bearer fallback is still intentionally present

`backend-hormonia/app/dependencies/auth_dependencies.py::get_current_user()` is now clearly session-first:
- if cookie/session header exists → `get_current_user_from_session(...)`
- else → `auth_legacy_firebase.authenticate_legacy_bearer_user(...)`

That makes the cleanup boundary very clear:
- session-first browser/runtime path is canonical
- bearer-token Firebase compatibility still exists for non-session callers and has **not** been proven removable

### 7) Raw grep counts would mislead this slice badly

A repo-wide `rg firebase_uid` still returns a huge surface across:
- tests
- docs
- migrations
- audit models
- compatibility helpers
- the retained `/session/*` router

A repo-wide `rg verify_firebase_token` or related symbols would also overcount because `.gsd` artifacts and test files remain part of the evidence trail.

So the main pitfall for S04 is exactly what R035 warned about: **confusing “still mentioned” with “still authoritative runtime behavior.”**

### 8) There is at least one more probable frontend orphan, but it is not part of S04’s ranked cleanup boundary

`frontend-hormonia/src/features/monthly-quiz/components/PublicQuizAccess.tsx` appears only to be exported from its local index and is not obviously routed from the main route definitions.

That is interesting, but it was **not** part of the S01/S04 ranked deletion ledger. It should be treated as a future evidence candidate, not as part of the already-closed S04 boundary.

## Live Repo Snapshot

From `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`:

- `backend.auth_dependencies.lines=675`
- `backend.auth_session.lines=731`
- `backend.candidate.verify_firebase_token.repo_refs=4`
- `backend.candidate.get_doctor_user.repo_refs=1`
- `backend.candidate.get_current_user_websocket.repo_refs=2`
- `frontend.api_client_index.lines=223`
- `frontend.api_client_types.lines=26`
- `frontend.legacy_types.lines=0`
- `frontend.legacy_api.lines=0`
- `frontend.use_quiz_session.lines=0`
- `frontend.duplicate_exports.count=0`
- `handoff.summary.open_scaffold_items=0`
- `handoff.uat.open_scaffold_items=0`

This confirms S04 is operating from a post-cleanup repo, not from a pre-cleanup plan.

## Don’t Hand-Roll

| Problem | Existing Solution | Why Use It |
|---|---|---|
| Preventing deleted compat files from silently returning | `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` | The slice already uses a negative contract test instead of comments or tombstones. |
| Proving dead backend auth exports stay dead | `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` | This keeps removed auth symbols absent without rebuilding obsolete wrappers for test convenience. |
| Distinguishing deleted residue from retained compatibility islands | `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md` | It is the clearest auditable ledger of what S04 actually changed and what it intentionally left alone. |
| Checking whether slice bookkeeping still matches the repo | `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all` and `--check all` | The verifier now treats deleted tracked files as zero-line surfaces, so it reflects intentional cleanup rather than failing on stale anchors. |

## Existing Code And Patterns

- `backend-hormonia/app/dependencies/auth_dependencies.py` — now a stable session-first façade with explicit bearer fallback instead of a giant mixed-responsibility bucket.
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` — explicit compatibility-only home for bearer/Firebase behavior that still exists.
- `backend-hormonia/app/dependencies/auth_role_dependencies.py` — best current example of canonical `id` / `user_id` first, `firebase_uid` fallback second.
- `backend-hormonia/app/routers/auth_session.py` — still-mounted compatibility island; not safe to classify as dead.
- `backend-hormonia/app/core/router_registry.py` — authoritative proof that `/session/*` is still mounted.
- `backend-hormonia/tests/services/websocket/test_connection_manager.py` — current pattern for rejecting removed websocket auth modes explicitly rather than silently preserving them.
- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts` — pattern for pinning deleted-file absence with executable proof.
- `frontend-hormonia/tests/unit/types-validation.test.ts` — shows the last test-only compat import has already been migrated to canonical owners.
- `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md` — final deleted-vs-retained ledger that downstream work should consume instead of reopening discovery.

## Constraints

- **Do not treat `auth_session.py` as dead.** It is still mounted and still carries compatibility behavior.
- **Do not treat `firebase_uid` as dead.** It remains a compatibility key with live readers and writers.
- **Do not remove bearer fallback without a new proof cycle.** The current code keeps it intentionally after session-first resolution fails to find a session identifier.
- **Do not use repo-wide symbol mentions as the only proof.** `.gsd`, tests, docs, and migrations materially inflate counts.
- **Do not broaden S04 casually.** The slice already has a closed manifest; new deletions belong to new research and new proof.

## Common Pitfalls

- **Confusing “already pruned in runtime” with “still needs code changes.”** In current repo state, some of the remaining S04 work was already test/verifier cleanup, not production cleanup.
- **Using stale test expectations as architecture truth.** The websocket manager is now authoritative for `jwt` / `session`; legacy `firebase` / `auto` modes are retired.
- **Mistaking mounted legacy routes for dead code because the frontend happy path moved away.** `/session/*` is the clearest example.
- **Broadening into a hidden Firebase retirement sequel.** S04’s retained islands are bounded; removing them is a new problem.

## Open Risks

- S05 still needs the integrated auth/dashboard/admin/websocket smoke after S02–S04. Slice-local proof is not the same thing as milestone-close assembled proof.
- Future cleanup work could incorrectly classify `auth_session.py`, `firebase_uid`, or bearer fallback as dead because the session-first happy path dominates current browser flows.
- The repo still carries a lot of Firebase-era test/doc/schema residue. Without disciplined scoping, a future agent could spend time cleaning historical references instead of live runtime risk.

## Skills Discovered

| Technology | Skill | Status |
|---|---|---|
| Investigation / debugging | `debug-like-expert` | installed locally and directly relevant to evidence-first cleanup research |
| FastAPI | `wshobson/agents@fastapi-templates` | available — `npx skills add wshobson/agents@fastapi-templates` (6.3K installs) |
| FastAPI | `mindrally/skills@fastapi-python` | available — `npx skills add mindrally/skills@fastapi-python` (2.1K installs) |
| React | `vercel-labs/agent-skills@vercel-react-best-practices` | available — `npx skills add vercel-labs/agent-skills@vercel-react-best-practices` (204.6K installs) |
| TypeScript | `wshobson/agents@typescript-advanced-types` | available — `npx skills add wshobson/agents@typescript-advanced-types` (13.1K installs) |

## Sources

### Local research / handoff artifacts
- `.gsd/milestones/M003/slices/S04/S04-PLAN.md`
- `.gsd/milestones/M003/slices/S04/tasks/T01-SUMMARY.md`
- `.gsd/milestones/M003/slices/S04/tasks/T02-SUMMARY.md`
- `.gsd/milestones/M003/slices/S04/tasks/T03-SUMMARY.md`
- `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md`
- `.gsd/milestones/M003/slices/S04/S04-SUMMARY.md`
- `.gsd/milestones/M003/slices/S04/S04-UAT.md`
- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`

### Backend code read directly
- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/app/dependencies/__init__.py`
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py`
- `backend-hormonia/app/dependencies/auth_role_dependencies.py`
- `backend-hormonia/app/routers/auth_session.py`
- `backend-hormonia/app/core/router_registry.py`
- `backend-hormonia/app/api/v2/routers/roles/dependencies.py`
- `backend-hormonia/app/api/v2/routers/auth.py`
- `backend-hormonia/app/services/websocket/connection_manager.py`

### Frontend code read directly
- `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts`
- `frontend-hormonia/tests/unit/types-validation.test.ts`
- `frontend-hormonia/src/features/monthly-quiz/hooks/useMonthlyQuiz.ts`
- `frontend-hormonia/src/app/routes/routeDefinitions.tsx`
- `frontend-hormonia/src/pages/QuestionariosPage.tsx`
- `frontend-hormonia/src/lib/api-client/auth.ts`

### Skill discovery commands run
- `npx skills find "FastAPI"`
- `npx skills find "React"`
- `npx skills find "TypeScript"`
