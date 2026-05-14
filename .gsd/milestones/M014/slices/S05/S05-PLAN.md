# S05: JWT/Config Posture, Evidence Matrix e Regression Closure

**Goal:** Close M014 by proving JWT/config posture where controlled proof is possible, mapping every R012/R013/R018-relevant item to evidence/not-applicable/deferred status, and producing a reviewer-facing evidence matrix plus fresh regression commands without widening into R014 production-like runtime scope.
**Demo:** Reviewer runs the documented M014 evidence matrix command suite and sees every R012/R013 row mapped to command evidence, not-applicable rationale or explicit deferral owner, plus JWT/config posture and touched M013 regression status.

## Must-Haves

- Focused S05 JWT/config posture proof passes and distinguishes controlled guarantees from R014/M015 runtime deferrals.
- `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md` maps every R012/R013/R018 item and every S01-S04 proof lane to command evidence, not-applicable rationale, or explicit deferral owner.
- Matrix validation pytest passes and checks required rows, command references, known deferrals, no TODO/TBD placeholders, and no unsafe PHI/secret/path sentinel strings.
- Fresh integrated M014 command suite passes or any intentionally unsupported production-like proof is explicitly deferred to R014/M015 in the matrix.
- Diagnostics and artifacts remain PHI-safe: no patient names/phones, prompts, answers, raw tokens, cookies, signed state values, secrets, provider payloads, or private filesystem paths.

## Proof Level

- This slice proves: Final-assembly controlled proof. Real production runtime required: no. Human/UAT required: no. Live provider or production-like DB+queue+WuzAPI/Gemini harness remains deferred to R014/M015 unless explicitly re-scoped.

## Integration Closure

Upstream surfaces consumed: S01 ingress/replay/rate-limit proof, S02 ADK auth/session proof, S03 browser cache/quiz proof, S04 upload/report artifact proof, active R012/R013/R018 requirement contracts, and the M013 evidence-matrix pattern. New wiring introduced: S05-focused posture proof tests and reviewer-facing M014 evidence matrix with executable validation. Remaining before milestone closure: milestone validation and summary after S05 completes.

## Verification

- Reviewer/future-agent observability is the evidence matrix plus pytest validators and exact command list. Failure surfaces are missing matrix rows, stale/missing command evidence, non-zero focused/integrated tests, unsafe sentinel strings in docs, or overclaimed runtime guarantees without proof.

## Tasks

- [x] **T01: Add JWT and deployment-posture proof** `est:2h`
  Why: S05 owns the remaining JWT/config posture risk and must prove controlled guarantees before the evidence matrix can claim closure.
  Do: Inspect the current JWT/session/auth consumers and config settings. Add or repair `backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py` to prove signed JWT type/expiration behavior, revoked/inactive session semantics where enforced, weak/default production secret rejection, database TLS/RLS posture classification, and explicit R014/M015 deferral boundaries without using live services or secrets. If implementation gaps are found, fix the shared helper/config seam rather than adding endpoint-local suppressions.
  Done when: The focused S05 posture test passes and its assertions avoid PHI, raw tokens, cookies, private paths, and secrets in failure text.
  - Files: `backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py`, `backend-hormonia/app/utils/security.py`, `backend-hormonia/app/api/v2/routers/users.py`, `backend-hormonia/app/api/websockets.py`, `backend-hormonia/app/config/settings/security.py`, `backend-hormonia/app/config/settings/database.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py

- [x] **T02: Write M014 evidence matrix and validator** `est:2h`
  Why: R013/R018 require no medium/proof-gap item to disappear; a reviewer-facing matrix is the durable inspection surface.
  Do: Create `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md` using the M013 matrix pattern and S01-S04/S05 evidence. Add `backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py` to validate all R012/R013/R018-relevant rows, S01-S05 command references, closed/not-applicable/deferred statuses, R014/M015 deferral language, and absence of TODO/TBD/unsafe PHI/secret/path sentinel values.
  Done when: The matrix exists, cites exact command classes/evidence IDs available from summaries, and the validator fails on missing required rows or unsafe placeholders.
  - Files: `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md`, `backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py`, `.gsd/milestones/M014/slices/S01/S01-SUMMARY.md`, `.gsd/milestones/M014/slices/S02/S02-SUMMARY.md`, `.gsd/milestones/M014/slices/S03/S03-SUMMARY.md`, `.gsd/milestones/M014/slices/S04/S04-SUMMARY.md`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py

- [x] **T03: Run integrated M014 regression closure** `est:2h`
  Why: The final slice must prove S01-S05 work composes and that touched M013 boundaries still have fresh evidence before M014 can validate R012/R013.
  Do: Run the focused S05 posture and matrix validators, then run the documented integrated M014 backend security command suite and the frontend/quiz commands referenced by S03 where applicable. Update the matrix with fresh integrated evidence IDs/results and use GSD requirement updates for R012/R013/R018 only after evidence is fresh. Keep R014/M015 production-like runtime proof explicitly deferred if not exercised.
  Done when: All documented closeout commands pass, the matrix references fresh S05/integrated evidence, and requirement outcomes are ready for milestone validation.
  - Files: `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md`, `.gsd/REQUIREMENTS.md`, `.gsd/milestones/M014/slices/S05/tasks/T03-SUMMARY.md`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py backend-hormonia/tests/security/test_m014_s01_webhook_replay.py backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py backend-hormonia/tests/security/test_m014_s03_cache_headers.py backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py

## Files Likely Touched

- backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py
- backend-hormonia/app/utils/security.py
- backend-hormonia/app/api/v2/routers/users.py
- backend-hormonia/app/api/websockets.py
- backend-hormonia/app/config/settings/security.py
- backend-hormonia/app/config/settings/database.py
- backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md
- backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py
- .gsd/milestones/M014/slices/S01/S01-SUMMARY.md
- .gsd/milestones/M014/slices/S02/S02-SUMMARY.md
- .gsd/milestones/M014/slices/S03/S03-SUMMARY.md
- .gsd/milestones/M014/slices/S04/S04-SUMMARY.md
- .gsd/REQUIREMENTS.md
- .gsd/milestones/M014/slices/S05/tasks/T03-SUMMARY.md
