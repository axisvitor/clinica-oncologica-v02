---
id: M003
provides:
  - Closed the structural cleanup milestone with smaller auth/client hotspots, proof-backed dead-code removal, and replayable integrated verification across auth, dashboard/admin, and WhatsApp-adjacent routed surfaces.
key_decisions:
  - Keep `app.dependencies.auth_dependencies`, `@/lib/api-client`, `@/lib/api-client/types`, and `@/types/api` as stable façades while moving ownership behind them.
  - Remove proven-dead compatibility files outright once grep plus focused test/type/build proof clears, and document retained compatibility islands explicitly instead of leaving ambiguous residue.
  - Do not treat M003 as complete until the assembled local stack proves legacy `/session/logout`, canonical session-first auth, and routed `/dashboard`, `/admin`, and `/whatsapp` smoke together.
patterns_established:
  - Start structural cleanup with a live evidence map, close it with a live verifier, and keep the verifier anchors current as files shrink or disappear.
  - Split mixed-responsibility hotspots by caller contract first, then enforce the seam with focused contract suites before widening into runtime smoke.
  - Leave one replayable closeout artifact (`M003-VERIFY.json`) that ties structural proof, direct runtime probes, and routed browser smoke to concrete commands.
observability_surfaces:
  - .gsd/milestones/M003/M003-VERIFY.json
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all
  - bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all
  - frontend-hormonia/tests/e2e/auth/session-first-hard-cut.spec.ts
  - .gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md
requirement_outcomes:
  - id: R034
    from_status: active
    to_status: validated
    proof: S02/S03 reduced the target hotspots materially (`auth_dependencies.py` 1579→675, `src/lib/api-client/index.ts` 1304→223, `src/lib/api-client/types.ts` 1159→26) and the focused backend/frontend proof packs plus the final structural gate stayed green.
  - id: R035
    from_status: active
    to_status: validated
    proof: S01 established the evidence-map verifier and deletion ledger; S04 executed in-scope removals with manifest-backed grep/test/type/build proof and kept the verifier green.
  - id: R036
    from_status: active
    to_status: validated
    proof: S04 deleted the proven-dead frontend compat files, kept removed backend auth exports off the public surface, and documented retained compatibility islands explicitly in `S04-CLEANUP-MANIFEST.md`.
  - id: R037
    from_status: active
    to_status: validated
    proof: Final proof now includes green direct runtime probes for canonical login/verify, Bearer fallback, legacy `/session/logout`, and post-logout `session/validate`, plus green routed smoke for `/dashboard`, `/admin`, and `/whatsapp` and a green seeded-user Chromium acceptance spec.
  - id: R038
    from_status: active
    to_status: validated
    proof: The milestone leaves smaller seams, explicit canonical-vs-legacy ownership maps, the S04 cleanup manifest, and `M003-VERIFY.json` as replayable maintenance guidance instead of one-off refactor diffs.
  - id: R039
    from_status: active
    to_status: validated
    proof: The final closeout combines the green evidence-map gate, focused backend/frontend suites, seeded-user Playwright acceptance, direct assembled-stack probes, and routed browser smoke rather than relying on structural diffs alone.
duration: 2 days across 5 slices
verification_result: passed
completed_at: 2026-03-13T22:17:00-03:00
---

# M003: Structural Refactor And Dead-Code Cleanup

**Closed the auth/client structural cleanup with real size reduction, evidence-backed dead-code removal, and final runtime proof across session auth, dashboard/admin, and WhatsApp-adjacent routes.**

## What Happened

S01 fixed the milestone boundary before any deletion or large refactor happened: it ranked the backend and frontend hotspots, defined the protected contracts, and turned the dead-code discussion into a verifier plus proof ledger instead of cleanup by taste.

S02 then split the backend auth/session hotspot along the real caller seams. `app.dependencies.auth_dependencies` stayed the stable import/override façade, while the session contract, cache hydration, user adaptation, role wrappers, and legacy Firebase/bearer/websocket compatibility moved into focused modules. The backend hotspot dropped from a 1579-line mixed-responsibility file to a 675-line façade backed by contract suites that kept mapping-style session dict behavior, `User` adaptation, request-state side effects, wrapper compatibility, and websocket diagnostics intact.

