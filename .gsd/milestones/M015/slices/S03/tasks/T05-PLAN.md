---
estimated_steps: 8
estimated_files: 8
skills_used: []
---

# T05: Run the provider seam and persist fresh sanitized evidence

Why: S03 is an operational proof slice; it is not complete until the root runner exercises the provider seam, writes stable redaction-validated evidence, and tears down cleanly.

Steps:
1. Run the static and contract gates after all provider code is in place.
2. Run `./scripts/security/verify-m015-runtime-security.sh --seam provider` against the isolated Docker runtime stack.
3. If runtime exposes a red provider security signal in the selected seam, fix product/harness behavior before recording green evidence.
4. Refresh `provider-seam-evidence.json` and `provider-seam-summary.md` with the final passing run.
5. Confirm summary non-goals explicitly defer S04 artifacts, S05 final matrix, live providers, production systems/data, browser/frontend flows, CDN/object-storage, and broad DAST/fuzzing.

Done when all listed gates pass and durable provider evidence says result passed, redaction validated, provider stubs used, worker participated, and teardown complete.

## Inputs

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `scripts/security/m015-runtime/provider_seam.py`
- `scripts/security/m015-runtime/provider_stub.py`
- `scripts/security/m015-runtime/m015_provider_security_taskiq.py`
- `backend-hormonia/tests/security/test_m015_s03_provider_runtime_contract.py`

## Expected Output

- `backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/provider-seam-summary.md`
- `.gsd/milestones/M015/slices/S03/tasks/T05-SUMMARY.md`

## Verification

bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s03_provider_runtime_contract.py tests/security/test_m015_runtime_harness.py tests/unit/test_gemini_client_stub_config.py -q && cd .. && ./scripts/security/verify-m015-runtime-security.sh --seam provider

## Observability Impact

Produces the durable provider seam evidence and summary that downstream S05 can validate and that future agents can inspect before rerunning the stack.
