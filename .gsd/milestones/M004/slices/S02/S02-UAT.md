# S02: Backend auth/sessão convergido para identidade canônica — UAT

**Milestone:** M004
**Written:** 2026-03-14

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S02 closes on backend proof packs plus a residue-boundary handoff, not a new browser-facing workflow. The trustworthy review is replaying the focused/helper acceptance suites and checking that the live backend residue report matches the published post-S02 story.

## Preconditions

- Run from the repository root: `/mnt/c/Meu Projetos/clinica-oncologica-v02-1`.
- Python dependencies for `backend-hormonia` are installed and `pytest` is available.
- `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json`, `.gsd/milestones/M004/slices/S01/S01-RESEARCH.md`, `.gsd/milestones/M004/slices/S01/S01-SUMMARY.md`, and `.gsd/milestones/M004/slices/S01/S01-UAT.md` are present in the working tree.
- `.gsd/milestones/M004/slices/S02/S02-SUMMARY.md` is present so the backend report can be checked against the published residue story.

## Smoke Test

1. Run `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py`.
2. Wait for pytest to finish.
3. **Expected:** The focused proof pack passes. Embedded canonical session payloads work without `firebase_uid`, helper fallback order stays `id` / `user_id` first, and mapping-style `request.state.session_id` / `user_id` / `user_role` behavior stays green.

## Test Cases

### 1. Canonical backend helper proof stays green

1. Run `cd backend-hormonia && pytest -q tests/unit/test_auth_session_cache_canonical_identity.py tests/api/v2/test_auth_session_shared_canonical_identity.py tests/api/v2/test_auth_dependency_override_contract.py`.
2. Review the passing assertions.
3. **Expected:** No helper test requires `firebase_uid` on the canonical happy path. The remaining `firebase_uid` assertions only cover explicit compatibility fallback when canonical IDs are absent.

### 2. Route-level acceptance pack stays green

1. Run `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_priority.py tests/api/v2/test_auth_local_login.py tests/api/test_websocket_session_auth_contract.py tests/integration/test_local_auth_core_flow.py`.
2. Wait for pytest to finish.
3. **Expected:** The suite passes. Local login, verify-session, logout, session precedence, websocket auth, and the local auth core flow still work while the helper convergence stays in place.

### 3. Live backend residue report matches the published S02 story

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`.
2. Compare the output to `S02-SUMMARY.md` and `S01-RESEARCH.md`.
3. **Expected:** The report ends with `RESULT: --report backend OK` and uses the same six category ids: `firebase_uid`, `root_legacy_session`, `x_session_id`, `session_bearer_fallback`, `websocket_session_id_query`, and `firebase_narrative`. The published story should still hold:
   - `firebase_uid` includes compatibility-only helper/passthrough residue plus deliberate legacy/admin seams.
   - `root_legacy_session`, `x_session_id`, `session_bearer_fallback`, and `websocket_session_id_query` are the remaining transport-retirement seams for S03/S04.
   - `firebase_narrative` is still tied to the retained root `/session/*` island and later frontend/admin narrative cleanup.

### 4. Drift gate stays green on the republished boundary

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`.
2. Wait for the verifier to finish.
3. **Expected:** The command succeeds, ends with `RESULT: --check backend OK`, and does not emit `unexpected_file=` or `moved_hotspot=` diagnostics.

## Edge Cases

### Flat backend residue counts after a real semantic shrink

1. Run the focused helper proof pack and `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --report backend`.
2. Compare the helper-proof result with the report and the handoff docs.
3. **Expected:** It is acceptable for the report to keep the same backend file counts if the meaning changed from happy-path dependence to compatibility-only fallback. In that case the allowlist descriptions/labels and the S01/S02 handoff files must already describe the narrower meaning.

### Green residue guard but red helper proof

1. Run `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check backend`.
2. Run the focused helper proof pack.
3. **Expected:** If `--check backend` stays green but the focused helper proof fails, treat it as a runtime regression in canonical identity behavior, not a bookkeeping-only problem.

## Failure Signals

- Any of the focused canonical helper tests fail, especially around embedded canonical session payloads, cache/DB lookup order, or explicit `firebase_uid` fallback quarantine.
- `tests/api/v2/test_auth_dependency_override_contract.py` fails its `request.state.session_id` / `user_id` / `user_role` assertions.
- The websocket contract suite stops emitting the stable `AUTH_WEBSOCKET_SESSION_INVALID` or `AUTH_WEBSOCKET_SESSION_LOOKUP_FAILED` diagnostics.
- `verify-runtime-residue.sh --report backend` introduces a new category/path, or the report story no longer matches `S01-RESEARCH.md` and `S02-SUMMARY.md`.
- `verify-runtime-residue.sh --check backend` emits `unexpected_file=` or `moved_hotspot=`.
- The docs describe a backend helper hotspot as compatibility-only but the focused proof shows `firebase_uid` is still required for canonical identity resolution.

## Requirements Proved By This UAT

- R048 — Backend auth/session helpers and the public dependency surface now share one canonical `user_id`-first identity contract.
- R049 — The backend happy path no longer needs `firebase_uid`; remaining hits are explicit compatibility residue rather than hidden canonical blockers.
- R047 — The live backend residue boundary is republished honestly enough to distinguish finished helper convergence from the later transport-retirement work.

## Not Proven By This UAT

- This UAT does not prove the official frontend has already cut over to the canonical contract; that remains S03 work.
- This UAT does not retire the root `/session/*` island, backend acceptance of `X-Session-ID`, session-as-Bearer, or websocket `session_id` query fallback; that remains S04 work.
- This UAT does not remove the remaining adjacent/admin `firebase_uid` residue or Firebase narrative outside the canonical backend happy path; that remains S05 work.
- This UAT does not prove the fully assembled no-Firebase local stack; that remains S06 work.

## Notes for Tester

- Read `S02-SUMMARY.md` before interpreting the backend report. After S02, flat `firebase_uid` counts do not mean the canonical helper path is still Firebase-shaped.
- Treat the existing `pytest_asyncio` loop-scope deprecation warning as known noise unless it changes the pass/fail result.
- When a later slice intentionally removes or relocates residue, update the S01 allowlist plus both S01/S02 handoff packs in the same change before trusting the verifier again.
- When in doubt, trust the pair: focused proof pack for behavior, residue verifier for bookkeeping. Either one alone can miss the real failure mode.
