---
id: T04
parent: S04
milestone: M015
key_files:
  - scripts/security/m015-runtime/artifact_seam.py
  - scripts/security/m015-runtime/redaction.py
  - backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py
key_decisions:
  - Add artifact-specific redaction denylist entries for raw `/uploads/private`-style paths, M015 private upload roots, raw `download_urls` mappings, and raw uploaded/report bytes instead of relying only on the older DB/provider/session denylist.
  - Keep sanitized evidence keys such as `raw_download_urls_persisted=false` allowed while rejecting actual raw `"download_urls": {...}` mappings.
  - Use tests to verify both malicious artifact evidence rejection and valid S04 evidence/summary acceptance before the Docker runtime run writes durable artifacts.
duration: 
verification_result: passed
completed_at: 2026-05-14T16:53:55.242Z
blocker_discovered: false
---

# T04: Hardened S04 artifact evidence redaction and test-covered safe evidence/summary shapes before the runtime artifact seam writes durable artifacts.

**Hardened S04 artifact evidence redaction and test-covered safe evidence/summary shapes before the runtime artifact seam writes durable artifacts.**

## What Happened

Hardened the M015 redaction helper for S04 artifact evidence. `redaction.py` now rejects raw private artifact/static paths such as `/uploads/private/...`, M015 private upload root paths, actual `download_urls` mappings, and raw uploaded/report byte assignments. Matching sanitizers were added for transient text. The artifact probe already writes evidence and summary through `write_validated_json` and `write_validated_text`; T04 added tests proving malicious artifact evidence is rejected and a valid S04 evidence/summary shape is accepted. The summary/evidence contract now explicitly permits only hashes, route labels, statuses/classes, header booleans, redirect booleans, redaction verdicts, teardown state, and explicit non-goals. A malformed regex was caught by verification before completion and corrected.

## Verification

Fresh T04 verification passed after the last edit: `cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_s04_artifact_runtime_contract.py tests/security/test_m015_runtime_harness.py -q`. The rerun reported `............................................ [100%]` for 44 tests.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_s04_artifact_runtime_contract.py tests/security/test_m015_runtime_harness.py -q` | 0 | ✅ pass — 44 artifact/harness redaction tests reached 100% after regex fix | 21700ms |

## Deviations

The first T04 verification run failed during import because the new private-artifact regex had an unbalanced character class. I fixed the regex and reran the exact T04 gate successfully.

## Known Issues

None.

## Files Created/Modified

- `scripts/security/m015-runtime/artifact_seam.py`
- `scripts/security/m015-runtime/redaction.py`
- `backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py`
