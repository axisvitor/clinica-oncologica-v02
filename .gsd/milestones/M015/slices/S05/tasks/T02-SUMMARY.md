---
id: T02
parent: S05
milestone: M015
key_files:
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/README.md
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
  - scripts/security/m015-runtime/tests/test_runner_contract.py
key_decisions:
  - No seam filter now means deterministic all-seam closeout (`db session provider artifact`) instead of missing-seam failure.
  - All-seam mode launches each seam as a child scoped runner invocation with child correlation/project IDs so per-seam teardown remains isolated.
  - `--keep-stack` and `--teardown-only` remain scoped-seam-only to avoid port/project collisions in all-seam closeout.
duration: 
verification_result: passed
completed_at: 2026-05-14T17:55:38.242Z
blocker_discovered: false
---

# T02: Implemented the static no-filter all-seam runner mode while preserving unknown-seam fail-closed behavior.

**Implemented the static no-filter all-seam runner mode while preserving unknown-seam fail-closed behavior.**

## What Happened

Updated the runner CLI so `--seam` is optional: scoped seam invocations still work, unknown seams still fail before setup, and no-filter mode calls `run_all_seams()` in deterministic order. All-seam mode creates a parent correlation/project context, then invokes child scoped seam runs with child correlation/project names to preserve the existing per-seam startup, evidence, and teardown behavior. README usage now documents no-filter closeout and final matrix validation. Static contract tests were updated to avoid accidentally starting Docker during fast test runs.

## Verification

Fresh verification passed: `bash -n scripts/security/verify-m015-runtime-security.sh` succeeded; `--list-seams` printed `db`, `session`, `provider`, `artifact`; `--seam not-a-seam` exited 64 and included `unknown seam`; 41 runner/harness contract tests passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `bash -n scripts/security/verify-m015-runtime-security.sh && ./scripts/security/verify-m015-runtime-security.sh --list-seams && ./scripts/security/verify-m015-runtime-security.sh --seam not-a-seam >/tmp/m015-unknown.out 2>&1; test $? -eq 64 && grep -q "unknown seam" /tmp/m015-unknown.out && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_runtime_harness.py ../scripts/security/m015-runtime/tests/test_runner_contract.py -q` | 0 | ✅ pass | 22500ms |

## Deviations

Implemented T02 alongside T01 contract work so the no-filter runner contract could be verified without leaving failing tests behind. Runtime all-seam execution is still reserved for T05; T02 proves the static/dry-run contract and unknown-seam failure behavior.

## Known Issues

The all-seam mode has not yet been exercised end-to-end through Docker; that is intentionally deferred to T05 after matrix generation/validation contracts are complete.

## Files Created/Modified

- `scripts/security/verify-m015-runtime-security.sh`
- `scripts/security/m015-runtime/README.md`
- `backend-hormonia/tests/security/test_m015_runtime_harness.py`
- `scripts/security/m015-runtime/tests/test_runner_contract.py`
