---
estimated_steps: 5
estimated_files: 3
---

# T01: Build the scoped runtime-residue verifier and regression harness

**Slice:** S01 — Guardrails do corte canônico de runtime
**Milestone:** M004

## Description

Turn the S01 research into an executable contract before any handoff prose is finalized. This task creates the scoped runtime-residue verifier, encodes the approved residue boundary in a machine-readable allowlist, and adds a real regression test so future slices inherit a guard that can prove drift rather than merely describe it.

## Steps

1. Create `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` with separate allowlist groups for `firebase_uid`, root legacy `/session/*`, `X-Session-ID`, session-as-Bearer fallback, websocket `session_id` query fallback, and Firebase narrative residue, plus the explicit out-of-scope exclusions from the slice research.
2. Implement `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` with `--report` and `--check` modes plus `backend`, `frontend`, and `all` scopes, deriving category matches from the current repo state instead of hard-coded counts.
3. Make `--report` print approved live residue by category/file/count and make `--check` fail with the residue category plus unexpected file or moved hotspot when the allowlist no longer matches the repo.
4. Add `backend-hormonia/tests/unit/test_runtime_residue_guard.py` as a subprocess-style regression suite that exercises approved fixtures, forbidden fixtures, and the script’s scope handling without depending on the real repo contents.
5. Run the verifier and the regression test, fixing harness issues until failures indicate real boundary drift rather than a broken guard script.

## Must-Haves

- [ ] The allowlist is category-specific and scope-specific instead of one broad repo-wide ban.
- [ ] The verifier explicitly excludes schema/model residue, unrelated vendor/session strings, and historical docs/tests from its failure surface.
- [ ] `--report` and `--check` both support `backend`, `frontend`, and `all` scopes.
- [ ] The regression test proves an approved compat island passes and an unallowlisted header/bearer/query/comment residue fails with a useful message.
- [ ] The verifier output stays redaction-safe and never echoes live tokens, cookies, or user data.

## Verification

- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`

## Observability Impact

- Signals added/changed: a deterministic verifier report that emits per-category residue counts and names the exact unexpected file or moved approved hotspot on drift.
- How a future agent inspects this: run `verify-runtime-residue.sh --report <scope>` for the current residue map and `--check <scope>` for pass/fail against the allowlist, then read the regression test for the expected guard behavior.
- Failure state exposed: the category (`firebase_uid`, `/session/*`, `X-Session-ID`, Bearer fallback, websocket query fallback, or narrative residue) and the offending file/path become explicit on failure instead of being buried in ad hoc grep output.

## Inputs

- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — defines the scoped residue categories, official-runtime boundary, exclusions, and known live hotspots.
- `.gsd/milestones/M002/slices/S04/verify-no-firebase-auth.sh` — existing scoped residue-scan pattern to reuse rather than inventing a noisier repo-wide ban.
- `.gsd/milestones/M003/slices/S01/verify-evidence-map.sh` — existing `--report` / `--check` slice-verifier pattern to adapt for machine-readable drift reporting.

## Expected Output

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — the approved residue boundary grouped by category and scope.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — the executable slice verifier for report/check runs.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — regression proof that the verifier distinguishes approved residue from reintroduced drift.
