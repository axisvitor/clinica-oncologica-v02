---
estimated_steps: 5
estimated_files: 3
---

# T03: Publish the cleanup manifest and close the slice proof gate

**Slice:** S04 — Dead-Code And Obsolete-Compatibility Cleanup
**Milestone:** M003

## Description

Turn the code deletions into an auditable slice handoff. This task writes the manifest that distinguishes removed residue from retained compatibility islands, records the proof commands/results behind each decision, and closes S04 with the evidence-map gate so S05 inherits a concrete cleanup boundary.

## Steps

1. Write `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md` with explicit sections for removed frontend residue, removed backend auth residue, retained compatibility islands, and why each retained island is still live.
2. Record the exact frontend/backend proof commands and outcomes from T01/T02 in the manifest so S05 can reuse the same acceptance surface without reopening discovery.
3. Run `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all` and capture the post-cleanup numbers/status in the manifest.
4. Update `.gsd/milestones/M003/slices/S04/S04-SUMMARY.md` and `.gsd/milestones/M003/slices/S04/S04-UAT.md` so the slice handoff clearly reflects what was deleted, what was isolated, and what S05 still has to smoke.
5. Confirm the manifest and handoff artifacts make `backend-hormonia/app/routers/auth_session.py`, `firebase_uid` fallback, and bearer-token fallback explicit retained surfaces rather than ambiguous leftovers.

## Must-Haves

- [ ] The manifest explicitly lists deleted frontend/backend residue and the retained live compatibility islands with rationale tied to evidence.
- [ ] The verifier outcome and focused proof commands/results are captured in the slice handoff artifacts so S05 inherits a concrete regression checklist.

## Verification

- `bash .gsd/milestones/M003/slices/S01/verify-evidence-map.sh --report all`
- `python3 - <<'PY'
from pathlib import Path
manifest = Path('.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md').read_text()
required = [
    'frontend-hormonia/src/lib/api.ts',
    'frontend-hormonia/src/lib/types/api.ts',
    'frontend-hormonia/src/hooks/use-quiz-session.ts',
    'verify_firebase_token',
    'get_doctor_user',
    'get_current_user_websocket',
    'backend-hormonia/app/routers/auth_session.py',
    'firebase_uid',
    'bearer-token fallback',
]
missing = [item for item in required if item not in manifest]
if missing:
    raise SystemExit(f'manifest missing required cleanup entries: {missing}')
print('manifest covers removed residue and retained compatibility islands')
PY`

## Observability Impact

- Signals added/changed: the slice ends with an explicit manifest/checklist instead of relying on scattered research notes to explain what is still legacy-only.
- How a future agent inspects this: read `S04-CLEANUP-MANIFEST.md`, `S04-SUMMARY.md`, and `S04-UAT.md`, then rerun the recorded verifier/proof commands.
- Failure state exposed: undocumented retained islands, missing deletion rationale, or verifier drift become explicit artifact/command failures.

## Inputs

- Outputs from T01 and T02 — the actual deleted files/exports and the focused proof results that justify them.
- `.gsd/milestones/M003/slices/S04/S04-RESEARCH.md` — the evidence baseline for what stays in scope for removal versus isolation.

## Expected Output

- `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md` — the dead-code cleanup manifest consumed by S05.
- `.gsd/milestones/M003/slices/S04/S04-SUMMARY.md` and `.gsd/milestones/M003/slices/S04/S04-UAT.md` — updated slice handoff artifacts with the final proof checklist.
