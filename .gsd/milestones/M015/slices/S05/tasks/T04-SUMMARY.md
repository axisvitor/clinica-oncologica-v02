---
id: T04
parent: S05
milestone: M015
key_files:
  - scripts/security/m015-runtime/evidence_matrix.py
  - backend-hormonia/tests/security/test_m015_final_matrix_contract.py
  - scripts/security/verify-m015-runtime-security.sh
  - backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json
  - backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.md
key_decisions:
  - Redaction failures inside seam evidence or matrix content are wrapped as `unsafe_sensitive_content` so the CLI emits a stable failure class.
  - Placeholder scanning ignores validator taxonomy fields so `placeholder_text` can exist as a failure class without self-triggering.
  - Negative tests mutate in-memory/current fixture copies rather than durable evidence files.
duration: 
verification_result: passed
completed_at: 2026-05-14T18:02:03.830Z
blocker_discovered: false
---

# T04: Enforced strict matrix validation and red-signal policy with negative tests.

**Enforced strict matrix validation and red-signal policy with negative tests.**

## What Happened

Tightened matrix validation so closure is blocked on missing required rows, missing evidence artifacts, failed seam evidence, stale/missing correlations, placeholder/TODO/TBD prose, raw private download URL/path leakage, unsafe sensitive content, unclassified warnings, and unresolved red-signal statuses. Added mutation tests that remove required rows, clear correlations, inject placeholders, set invalid statuses, inject raw private URLs and cookie-shaped strings, remove warnings, remove evidence artifacts, and mark a seam result failed. The current generated matrix validates cleanly and the negative tests prove the validator catches false-green shapes.

## Verification

Fresh verification passed: matrix CLI printed `M015 evidence matrix validated: backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json`; 48 final matrix/runtime harness tests passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python3 scripts/security/m015-runtime/evidence_matrix.py --input-dir backend-hormonia/docs/reports/security/m015 --output-dir backend-hormonia/docs/reports/security/m015 --validate && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_final_matrix_contract.py tests/security/test_m015_runtime_harness.py -q` | 0 | ✅ pass | 26500ms |

## Deviations

Expanded the T04 validator work inside the existing matrix helper rather than creating a separate companion script, keeping generation and validation in one CLI surface.

## Known Issues

The all-seam Docker runner has not yet been exercised after matrix validation wiring; that is T05's final operational proof.

## Files Created/Modified

- `scripts/security/m015-runtime/evidence_matrix.py`
- `backend-hormonia/tests/security/test_m015_final_matrix_contract.py`
- `scripts/security/verify-m015-runtime-security.sh`
- `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.json`
- `backend-hormonia/docs/reports/security/m015/m015-evidence-matrix.md`