S03 did the same job on the frontend client/type surface. The public façades stayed stable (`@/lib/api-client`, `@/lib/api-client/types`, `@/types/api`), while `src/lib/api-client/index.ts` became a composition seam and `src/lib/api-client/types.ts` became a barrel over domain-owned transport DTO modules. The main client hotspot dropped from 1304 lines to 223 and the transport type bag dropped from 1159 lines to 26, while focused structural, integration, typecheck, and build proof stayed green.

S04 used the proof ledger instead of intuition. It deleted the strongest proven-dead frontend compatibility residue (`src/lib/api.ts`, `src/lib/types/api.ts`, `src/hooks/use-quiz-session.ts`), converted backend cleanup drift into negative contract coverage rather than reviving obsolete wrappers, and published `S04-CLEANUP-MANIFEST.md` so the remaining compatibility islands were explicit instead of half-dead folklore.

S05 finished the milestone the way the roadmap required: on assembled proof, not on prettier files. The structural gate was replayed green, the no-Firebase local stack re-proved canonical session-first auth plus Bearer fallback, legacy `/session/logout` was replayed green on the assembled backend, the seeded-user Chromium acceptance spec passed, and routed smoke for `/dashboard`, `/admin`, and `/whatsapp` loaded successfully on the live frontend. The last bookkeeping drift in the living verifier was two stale backend line-count anchors in `S01-RESEARCH.md`; once corrected, the milestone gate returned to green.

## Cross-Slice Verification

- **Success criterion: the chosen hotspots are materially smaller and clearer.**
  - Backend: `backend-hormonia/app/dependencies/auth_dependencies.py` shrank from 1579 lines at S01 baseline to 675 lines at final check, with responsibility split into `auth_session_contract.py`, `auth_session_cache.py`, `auth_user_adapter.py`, `auth_role_dependencies.py`, and `auth_legacy_firebase.py`.
  - Frontend: `frontend-hormonia/src/lib/api-client/index.ts` shrank from 1304 to 223 lines; `frontend-hormonia/src/lib/api-client/types.ts` shrank from 1159 to 26 lines.
  - Proof: `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all` → `RESULT: --check all OK`; focused backend/frontend structural packs passed.

- **Success criterion: dead-code or obsolete compatibility removal is backed by explicit evidence.**
  - Proof surfaces: `S01-RESEARCH.md`, `verify-evidence-map.sh`, and `S04-CLEANUP-MANIFEST.md`.
  - Removal proof: `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts`, `backend-hormonia/tests/unit/test_auth_dependency_module_split.py`, focused frontend/backend suites, typecheck/build, and manifest-backed deletion ledger.

- **Success criterion: auth/session, dashboard/admin, and affected critical paths keep the same visible contract.**
  - Focused proof: `cd backend-hormonia && pytest -q tests/unit/test_auth_dependency_module_split.py tests/api/v2/test_auth_hard_cut_cleanup.py tests/api/test_websocket_session_auth_contract.py tests/auth/test_session_role_enforcement.py tests/security/test_rbac_authorization.py tests/auth/test_session_validation.py tests/services/websocket/test_connection_manager.py tests/integration/test_auth_hard_cut_end_to_end.py` → passed.
  - Focused frontend proof: `cd frontend-hormonia && npm run test -- tests/integration/api-client.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts && npm run typecheck && npm run build` → passed.
  - Direct runtime proof: canonical login, cookie verify, Bearer verify, Bearer `/users/me`, legacy `/session/logout`, and post-logout `/session/validate` all behaved as expected on the assembled local stack; recorded in `.gsd/milestones/M003/M003-VERIFY.json`.

- **Success criterion: the milestone closes with focused proof plus critical smoke, not just static diffs.**
  - Seeded-user browser acceptance: `cd frontend-hormonia && source /tmp/gsd-s05-browser-bootstrap ./node_modules/.bin/playwright test tests/e2e/auth/session-first-hard-cut.spec.ts --config tests/e2e/playwright.config.e2e.ts --project=chromium` → passed.
  - Routed smoke: live headless browser replay reached `/dashboard`, `/admin`, and `/whatsapp` with the expected headings `Dashboard`, `Admin Dashboard`, and `WhatsApp Integration`; recorded in `.gsd/milestones/M003/M003-VERIFY.json`.
  - Structural gate: `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all` and `--check all` → passed after refreshing two stale anchors.

