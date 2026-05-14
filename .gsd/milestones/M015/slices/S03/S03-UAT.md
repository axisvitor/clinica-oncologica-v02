# S03: Network-Real WuzAPI/Gemini Stub Boundary — UAT

**Milestone:** M015
**Written:** 2026-05-14T15:51:43.849Z

## UAT: M015/S03 provider runtime seam

### Scope
Validate the synthetic-only provider seam against a running local backend runtime. This UAT proves configured local WuzAPI/Gemini HTTP stubs, selected provider failure modes, Taskiq worker participation, PHI-safe evidence, and clean teardown. It does not prove live providers, private artifact app-route access, browser/frontend behavior, production systems/data, CDN/object storage, broad DAST/fuzzing, or final all-seam matrix closure.

### Command
```bash
bash -n scripts/security/verify-m015-runtime-security.sh \
  && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet \
  && cd backend-hormonia \
  && PYTHONPATH=. pytest tests/security/test_m015_s03_provider_runtime_contract.py tests/security/test_m015_runtime_harness.py tests/unit/test_gemini_client_stub_config.py -q \
  && cd .. \
  && ./scripts/security/verify-m015-runtime-security.sh --seam provider
```

### Expected result
- Static runner/Compose/provider contracts pass.
- The provider seam starts the isolated local runtime stack and stubs.
- WuzAPI and Gemini use configured local HTTP stubs, not live providers.
- Success, failure, timeout, and replay-style outcomes are captured as sanitized classes.
- A real Taskiq worker participates in the provider proof.
- Durable evidence and summary pass redaction validation.
- Compose teardown completes, including tools-profile services.

### Actual result
Pass. The fresh run exited 0 in 158.0s with 42 scoped tests at `[100%]`. Runtime evidence correlation: `m015-20260514T154638Z-1968863`. Provider summary reports WuzAPI 5 scenarios, Gemini 2 scenarios, local provider stubs used, live providers `not_used`, worker boundary `taskiq`, and teardown `complete`. Follow-up check found no active M015 runtime containers or M015 bound ports.
