---
estimated_steps: 4
estimated_files: 6
---

# T05: Shrink the frontend residue boundary and publish the S03 handoff

**Slice:** S03 — Frontend oficial convergido para contrato session-first canônico
**Milestone:** M004

## Description

Close S03 the same way S01 and S02 closed: with the residue guard, the handoff artifacts, and the focused proof all telling the same story. Once the official frontend contract is clean, the frontend side of the S01 boundary must shrink and the slice has to publish what remains for S04, S05, and S06 instead of leaving later work to infer it from diffs.

## Steps

1. Re-run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend` after the code changes and compare removed or moved frontend hotspots against the current allowlist.
2. Update `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`, `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`, `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`, and `.gsd/milestones/M004/slices/S01/S01-UAT.md` so the frontend residue boundary reflects the post-S03 state honestly.
3. Write `.gsd/milestones/M004/slices/S03/S03-SUMMARY.md` and `.gsd/milestones/M004/slices/S03/S03-UAT.md` with the canonical frontend contract, routed `/login` → `/dashboard` → `/admin` proof, and the exact backend-owned legacy transport surfaces left for later slices.
4. Re-run the full S03 verification pack, `npm run build`, and `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend` so the code, proof, and handoff close together.

## Must-Haves

- [ ] The S01 allowlist, S01 handoff artifacts, and S03 handoff artifacts all describe the same reduced frontend residue boundary.
- [ ] Remaining auth/session legacy after S03 is named explicitly with the verifier’s existing category ids and scope names.
- [ ] The S03 handoff tells later slices what is still backend-owned or adjacently out of scope instead of implying the milestone is already done.
- [ ] Focused frontend proof, build, and the frontend residue guard are all green at slice closeout.

## Verification

- `(cd frontend-hormonia && npx vitest run tests/unit/api-client/auth-headers.test.ts tests/lib/api-client/core.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/admin-auth-flow.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts tests/unit/hooks/useSessionManagement.test.ts tests/unit/types/admin-types.test.ts tests/lib/api-client/__tests__/normalizers.test.ts src/utils/__tests__/init-validator.test.ts && npm run build) && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report frontend && bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`

## Observability Impact

- Signals added/changed: the live frontend residue report becomes the authoritative inventory for what legacy auth/session surface still remains after S03.
- How a future agent inspects this: replay the S03 verification command and compare it with the updated S01/S03 handoff artifacts.
- Failure state exposed: stale allowlist bookkeeping, moved hotspots, or undocumented surviving residue fail as explicit guard or handoff mismatches rather than as silent drift.

## Inputs

- `.gsd/milestones/M004/slices/S03/tasks/T01-PLAN.md` — the focused frontend proof that must be green at closeout.
- `.gsd/milestones/M004/slices/S03/tasks/T02-PLAN.md` — HTTP/session-storage residue that should now be gone from the official frontend path.
- `.gsd/milestones/M004/slices/S03/tasks/T03-PLAN.md` — websocket query residue that should now be gone from the official realtime path.
- `.gsd/milestones/M004/slices/S03/tasks/T04-PLAN.md` — official narrative/type residue that should now be cleaned from the canonical frontend story.
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` — current residue-boundary contract that this task must shrink intentionally.
- `.gsd/milestones/M004/slices/S02/S02-SUMMARY.md` — backend handoff that defines the remaining transport/backend work still outside S03.

## Expected Output

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — reduced frontend residue boundary aligned to the post-S03 runtime.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — updated readable frontend hotspot map.
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` — condensed guardrail handoff updated for the post-S03 frontend boundary.
- `.gsd/milestones/M004/slices/S01/S01-UAT.md` — reviewer script aligned to the smaller frontend residue surface.
- `.gsd/milestones/M004/slices/S03/S03-SUMMARY.md` — slice closeout summary with canonical frontend contract and remaining milestone work.
- `.gsd/milestones/M004/slices/S03/S03-UAT.md` — replayable S03 verification checklist for later slices.
