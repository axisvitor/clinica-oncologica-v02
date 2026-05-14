# S05: Unified Runner, Evidence Matrix, and Strict Closure Gate

**Goal:** Assemble M015 into a strict closeout path: the runner can execute all implemented seams with no seam filter, every M014-deferred runtime item is mapped to fresh evidence/fixed outcome/non-goal in a redaction-safe matrix, a validator mechanically rejects false green results, and the final command leaves no M015 runtime containers or bound ports behind.
**Demo:** Run `./scripts/security/verify-m015-runtime-security.sh` with no seam filter and receive a pass/fail result plus an M015 evidence matrix that maps every M014-deferred runtime item to fresh evidence, an explicit non-goal, or a fixed outcome.

## Must-Haves

- Running `./scripts/security/verify-m015-runtime-security.sh` with no `--seam` filter executes all implemented seams (`db`, `session`, `provider`, `artifact`) in deterministic order and returns a real pass/fail result.
- Unknown seams still fail closed before setup; no-filter no longer means a false error, it means all-seam closeout.
- A durable M015 evidence matrix maps each M014-deferred runtime item and requirements R012/R013/R014/R015/R017/R018 to fresh evidence, fixed outcome, explicit non-goal, or closure-blocking failure.
- The matrix validator rejects missing rows, stale correlation IDs, placeholders/TODOs, failed seam results, unsafe sensitive content, raw IDs/paths/URLs/cookies/session data, and unresolved red signals.
- Final evidence includes command, seam correlations, evidence paths, validator status, teardown status, non-goals, and warning policy without live-provider, production, real PHI, browser/frontend, CDN/object-storage, broad DAST, or exploitation overclaims.
- Post-run verification confirms no active M015 Docker containers and no M015 host ports remain bound.

## Proof Level

- This slice proves: Final-assembly operational proof. Real runtime required: yes — the final task must run the actual M015 Docker runner across all seams. Human/UAT required: no; CLI output, evidence artifacts, validator results, and teardown state are the proof.

## Integration Closure

Consumes S01 DB, S02 session, S03 provider, and S04 artifact seam evidence and runner branches. Introduces unified all-seam orchestration plus matrix generation/validation. After S05, M015 should be ready for milestone validation/closure; no downstream slice remains inside this milestone.

## Verification

- Adds final matrix diagnostics, per-row evidence source/status/non-goal fields, validator failure classes, unified runner phase logs, and post-run teardown checks so a future agent can see exactly which seam/row blocked closure without exposing secrets or PHI.

## Tasks

- [x] **T01: Lock final matrix and no-filter runner contracts** `est:2h`
  Why: S05 must define the closeout contract before changing runner behavior; otherwise matrix generation can silently omit a deferred item.
  Do:
  1. Add static tests that define required all-seam behavior, matrix artifact names, required matrix rows, and validator failure cases.
  2. Include contract rows for R012/R013/R014/R015/R017/R018 and M014-deferred DB/session/provider/artifact runtime items.
  3. Assert matrix artifacts are written under `backend-hormonia/docs/reports/security/m015/` and use redaction validation.
  4. Keep tests static/fast; do not start Docker in this task.
  Done when: contract tests fail on the current no-filter behavior/missing matrix, and pass after later tasks implement it.
  - Files: `backend-hormonia/tests/security/test_m015_final_matrix_contract.py`, `backend-hormonia/tests/security/test_m015_runtime_harness.py`, `scripts/security/m015-runtime/tests/test_runner_contract.py`
  - Verify: cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_final_matrix_contract.py tests/security/test_m015_runtime_harness.py ../scripts/security/m015-runtime/tests/test_runner_contract.py -q

- [x] **T02: Implement unified all-seam runner mode** `est:3h`
  Why: The milestone success criteria require a single committed runner that can execute all seams; S05 must convert no-filter invocation from fail-closed placeholder into all-seam closeout while preserving unknown seam fail-closed behavior.
  Do:
  1. Update CLI usage/listing so `--seam` is optional for all-seam closeout but still accepted for scoped debugging.
  2. Add deterministic seam order: `db`, `session`, `provider`, `artifact`.
  3. Ensure each seam gets its own correlation ID/evidence directory or a clear parent all-run correlation with child seam correlations.
  4. Preserve `--keep-stack`, `--teardown-only`, port/project isolation, and sanitized phase logs.
  5. Keep scoped seam behavior unchanged.
  Done when: no-filter dry/static contracts pass and unknown seam still exits before setup.
  - Files: `scripts/security/verify-m015-runtime-security.sh`, `scripts/security/m015-runtime/README.md`, `backend-hormonia/tests/security/test_m015_runtime_harness.py`, `scripts/security/m015-runtime/tests/test_runner_contract.py`
  - Verify: bash -n scripts/security/verify-m015-runtime-security.sh && ./scripts/security/verify-m015-runtime-security.sh --list-seams && ./scripts/security/verify-m015-runtime-security.sh --seam not-a-seam >/tmp/m015-unknown.out 2>&1; test $? -eq 64 && grep -q "unknown seam" /tmp/m015-unknown.out && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_runtime_harness.py ../scripts/security/m015-runtime/tests/test_runner_contract.py -q

