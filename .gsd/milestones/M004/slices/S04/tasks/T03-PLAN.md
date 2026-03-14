---
estimated_steps: 4
estimated_files: 7
---

# T03: Tombstone `/session/*` and republish the backend residue boundary

**Slice:** S04 — Superfícies legadas de auth/sessão aposentadas
**Milestone:** M004

## Description

S04 is not done when the old root router merely disappears from grep. It needs an intentional retirement surface and a verifier story that matches it. This task makes `/session/*` explicitly dead, keeps the retirement diagnosable, and republishes the S01 residue contract so future drift is caught by the same guard that defined the slice boundary.

## Steps

1. Replace the mounted root `/session/*` compatibility island with explicit tombstone/rejection behavior in the central router wiring instead of leaving generic 404 drift.
2. Update the legacy router tests so they prove deterministic retirement status/body semantics rather than the old Firebase-era behavior.
3. Republish `runtime-residue-allowlist.json` and the S01 handoff docs so removed `root_legacy_session`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query` anchors disappear or are reclassified honestly.
4. Re-run the retirement tests plus the residue report/check so the executable boundary and the written handoff say the same thing.

## Must-Haves

- [ ] `/session/*` is intentionally retired with explicit, testable behavior.
- [ ] No stale S01-approved legacy anchors remain for surfaces that S04 actually removed.
- [ ] The residue report/check describe the same post-cut backend boundary as the code and tests.
- [ ] The slice leaves a durable regression gate instead of a one-off cleanup diff.

## Verification

- `cd backend-hormonia && pytest -q tests/auth/test_session_validation.py`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`

## Observability Impact

- Signals added/changed: explicit `/session/*` retirement status/body semantics and a reduced backend residue inventory for auth/session legacy transport.
- How a future agent inspects this: hit the retirement test file for route behavior, then run the residue report/check to see whether the issue is runtime regression or stale allowlist/docs bookkeeping.
- Failure state exposed: stale approved anchors, accidental route resurrection, or silent route disappearance become separate visible failure modes.

## Inputs

- `backend-hormonia/app/routers/auth_session.py` — still mounted Firebase-era compatibility island.
- `backend-hormonia/app/core/router_registry.py` — central mount point for the root `/session/*` surface.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — authoritative residue boundary that must shrink with the hard cut.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — guardrail narrative that must stay aligned with the verifier.
- T01/T02 outputs: official cookie-only staff session transport is already in place, so `/session/*` can be retired without preserving runtime compatibility.

## Expected Output

- `backend-hormonia/app/routers/auth_session.py` — explicit tombstone/rejection implementation for the retired root session surface, or a minimal retirement router if the old implementation is removed.
- `backend-hormonia/app/core/router_registry.py` — central wiring that mounts the intentional retirement surface instead of the legacy compatibility island.
- `backend-hormonia/tests/auth/test_session_validation.py` — proof of deterministic `/session/*` retirement behavior.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — republished backend residue contract after the S04 transport cut.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — updated guardrail narrative for the reduced backend auth/session boundary.
- `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md` — condensed handoff aligned to the post-S04 residue boundary.
- `.gsd/milestones/M004/slices/S01/S01-UAT.md` — replay guidance aligned to the new retirement proof and residue report.
