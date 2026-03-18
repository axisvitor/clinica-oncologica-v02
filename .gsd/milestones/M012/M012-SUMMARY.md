---
id: M012
provides:
  - Dedicated patient_flow_overrides persistence, merged GET/PUT API, and fixed override semantics per patient
  - Override-first pipeline lookup in both on-demand and batch paths with shared Redis cache and skip handling
  - PatientDetailPage override editor with source badges, future-only editing, add-day, and skip toggle
  - Replayable closeout verifier (verify-m012.sh + M012-VERIFY.json) proving the assembled milestone
key_decisions:
  - D021/D022 — patient-specific overrides live in a dedicated table and are merged at read-time so later global template edits do not overwrite them
  - D023/D024 — only future days are editable, but physicians can fully override content, message type, expects_response, add days, and skip days
  - D025/D026 — physician-authored override content bypasses AI personalization, and patients with no overrides cache an empty-dict miss sentinel
patterns_established:
  - Shared Redis key flow_override:{state_id}:days with glob invalidation flow_override:{state_id}:*
  - Merge algorithm overlays override rows onto global template days, appends override-only extra days, and annotates source/editable per day
  - PatientDetailPage uses a dedicated dialog + typed React Query hook instead of mutating the global template editor directly
  - Milestone closure is replayable through grouped verifier phases rather than one-off terminal proof
observability_surfaces:
  - bash verify-m012.sh — 11 grouped PASS/FAIL checks spanning syntax, structure, pipeline wiring, and frontend build
  - .gsd/milestones/M012/M012-VERIFY.json — persisted phase audit for the replayable verifier
  - Structured PUT log "Flow overrides saved" with patient_id, flow_state_id, and override_count
  - Redis key flow_override:{patient_flow_state_id}:days and SQL query on patient_flow_overrides for runtime inspection
requirement_outcomes:
  - id: R064
    from_status: active
    to_status: validated
    proof: S01 delivered persistence + merge API, S02 injected override-first + skip pipeline behavior, S03 delivered the PatientDetailPage editor, and S04 re-ran verify-m012.sh green (11/11).
  - id: R104
    from_status: active
    to_status: validated
    proof: patient_flow_overrides migration/model shipped in S01 and verify-m012.sh phases 1-2 re-confirmed syntax and migration structure.
  - id: R105
    from_status: active
    to_status: validated
    proof: merged GET contract and PUT save/invalidation path shipped in S01 and verify-m012.sh phases 3-4 re-confirmed them.
  - id: R106
    from_status: active
    to_status: validated
    proof: S02 extended _get_day_config with override-first lookup and verify-m012.sh phase 5 re-confirmed the shared cache path.
  - id: R107
    from_status: active
    to_status: validated
    proof: S02 added skip handling in both pipeline paths and verify-m012.sh phase 6 re-confirmed it.
  - id: R108
    from_status: active
    to_status: validated
    proof: S03 delivered the PatientDetailPage editor and verify-m012.sh phases 8-11 re-confirmed button wiring, future-day gating, tsc --noEmit, and vite build.
  - id: R109
    from_status: active
    to_status: validated
    proof: S01 kept overrides separate from the global template and verify-m012.sh phase 7 re-confirmed merge-at-read immutability.
duration: 69m
verification_result: passed
completed_at: 2026-03-17
---

# M012: Override de Template por Paciente

**Per-patient flow overrides now persist independently of the global template, drive the real sending pipeline with cache-backed override/skip behavior, and are editable from PatientDetailPage through a future-day-only visual editor backed by a replayable milestone verifier.**

## What Happened

M012 closed the gap between the physician-facing global template editor from M007 and the real need to adapt follow-up for individual oncology patients.

S01 established the data and contract layer. It introduced the dedicated `patient_flow_overrides` table, the `PatientFlowOverride` model, the override schemas, and GET/PUT endpoints that project a merged day list for a specific patient. The merge logic overlays patient-specific overrides on top of the physician’s global template, preserves inherited global days, appends extra override-only days, labels each row with `source: "global" | "override"`, and gates editability by `current_flow_day`. PUT uses DELETE+INSERT replacement in one transaction and invalidates the patient override cache namespace.

