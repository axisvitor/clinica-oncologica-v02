---
estimated_steps: 8
estimated_files: 4
skills_used: []
---

# T01: Add controlled WuzAPI/Gemini provider stubs and redaction contracts

Why: S03 needs controlled network-real endpoints before product code or the runner can truthfully prove provider wiring.

Steps:
1. Add a small local provider stub service under `scripts/security/m015-runtime/` that exposes WuzAPI-compatible paths used by the seam and a Gemini-compatible catchment for generated-content calls.
2. Make stub scenarios deterministic: success, explicit 4xx, 5xx, timeout, and duplicate/replay-style responses.
3. Persist sanitized stub observations only as endpoint names, methods, scenario names, counts, status classes, and redaction verdicts; reject/omit raw headers, token values, cookies, prompt/provider request bodies, DSNs, host paths, and PHI-shaped strings.
4. Add stub contract tests that prove scenario routing, token/header redaction, timeout simulation hooks, and sensitive-value rejection.
5. Update the M015 README with the stub evidence contract and non-goals.

Done when the stub contract can be tested without Docker and produces no sensitive durable output.

## Inputs

- `scripts/security/m015-runtime/redaction.py`
- `scripts/security/m015-runtime/README.md`
- `backend-hormonia/app/integrations/wuzapi/client.py`
- `backend-hormonia/app/ai/client.py`

## Expected Output

- `scripts/security/m015-runtime/provider_stub.py`
- `scripts/security/m015-runtime/tests/test_provider_stub_contract.py`
- `scripts/security/m015-runtime/README.md`

## Verification

PYTHONPATH=scripts/security/m015-runtime python -m pytest scripts/security/m015-runtime/tests/test_provider_stub_contract.py -q

## Observability Impact

Adds provider-stub scenario counters and redaction-validated observation files that future agents can inspect without exposing provider payloads or secrets.
