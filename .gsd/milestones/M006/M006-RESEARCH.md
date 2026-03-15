# M006 — Research

**Date:** 2026-03-14

## Summary

M006 should start by treating the remaining auth/session compatibility seams as the highest-risk residue, not the easiest deletions. The repo already has the right proof scaffolding: `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` for scoped runtime residue, `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` for fresh/existing schema replay plus mounted backend proof, and an explicit tombstone contract for retired `/session/*`. The first thing to prove is that this baseline still holds before removal starts. From there, the deepest cleanup target is the backend legacy-auth seam: `backend-hormonia/app/dependencies/auth_dependencies.py` still lazy-loads Firebase bearer compatibility when no session cookie is present, but the target module `backend-hormonia/app/dependencies/auth_legacy_firebase.py` currently contains unresolved merge markers and fails `python -m py_compile`. That means a supposed compatibility path is already not honest runtime behavior.

After that seam is retired or converted into explicit rejection, the rest of M006 separates into two bands. One band is low-risk dead residue: 36 `TOMBSTONE` stubs in `backend-hormonia/app`, explicit frontend bridge barrels like `frontend-hormonia/lib/flow-engine/*.ts`, deprecated compatibility barrels like `frontend-hormonia/lib/types/ai.ts`, and stale Firebase/config/script/docs references. The other band is schema-bearing residue: `backend-hormonia/app/models/user.py` still carries `firebase_uid` plus several `firebase_*` columns with transition comments, and that work must stay Alembic-backed and replayed through the M005 proof runner rather than being handled with static grep cleanup. Primary recommendation: order M006 as baseline proof → retire broken auth compatibility seams → remove provably dead bridges/services/config/docs/tests → drop schema residue with migrations → republish the residue guard and closeout artifacts.

## Recommendation

Take M006 in this order:

1. **Freeze the current proof baseline first.** Re-run the published runtime residue verifier and the M005 final-schema proof for both `--fresh` and `--existing` histories before changing code. That gives M006 an honest starting line instead of assuming M004/M005 still hold.
2. **Make the auth boundary honest before broad cleanup.** `backend-hormonia/app/dependencies/auth_legacy_firebase.py` is already syntactically broken, while `auth_dependencies.py` still points at it as a lazy fallback. Retire that bearer/Firebase seam early: either delete it and its callers, or replace it with explicit rejection/tombstone behavior. Do not preserve a broken compatibility path just because it is old.
3. **Shrink backend residue categories to zero-approved, not just smaller-approved.** The current M004 allowlist still approves backend `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query` hotspots. M006 is the milestone where those should stop being approved runtime residue and become either absent or explicitly historical outside the runtime guard.
4. **Then remove the easy dead code.** That includes tombstone stubs, dead Firebase-oriented services like `SessionService`, explicit frontend bridge barrels, deprecated type aliases, stale scripts, and docs/config/env/workflow narrative that still treats Firebase as operational.
5. **Keep schema cleanup as its own proof-backed step.** `firebase_uid` and the remaining Firebase-era user columns need Alembic revisions plus both fresh/existing replay through the existing final-schema runner.

If planning wants to bind one new requirement, the strongest candidate is: **after M006, the runtime residue verifier reports zero approved backend auth/session residue in the old Firebase/header/bearer/query categories**. CI automation for that guard looks useful, but should remain advisory unless the milestone plan explicitly adopts it.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Runtime residue drift across backend/frontend | `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` + `runtime-residue-allowlist.json` | Already distinguishes approved hotspots from unexpected drift and catches moved anchors; M006 should republish this guard, not replace it with ad hoc grep notes. |
| Fresh/existing schema + mounted backend replay | `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` | Already serializes `canonical_head -> pytest_replay -> mounted_backend -> live_auth_probe` and reuses the mounted helper from M004; it is the right integrated proof surface for schema-bearing cleanup. |
| Retired root `/session/*` behavior | `backend-hormonia/app/routers/auth_session.py` | Already returns a stable 410 retirement response with explicit diagnostics. If the route survives, keep this contract instead of recreating soft compatibility or vague 404 drift. |
| Cleanup boundary publication | `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md` | Already models removed surfaces, retained boundaries, and exact proof commands. M006 should publish the same kind of closeout instead of a diff-only summary. |