S02 injected those overrides into the actual messaging runtime instead of leaving them as dead configuration. `_get_day_config` now checks the patient override cache/DB path before the global template, and the batch cron path mirrors that behavior through a sync helper so both sending surfaces stay aligned. `skip=true` now suppresses the day in both paths, and physician-authored override content bypasses AI personalization by design. Patients with no overrides transparently fall through to the original global-template path, with `{}` cached as a miss sentinel to avoid repeated DB reads.

S03 made the capability usable by physicians. `usePatientFlowOverrides` gives PatientDetailPage a typed GET/PUT hook, and `PatientFlowOverrideEditor` exposes the merged day list with `Global` / `Personalizado` / `Pulado` badges, disabled controls for already-sent days, add-day support, skip toggles, and save behavior that only persists override-source rows. The page now exposes the feature through the `Personalizar Fluxo` button in the right sidebar.

S04 turned the assembled work into a reliable closeout surface. `verify-m012.sh` now checks all milestone promises in one pass: backend syntax, migration/API structure, cache invalidation, override-first lookup, skip behavior, immutability, PatientDetailPage wiring, future-day restriction, `tsc --noEmit`, and `vite build`. The result is persisted in `M012-VERIFY.json`, so the milestone no longer depends on scattered slice claims or a placeholder verification summary.

## Cross-Slice Verification

- **PatientDetailPage exposes the feature with visible inheritance cues** — S03 delivered `PatientFlowOverrideEditor` with source badges and wired the `Personalizar Fluxo` button into `PatientDetailPage`; `bash verify-m012.sh` phase 8 re-confirmed the editor import and button text on the current filesystem.
- **Override edits persist in `patient_flow_overrides` and invalidate cache** — S01 delivered the table, transactional PUT save path, and `delete_pattern(f"flow_override:{flow_state.id}:*")`; `bash verify-m012.sh` phases 2 and 4 re-confirmed the migration and invalidation pattern.
- **`_get_day_config` returns the override when one exists and falls back otherwise** — S02 added the override-first lookup plus miss-sentinel fallback; `bash verify-m012.sh` phase 5 re-confirmed the `patient_flow_state_id` wiring and shared cache key.
- **`skip=true` suppresses the day in the pipeline** — S02 added skip handling to both on-demand and batch paths; `bash verify-m012.sh` phase 6 re-confirmed skip logic in `state.py` and `flow_helpers.py`.
- **Patients without overrides behave exactly as before** — S02’s `{}` miss sentinel and transparent fallthrough preserve the unchanged global-template path for the default case; no slice introduced a non-override behavior fork beyond the override-first guard.
- **Frontend closure stayed green** — S03 originally recorded `npx tsc --noEmit` and `npx vite build` as green; `bash verify-m012.sh` phases 10 and 11 re-ran both successfully during milestone closeout.
- **Backend syntax stayed green across all modified files** — S01/S02 both recorded syntax checks, and `bash verify-m012.sh` phase 1 re-ran `ast.parse` successfully on all 9 backend Python files touched by M012.
- **Definition of done fully satisfied** — all four slices are `[x]`, all slice summaries now exist (including a real S04 summary replacing the earlier placeholder), `verify-m012.sh` passed 11/11, and every roadmap success criterion has direct evidence.
- **Criteria not met** — none.

## Requirement Changes

- R064: active → validated — Milestone closeout now proves the full per-patient override capability end to end across persistence/API (S01), pipeline injection/skip behavior (S02), physician UI (S03), and replayable verification (S04).
- R104: active → validated — The dedicated `patient_flow_overrides` table/model shipped in S01 and was re-confirmed by `verify-m012.sh` phases 1-2.
- R105: active → validated — The merged GET contract and PUT save/invalidation path shipped in S01 and were re-confirmed by `verify-m012.sh` phases 3-4.
- R106: active → validated — S02’s override-first `_get_day_config` path was re-confirmed by `verify-m012.sh` phase 5.
- R107: active → validated — S02’s skip behavior in both pipeline surfaces was re-confirmed by `verify-m012.sh` phase 6.
- R108: active → validated — S03’s PatientDetailPage editor and future-day UI contract were re-confirmed by `verify-m012.sh` phases 8-11.
- R109: active → validated — Separate-table persistence and merge-at-read immutability were re-confirmed by `verify-m012.sh` phase 7.

