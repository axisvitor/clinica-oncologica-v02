---
estimated_steps: 3
estimated_files: 3
skills_used: []
---

# T03: Run integrated M014 regression closure

Why: The final slice must prove S01-S05 work composes and that touched M013 boundaries still have fresh evidence before M014 can validate R012/R013.
Do: Run the focused S05 posture and matrix validators, then run the documented integrated M014 backend security command suite and the frontend/quiz commands referenced by S03 where applicable. Update the matrix with fresh integrated evidence IDs/results and use GSD requirement updates for R012/R013/R018 only after evidence is fresh. Keep R014/M015 production-like runtime proof explicitly deferred if not exercised.
Done when: All documented closeout commands pass, the matrix references fresh S05/integrated evidence, and requirement outcomes are ready for milestone validation.

## Inputs

- `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md`
- `backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py`
- `backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py`
- `.gsd/REQUIREMENTS.md`

## Expected Output

- `Updated backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md with fresh closeout evidence`
- `Updated requirement validation/status for R012/R013/R018 via GSD tools if supported by proof`

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py backend-hormonia/tests/security/test_m014_s01_webhook_replay.py backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py backend-hormonia/tests/security/test_m014_s03_cache_headers.py backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py

## Observability Impact

Integrated proof establishes the final S05 health signal; failures localize to a specific security lane/test file or matrix row.
