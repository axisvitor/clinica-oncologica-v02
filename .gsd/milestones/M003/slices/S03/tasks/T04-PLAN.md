---
estimated_steps: 5
estimated_files: 8
---

# T04: Migrate the remaining compat caller and close the focused frontend proof gate

**Slice:** S03 — Frontend Client/Type Surface Refactor
**Milestone:** M003

## Description

Close the slice by removing the last live app dependency on `src/lib/types/api.ts`, refreshing the affected hook/type tests, and rerunning the focused frontend proof pack. This task turns the structural refactor into a verified handoff for S04 instead of a partial internal cleanup.

## Steps

1. Migrate `frontend-hormonia/src/hooks/usePatients.ts` from `src/lib/types/api.ts` to the canonical type/source import chosen during the split, keeping runtime behavior the same.
2. Update `frontend-hormonia/src/hooks/__tests__/usePatients.test.ts` and `frontend-hormonia/tests/unit/types-validation.test.ts` so they assert the new ownership path and catch regressions if the compat barrel leaks back into live app code.
3. Leave `frontend-hormonia/src/lib/types/api.ts` present but more isolated, documenting it as S04 cleanup work rather than deleting it here.
4. Run the focused auth/session/realtime/dashboard suites, hook/type suites, `npm run typecheck`, and `npm run build` to prove the client/type split did not break visible frontend behavior.
5. Run the structural shrink check and `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend` so the slice closes with both runtime proof and evidence-contract proof.

## Must-Haves

- [ ] `src/hooks/usePatients.ts` no longer imports the compatibility barrel, and the remaining `src/lib/types/api.ts` residue is explicitly isolated for S04 instead of silently broadened.
- [ ] The full focused frontend proof pack is green, including auth/session/realtime/client behavior, hook/type coverage, build/typecheck, and the structural shrink/evidence checks.

## Verification

- `cd frontend-hormonia && npm run test -- src/hooks/__tests__/usePatients.test.ts tests/unit/types-validation.test.ts tests/integration/auth/session-first-cutover.test.tsx tests/integration/realtime/session-websocket-cutover.test.ts tests/integration/initialization/session-auth-operational-surfaces.test.tsx tests/components/dashboard/QuickStats.test.tsx`
- `cd frontend-hormonia && npm run typecheck && npm run build`
- `cd frontend-hormonia && python3 - <<'PY'
from pathlib import Path
index_source = Path('src/lib/api-client/index.ts').read_text()
types_source = Path('src/lib/api-client/types.ts').read_text()
if len(index_source.splitlines()) >= 800:
    raise SystemExit(f'api-client/index.ts still too large: {len(index_source.splitlines())} lines')
if len(types_source.splitlines()) >= 450:
    raise SystemExit(f'api-client/types.ts still too large: {len(types_source.splitlines())} lines')
if Path('src/hooks/usePatients.ts').read_text().count('lib/types/api'):
    raise SystemExit('usePatients.ts still imports the compatibility type barrel')
print({'index_lines': len(index_source.splitlines()), 'types_lines': len(types_source.splitlines())})
PY && bash ../.gsd/milestones/M003/slices/S01/verify-evidence-map.sh --check frontend`

## Observability Impact

- Signals added/changed: The slice closes with both behavior-level and structure-level proof, so future regressions show up either as focused Vitest failures or as explicit shrink/evidence-check failures.
- How a future agent inspects this: Re-run the verification commands above and inspect `src/hooks/usePatients.ts`, `src/lib/api-client/index.ts`, and `src/lib/api-client/types.ts` when a proof gate fails.
- Failure state exposed: lingering compat imports, hotspot regrowth, auth/session client drift, and build/type regressions become explicit acceptance failures.

## Inputs

- `frontend-hormonia/src/hooks/usePatients.ts` — the last live app caller still on `src/lib/types/api.ts` according to S01/S03 research.
- `frontend-hormonia/src/hooks/__tests__/usePatients.test.ts` and `frontend-hormonia/tests/unit/types-validation.test.ts` — the focused test coverage that should move with the canonical import path.
- Outputs from T01–T03 — the structural tests, extracted modules, and type barrel split that make the migration safe to finish.

## Expected Output

- `frontend-hormonia/src/hooks/usePatients.ts` — migrated to a canonical type/source import with unchanged visible hook behavior.
- `frontend-hormonia/src/hooks/__tests__/usePatients.test.ts` and `frontend-hormonia/tests/unit/types-validation.test.ts` — refreshed proof aligned with the new ownership boundary.
- A green focused frontend verification pack plus shrink/evidence-check output that hands S04 a genuinely isolated compat barrel instead of a live app dependency.