## Forward Intelligence

### What the next milestone should know
- `bash verify-m012.sh` is the canonical re-entry point if any M012 regression is suspected; it covers every shipped promise in one command.
- When debugging live behavior, inspect the DB row set and the Redis dict together: `SELECT * FROM patient_flow_overrides WHERE patient_flow_state_id = :id ORDER BY day_number`, `GET /api/v2/patients/{id}/flow-overrides`, and `redis-cli GET flow_override:{state_id}:days` tell you what was configured, what the API shows, and what the pipeline will read.

### What's fragile
- Override logic is intentionally mirrored in two places: async `_get_day_config` (`state.py`) and sync `_check_patient_override_for_day` (`flow_helpers.py`). If the override cache format or day-shape changes, both paths must be updated together.
- The closeout verifier is structural/build-based, not a live stack replay. It is excellent for regression detection on wiring and contracts, but HTTP/runtime bugs that preserve those structures would still require mounted-stack replay.

### Authoritative diagnostics
- `bash verify-m012.sh` / `.gsd/milestones/M012/M012-VERIFY.json` — fastest trustworthy milestone-level signal because they cover the full assembled scope, not an isolated slice.
- `GET /api/v2/patients/{id}/flow-overrides` and `SELECT * FROM patient_flow_overrides WHERE patient_flow_state_id = :id ORDER BY day_number` — canonical read surfaces for merged vs. persisted override state.
- `redis-cli GET flow_override:{state_id}:days` — authoritative view of what the pipeline will see before it falls through to DB/template loading.

### What assumptions changed
- The milestone context sketched a per-day cache key (`flow_override:{state_id}:day:{day}`), but the shipped implementation uses a single per-state dict key (`flow_override:{state_id}:days`) plus glob invalidation. That shared format is now the real contract for both async and sync pipeline paths.
- The pre-closeout artifact set included a placeholder S04 summary; milestone completion required replacing that with a real integrated verification record so the proof chain is durable.

## Files Created/Modified

- `backend-hormonia/alembic/versions/m012_s01_patient_flow_overrides.py` — creates the dedicated override table and Alembic head linkage.
- `backend-hormonia/app/models/flow.py` — adds `PatientFlowOverride` and the `PatientFlowState.overrides` relationship.
- `backend-hormonia/app/schemas/v2/patient_overrides.py` — defines override request/response contracts including `source`, `skip`, and `editable`.
- `backend-hormonia/app/api/v2/routers/patients/flow_overrides.py` — implements merged GET, transactional PUT, future-day validation, and Redis invalidation.
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` — injects override-first lookup, cache reads, and skip handling into `_get_day_config`.
- `backend-hormonia/app/services/flow/_flow_message_flow.py` — reorders flow-state loading so on-demand message flow can pass `patient_flow_state_id` into `_get_day_config`.
- `backend-hormonia/app/services/flow/_flow_response_flow.py` — passes `patient_flow_state_id` into the response path’s `_get_day_config` call.
- `backend-hormonia/app/tasks/helpers/flow_helpers.py` — adds the batch-path override helper and skip/content-direct logic.
- `frontend-hormonia/src/features/patients/hooks/usePatientFlowOverrides.ts` — adds the typed React Query GET/PUT hook and TypeScript contracts.
- `frontend-hormonia/src/features/patients/components/PatientFlowOverrideEditor.tsx` — adds the physician-facing override editor dialog with badges, future-day gating, skip toggle, and add-day.
- `frontend-hormonia/src/pages/PatientDetailPage.tsx` — adds the `Personalizar Fluxo` entry point and dialog wiring.
- `verify-m012.sh` — adds the replayable 11-phase milestone verifier.
- `.gsd/milestones/M012/M012-VERIFY.json` — persists the verifier’s phase-level audit trail.
