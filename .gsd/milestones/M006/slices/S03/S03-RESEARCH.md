# S03 — Research

**Date:** 2026-03-15

## Summary

S03 supports **R052** by cleaning the remaining repo-wide residue *after* S01 made the auth/session boundary honest and S02 finished the schema-side Firebase drop. The cleanest low-risk wins are on the frontend: `frontend-hormonia/lib/flow-engine/FlowEngine.ts` and `TemplateManager.ts` are pure root-level bridges into `src/lib/flow-engine/*`, and `frontend-hormonia/lib/types/ai.ts` is a deprecated compatibility barrel whose canonical home is already `frontend-hormonia/src/types/api.ts`. The key surprise is that the only visible `useFlowEngine` imports use `../lib/...` from inside `src/hooks`, so they resolve to `src/lib/...`, **not** to the root `frontend-hormonia/lib/...` bridges. That means the root bridges look genuinely deletable once absence checks are pinned.

Backend residue splits into two different classes. `backend-hormonia/app/services/session_service.py` is still a Firebase-centric facade, but the live runtime already uses `SimpleSessionService`, and the remaining `SessionService` hits are test-only plus the file itself. That makes it a strong S03 deletion target. `backend-hormonia/app/dependencies/auth_legacy_firebase.py` is more extreme: after S01 it is no longer the live auth seam, it still contains merge markers, and the remaining visible callers are in `tests/unit/test_auth_dependency_module_split.py` — a test file that also contains merge markers and fails `py_compile`. This is broken legacy residue, not honest runtime compatibility.

The biggest unfinished surface is the **operational story**. CI workflows, env examples, and docs still tell operators that Firebase is part of the current system: `.github/workflows/rls-api-tests.yml`, `.github/workflows/postman-tests.yml`, `backend-hormonia/.env.example`, `docs/backend/architecture/overview.md`, `docs/backend/guides/environment-validation.md`, `.github/CONTRIBUTING.md`, and `docs/compatibility/backward-compatibility-inventory.md` all still advertise Firebase-era configuration or compatibility as if it were active. Recommendation: execute S03 as exact bridge/dead-service removal first, then rewrite current operator surfaces to the canonical post-Firebase story, while preserving only truly historical or security-useful surfaces such as the Firebase API-key scanner in pre-commit validation.

## Recommendation

Take S03 in four passes:

1. **Delete the root frontend bridges with proof of non-use.**
   Remove `frontend-hormonia/lib/flow-engine/FlowEngine.ts`, `frontend-hormonia/lib/flow-engine/TemplateManager.ts`, and `frontend-hormonia/lib/types/ai.ts` only after pinning exact `rg` absence checks. The canonical implementations/types already live under `frontend-hormonia/src/`.
2. **Delete backend dead code that is no longer on the runtime path.**
   `backend-hormonia/app/services/session_service.py` is the cleanest candidate. `backend-hormonia/app/dependencies/auth_legacy_firebase.py` and `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` should be treated as dead/broken residue together, not as live compatibility deserving protection.
3. **Rewrite operational entrypoints so they tell the canonical story.**
   Remove or republish Firebase-era instructions from workflow env blocks, `.env.example`, `docs/backend/architecture/overview.md`, `docs/backend/guides/environment-validation.md`, `.github/CONTRIBUTING.md`, and `docs/compatibility/backward-compatibility-inventory.md`. If a historical record is worth keeping, move it behind explicit archival framing instead of leaving it in current operator docs.
4. **Keep verification narrow and evidence-based.**
   Reuse exact import scans, the republished S01 residue guard, and the existing frontend build/typecheck proof path. Do not widen S03 into AI/ADK cleanup, schema work, or broad speculative refactors.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Distinguish live auth/session residue from retired proof-only legacy text | `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend` | S01 already split backend auth/session hits into `no approved residue` vs `proof_only` boundaries; use that instead of ad hoc grep judgments. |
| Canonical home for flow-engine code | `frontend-hormonia/src/lib/flow-engine/FlowEngine.ts` and `frontend-hormonia/src/lib/flow-engine/TemplateManager.ts` | These are the real implementations; S03 should delete the root bridges instead of preserving or recreating re-export layers. |
| Canonical home for AI types | `frontend-hormonia/src/types/api.ts` | The repo already documents the migration target there, so `lib/types/ai.ts` does not need a second compatibility life. |
| Canonical runtime session service | `backend-hormonia/app/service_provider.py` + `backend-hormonia/app/services/simple_session_service.py` | Shows the live runtime path already bypasses the old Firebase-centric `SessionService`; deletion can be justified against the real provider wiring. |
| Distinguish useful security checks from live Firebase dependency | `.github/workflows/pre-commit-validation.yml` | The Firebase API-key scan is still a worthwhile secret guard, so S03 should keep it rather than deleting every Firebase string blindly. |