- **Milestone definition of done check.**
  - Slices S01–S05 are checked in the roadmap.
  - Slice summaries exist for S01–S05.
  - Cross-slice integration points now work on current proof: stable backend auth/session façade, stable frontend client/type façade, manifest-backed cleanup boundary, green structural gate, green direct runtime probes, and green routed browser smoke.
  - Result: definition of done met.

## Requirement Changes

- R034: active → validated — S02/S03 materially reduced the targeted backend/frontend hotspots and the final gate re-proved the reduced seams under focused verification.
- R035: active → validated — S01’s evidence map plus S04’s manifest-backed removals proved cleanup stayed evidence-first.
- R036: active → validated — obsolete compatibility layers were either deleted (`src/lib/api.ts`, `src/lib/types/api.ts`, `src/hooks/use-quiz-session.ts`) or explicitly isolated/documented.
- R037: active → validated — assembled auth/session continuity, legacy logout continuity, seeded-user Playwright acceptance, and routed `/dashboard` / `/admin` / `/whatsapp` smoke are now green together.
- R038: active → validated — maintainers inherit smaller seams, cleaner ownership maps, explicit retained-compatibility rationale, and a replayable verification artifact instead of rediscovery work.
- R039: active → validated — milestone closeout now rests on a green structural verifier, focused backend/frontend packs, live runtime probes, and browser proof.

## Forward Intelligence

### What the next milestone should know
- `M003-VERIFY.json` is the shortest trustworthy replay surface for what actually closed this milestone: structural gate, focused packs, direct runtime probe, seeded-user Chromium acceptance, and routed smoke.
- The remaining large files after M003 are adjacent hotspots (`flows.py`, `message_handler.py`, `types/api.ts`) rather than the auth/client seams already targeted here.
- The routed smoke surfaced one still-non-blocking runtime annoyance: `TaskHealthIndicator` logs queue-status fetch errors during route smoke even though `/dashboard`, `/admin`, and `/whatsapp` load successfully.

### What's fragile
- `backend-hormonia/app/routers/auth_session.py` — still a retained compatibility island with legacy session behavior; M003 proved it works, not that it is ready for deletion.
- `frontend-hormonia/src/types/api.ts` — still a large app-facing façade even after the transport type split; future cleanup should narrow ownership carefully rather than flattening UI and transport types together.

### Authoritative diagnostics
- `.gsd/milestones/M003/M003-VERIFY.json` — current milestone-close source of truth for what passed and which commands produced the proof.
- `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md` — authoritative deleted-vs-retained compatibility boundary.
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all` — fastest structural drift detector for the hotspot and cleanup boundary.

### What assumptions changed
- "S05 is still blocked on `/session/logout`" — no longer true on the current branch; the assembled direct probe now returns `200` with successful session invalidation.
- "The last proof needed is probably another focused test rerun" — false; the real milestone close required seeded-user browser proof and routed smoke, not more structural aesthetics.
- "The evidence-map gate is fully stable once S04 lands" — almost; the final close still had two stale line-count anchors that needed refresh after later code movement.

## Files Created/Modified

- `.gsd/milestones/M003/M003-SUMMARY.md` — milestone closeout tying the five slices to final proof and requirement transitions.
- `.gsd/milestones/M003/M003-VERIFY.json` — replayable final verification artifact for structural gate, focused packs, direct runtime probes, and routed smoke.
- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — refreshed the last stale verifier anchors so the living evidence gate matches the shipped repo state.
- `.gsd/REQUIREMENTS.md` — moved R034, R035, R036, R037, R038, and R039 into validated status for the completed milestone.
- `.gsd/PROJECT.md` — marked M003 complete and updated the current project state.
- `.gsd/STATE.md` — kept the repo-level status aligned with the now-green M003 closeout.