## Existing Code and Patterns

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — Current machine-readable residue contract. Important detail: it still approves backend hotspots for `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`, while frontend scopes are already zero-approved. M006 should tighten this to absence, not pad the allowlist.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — Deterministic scanner that reports unexpected files and moved hotspots. Reuse it as the milestone guardrail.
- `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh` — Final proof topology. It already runs both schema preparation and mounted backend verification and should stay the integration gate for any model/migration cleanup.
- `backend-hormonia/app/dependencies/auth_session_contract.py` — Canonical cookie-only staff session resolver. This is the contract to preserve while deleting legacy branches elsewhere.
- `backend-hormonia/app/dependencies/auth_dependencies.py` — Current auth chokepoint. `get_current_user_from_session()` is session-first, but `get_current_user()` still lazy-loads legacy Firebase bearer auth when no session cookie is present.
- `backend-hormonia/app/dependencies/auth_session_cache.py` — Still serializes and caches `firebase_uid` alongside canonical `user_id`, so it remains one of the key backend narrowing steps after auth fallback retirement.
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` — Strong candidate for immediate retirement. It still represents a live fallback target from `auth_dependencies.py`, but currently contains unresolved merge markers and does not compile.
- `backend-hormonia/app/routers/auth_session.py` — No longer the old live compat router from M003; it is now an explicit 410 retirement router. M006 should either keep it as a published tombstone or remove it with proof, but not treat it as ambiguous live compatibility.
- `backend-hormonia/app/service_provider.py` — Canonical runtime already instantiates `SimpleSessionService` for its `session_service` property.
- `backend-hormonia/app/services/simple_session_service.py` — Shows the surviving no-Firebase session behavior for quiz/session storage.
- `backend-hormonia/app/services/session_service.py` — Old Firebase-centric session facade still present. Good M006 deletion target once any remaining direct tests or callers are removed or rewritten.
- `backend-hormonia/app/models/user.py` — Still carries `firebase_uid` and multiple `firebase_*` columns with explicit transition comments. This is migration work, not just code deletion.
- `frontend-hormonia/lib/flow-engine/FlowEngine.ts` — Explicit backward-compatible bridge into `src/lib/flow-engine/FlowEngine`.
- `frontend-hormonia/lib/flow-engine/TemplateManager.ts` — Same bridge pattern for `TemplateManager`. Good candidate for M006 once exact import proof says nothing still needs the public bridge.
- `frontend-hormonia/lib/types/ai.ts` — Deprecated compatibility barrel that re-exports canonical types but still defines extra legacy aliases/interfaces. Worth cleaning after exact import/type/build proof.
- `frontend-hormonia/firebase.json` + `frontend-hormonia/.firebaserc` — Firebase Hosting residue still present in the frontend repo. Candidate cleanup, but only after deploy/workflow references are checked.
- `.github/workflows/rls-api-tests.yml`, `.github/workflows/postman-tests.yml`, `backend-hormonia/.env.example` — Operational narrative still injects or documents Firebase admin vars and Firebase-hosted URLs. M006 must audit CI/env templates, not only runtime code.
- `docs/compatibility/backward-compatibility-inventory.md` — Still describes Firebase bearer migration waves as if they are live compat work. Good M006 docs target.

## Constraints

- **The M004 runtime verifier is intentionally narrower than M006.** It excludes docs, tests, models, schemas, and archival content by design. M006 therefore needs a second boundary for “historical but honest” vs “current and misleading”.
- **`auth_dependencies.py` still routes no-cookie requests into a legacy Firebase seam.** Deleting downstream modules without changing that call graph will just move failure around.
- **`auth_legacy_firebase.py` is already broken.** Any path that genuinely relies on it will fail import/compile today. That makes early retirement safer and more urgent.
- **`auth_session.py` is already a tombstone, not a live island.** Old M003 assumptions about preserving it as operational compatibility are stale.
- **Schema cleanup still requires Alembic.** `firebase_uid`, `firebase_last_sign_in`, `firebase_photo_url`, and related fields in `app/models/user.py` must be removed with migrations and replayed through both M005 histories.
- **Firebase-named cache code is not automatically dead.** `auth_session_cache.py`, `auth_dependencies.py`, and `app/api/websockets.py` still reference Redis/Firebase-shaped cache surfaces. Narrow consumers before deleting cache abstractions.
- **CI and env templates still mention Firebase.** If M006 cleans runtime code but leaves workflow/env surfaces untouched, the repo will still tell a mixed operational story.
- **Historical docs should be classified, not indiscriminately deleted.** Legacy reports/ADRs under clearly archival trees can remain if they are honest and isolated from current operator entrypoints.

## Common Pitfalls

- **Deleting the broken bearer seam last** — `auth_legacy_firebase.py` already contains merge markers and fails compile; treat it as broken residue to retire early, not as healthy compatibility that deserves protection.
- **Assuming every Firebase-named cache/helper is dead** — `FirebaseRedisCache`-shaped code still fronts live auth/websocket/cache consumers. Remove or rename consumers first, then delete the backing layer when imports truly reach zero.
- **Using the M004 runtime verifier as the only proof** — it cannot see docs/tests/models. Pair it with focused scans for scripts, workflows, env templates, and doc surfaces, plus the M005 final-schema runner.
- **Dropping model columns without migration replay** — deleting Firebase-era fields from `app/models/user.py` without Alembic will break fresh/existing head convergence.
- **Treating explicit bridges as automatically safe to delete** — `frontend-hormonia/lib/flow-engine/*.ts` and `frontend-hormonia/lib/types/ai.ts` are compatibility barrels and still need exact import + type/build proof before removal.
- **Cleaning docs cosmetically instead of classifying them** — current operational docs, env templates, and workflows must describe the canonical system; archival docs can remain if clearly marked historical.

## Open Risks

- The merge-conflict state in `auth_legacy_firebase.py` suggests legacy bearer auth is either dead, untested, or both. Removing it may still expose forgotten callers that were silently relying on a path that no longer imports.
- CI workflows and env examples still ship Firebase variables and Firebase-hosted URLs. Cleanup may require workflow/test fixture changes, not just code deletion.
- Some tests still appear to validate historical Firebase boundaries. M006 has to distinguish “proof of archived boundary” from “proof of live runtime” so it does not delete useful historical evidence blindly.
- The remaining Firebase-era user columns may need more than one migration if current readers/tests still mirror them.
- **Candidate requirement:** after M006, the M004 runtime residue verifier should report zero approved backend residue for `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`.
- **Candidate requirement:** M006 closeout should include one replayable absence pack combining the runtime residue verifier, focused no-Firebase scans for scripts/workflows/env templates, and the M005 final-schema runner for both histories.
- **Advisory only:** add the absence pack to CI after M006. Useful, but not automatically worth widening the milestone if it turns into separate infra work.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| FastAPI | `wshobson/agents@fastapi-templates` | available — install with `npx skills add wshobson/agents@fastapi-templates` |
| Alembic / SQLAlchemy | `wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` | available — install with `npx skills add wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` |
| React | `vercel-labs/agent-skills@vercel-react-best-practices` | available — install with `npx skills add vercel-labs/agent-skills@vercel-react-best-practices` |

## Sources

- Current runtime residue contract still approves backend `firebase_uid`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query`, while frontend scopes are already zero-approved. (source: `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`)
- The runtime verifier flags unexpected files and moved hotspots instead of acting like a loose grep, so it is the right M006 guardrail to republish. (source: `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`)
- The final-schema runner already serializes `canonical_head -> pytest_replay -> mounted_backend -> live_auth_probe` and reuses the mounted helper from M004. (source: `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh`)
- `service_provider.session_service` already instantiates `SimpleSessionService`, not the older Firebase-centric `SessionService`. (source: `backend-hormonia/app/service_provider.py`)
- `SessionService` still advertises Firebase token validation and `FirebaseRedisCache`-backed session creation, making it strong dead-code candidate territory once callers/tests are cleaned. (source: `backend-hormonia/app/services/session_service.py`)
- `auth_dependencies.get_current_user()` still falls back to lazy-loaded legacy Firebase bearer auth when no session cookie is present. (source: `backend-hormonia/app/dependencies/auth_dependencies.py`)
- `auth_session_contract.py` is already cookie-only and treats legacy headers only as rejected transport signals. (source: `backend-hormonia/app/dependencies/auth_session_contract.py`)
- `auth_session_cache.py` still serializes and caches `firebase_uid` alongside canonical `user_id`. (source: `backend-hormonia/app/dependencies/auth_session_cache.py`)
- `auth_legacy_firebase.py` currently contains merge markers and fails `python -m py_compile app/dependencies/auth_legacy_firebase.py` with `SyntaxError`. (source: `backend-hormonia/app/dependencies/auth_legacy_firebase.py`; verification command run locally)
- `auth_session.py` is now a 410 retirement router for `/session/*`, not the old live compatibility router. (source: `backend-hormonia/app/routers/auth_session.py`)
- `app/models/user.py` still carries `firebase_uid` and multiple Firebase-era profile/auth columns with explicit transition comments. (source: `backend-hormonia/app/models/user.py`)
- The backend app still contains 36 `TOMBSTONE` stubs, so there is low-risk dead-code cleanup available once the auth boundary is fixed. (source: local command `rg -l 'TOMBSTONE' backend-hormonia/app | wc -l`)
- `frontend-hormonia/lib/flow-engine/FlowEngine.ts` and `TemplateManager.ts` are explicit backward-compatible re-export bridges, while `frontend-hormonia/lib/types/ai.ts` is a deprecated compatibility barrel. (source: `frontend-hormonia/lib/flow-engine/FlowEngine.ts`, `frontend-hormonia/lib/flow-engine/TemplateManager.ts`, `frontend-hormonia/lib/types/ai.ts`)
- Frontend Firebase Hosting config still exists locally, while CI/workflow/env surfaces still mention Firebase admin vars and Firebase-hosted URLs. (source: `frontend-hormonia/firebase.json`, `frontend-hormonia/.firebaserc`, `.github/workflows/rls-api-tests.yml`, `.github/workflows/postman-tests.yml`, `backend-hormonia/.env.example`)
- Compatibility docs still describe Firebase bearer migration waves as live work. (source: `docs/compatibility/backward-compatibility-inventory.md` via repo grep)
