---
id: T03
parent: S03
milestone: M015
key_files:
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/docker-compose.yml
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
  - scripts/security/m015-runtime/tests/test_runner_contract.py
  - scripts/security/m015-runtime/README.md
key_decisions:
  - Make `provider` a first-class fail-closed runner seam now, but keep runtime proof deferred until provider probe/task implementation exists.
  - Start provider-stub and provider-worker only for the provider seam so existing DB/session seam startup is not burdened by provider services.
  - Use a separate `provider-worker` service/profile for provider Taskiq proof instead of changing the already-proven S02 session worker command.
duration: 
verification_result: passed
completed_at: 2026-05-14T13:10:49.133Z
blocker_discovered: false
---

# T03: Wired `provider` as a first-class M015 runner/Compose seam with local stub URLs, provider services, evidence paths, sanitized diagnostics, and static fail-closed contracts.

**Wired `provider` as a first-class M015 runner/Compose seam with local stub URLs, provider services, evidence paths, sanitized diagnostics, and static fail-closed contracts.**

## What Happened

Extended the M015 runner so `provider` appears in `--list-seams`, is accepted by CLI validation, receives provider-specific evidence paths, generated synthetic WuzAPI/Gemini base URL configuration, teardown evidence handling, provider readiness checks, and a provider probe dispatch branch. The runner now sanitizes `Token:` headers in addition to Authorization/Cookie/Set-Cookie shapes. Updated Compose with local-only provider settings, a `provider-stub` service, a profile-scoped `provider-worker` service, and a profile-scoped `provider-probe` service with explicit mounts for provider stub/probe/task modules and redaction helpers. Static backend and root runner-contract tests now assert the provider seam listing, fail-closed unknown seam behavior, provider service/mount contracts, no live provider service/container names, local stub base URLs, provider evidence paths, and redaction-clean artifact handling. The README now documents `--seam provider` and clarifies that runtime proof awaits later S03 tasks.

## Verification

Fresh verification after the final fixes: `bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_runtime_harness.py -q && cd .. && PYTHONPATH=scripts/security/m015-runtime python -m pytest scripts/security/m015-runtime/tests/test_runner_contract.py -q` exited 0. Backend harness tests reached `[100%]` with 1 expected skip for Docker-produced runtime artifacts; root runner-contract tests reported `8 passed in 0.45s`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_runtime_harness.py -q && cd .. && PYTHONPATH=scripts/security/m015-runtime python -m pytest scripts/security/m015-runtime/tests/test_runner_contract.py -q` | 0 | ✅ pass — backend static harness reached 100% with 1 expected skip; root runner contracts 8 passed | 23400ms |

## Deviations

Added provider-stub README updates and runner `Token:` header sanitization as part of static contract hardening. Provider runtime execution remains intentionally deferred to T04/T05.

## Known Issues

Provider runtime execution is not claimed by T03. `provider_seam.py` and `m015_provider_security_taskiq.py` are intentionally mounted/wired for T04 implementation, so `--seam provider` is not expected to pass until T04/T05 complete.

## Files Created/Modified

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/docker-compose.yml`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `scripts/security/m015-runtime/tests/test_runner_contract.py`
- `scripts/security/m015-runtime/README.md`
