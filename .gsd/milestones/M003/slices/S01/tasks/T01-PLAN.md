---
estimated_steps: 5
estimated_files: 4
---

# T01: Add an executable evidence verifier and artifact scaffolds

**Slice:** S01 — Evidence Map And Cleanup Guardrails
**Milestone:** M003

## Description

Freeze the S01 stopping condition before any more research churn. This task adds the rerunnable verifier that later tasks must satisfy and scaffolds the slice artifacts the verifier checks so the rest of the slice closes against an explicit contract instead of loose notes.

## Steps

1. Create `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` with `--check` and `--report` modes plus `backend` / `frontend` / `all` scopes, deriving hotspot line counts, caller/import counts, and candidate reference counts from live repo scans (`rg`, `wc`) instead of hard-coded values.
2. Encode the required slice contract in the verifier: ranked hotspot inventory, cleanup guardrail matrix, deletion candidate ledger, explicit non-candidates, exact downstream verification commands, and handoff sections in `S01-SUMMARY.md` / `S01-UAT.md`.
3. Scaffold `S01-SUMMARY.md` and `S01-UAT.md` with the headings/checklists that later tasks must fill, and add any missing headings in `S01-RESEARCH.md` so the verifier has deterministic targets.
4. Keep verifier output high-signal and safe: name the missing section/file/symbol on failure, and never emit secrets, tokens, cookies, or raw payloads.
5. Run the verifier in `--check` mode and fix shell/harness issues until any failure is about missing slice content rather than a broken verification harness.

## Must-Haves

- [ ] The verifier derives evidence from the current repo state rather than trusting pasted numbers.
- [ ] The verifier supports `backend`, `frontend`, and `all` scopes so each later task can verify only the boundary it just finalized.
- [ ] The verifier reports missing or drifting sections with file/symbol names that a future agent can act on immediately.
- [ ] `S01-SUMMARY.md` and `S01-UAT.md` exist with clear placeholders for the downstream handoff and reviewer checks.
- [ ] The verification harness emits only static codebase metadata and respects the no-secrets boundary.

## Verification

- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check all`

## Observability Impact

- Signals added/changed: the slice gains one deterministic repo-scan surface that prints hotspot/candidate counts and names the exact missing evidence on failure for `backend`, `frontend`, or `all` scope.
- How a future agent inspects this: run `verify-evidence-map.sh --report <scope>` for the current scan snapshot and `--check <scope>` for pass/fail on slice completeness.
- Failure state exposed: missing inventory rows, missing guardrail commands, absent non-candidate notes, or incomplete handoff artifacts become explicit verifier failures instead of silent planning drift.

## Inputs

- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — existing research baseline that already contains the main hotspot findings but not the executable proof boundary.
- `.gsd/milestones/M003/slices/S01/S01-PLAN.md` — defines the slice-level must-haves and the contract the verifier must enforce.

## Expected Output

- `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` — rerunnable slice verifier with `--check` / `--report` modes and `backend` / `frontend` / `all` scopes.
- `.gsd/milestones/M003/slices/S01/S01-SUMMARY.md` and `.gsd/milestones/M003/slices/S01/S01-UAT.md` — scaffolded closeout artifacts ready for the finalized handoff.
- `.gsd/milestones/M003/slices/S01/S01-RESEARCH.md` — updated with any missing verifier-target headings needed for deterministic checks.
