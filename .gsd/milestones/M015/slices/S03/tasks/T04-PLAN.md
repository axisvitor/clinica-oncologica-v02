---
estimated_steps: 8
estimated_files: 6
skills_used: []
---

# T04: Build the provider runtime probe and worker participation proof

Why: Static wiring is insufficient; S03 must drive FastAPI and a real Taskiq worker across network boundaries to the local stubs and capture sanitized results for the exact success/failure modes claimed.

Steps:
1. Add `provider_seam.py` as the provider-probe entrypoint that waits for stubs/API/worker readiness, obtains or seeds synthetic auth/session state through the existing harness pattern, and drives selected WuzAPI and Gemini calls.
2. Add a harness-only `m015_provider_security_taskiq.py` task module that the real worker imports explicitly and that calls the app's WuzAPI/Gemini clients using configured stub URLs.
3. Exercise WuzAPI success plus controlled 4xx/5xx/timeout/duplicate-style cases through app/client code, and Gemini success plus sanitized prompt/redaction and provider-error cases through the configured local base URL.
4. Record only sanitized evidence: scenario names, counts, status classes, timeout/error classes, redaction verdicts, and hashed identifiers; do not persist raw provider bodies, prompts, tokens, cookies, DSNs, SQL, or host paths.
5. Extend tests for provider probe evidence shape, worker task sanitization, local-stub env usage, and no raw payload persistence.

Done when provider probe and worker modules compile, contract tests pass, and evidence shape is validated without running Docker.

## Inputs

- `scripts/security/m015-runtime/provider_stub.py`
- `scripts/security/m015-runtime/redaction.py`
- `scripts/security/m015-runtime/session_seam.py`
- `scripts/security/m015-runtime/m015_session_security_taskiq.py`
- `backend-hormonia/app/integrations/wuzapi/client.py`
- `backend-hormonia/app/ai/client.py`

## Expected Output

- `scripts/security/m015-runtime/provider_seam.py`
- `scripts/security/m015-runtime/m015_provider_security_taskiq.py`
- `backend-hormonia/tests/security/test_m015_s03_provider_runtime_contract.py`
- `backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/provider-seam-summary.md`

## Verification

PYTHONPATH=backend-hormonia python -m py_compile scripts/security/m015-runtime/provider_seam.py scripts/security/m015-runtime/m015_provider_security_taskiq.py scripts/security/m015-runtime/provider_stub.py && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s03_provider_runtime_contract.py tests/security/test_m015_runtime_harness.py tests/unit/test_gemini_client_stub_config.py -q

## Observability Impact

Adds provider-probe phase diagnostics and worker outcome fields that distinguish stub mismatch, provider timeout, provider error, redaction failure, and teardown failure without exposing sensitive payloads.
