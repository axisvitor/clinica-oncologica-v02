# S03: Network-Real WuzAPI/Gemini Stub Boundary

**Goal:** Prove the M015 network-real provider boundary end to end without live side effects: FastAPI and a real Taskiq worker must use configured local WuzAPI/Gemini stub URLs, controlled success/failure/replay/timeout scenarios must fail closed or produce expected sanitized outcomes, and durable provider evidence must contain only counts/status classes/redaction verdicts rather than raw tokens, cookies, provider payloads, prompts, PHI-shaped data, or private paths. Owned requirement: R014 provider/queue portion. Supporting requirements: R015 synthetic-only/no production data, R017 PHI-safe evidence, and R018 no silent deferred-item loss. Consumes S01 DB/runtime substrate and S02 DB-authoritative session behavior.
**Demo:** Run the provider seam to show the backend and workers use configured local WuzAPI/Gemini stub URLs, handle controlled failure modes safely, and record only redacted synthetic request evidence.

## Must-Haves

- `./scripts/security/verify-m015-runtime-security.sh --list-seams` lists `db`, `session`, and `provider`; unknown/omitted seams still fail closed before setup.
- `docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet` succeeds and the M015 Compose file remains isolated from project `.env`, live WuzAPI service containers, live Gemini credentials, and production volumes.
- A local WuzAPI stub is reached over HTTP through configured `WHATSAPP_WUZAPI_BASE_URL`; it verifies expected paths/methods and token-header presence without storing token values or raw request bodies.
- A local Gemini stub is reached over HTTP through a product configuration seam such as `AI_GEMINI_BASE_URL`; app code uses the configured stub endpoint rather than in-process fakes.
- Provider probes exercise controlled success, 4xx/5xx, timeout, and duplicate/replay-style scenarios, and failures are reported as sanitized fail-closed/status-class outcomes.
- At least one real Taskiq worker path participates in the provider seam and uses configured stub URLs rather than in-process mocks.
- `./scripts/security/verify-m015-runtime-security.sh --seam provider` exits 0, writes `backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json` and `backend-hormonia/docs/reports/security/m015/provider-seam-summary.md`, passes redaction validation, and tears down cleanly.
- Evidence explicitly records S04/S05 downstream non-goals and avoids claiming live provider, browser/frontend, production data, CDN/object-storage, or artifact-route guarantees.

## Proof Level

- This slice proves: Operational runtime integration proof. Real runtime required: yes — local/CI Docker only, with separate FastAPI, PostgreSQL, Dragonfly, Taskiq worker, and local provider-stub services. Human/UAT required: no. This slice proves network/env wiring to controlled stubs and selected provider failure modes, not live providers, production exploitation, browser/frontend flows, artifact routes, CDN/object storage, or final all-seam closure.

## Integration Closure

Consumes S01's runtime harness and redaction helpers plus S02's authenticated session/worker substrate. Introduces local WuzAPI/Gemini HTTP stubs, a Gemini base-URL configuration seam, a `provider` runner seam, a provider probe service, and a harness-only provider Taskiq module. After S03, S04 still needs private artifact app-route proof and S05 still needs the unified no-filter runner plus final evidence matrix/strict closure gate.

## Verification

- Provider seam diagnostics must identify setup, compose/readiness, stub-readiness, wuzapi, gemini, worker, evidence, redaction, and teardown phases with correlation IDs and sanitized failure classes. Stub evidence must persist only endpoint names, scenario names, status classes, request counts, redaction verdicts, and hashed identifiers; it must never persist token values, Authorization/Cookie headers, raw provider request bodies, raw prompts, DSNs, local host paths, or PHI-shaped values.

## Tasks

- [x] **T01: Add controlled WuzAPI/Gemini provider stubs and redaction contracts** `est:2h`
  Why: S03 needs controlled network-real endpoints before product code or the runner can truthfully prove provider wiring.
  - Files: `scripts/security/m015-runtime/provider_stub.py`, `scripts/security/m015-runtime/tests/test_provider_stub_contract.py`, `scripts/security/m015-runtime/redaction.py`, `scripts/security/m015-runtime/README.md`
  - Verify: PYTHONPATH=scripts/security/m015-runtime python -m pytest scripts/security/m015-runtime/tests/test_provider_stub_contract.py -q

