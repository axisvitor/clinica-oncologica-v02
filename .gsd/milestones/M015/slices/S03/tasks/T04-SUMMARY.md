---
id: T04
parent: S03
milestone: M015
key_files:
  - scripts/security/m015-runtime/provider_seam.py
  - scripts/security/m015-runtime/m015_provider_security_taskiq.py
  - scripts/security/m015-runtime/redaction.py
  - backend-hormonia/tests/security/test_m015_s03_provider_runtime_contract.py
  - scripts/security/m015-runtime/tests/test_provider_stub_contract.py
key_decisions:
  - Keep `provider_seam.py` as a thin explicit Compose entrypoint and centralize probe/worker logic in `m015_provider_security_taskiq.py`, matching the S02 session seam pattern.
  - Use direct local-stub HTTP checks for deterministic WuzAPI/Gemini scenario coverage, and a harness-only Taskiq provider task for worker participation.
  - Use the app `WuzAPIClient` and `GeminiClient` inside the provider worker boundary while persisting only sanitized routing/status facts.
duration: 
verification_result: passed
completed_at: 2026-05-14T13:21:12.663Z
blocker_discovered: false
---

# T04: Built the provider runtime probe/worker implementation and redaction-safe evidence contract for S03, ready for the real provider seam runner gate in T05.

**Built the provider runtime probe/worker implementation and redaction-safe evidence contract for S03, ready for the real provider seam runner gate in T05.**

## What Happened

Added `provider_seam.py` as the explicit provider-probe entrypoint and `m015_provider_security_taskiq.py` as the shared provider probe/worker module. The module defines sanitized HTTP outcome/evidence builders, direct local-stub WuzAPI and Gemini scenario checks, a harness-only Taskiq task named `m015_provider_security_boundary`, and provider evidence/summary writers. The worker task uses the app WuzAPI client against the configured local stub and initializes the app Gemini client to prove the configured base-URL boundary is present, while returning only status classes, scenario names, hashes, booleans, and redaction flags. Added `test_m015_s03_provider_runtime_contract.py` to prove backend-path bootstrapping happens before broker import, the entrypoint delegates correctly, provider code uses app clients/configured stub env vars, evidence shape is redaction-safe, non-goals are recorded, and raw provider payload shapes are rejected. Tightened `redaction.py` so quoted JSON keys like `"provider_payload"` and `"patient_name"` are denylisted in durable evidence.

## Verification

Fresh verification after the final redaction fix: `PYTHONPATH=backend-hormonia python -m py_compile scripts/security/m015-runtime/provider_seam.py scripts/security/m015-runtime/m015_provider_security_taskiq.py scripts/security/m015-runtime/provider_stub.py && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s03_provider_runtime_contract.py tests/security/test_m015_runtime_harness.py tests/unit/test_gemini_client_stub_config.py -q` exited 0 and reached `[100%]` with 1 expected skip for Docker-produced runtime artifacts. Regression check `PYTHONPATH=scripts/security/m015-runtime python -m pytest scripts/security/m015-runtime/tests/test_provider_stub_contract.py -q` exited 0 with `8 passed in 0.39s`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m py_compile scripts/security/m015-runtime/provider_seam.py scripts/security/m015-runtime/m015_provider_security_taskiq.py scripts/security/m015-runtime/provider_stub.py && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s03_provider_runtime_contract.py tests/security/test_m015_runtime_harness.py tests/unit/test_gemini_client_stub_config.py -q` | 0 | ✅ pass — T04 compile/static pytest gate reached 100% with 1 expected skip | 21800ms |
| 2 | `PYTHONPATH=scripts/security/m015-runtime python -m pytest scripts/security/m015-runtime/tests/test_provider_stub_contract.py -q` | 0 | ✅ pass — provider stub regression 8 passed in 0.39s | 11200ms |

## Deviations

While implementing T04, verification exposed a redaction gap for quoted JSON keys such as `"provider_payload"`; `scripts/security/m015-runtime/redaction.py` was tightened to reject quoted PHI/provider-payload keys. The T01 provider-stub contract was rerun after that shared change.

## Known Issues

T04 does not claim the Docker provider seam passes; the real `./scripts/security/verify-m015-runtime-security.sh --seam provider` run and durable evidence refresh are assigned to T05.

## Files Created/Modified

- `scripts/security/m015-runtime/provider_seam.py`
- `scripts/security/m015-runtime/m015_provider_security_taskiq.py`
- `scripts/security/m015-runtime/redaction.py`
- `backend-hormonia/tests/security/test_m015_s03_provider_runtime_contract.py`
- `scripts/security/m015-runtime/tests/test_provider_stub_contract.py`