## Existing Code and Patterns

- `frontend-hormonia/lib/flow-engine/FlowEngine.ts` — pure backward-compatible re-export bridge into `../../src/lib/flow-engine/FlowEngine`.
- `frontend-hormonia/lib/flow-engine/TemplateManager.ts` — same bridge pattern for `TemplateManager`.
- `frontend-hormonia/src/hooks/useFlowEngine.ts` — imports `../lib/flow-engine/*` from inside `src/hooks`; that path resolves to `frontend-hormonia/src/lib/flow-engine/*`, which means the root bridge barrels are not needed by this main hook.
- `frontend-hormonia/lib/types/ai.ts` — deprecated compatibility barrel that re-exports canonical types but still defines a large set of legacy interfaces and aliases.
- `frontend-hormonia/src/types/api.ts` — canonical AI type surface; it explicitly marks the advanced AI types as migrated from `lib/types/ai.ts`.
- `frontend-hormonia/firebase.json` + `frontend-hormonia/.firebaserc` — Firebase Hosting residue still present in the frontend repo and worth proving unused before deletion.
- `backend-hormonia/app/services/session_service.py` — still advertises Firebase authentication + Redis session storage as a unified session facade.
- `backend-hormonia/app/service_provider.py` — canonical runtime uses `SimpleSessionService`, not `SessionService`.
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` — legacy Firebase/bearer/websocket helper module that still contains merge markers after S01 retired the live seam.
- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` — broken split-contract test still targeting `auth_legacy_firebase`; contains unresolved merge markers and cannot be trusted as current proof.
- `.github/workflows/rls-api-tests.yml` — still injects Firebase admin secrets into CI.
- `.github/workflows/postman-tests.yml` — still writes Firebase admin env vars into the backend test environment.
- `backend-hormonia/.env.example` — still publishes large Firebase admin/security sections as normal backend configuration.
- `docs/backend/architecture/overview.md` — still describes backend security as Firebase Admin SDK based and shows `API -> Firebase Auth` in the architecture diagram.
- `docs/backend/guides/environment-validation.md` — still documents Firebase Admin SDK as an optional live runtime mode.
- `.github/CONTRIBUTING.md` — current contributor/deploy guidance still lists Firebase/Supabase among common backend variables.
- `docs/compatibility/backward-compatibility-inventory.md` — still frames bearer/header/session shims as active migration layers even though S01 already retired that live behavior.
- `.github/workflows/pre-commit-validation.yml` — useful exception: Firebase API-key scanning still makes sense as a secret-leak guard.

## Constraints

- **R052 is the only active requirement this slice supports.** S03 succeeds only if removals are evidence-backed and replayable, not because the repo merely looks cleaner.
- **S01 already hard-cut the live auth/session seam.** S03 should consume that boundary and classify residue as dead, proof-only, or historical — not reopen runtime auth behavior.
- **S02 already owns the structural Firebase schema drop.** S03 should not widen back into Alembic/model convergence work unless a supposedly dead surface proves it still depends on the canonical head.
- **Relative import resolution matters.** `../lib/flow-engine/FlowEngine` from `src/hooks/useFlowEngine.ts` resolves inside `src/`, so naive text matching can overstate root-bridge usage.
- **Current operator surfaces must tell the current story.** Workflow env blocks, `.env.example`, and docs in active entrypoint paths cannot keep advertising Firebase as live runtime.
- **Not every Firebase string is dead residue.** Secret scanning and explicitly historical docs can stay if they are honest and isolated.
- **Broken merge-marker files poison proof.** `auth_legacy_firebase.py` and `tests/unit/test_auth_dependency_module_split.py` currently make “legacy compatibility” look more alive than it really is.

## Common Pitfalls

- **Misclassifying `src/hooks/useFlowEngine.ts` as a consumer of the root bridge barrels** — verify relative path resolution before preserving `frontend-hormonia/lib/flow-engine/*`.
- **Deleting every Firebase mention blindly** — keep useful security guardrails like the Firebase API-key scan in `.github/workflows/pre-commit-validation.yml`.
- **Removing `SessionService` without cleaning its test-only callers** — the runtime is already off it, but several test files still instantiate it directly.
- **Treating `docs/compatibility/backward-compatibility-inventory.md` as archival just because of its name** — it lives in an active docs tree and still states claims that S01 already invalidated.
- **Cleaning code only and forgetting operator entrypoints** — `.github/CONTRIBUTING.md`, backend architecture docs, env examples, and CI workflows are part of the shipped narrative for this slice.