- [x] **T02: Add a test-covered Gemini base-URL configuration seam** `est:1.5h`
  Why: WuzAPI already has a base URL setting, but Gemini currently initializes `google-genai` without a configurable local endpoint; without a product config seam, S03 cannot honestly prove app-to-Gemini-stub network wiring.
  - Files: `backend-hormonia/app/config/settings/integrations.py`, `backend-hormonia/app/ai/client.py`, `backend-hormonia/tests/unit/test_gemini_client_stub_config.py`, `backend-hormonia/tests/unit/test_gemini_client_pii_redaction.py`
  - Verify: cd backend-hormonia && PYTHONPATH=. pytest tests/unit/test_gemini_client_stub_config.py tests/unit/test_gemini_client_pii_redaction.py -q

- [x] **T03: Wire the provider seam into the runner, Compose stack, and static contracts** `est:2h`
  Why: The runner currently implements only `db` and `session`; provider proof must be a fail-closed first-class seam with Compose services and static contracts before any runtime claim is made.
  - Files: `scripts/security/verify-m015-runtime-security.sh`, `scripts/security/m015-runtime/docker-compose.yml`, `backend-hormonia/tests/security/test_m015_runtime_harness.py`, `scripts/security/m015-runtime/tests/test_runner_contract.py`, `scripts/security/m015-runtime/provider_stub.py`
  - Verify: bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_runtime_harness.py -q && cd .. && PYTHONPATH=scripts/security/m015-runtime python -m pytest scripts/security/m015-runtime/tests/test_runner_contract.py -q

- [x] **T04: Build the provider runtime probe and worker participation proof** `est:3h`
  Why: Static wiring is insufficient; S03 must drive FastAPI and a real Taskiq worker across network boundaries to the local stubs and capture sanitized results for the exact success/failure modes claimed.
  - Files: `scripts/security/m015-runtime/provider_seam.py`, `scripts/security/m015-runtime/m015_provider_security_taskiq.py`, `scripts/security/m015-runtime/provider_stub.py`, `scripts/security/m015-runtime/redaction.py`, `backend-hormonia/tests/security/test_m015_s03_provider_runtime_contract.py`, `backend-hormonia/tests/security/test_m015_runtime_harness.py`
  - Verify: PYTHONPATH=backend-hormonia python -m py_compile scripts/security/m015-runtime/provider_seam.py scripts/security/m015-runtime/m015_provider_security_taskiq.py scripts/security/m015-runtime/provider_stub.py && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s03_provider_runtime_contract.py tests/security/test_m015_runtime_harness.py tests/unit/test_gemini_client_stub_config.py -q

- [x] **T05: Run the provider seam and persist fresh sanitized evidence** `est:1.5h`
  Why: S03 is an operational proof slice; it is not complete until the root runner exercises the provider seam, writes stable redaction-validated evidence, and tears down cleanly.
  - Files: `backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json`, `backend-hormonia/docs/reports/security/m015/provider-seam-summary.md`, `scripts/security/verify-m015-runtime-security.sh`, `scripts/security/m015-runtime/docker-compose.yml`, `scripts/security/m015-runtime/provider_seam.py`, `scripts/security/m015-runtime/provider_stub.py`, `scripts/security/m015-runtime/m015_provider_security_taskiq.py`, `backend-hormonia/tests/security/test_m015_s03_provider_runtime_contract.py`
  - Verify: bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s03_provider_runtime_contract.py tests/security/test_m015_runtime_harness.py tests/unit/test_gemini_client_stub_config.py -q && cd .. && ./scripts/security/verify-m015-runtime-security.sh --seam provider

## Files Likely Touched

- scripts/security/m015-runtime/provider_stub.py
- scripts/security/m015-runtime/tests/test_provider_stub_contract.py
- scripts/security/m015-runtime/redaction.py
- scripts/security/m015-runtime/README.md
- backend-hormonia/app/config/settings/integrations.py
- backend-hormonia/app/ai/client.py
- backend-hormonia/tests/unit/test_gemini_client_stub_config.py
- backend-hormonia/tests/unit/test_gemini_client_pii_redaction.py
- scripts/security/verify-m015-runtime-security.sh
- scripts/security/m015-runtime/docker-compose.yml
- backend-hormonia/tests/security/test_m015_runtime_harness.py
- scripts/security/m015-runtime/tests/test_runner_contract.py
- scripts/security/m015-runtime/provider_seam.py
- scripts/security/m015-runtime/m015_provider_security_taskiq.py
- backend-hormonia/tests/security/test_m015_s03_provider_runtime_contract.py
- backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json
- backend-hormonia/docs/reports/security/m015/provider-seam-summary.md
