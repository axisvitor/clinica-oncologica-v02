---
estimated_steps: 4
estimated_files: 6
---

# T03: Publish the slice closeout and milestone state

**Slice:** S05 — Integrated Proof And Structural Closeout
**Milestone:** M003

## Description

Turn the proof from T01 and T02 into the durable milestone closeout. This task writes the slice summary and UAT, updates roadmap/requirements/state only when the proof supports it, and leaves the retained compatibility islands and any remaining fragility explicit so the next maintainer does not have to reconstruct what S05 actually proved.

## Steps

1. Write `S05-SUMMARY.md` and any task summaries needed to compress the structural gate, assembled runtime smoke, compatibility proof, and blocker state into one replayable handoff.
2. Update `S05-UAT.md` so the final operator-facing acceptance path includes the exact routed entrypoints, direct compat checks, and any conditional Playwright skip reason.
3. If the proof is green, mark S05 complete in the roadmap and move R037, R038, and R039 from active to validated in `REQUIREMENTS.md`; if not, leave those states unchanged and record the blocker honestly.
4. Update `.gsd/DECISIONS.md` and `.gsd/STATE.md` so the current acceptance strategy, retained compatibility islands, and next action are explicit for the next agent.

## Must-Haves

- [ ] The slice closeout artifacts make it obvious which exact proof closed or blocked R037, R038, and R039.
- [ ] Roadmap, requirements, decisions, and state files reflect the real outcome of S05 instead of a ceremonial completion.

## Verification

- `rg -n 'R037|R038|R039|/admin|/dashboard|/whatsapp|session/validate|Bearer' .gsd/milestones/M003/slices/S05/S05-SUMMARY.md .gsd/milestones/M003/slices/S05/S05-UAT.md .gsd/REQUIREMENTS.md`
- `rg -n 'S05: Integrated Proof And Structural Closeout' .gsd/milestones/M003/M003-ROADMAP.md`
- `rg -n 'Active Slice|Phase|Next Action' .gsd/STATE.md`

## Inputs

- `.gsd/milestones/M003/slices/S05/tasks/T01-SUMMARY.md` — structural gate replay outcome.
- `.gsd/milestones/M003/slices/S05/tasks/T02-SUMMARY.md` — local-stack runtime/compat proof outcome.
- `.gsd/milestones/M003/slices/S05/S05-UAT.md` — assembled acceptance evidence that the closeout must summarize faithfully.
- `.gsd/REQUIREMENTS.md` — active requirement states for R037, R038, and R039.

## Expected Output

- `.gsd/milestones/M003/slices/S05/S05-SUMMARY.md` — compressed slice closeout tied directly to proof and requirement status.
- `.gsd/milestones/M003/slices/S05/S05-UAT.md` — finalized acceptance log for the real runtime path.
- `.gsd/milestones/M003/M003-ROADMAP.md` — S05 marked complete only if the proof is green.
- `.gsd/REQUIREMENTS.md` — R037, R038, and R039 moved to validated only if the closeout evidence supports it.
- `.gsd/DECISIONS.md` — any final acceptance-strategy or retained-compatibility decisions recorded.
- `.gsd/STATE.md` — current phase and next action updated to match the real slice outcome.
