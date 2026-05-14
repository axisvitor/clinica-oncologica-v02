---
estimated_steps: 5
estimated_files: 8
skills_used: []
---

# T05: Harden harness contract tests and run the S01 closure gate

Why: After the migration TLS blocker is fixed, S01 still needs regression-safe closure. Contract tests should prevent future false-green runner changes, live-provider drift, unsupported TLS option regressions, and redaction failures without requiring Docker for every edit; the final command still exercises the real DB seam.
- Finalize `test_m015_runtime_harness.py` coverage for seam CLI validation, Compose isolation/no live provider references, evidence path discipline, redaction denylist behavior, and migration URL TLS option filtering.
- Confirm evidence validation rejects credentials, private key/cert material, cookies/tokens, Firebase/service-account content, real-looking CPF/email/phone/patient names, `/mnt/c` absolute paths, and unsafe raw SQL stderr.
- Run the exact S01 static, unit/contract, Compose config, and DB seam verification commands from the slice must-haves.
- Record completion only with fresh verification output from the current run and without modifying completed T01-T03 summaries.

## Inputs

- `.gsd/milestones/M015/slices/S01/S01-PLAN.md`
- `.gsd/milestones/M015/slices/S01/tasks/T04-PLAN.md`
- `scripts/security/m015-runtime/redaction.py`
- `scripts/security/m015-runtime/tests/test_runner_contract.py`

## Expected Output

- `Updated harness contract tests that cover the fixed migration TLS compatibility path and evidence/redaction guardrails.`
- `All S01 must-have verification commands pass with fresh output.`
- `Sanitized DB seam evidence and summary remain present and validator-clean after the final runtime run.`
- `S01 is ready for task and slice completion recording.`

## Verification

bash -n scripts/security/verify-m015-runtime-security.sh
docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet
cd backend-hormonia && PYTHONPATH=. pytest tests/core/test_async_engine_tls_config.py tests/security/test_m015_runtime_harness.py -q
cd .. && ./scripts/security/verify-m015-runtime-security.sh --seam db
