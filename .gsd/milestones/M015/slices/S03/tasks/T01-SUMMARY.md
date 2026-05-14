---
id: T01
parent: S03
milestone: M015
key_files:
  - scripts/security/m015-runtime/provider_stub.py
  - scripts/security/m015-runtime/tests/test_provider_stub_contract.py
  - scripts/security/m015-runtime/README.md
key_decisions:
  - Keep provider stubs as synthetic-only stdlib HTTP endpoints with pure response/observation functions so they can be contract-tested before Docker runner wiring.
  - Persist only redaction-validated observation metadata: provider, endpoint, method, scenario, status class, header-presence booleans, body hashes, and redaction flags.
duration: 
verification_result: passed
completed_at: 2026-05-14T12:50:00.089Z
blocker_discovered: false
---

# T01: Added contract-tested synthetic WuzAPI/Gemini provider stubs that produce redaction-safe observations for the upcoming S03 provider runtime seam.

**Added contract-tested synthetic WuzAPI/Gemini provider stubs that produce redaction-safe observations for the upcoming S03 provider runtime seam.**

## What Happened

Added `provider_stub.py`, a deterministic synthetic HTTP stub for the S03 provider seam. The module classifies WuzAPI and Gemini paths, resolves scenarios from query/header input, returns synthetic success/error responses, and builds durable observations without raw headers, token values, cookies, request bodies, prompts, DSNs, host paths, or PHI-shaped values. It includes a stdlib `ThreadingHTTPServer` entrypoint for later Compose use plus pure functions for test-first contract coverage. Added `test_provider_stub_contract.py` to verify WuzAPI/Gemini path classification, scenario aliases, token-required WuzAPI behavior, success/4xx/5xx/timeout/duplicate outcomes, Gemini synthetic response behavior, JSONL observation writes, and fail-closed redaction rejection. Updated the M015 runtime README with the provider-stub support section and explicit non-goals so the stub is not mistaken for a completed provider seam before T03/T05.

## Verification

Fresh verification after the last code change: `PYTHONPATH=scripts/security/m015-runtime python -m pytest scripts/security/m015-runtime/tests/test_provider_stub_contract.py -q` exited 0 with `8 passed in 0.41s` (job duration 11.2s including startup).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=scripts/security/m015-runtime python -m pytest scripts/security/m015-runtime/tests/test_provider_stub_contract.py -q` | 0 | ✅ pass — 8 passed in 0.41s | 11200ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `scripts/security/m015-runtime/provider_stub.py`
- `scripts/security/m015-runtime/tests/test_provider_stub_contract.py`
- `scripts/security/m015-runtime/README.md`
