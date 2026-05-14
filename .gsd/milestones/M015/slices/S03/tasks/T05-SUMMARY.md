---
id: T05
parent: S03
milestone: M015
key_files:
  - scripts/security/m015-runtime/docker-compose.yml
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/provider_stub.py
  - scripts/security/m015-runtime/m015_provider_security_taskiq.py
  - scripts/security/m015-runtime/provider_seam.py
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
  - backend-hormonia/tests/security/test_m015_s03_provider_runtime_contract.py
  - backend-hormonia/tests/unit/test_gemini_client_stub_config.py
  - backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/provider-seam-summary.md
  - backend-hormonia/docs/reports/security/m015/provider-stub-observations.jsonl
key_decisions:
  - D028: Route provider-probe and provider-worker through a provider-specific Taskiq broker namespace to prevent the default worker from consuming provider-only proof tasks.
duration: 
verification_result: passed
completed_at: 2026-05-14T14:40:48.948Z
blocker_discovered: false
---

# T05: Ran the M015 provider seam through local WuzAPI/Gemini stubs and persisted passing redaction-validated provider evidence.

**Ran the M015 provider seam through local WuzAPI/Gemini stubs and persisted passing redaction-validated provider evidence.**

## What Happened

Resumed from a failed provider evidence state, verified the T05 inputs/artifacts existed, then ran the full static/contract/runtime gate. The static and contract portion passed, but the Docker provider seam failed closed at the worker phase with `TaskiqResultTimeoutError`. Sanitized compose logs showed the default app worker consumed the provider-only Taskiq message from the shared `hormonia` queue and logged `task "m015_provider_security_boundary" is not found`, leaving the provider probe waiting for a result. I fixed the harness behavior by routing both `provider-probe` and `provider-worker` through a provider-specific Taskiq broker namespace while leaving the default worker on the normal broker, and added contract assertions so the isolation remains explicit. After that, the static/contract gate passed and the provider seam completed successfully. The refreshed durable evidence uses correlation `m015-20260514T143555Z-1845365`, records local provider stub usage, WuzAPI status classes `2xx/4xx/5xx/network_error`, Gemini status classes `2xx/5xx`, Taskiq worker participation, redaction validation, and runner teardown completion.

## Verification

Verified shell syntax, Compose config, provider runtime contract tests, runtime harness tests, Gemini base-URL seam tests, the Docker provider seam itself, final evidence field expectations/non-goals, and redaction cleanliness of provider evidence/summary/observations. The final provider seam passed and refreshed `provider-seam-evidence.json`, `provider-seam-summary.md`, and `provider-stub-observations.jsonl` with sanitized synthetic-only data.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && PYTHONPATH=backend-hormonia pytest backend-hormonia/tests/security/test_m015_s03_provider_runtime_contract.py backend-hormonia/tests/security/test_m015_runtime_harness.py backend-hormonia/tests/unit/test_gemini_client_stub_config.py -q` | 0 | ✅ pass | 23844ms |
| 2 | `./scripts/security/verify-m015-runtime-security.sh --seam provider` | 0 | ✅ pass | 145343ms |
| 3 | `python3 final provider evidence field/non-goal validation` | 0 | ✅ pass | 55ms |
| 4 | `PYTHONPATH=backend-hormonia:scripts/security/m015-runtime python3 redaction validation for provider evidence, summary, and stub observations` | 0 | ✅ pass | 111ms |

## Deviations

None. The Taskiq broker isolation fix was within the plan's instruction to fix harness behavior before recording green evidence when the runtime exposed a red provider signal.

## Known Issues

None.

## Files Created/Modified

- `scripts/security/m015-runtime/docker-compose.yml`
- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/provider_stub.py`
- `scripts/security/m015-runtime/m015_provider_security_taskiq.py`
- `scripts/security/m015-runtime/provider_seam.py`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `backend-hormonia/tests/security/test_m015_s03_provider_runtime_contract.py`
- `backend-hormonia/tests/unit/test_gemini_client_stub_config.py`
- `backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/provider-seam-summary.md`
- `backend-hormonia/docs/reports/security/m015/provider-stub-observations.jsonl`
