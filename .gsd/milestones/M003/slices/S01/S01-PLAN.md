# S01: Evidence Map And Cleanup Guardrails

**Goal:** Turn the M003 hotspot research into an executable evidence map that ranks the first cleanup seams, pins the visible contracts that later refactors must preserve, and defines proof-before-deletion guardrails for every early cleanup candidate.
**Demo:** A future agent can run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all` and use `S01-RESEARCH.md`, `S01-SUMMARY.md`, and `S01-UAT.md` to see the exact backend/frontend attack order, the protected auth/client façades, the deletion candidates that still need proof, and the focused verification commands that downstream slices must keep green.

## Requirement Coverage

- Owned by this slice: **R035** — dead-code removal is evidence-based, not taste-based.
- Supported by this slice: **R039** — structural cleanup leaves strong proof, not just nicer files.
- Not claimed here: **R034**, **R036**, **R037**, and **R038** remain downstream execution slices.

## Must-Haves

- Add a rerunnable slice verifier that fails when the hotspot inventory, cleanup guardrail matrix, deletion candidate ledger, explicit non-candidates, or downstream handoff sections are missing or drift from repo evidence.  
  _Covers: R035, R039_
- `S01-RESEARCH.md` records a ranked backend/frontend hotspot inventory with concrete blast-radius evidence, rationale, and recommended attack order for S02/S03.  
  _Covers: R035_
- `S01-RESEARCH.md` records cleanup guardrails for the backend session dict contract, backend `User` contract, canonical auth writer/reader alignment, admin/dashboard wrappers, websocket auth adjacency, frontend client/type façades, and final smoke obligations.  
  _Covers: R035, supports R039_
- `S01-RESEARCH.md` records a deletion candidate ledger with current evidence, required proof before removal or isolation, and explicit non-candidates that must stay live for now.  
  _Covers: R035_
- `S01-SUMMARY.md` and `S01-UAT.md` hand off the exact next-slice execution order, verification commands, and reviewer checks so S02–S05 do not need to reopen repo-wide discovery work.  
  _Supports: R039_

## Proof Level

- This slice proves: contract
- Real runtime required: no
- Human/UAT required: no

## Verification

- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`

## Observability / Diagnostics

- Runtime signals: `verify-evidence-map.sh --report <backend|frontend|all>` emits current hotspot line counts, caller/import counts, candidate-reference counts, and section-level drift notes keyed by file or symbol.
- Inspection surfaces: `S01-RESEARCH.md`, `S01-SUMMARY.md`, `S01-UAT.md`, and the verifier script stdout/exit status.
- Failure visibility: the verifier exits non-zero with a named missing section, missing verification command, or evidence mismatch so the next agent can localize drift quickly.
- Redaction constraints: output is limited to source paths, static counts, and test/script names; do not emit secrets, cookies, tokens, or patient data.

## Integration Closure

- Upstream surfaces consumed: `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/api/v2/routers/admin/dependencies.py`, `backend-hormonia/app/api/v2/routers/reports.py`, `backend-hormonia/app/api/v2/routers/enhanced_reports.py`, `backend-hormonia/app/api/v2/routers/roles/dependencies.py`, `frontend-hormonia/src/lib/api-client.ts`, `frontend-hormonia/src/lib/api-client/index.ts`, `frontend-hormonia/src/lib/api-client/types.ts`, `frontend-hormonia/src/types/api.ts`, `frontend-hormonia/src/lib/types/api.ts`, plus the M003 roadmap/research/requirements decisions already established.
- New wiring introduced in this slice: a single slice verifier binds live repo scans to the research, summary, and UAT artifacts so later cleanup slices inherit one consistent evidence contract instead of ad hoc grep notes.
- What remains before the milestone is truly usable end-to-end: S02 must split backend auth/session behind the preserved contracts, S03 must split frontend client/type ownership behind the preserved façades, S04 must remove or isolate only proven-dead residue, and S05 must replay focused plus integrated smoke proof.

## Tasks

- [x] **T01: Add an executable evidence verifier and artifact scaffolds** `est:45m`
  - Why: S01 should close on a rerunnable proof boundary, not on prose alone; the verifier makes the slice fail loudly when required inventory, guardrails, or handoff sections are missing.
  - Files: `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh`, `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md`, `.gsd/milestones/M003/slices/S01/S01-SUMMARY.md`, `.gsd/milestones/M003/slices/S01/S01-UAT.md`
  - Do: Create `verify-evidence-map.sh` with `--check` and `--report` modes plus `backend` / `frontend` / `all` scopes, deriving hotspot counts from live repo scans instead of hand-entered numbers; make it assert the required hotspot/guardrail/candidate/non-candidate/handoff sections; scaffold any missing slice artifacts so later tasks have explicit targets; keep output safe and deterministic.
  - Verify: `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all && bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`
  - Done when: the verifier runs without shell/harness errors, reports current repo evidence, and fails only on real missing slice content.
- [x] **T02: Finalize backend hotspot evidence and cleanup guardrails** `est:1h05m`
  - Why: The highest-risk next slice is backend auth/session, so S01 has to pin the real contract, blast radius, wrapper drift, and deletion proof requirements before any structural split begins.
  - Files: `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md`, `backend-hormonia/app/dependencies/auth_dependencies.py`, `backend-hormonia/app/api/v2/routers/auth.py`, `backend-hormonia/app/api/v2/routers/admin/dependencies.py`, `backend-hormonia/app/api/v2/routers/reports.py`, `backend-hormonia/app/api/v2/routers/enhanced_reports.py`, `backend-hormonia/app/api/v2/routers/roles/dependencies.py`
  - Do: Re-scan backend hotspot size and caller counts; document the stable mapping-style vs `User` auth contracts and `request.state` side effects; capture wrapper drift and cookie alias risks; and fill backend guardrail + deletion-ledger rows with exact proof commands and explicit non-candidates like the still-live `permissions` field.
  - Verify: `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check backend && bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report backend`
  - Done when: the research artifact records the backend ranking, guardrails, and candidate proof gates precisely enough that S02 can start without reopening the backend scan.
- [x] **T03: Finalize frontend hotspot evidence and close the handoff pack** `est:1h05m`
  - Why: S03 and S04 need one clear frontend source-of-truth for public façades, duplicate-type ownership, and compatibility cleanup candidates; the slice is not done until that handoff is explicit and rerunnable.
  - Files: `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md`, `.gsd/milestones/M003/slices/S01/S01-SUMMARY.md`, `.gsd/milestones/M003/slices/S01/S01-UAT.md`, `frontend-hormonia/src/lib/api-client.ts`, `frontend-hormonia/src/lib/api-client/index.ts`, `frontend-hormonia/src/lib/api-client/types.ts`, `frontend-hormonia/src/types/api.ts`, `frontend-hormonia/src/lib/types/api.ts`
  - Do: Re-scan the frontend façade/import and duplicate-type evidence; finish the frontend ranking, guardrail, and deletion-ledger sections; write the slice summary and UAT checklist with the downstream execution order and proof commands; and reconcile the artifacts with the verifier report so later slices inherit one stable plan.
  - Verify: `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all && bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
  - Done when: the verifier passes end-to-end, the handoff artifacts are complete, and S02/S03 can begin from the slice outputs without redoing repo-wide discovery.

## Files Likely Touched

- `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh`
- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md`
- `.gsd/milestones/M003/slices/S01/S01-SUMMARY.md`
- `.gsd/milestones/M003/slices/S01/S01-UAT.md`
