---
id: S01
parent: M004
milestone: M004
provides:
  - Executable guardrails for official-runtime auth/session residue with a machine-readable boundary, live verifier, and regression harness.
requires: []
affects:
  - M004/S02
  - M004/S03
  - M004/S04
  - M004/S05
key_files:
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
  - .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh
  - .gsd/milestones/M004/slices/S01/S01-RESEARCH.md
  - .gsd/milestones/M004/slices/S01/S01-UAT.md
  - backend-hormonia/tests/unit/test_runtime_residue_guard.py
key_decisions:
  - The official-runtime residue boundary is enforced per category and per scope, with approved hotspots pinned by explicit file anchors.
  - Published handoff artifacts reuse the verifier's exact category ids and backend/frontend scope names so later slices cannot drift into alternate naming.
  - Boundary shrinkage is only complete when the allowlist, research, summary, and UAT move together with a green verifier run.
patterns_established:
  - Slice-local shell verification delegates deterministic scanning and JSON parsing to embedded Python while remaining black-box testable through subprocess pytest.
  - Guardrail slices close with both an executable gate and a readable hotspot map so later cleanup work updates one boundary contract instead of reopening discovery.
observability_surfaces:
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all
  - bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all
  - cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k unexpected_residue
  - cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k moved_hotspot_reports_anchor_name
  - .gsd/milestones/M004/slices/S01/S01-RESEARCH.md
  - .gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json
drill_down_paths:
  - .gsd/milestones/M004/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S01/tasks/T02-SUMMARY.md
duration: ~3h40m
verification_result: passed
completed_at: 2026-03-14T00:45:23-03:00
---

# S01: Guardrails do corte canônico de runtime

**Scoped runtime-residue guardrails now freeze the official auth/session boundary with a live allowlist, `--report` / `--check` verifier, and regression proof for unexpected residue plus moved approved hotspots.**

## What Happened

S01 turned the runtime-cut discussion into an executable boundary. The slice added `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` as the machine-readable contract for the six residue classes that still matter to the official runtime: `firebase_uid`, root legacy `/session/*`, `X-Session-ID`, session-as-Bearer fallback, websocket `session_id` query fallback, and Firebase narrative residue. The boundary is deliberately scoped to `backend-hormonia/app`, `frontend-hormonia/src`, and slice-local proof artifacts, with explicit exclusions for schema/model residue, historical docs/tests, and unrelated vendor/public session strings.

On top of that contract, the slice shipped `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`. In `--report` mode it emits approved residue by scope, category, file, and count. In `--check` mode it fails on drift with named diagnostics like `unexpected_file=` and `moved_hotspot=... anchor=...`. That makes later slices update the boundary intentionally instead of relying on grep memory.

The guardrail is backed by `backend-hormonia/tests/unit/test_runtime_residue_guard.py`, which runs the real shell verifier in subprocesses against temp repos and temp allowlists. The suite proves three things that matter downstream: approved hotspots stay green, newly introduced residue fails loudly in the right category, and anchor drift reports the moved hotspot name instead of collapsing into an opaque nonzero exit.

S01 also published the human-readable handoff pack. `S01-RESEARCH.md` mirrors the live residue map with the verifier's exact category ids and scope names. This summary compresses the slice for downstream execution. `S01-UAT.md` turns the guardrail into an artifact-driven review script so later slices can verify both the happy path and the expected failure paths without reopening repo-wide discovery.

## Verification

Passed on closeout rerun:

- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py`
- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k unexpected_residue`
- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k moved_hotspot_reports_anchor_name`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all`
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`

Observability/diagnostic surfaces confirmed on rerun:

- `--report all` emitted backend/frontend category-file-count rows for the approved live boundary.
- `--check all` stayed green on the current boundary.
- The two targeted pytest subsets still exercise the failure-path diagnostics for unexpected residue and moved hotspots.

## Requirements Advanced

- R047 — The slice now names and guards every approved Firebase-era residue hotspot that still leaks into the official runtime boundary.
- R048 — The slice makes dual auth/session surfaces measurable, so later slices can remove them against a single executable contract.
- R049 — The slice freezes where `firebase_uid` still survives in the official runtime and prevents silent reintroduction while backend convergence happens.
- R050 — The slice exposes the frontend's remaining Firebase/session residue explicitly, including narrative/comment hotspots and legacy session transport fallbacks.

## Requirements Validated

- none — S01 proves the residue boundary and guardrails, not the final no-Firebase runtime behavior.

## New Requirements Surfaced

- none

## Requirements Invalidated or Re-scoped

- none

## Deviations

Added explicit failure-path verification commands to `S01-PLAN.md` during execution so slice closeout proves diagnostics, not only green-path reruns.

## Known Limitations

- The approved residue is still live by design. S02–S05 must now shrink the allowlist instead of treating the green guard as convergence.
- `backend-hormonia` pytest still emits the existing `pytest_asyncio` loop-scope deprecation warning during the guard suite. It is unchanged and non-blocking.

## Follow-ups

- S02 should start with the backend-heavy hotspots from the current report: `auth_dependencies.py`, `auth_session_cache.py`, `auth_legacy_firebase.py`, `auth_session.py`, and the remaining `X-Session-ID` / bearer / root `/session/*` seams.
- Any later slice that removes or relocates approved residue must update `runtime-residue-allowlist.json`, `S01-RESEARCH.md`, this summary, and `S01-UAT.md` in the same change.

## Files Created/Modified

- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` — machine-readable boundary for approved residue classes, scopes, anchors, and exclusions.
- `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh` — executable `--report` / `--check` guard with deterministic counts and drift diagnostics.
- `backend-hormonia/tests/unit/test_runtime_residue_guard.py` — black-box regression harness for approved residue, unexpected residue, scope handling, and moved hotspots.
- `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md` — readable hotspot map aligned to live verifier output.
- `.gsd/milestones/M004/slices/S01/S01-UAT.md` — artifact-driven reviewer script for green-path and failure-path boundary checks.
- `.gsd/milestones/M004/slices/S01/S01-PLAN.md` — slice verification block updated with explicit failure-path checks and task completion markers.

## Forward Intelligence

### What the next slice should know
- The verifier is already scoped tightly enough to be actionable. Do not broaden it repo-wide; shrink the allowlist as backend/frontend convergence lands.
- The current highest-value backend residue is concentrated in auth/session seams, not random stragglers. Start there instead of chasing low-count leaf files.
- Frontend narrative residue is small in file count but strategically important because R050 includes comments and operational semantics, not only live transport code.

### What's fragile
- Allowlist anchors in `auth_session.py`, `auth_dependencies.py`, and the websocket/client session helpers — these files are likely to move during S02/S03, so anchor drift will fail until the boundary contract is updated intentionally.
- The distinction between official-runtime scope and out-of-scope schema/history strings — broadening scans casually will create noise and weaken the guard.

### Authoritative diagnostics
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report all` — source of truth for what residue is still approved right now.
- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` — fastest way to catch new live residue or stale hotspot bookkeeping.
- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k unexpected_residue` — trusted proof that new residue still fails with category/file diagnostics.
- `cd backend-hormonia && pytest -q tests/unit/test_runtime_residue_guard.py -k moved_hotspot_reports_anchor_name` — trusted proof that moved approved hotspots still surface anchor-aware failures.

### What assumptions changed
- "A couple of grep commands plus prose will be enough for the handoff" — not true; the boundary needed a machine-readable allowlist, named anchors, and black-box failure-path tests.
- "Green report/check output alone is enough to close the slice" — not true; later slices need the readable hotspot map and UAT in lockstep or the guard becomes opaque bookkeeping.