## Open Risks

- CI and Postman jobs may still assume Firebase env vars or fixtures in ways that are not visible from static workflow snippets alone.
- `frontend-hormonia/firebase.json` / `.firebaserc` may still be referenced by unpublished manual deploy habits or scripts outside the most obvious repo entrypoints.
- Deleting `auth_legacy_firebase.py` and the split-contract test could expose other stale import assumptions that the broken test currently hides.
- Frontend proof may still have unrelated noise outside the bridge barrels, so S03 verification should keep failures localized to import/build/type surfaces that actually changed.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| GitHub Actions | `github-workflows` | installed in `<available_skills>`; directly relevant for workflow cleanup and any syntax changes |
| FastAPI | `wshobson/agents@fastapi-templates` | available (from prior M006 research); useful if S03 needs deeper FastAPI router/dependency cleanup |
| React | `vercel-labs/agent-skills@vercel-react-best-practices` | available (from prior M006 research); useful if bridge removal unexpectedly touches live frontend patterns |

## Sources

- `frontend-hormonia/lib/flow-engine/FlowEngine.ts` and `TemplateManager.ts` are pure backward-compatible bridge barrels into `src/lib/flow-engine/*`. (source: `frontend-hormonia/lib/flow-engine/FlowEngine.ts`, `frontend-hormonia/lib/flow-engine/TemplateManager.ts`)
- `frontend-hormonia/src/hooks/useFlowEngine.ts` imports `../lib/flow-engine/*` from inside `src/hooks`, so the hook resolves the canonical `src/lib/*` path rather than the root `frontend-hormonia/lib/*` bridge. (source: `frontend-hormonia/src/hooks/useFlowEngine.ts`)
- `frontend-hormonia/lib/types/ai.ts` is explicitly deprecated, while `frontend-hormonia/src/types/api.ts` already documents AI advanced types as migrated from that barrel. (source: `frontend-hormonia/lib/types/ai.ts`, `frontend-hormonia/src/types/api.ts`)
- `backend-hormonia/app/services/session_service.py` still documents Firebase-integrated session management, while the canonical runtime provider uses `SimpleSessionService`. (source: `backend-hormonia/app/services/session_service.py`, `backend-hormonia/app/service_provider.py`)
- `backend-hormonia/app/dependencies/auth_legacy_firebase.py` still contains merge markers, and the visible remaining callers are in the broken split-contract test. (source: `backend-hormonia/app/dependencies/auth_legacy_firebase.py`, `backend-hormonia/tests/unit/test_auth_dependency_module_split.py`, local repo import search)
- `backend-hormonia/tests/unit/test_auth_dependency_module_split.py` contains unresolved merge markers and still targets `auth_legacy_firebase`, so it is not trustworthy current proof. (source: `backend-hormonia/tests/unit/test_auth_dependency_module_split.py`)
- `.github/workflows/rls-api-tests.yml`, `.github/workflows/postman-tests.yml`, and `backend-hormonia/.env.example` still publish Firebase admin credentials/config as if they were active operational requirements. (source: `.github/workflows/rls-api-tests.yml`, `.github/workflows/postman-tests.yml`, `backend-hormonia/.env.example`)
- `docs/backend/architecture/overview.md`, `docs/backend/guides/environment-validation.md`, and `.github/CONTRIBUTING.md` still describe Firebase as part of the current backend/operator setup. (source: `docs/backend/architecture/overview.md`, `docs/backend/guides/environment-validation.md`, `.github/CONTRIBUTING.md`)
- `docs/compatibility/backward-compatibility-inventory.md` still frames header/bearer/session fallback as active migration shims even though S01 retired those live paths. (source: `docs/compatibility/backward-compatibility-inventory.md`)
- `.github/workflows/pre-commit-validation.yml` still uses Firebase-pattern scanning as a secret-leak guard, which is useful and should not be mistaken for live runtime dependency. (source: `.github/workflows/pre-commit-validation.yml`)
- `frontend-hormonia/firebase.json` and `.firebaserc` still exist as repo residue and should be proven unused before removal. (source: `frontend-hormonia/firebase.json`, `frontend-hormonia/.firebaserc`)
