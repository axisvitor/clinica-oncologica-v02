# S04: Private Artifact App-Route Runtime Proof

**Goal:** Prove private artifact app-route runtime behavior against the M015 synthetic backend stack: owner/admin access succeeds for private upload/report artifacts, anonymous/cross-owner access fails closed, unsafe private/static/export URLs do not redirect or leak bytes/paths, response headers are attachment-safe, evidence is redaction-clean, and the runner tears down cleanly. This consumes S01 runtime substrate and S02 real cookie-session auth; it does not claim CDN, object-storage, browser rendering, live providers, production data, broad DAST, or final all-seam matrix closure.
**Demo:** Run the artifact seam against the harness to show owner/admin access succeeds, anonymous and cross-owner access fail closed, response headers are safe, and no redirect or static path exposes private artifacts.

## Must-Haves

- `./scripts/security/verify-m015-runtime-security.sh --list-seams` lists `db`, `session`, `provider`, and `artifact`; unknown/omitted seams still fail closed before setup.
- Docker Compose config remains isolated from project `.env`, production volumes, live providers, and accidental public/private path mounts.
- Artifact probe uses real HTTP against the running FastAPI app with S02-style synthetic cookie sessions; no dependency overrides, Bearer shortcuts, or in-process TestClient proof is used for the runtime claim.
- Private upload runtime proof covers private create/status/download, owner/admin success, anonymous/cross-owner denial, direct static `/uploads/<private-relative-path>` denial, safe attachment headers, and no private bytes/path leakage.
- Report/export runtime proof covers base report download, enhanced builder download, enhanced export status/download unsafe URL withholding, no unsafe/private redirects, fallback attachment behavior where supported, and cross-owner/anonymous denial.
- `./scripts/security/verify-m015-runtime-security.sh --seam artifact` exits 0, writes `backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json` and `backend-hormonia/docs/reports/security/m015/artifact-seam-summary.md`, passes redaction validation, and tears down cleanly including tools-profile services.
- Evidence explicitly records S05 downstream non-goals and avoids claiming live providers, frontend/browser, production data, CDN/object-storage, broad DAST/fuzzing, or final all-seam closure.

## Proof Level

- This slice proves: Operational runtime integration proof. Real runtime required: yes — local/CI Docker stack with FastAPI, TLS PostgreSQL, Dragonfly, and an artifact probe making HTTP calls to app routes. Human/UAT required: no. This slice proves app-route artifact behavior for synthetic private uploads/base reports/enhanced reports/exports; it does not prove CDN/object-storage/browser/live-provider/final matrix behavior.

## Integration Closure

Consumes S01's Docker runtime stack, redaction helpers, TLS PostgreSQL/Dragonfly/FastAPI readiness, and teardown discipline; consumes S02's DB-backed staff-session cookie/auth substrate. Introduces an `artifact` runner seam, artifact probe service/script, runtime upload/report/export fixtures, and durable artifact seam evidence. After S04, S05 still needs the unified no-filter runner, final evidence matrix, strict validator, and milestone closure gate.

## Verification

- S04 must add phase-stamped artifact seam diagnostics with correlation ID, route labels, status classes, header booleans, redirect booleans, redaction verdict, failure class, evidence paths, and teardown result. Durable evidence must omit cookies, session IDs, raw IDs, raw bytes, private filesystem paths, DSNs, Authorization/Cookie headers, raw report download URLs, and PHI-shaped values.

## Tasks

- [x] **T01: Register artifact seam and static runtime contract** `est:2h`
  Why: S04 needs to become a first-class runner seam before runtime probes can be trusted; the contract must prevent false green results and define the synthetic fixture/evidence schema up front.
  - Files: `scripts/security/verify-m015-runtime-security.sh`, `scripts/security/m015-runtime/docker-compose.yml`, `scripts/security/m015-runtime/README.md`, `backend-hormonia/tests/security/test_m015_runtime_harness.py`, `scripts/security/m015-runtime/tests/test_runner_contract.py`
  - Verify: bash -n scripts/security/verify-m015-runtime-security.sh && ./scripts/security/verify-m015-runtime-security.sh --list-seams && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_runtime_harness.py ../scripts/security/m015-runtime/tests/test_runner_contract.py -q

- [x] **T02: Build private upload app-route runtime probe** `est:3h`
  Why: The private upload boundary is the clearest app-route artifact seam; S04 must prove it through the running app with real cookie sessions and without exposing the private storage root through `/uploads`.
  - Files: `scripts/security/m015-runtime/artifact_seam.py`, `backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py`
  - Verify: python3 -m py_compile scripts/security/m015-runtime/artifact_seam.py && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_s04_artifact_runtime_contract.py tests/api/v2/test_private_upload_serving.py tests/security/test_m014_s04_private_artifact_serving.py -q

- [x] **T03: Build report and export app-route runtime probe** `est:3h`
  Why: S04 also needs report and enhanced export app-route proof, including ownership checks and unsafe URL withholding, without overclaiming that all redirects are forbidden.
  - Files: `scripts/security/m015-runtime/artifact_seam.py`, `backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py`
  - Verify: cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_s04_artifact_runtime_contract.py tests/api/v2/test_report_ownership_closure.py tests/security/test_m014_s04_report_artifact_serving.py -q

- [x] **T04: Write redaction-safe artifact evidence and summary** `est:2h`
  Why: The operational proof is only useful if durable evidence is safe for review and final S05 aggregation; S04 must reject artifacts that contain raw cookies, private paths, bytes, IDs, or PHI-shaped data.
  - Files: `scripts/security/m015-runtime/artifact_seam.py`, `scripts/security/m015-runtime/redaction.py`, `backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py`, `backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json`, `backend-hormonia/docs/reports/security/m015/artifact-seam-summary.md`
  - Verify: cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_s04_artifact_runtime_contract.py tests/security/test_m015_runtime_harness.py -q

- [x] **T05: Run artifact seam end to end and persist fresh evidence** `est:1.5h`
  Why: S04 is not complete until the root runner exercises the artifact seam through Docker, writes fresh redaction-validated evidence, keeps M014 regressions green, and tears down cleanly.
  - Files: `scripts/security/verify-m015-runtime-security.sh`, `backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json`, `backend-hormonia/docs/reports/security/m015/artifact-seam-summary.md`, `scripts/security/m015-runtime/evidence/`
  - Verify: bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && PYTHONPATH=backend-hormonia:scripts/security/m015-runtime pytest scripts/security/m015-runtime/tests/test_runner_contract.py backend-hormonia/tests/security/test_m015_runtime_harness.py backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py backend-hormonia/tests/api/v2/test_private_upload_serving.py backend-hormonia/tests/api/v2/test_report_ownership_closure.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py -q && ./scripts/security/verify-m015-runtime-security.sh --seam artifact && (docker ps --format '{{.Names}} {{.Ports}}' | grep -E 'm015-runtime|18080|15432' && exit 1 || true)

## Files Likely Touched

- scripts/security/verify-m015-runtime-security.sh
- scripts/security/m015-runtime/docker-compose.yml
- scripts/security/m015-runtime/README.md
- backend-hormonia/tests/security/test_m015_runtime_harness.py
- scripts/security/m015-runtime/tests/test_runner_contract.py
- scripts/security/m015-runtime/artifact_seam.py
- backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py
- scripts/security/m015-runtime/redaction.py
- backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json
- backend-hormonia/docs/reports/security/m015/artifact-seam-summary.md
- scripts/security/m015-runtime/evidence/
