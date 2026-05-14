---
id: T05
parent: S03
milestone: M015
key_files:
  - scripts/security/verify-m015-runtime-security.sh
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
  - scripts/security/m015-runtime/m015_provider_security_taskiq.py
  - backend-hormonia/tests/security/test_m015_s03_provider_runtime_contract.py
  - backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/provider-seam-summary.md
  - backend-hormonia/docs/reports/security/m015/provider-stub-observations.jsonl
key_decisions:
  - Treat Docker Compose tools-profile services as part of M015 runtime teardown before claiming teardown completion.
  - Record provider stub usage explicitly in provider-seam evidence and summary so S03 proves configured local WuzAPI/Gemini stubs, not live providers.
duration: 
verification_result: passed
completed_at: 2026-05-14T15:17:58.362Z
blocker_discovered: false
---

# T05: Ran the provider seam through local WuzAPI/Gemini stubs, fixed tools-profile teardown, and persisted redaction-validated evidence with explicit stub-use proof.

**Ran the provider seam through local WuzAPI/Gemini stubs, fixed tools-profile teardown, and persisted redaction-validated evidence with explicit stub-use proof.**

## What Happened

Executed the authoritative provider seam gate for M015/S03. The first runtime attempt failed closed during setup because host port 18080 was already owned by a stale M015 Compose stack. Investigation showed prior profile-scoped `provider-worker` containers were not removed by teardown because the runner called `docker compose down` without including the `tools` profile. I updated `scripts/security/verify-m015-runtime-security.sh` so teardown runs `compose --profile tools down`, added a static regression in `test_m015_runtime_harness.py`, cleaned stale M015 runtime projects, and verified no M015 containers remained. I also made the durable provider evidence explicitly state that WuzAPI and Gemini used configured local HTTP provider stubs and that live providers were not used, with a regression in `test_m015_s03_provider_runtime_contract.py`. The final full gate rebuilt/refreshed `provider-seam-evidence.json`, `provider-seam-summary.md`, and provider stub observations for correlation `m015-20260514T151252Z-1915865`.

## Verification

Ran the full T05 verification command: shell syntax validation for `verify-m015-runtime-security.sh`, Docker Compose config validation, focused provider/runtime/Gemini pytest contracts, and `./scripts/security/verify-m015-runtime-security.sh --seam provider`. The final run exited 0, wrote passing provider evidence, recorded explicit local stub usage for WuzAPI/Gemini, showed redaction validated, showed worker boundary `taskiq`, recorded teardown `complete`, and left no M015 runtime containers. Additional diagnostics confirmed runner phases include setup/compose/readiness/stub-readiness/wuzapi/gemini/worker/evidence/teardown and provider stub observations persist only redaction-safe metadata/header-presence/body-hash fields.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s03_provider_runtime_contract.py tests/security/test_m015_runtime_harness.py tests/unit/test_gemini_client_stub_config.py -q && cd .. && ./scripts/security/verify-m015-runtime-security.sh --seam provider` | 0 | ✅ pass — authoritative T05 gate passed; provider evidence refreshed and teardown completed with tools-profile services included | 155707ms |
| 2 | `python evidence diagnostic: validate provider-seam-evidence.json result/redaction/stub usage/worker boundary/teardown and no remaining M015 containers` | 0 | ✅ pass — result passed, redaction_validated true, local stub usage recorded, worker boundary taskiq, teardown complete, remaining_containers=none | 389ms |
| 3 | `python provider stub observation diagnostic: validate observation count and redaction flags/header-presence/body-hash-only fields` | 0 | ✅ pass — 8 observations, redaction_validated true, no raw headers/bodies, header presence only, body hashes only | 43ms |

## Deviations

While running T05, verification exposed an unplanned teardown bug for Compose tools-profile services. I fixed the runner and added regressions before recording the final green evidence. I also made provider-stub usage explicit in the durable evidence/summary to satisfy the task done condition unambiguously.

## Known Issues

None.

## Files Created/Modified

- `scripts/security/verify-m015-runtime-security.sh`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `scripts/security/m015-runtime/m015_provider_security_taskiq.py`
- `backend-hormonia/tests/security/test_m015_s03_provider_runtime_contract.py`
- `backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json`
- `backend-hormonia/docs/reports/security/m015/provider-seam-summary.md`
- `backend-hormonia/docs/reports/security/m015/provider-stub-observations.jsonl`
