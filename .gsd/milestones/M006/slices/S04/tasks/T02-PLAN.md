---
estimated_steps: 8
estimated_files: 5
---

# T02: Replay the full proof topology and publish M006 closeout artifacts

**Slice:** S04 — Publicar o closeout final e provar o sistema montado pós-purga
**Milestone:** M006

## Description

With the caplog blocker resolved in T01, this task runs every published verification surface on the post-purge state and records the results into a machine-readable `M006-VERIFY.json` and a human-readable `M006-SUMMARY.md`. This is the milestone's final deliverable — the replayable proof that the M004→M006 convergence arc is honest.

## Steps

1. **Run S01 residue guards.**
   - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`
   - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check frontend`
   Record pass/fail and output summary.

2. **Run S02 focused backend packs (default harness).**
   - `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_uid_validation.py tests/api/v2/test_auth_timeout.py tests/integration/test_auth_fallback.py`
   - `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py tests/api/v2/test_physicians_crud_regression.py tests/api/v2/test_admin.py tests/unit/services/test_admin_stats_service.py`
   Record pass/fail and test counts.

3. **Run S02 schema convergence under Postgres.**
   - `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_canonical_schema_head_convergence.py`
   Record pass/fail.

4. **Run S03 absence and build scans.**
   - Absence: confirm these files are absent: `backend-hormonia/app/services/session_service.py`, `backend-hormonia/app/dependencies/auth_legacy_firebase.py`. Confirm `FIREBASE_SESSION_TTL_SECONDS` has 0 hits in `backend-hormonia/app/`. Confirm `WHATSAPP_EVOLUTION_` has 0 hits in `backend-hormonia/config/cloud-run/`. Confirm `FIREBASE_ADMIN` has 0 hits in `.github/workflows/`.
   - Frontend: `cd frontend-hormonia && npx vitest run tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts`
   - Typecheck + build: `cd frontend-hormonia && npm run typecheck && npm run build`
   Record all results.

5. **Run final-schema proof `--fresh`.**
   - `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`
   Record pass/fail and point to `/tmp/gsd-m005-s04-final-schema-proof/fresh/status.json`.

6. **Run final-schema proof `--existing`.**
   - `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`
   Record pass/fail and point to `/tmp/gsd-m005-s04-final-schema-proof/existing/status.json`.

7. **Write closeout artifacts.**
   - Write `.gsd/milestones/M006/M006-VERIFY.json` following the M003-VERIFY.json structure. Each phase entry must have `status`, `command`, and a `diagnostic` pointer (file path or output location). The JSON must parse cleanly and pass: `python3 -c "import json; v=json.load(open('.gsd/milestones/M006/M006-VERIFY.json')); assert all(p.get('status')=='passed' for p in v['phases'].values())"`.
   - Write `.gsd/milestones/M006/M006-SUMMARY.md` using the standard summary YAML frontmatter format (see S02-SUMMARY.md or S03-SUMMARY.md as models). Include: what happened across all four slices, verification results, R052 validation, files modified across the milestone, known limitations, and forward intelligence for future maintainers. Set `verification_result: passed`.

8. **Update project state.**
   - In `.gsd/REQUIREMENTS.md`: move R052 from Active to Validated with proof reference to M006-VERIFY.json.
   - In `.gsd/milestones/M006/M006-ROADMAP.md`: mark S04 `[x]`.
   - In `.gsd/STATE.md`: mark M006 complete, clear active slice, update phase.

## Must-Haves

- [ ] All proof phases pass: S01 residue guards, S02 backend packs, S02 schema convergence, S03 absence/build/typecheck, frontend import-boundary, final-schema `--fresh`, final-schema `--existing`.
- [ ] `M006-VERIFY.json` exists, parses cleanly, and all phases report `status: "passed"`.
- [ ] `M006-SUMMARY.md` exists with `verification_result: passed` in frontmatter.
- [ ] R052 is validated in `REQUIREMENTS.md`.
- [ ] `STATE.md` reflects M006 complete.

## Verification

- `python3 -c "import json; v=json.load(open('.gsd/milestones/M006/M006-VERIFY.json')); assert all(p.get('status')=='passed' for p in v['phases'].values()), 'not all phases passed'; print(f'All {len(v[\"phases\"])} phases passed')"` → prints count and exits 0
- `grep 'verification_result: passed' .gsd/milestones/M006/M006-SUMMARY.md` → match found
- `grep -A2 'R052' .gsd/REQUIREMENTS.md | grep 'validated'` → match found
- `grep '✅.*M006' .gsd/STATE.md` → match found

## Inputs

- T01 completed: the caplog blocker is fixed and the S02 focused backend packs are green.
- Published runners (all reuse, no modifications):
  - `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`
  - `.gsd/milestones/M005/slices/S04/run-final-schema-proof.sh`
  - `frontend-hormonia/tests/unit/import-boundaries/dead-compat-cleanup.contract.test.ts`
- `.gsd/milestones/M003/M003-VERIFY.json` — structural model for M006-VERIFY.json.
- `.gsd/milestones/M006/slices/S02/S02-SUMMARY.md` and `.gsd/milestones/M006/slices/S03/S03-SUMMARY.md` — slice summaries to reference in milestone closeout.

## Expected Output

- `.gsd/milestones/M006/M006-VERIFY.json` — machine-readable closeout proof with all phases green.
- `.gsd/milestones/M006/M006-SUMMARY.md` — milestone closeout summary.
- `.gsd/REQUIREMENTS.md` — R052 moved to validated.
- `.gsd/milestones/M006/M006-ROADMAP.md` — S04 marked complete.
- `.gsd/STATE.md` — M006 marked complete.