- [x] **T03: Generate redaction-safe M015 evidence matrix** `est:3h`
  Why: S05's central artifact is the evidence matrix, not another seam log; the generator must consolidate prior seam evidence into explicit requirement/deferred-item rows.
  Do:
  1. Implement a matrix helper script/module under `scripts/security/m015-runtime/` that reads DB/session/provider/artifact evidence and summaries.
  2. Emit `m015-evidence-matrix.json` and `m015-evidence-matrix.md` under `backend-hormonia/docs/reports/security/m015/`.
  3. Populate rows with requirement IDs, source seam, evidence path, correlation ID, result, proof class, non-goal/fixed-outcome status, and redaction verdict.
  4. Include the S04-discovered upload schema/auth fixes as fixed outcomes, and the upload quota warning as an explicit warning-policy item for validator review.
  5. Validate outputs with existing redaction denylist helpers.
  Done when: the generator creates matrix artifacts from current seam evidence without Docker and contract tests pass.
  - Files: `scripts/security/m015-runtime/evidence_matrix.py`, `scripts/security/m015-runtime/redaction.py`, `backend-hormonia/tests/security/test_m015_final_matrix_contract.py`, `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json`, `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.md`
  - Verify: python3 -m py_compile scripts/security/m015-runtime/evidence_matrix.py && python3 scripts/security/m015-runtime/evidence_matrix.py --input-dir backend-hormonia/docs/reports/security/m015 --output-dir backend-hormonia/docs/reports/security/m015 && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_final_matrix_contract.py -q

- [x] **T04: Enforce strict matrix validator and red-signal policy** `est:3h`
  Why: Final closure must be mechanically blocked on missing/stale/unsafe/failed evidence rather than relying on narrative review.
  Do:
  1. Add strict validation mode to the matrix helper or a companion validator.
  2. Reject missing required rows/artifacts, non-passed seam results, stale/mismatched correlation references, placeholders/TODO text, raw sensitive shapes, raw download URLs/private paths/cookies/session IDs, unclassified warnings, and unresolved red signals.
  3. Add negative tests using temporary mutated evidence/matrix fixtures.
  4. Wire the validator into the runner's all-seam closeout path after matrix generation.
  Done when: negative tests prove false greens are rejected and the current generated matrix validates cleanly.
  - Files: `scripts/security/m015-runtime/evidence_matrix.py`, `backend-hormonia/tests/security/test_m015_final_matrix_contract.py`, `scripts/security/verify-m015-runtime-security.sh`, `scripts/security/m015-runtime/README.md`
  - Verify: python3 scripts/security/m015-runtime/evidence_matrix.py --input-dir backend-hormonia/docs/reports/security/m015 --output-dir backend-hormonia/docs/reports/security/m015 --validate && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_final_matrix_contract.py tests/security/test_m015_runtime_harness.py -q

- [x] **T05: Run final all-seam proof and persist closure matrix** `est:2h`
  Why: M015 is not complete until the final entrypoint exercises all seams, generates/validates the matrix, preserves only redaction-safe evidence, and tears down cleanly.
  Do:
  1. Run the full static/regression gate for runner, matrix, S01-S04 seam contracts, and M014 regressions.
  2. Run `./scripts/security/verify-m015-runtime-security.sh` with no seam filter to execute all seams and final matrix validation.
  3. Fix any red signals discovered by the all-seam pass; do not document failures as green.
  4. Confirm durable matrix JSON/MD and all seam evidence record passed/fixed/non-goal statuses.
  5. Confirm no active M015 runtime containers or bound ports remain.
  Done when: the full S05 gate exits 0 and durable matrix artifacts validate redaction-clean with all required rows present.
  - Files: `scripts/security/verify-m015-runtime-security.sh`, `scripts/security/m015-runtime/evidence_matrix.py`, `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json`, `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.md`, `backend-hormonia/tests/security/test_m015_final_matrix_contract.py`
  - Verify: bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && PYTHONPATH=backend-hormonia:scripts/security/m015-runtime pytest scripts/security/m015-runtime/tests/test_runner_contract.py backend-hormonia/tests/security/test_m015_runtime_harness.py backend-hormonia/tests/security/test_m015_final_matrix_contract.py backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py backend-hormonia/tests/api/v2/test_private_upload_serving.py backend-hormonia/tests/api/v2/test_report_ownership_closure.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py -q && ./scripts/security/verify-m015-runtime-security.sh && python3 scripts/security/m015-runtime/evidence_matrix.py --input-dir backend-hormonia/docs/reports/security/m015 --output-dir backend-hormonia/docs/reports/security/m015 --validate && (docker ps --format '{{.Names}} {{.Ports}}' | grep -E 'm015-runtime|18080|15432' && exit 1 || true)

## Files Likely Touched

- backend-hormonia/tests/security/test_m015_final_matrix_contract.py
- backend-hormonia/tests/security/test_m015_runtime_harness.py
- scripts/security/m015-runtime/tests/test_runner_contract.py
- scripts/security/verify-m015-runtime-security.sh
- scripts/security/m015-runtime/README.md
- scripts/security/m015-runtime/evidence_matrix.py
- scripts/security/m015-runtime/redaction.py
- backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json
- backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.md
