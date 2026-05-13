---
id: M013
title: "Remediação de Segurança Crítica/Alta"
status: complete
completed_at: 2026-05-13T03:52:32.495Z
key_decisions:
  - Prioritized critical/high findings F-01..F-11 in M013 while explicitly deferring medium/proof/runtime gaps to provisional M014/M015.
  - Used shared auth, role, patient ownership, and report access helpers instead of endpoint-local authorization patches.
  - Made fail-closed, PHI-safe diagnostics the common rule for auth, ownership, SSRF, private files, quiz, and reports.
  - Separated public `/uploads` from unmounted private upload/report roots and served private bytes through application authorization.
  - Made public quiz access/submit depend on persisted token/session/link invariants plus signed HttpOnly state rather than raw session IDs.
  - Used report-id-only generated artifact names and allowlisted Taskiq diagnostics to avoid free-form `report_type` leakage.
  - Consolidated final proof in a reviewer-facing F-01..F-11 evidence matrix with Fresh S06 command evidence and explicit deferrals.
key_files:
  - backend-hormonia/app/integrations/whatsapp/api/routes.py
  - backend-hormonia/app/integrations/wuzapi/ssrf_guard.py
  - backend-hormonia/app/integrations/wuzapi/media.py
  - backend-hormonia/app/api/v2/patients_shared_helpers.py
  - backend-hormonia/app/api/v2/routers/messages.py
  - backend-hormonia/app/api/v2/routers/patients/flow_responses.py
  - backend-hormonia/app/api/v2/routers/patients/flow_overrides.py
  - backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public_security.py
  - backend-hormonia/app/api/v2/routers/monthly_quiz_operations/public.py
  - backend-hormonia/app/api/v2/routers/monthly_quiz_operations/crud.py
  - backend-hormonia/app/api/v2/routers/upload/handlers.py
  - backend-hormonia/app/api/v2/routers/upload/storage.py
  - backend-hormonia/app/core/application_factory.py
  - backend-hormonia/app/services/reporting/report_access.py
  - backend-hormonia/app/api/v2/routers/reports.py
  - backend-hormonia/app/api/v2/routers/enhanced_reports.py
  - backend-hormonia/app/services/reporting/enhanced_reports_service.py
  - backend-hormonia/app/tasks/helpers/reports_helpers.py
  - backend-hormonia/app/tasks/reports_taskiq.py
  - backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md
  - .gsd/milestones/M013/M013-LEARNINGS.md
  - .gsd/PROJECT.md
lessons_learned:
  - Backend pytest commands must preserve the `backend-hormonia` working directory contract or use explicit root-cwd wrappers.
  - Task-level VERIFY.json can become stale after failed runner attempts; closeout should compare it against summaries, DB status, and current proof.
  - Sanitized free-form clinical strings are still unsafe for filenames/logs; use opaque IDs or reviewed allowlists for PHI-adjacent metadata.
  - Broad regression proofs can reveal local schema drift unrelated to the security fix; test-only alignment fixtures can restore proof without weakening production code.
  - Validation artifacts should distinguish implementation blockers from documentation/artifact-shape caveats so non-critical attention items do not obscure a completed security scope.
---

# M013: Remediação de Segurança Crítica/Alta

**M013 closed the critical/high security findings F-01..F-11 with admin-gated WhatsApp management, SSRF-guarded media fetches, patient/report/quiz ownership boundaries, private upload/report serving, PHI-safe diagnostics, and a reproducible Fresh S06 evidence matrix.**

## What Happened

M013 remediated the critical/high security package across six completed slices. S01 locked WhatsApp management behind the canonical admin session while keeping only health public, and introduced a reusable WuzAPI media SSRF guard that validates initial URLs, DNS/IP ranges, and every manual redirect before outbound fetch. S02 centralized admin-or-assigned-doctor patient ownership for messages, flow responses, and flow overrides, with reusable two-doctor/two-patient negative tests and PHI-free denial diagnostics. S03 applied that ownership model to authenticated quiz operations and made persisted/signed public quiz session state authoritative so raw or forged session IDs are never sufficient. S04 split public and private upload roots, moved generated report artifacts out of public static serving, and added gated owner/admin download behavior. S05 closed report ownership across base/enhanced report download, export, share, history, builder, restore, redirects, and cache-backed metadata. S06 tightened generated report artifact/log leakage, produced `backend-hormonia/docs/reports/security/m013-critical-high-evidence-matrix.md`, and ran the integrated Fresh S06 proof.

Closeout started with the duplicate-completion guard: `gsd_milestone_status(M013)` reported M013 active with all six slices complete and 24/24 tasks done. Because the existing validation artifact had verdict `needs-attention`, fresh closeout review was performed before learnings: reviewer/security/tester subagents found no unresolved critical/high blocker. Their remaining attention items were non-functional/documentation/scope issues: R012/R013/R014 are explicitly deferred, S01→S02 consumption wording is not a functional dependency, and standalone `*ASSESSMENT.md` artifacts were absent but summaries/UAT/DB/matrix evidence exist.

Verification evidence produced during closeout: `gsd_exec 049bd951-b415-4663-94bb-999b1c34044a` compared HEAD to recorded integration branch `origin/docs-refactor-py313` and found non-.gsd diff evidence; `gsd_exec f659a55a-5b20-46b9-81ee-973f9fcaaa70` found M013 milestone commit evidence touching backend/tests non-.gsd files; `gsd_exec f3623af4-11dd-426b-9045-38849d74b752` verified all slice SUMMARY/UAT artifacts, the F-01..F-11 matrix, R001..R014 references, Fresh S06/exit-0 markers, deferred R012-R014 markers, latest integrated proof metadata `4f988569-f9c7-401d-b418-60f3415d9008` exit 0, and no relevant app/test/security-report files newer than that proof; `gsd_exec 2fe3242b-8f39-4183-a81b-2b4249f9c4d5` verified the roadmap has six checked slice checkboxes, zero unchecked items, and no Horizontal Checklist section; `gsd_exec 93decccd-d426-496f-97fe-8dd9e83259c2` confirmed R001-R011 validated, R012-R014 deferred, and R015-R018 out-of-scope. The latest integrated proof reused by closeout is `gsd_exec 4f988569-f9c7-401d-b418-60f3415d9008`, which ran the selected critical/high backend pytest suite with exit 0 and one expected skip for rate limiting disabled in the test environment.

Decision Re-evaluation:

| Decision | Shipped outcome | Revisit? |
|---|---|---|
| D001 — Scope M013 to F-01..F-11 critical/high and defer medium/proof gaps | Shipped as planned: F-01..F-11 are mapped in the evidence matrix; R012/R013/R014 remain explicit deferrals; R015-R018 are non-goals. | No for M013; revisit only when planning M014/M015. |
| D002 — Use shared auth/role/patient ownership helpers | Shipped: `load_patient_with_access` and report access helpers were reused across messages, flows, quiz, and report surfaces. | No. |
| D003 — Fail closed with PHI-safe diagnostics | Shipped across auth, SSRF, ownership, quiz, upload/report and report-task diagnostics; matrix validates no unsafe sentinel leakage. | No; continue enforcing in future surfaces. |
| D004/D010/D011 — Private uploads/reports not served by public StaticFiles | Shipped: `/uploads` is public-only, private upload/report roots are unmounted, and gated download/private artifact tests pass. | Revisit only if a signed-URL storage backend replaces local serving. |
| D005/D009 — Public quiz requires persisted/signed session/link state | Shipped: token hash, link/session status, binding, expiration, revocation, and signed HttpOnly state are authoritative; raw session IDs fail closed. | No. |
| D006/D007 — WhatsApp admin boundary and WuzAPI SSRF guard | Shipped with auth-ordering tests, deterministic resolver seam, and manual redirect validation before GET. | No. |
| D008 — Cross-doctor patient denial semantics use 403 for known foreign resources | Shipped in helper and boundary tests without PHI in denials. | No. |
| D012 — Authorize cache-backed report resources from raw metadata before normalization | Shipped across report downloads/exports/share/history/builder/restore and redirects. | No. |
| D013/D014 — Report artifacts and diagnostics must not expose free-form report_type | Shipped with report-id-only filenames and allowlisted Taskiq diagnostic fields. | No; revisit only for a strict non-PHI report-type taxonomy. |

## Success Criteria Results

- **WhatsApp management auth:** Met. S01 tests prove anonymous/non-admin requests fail before service/queue/DB side effects while admin mocked send works; S06 re-evidences F-01/R001 with Fresh S06 exit 0.
- **Doctor/patient ownership isolation:** Met. S02 covers messages, flow responses, and flow overrides; S03 covers quiz ownership; S04 covers foreign private upload denial; S05 covers report ownership; S06 integrated proof exits 0.
- **SSRF/media guard:** Met. S01 blocks unsafe schemes, loopback/private/link-local/metadata ranges, DNS failures, and unsafe redirects before outbound fetch while allowed HTTP(S) media remains functional.
- **Private uploads/reports not publicly served:** Met. S04 makes `/uploads` public-only, serves private uploads via gated download, and stores generated PDFs privately; S06 closes opaque private report artifact naming/log leakage.
- **Public quiz submit cannot rely on forged/stolen raw `quiz_session_id`:** Met. S03 requires signed/persisted session/link state and rejects raw-only, forged, expired, revoked/cancelled/used, and mismatched patient/template/session/token states.
- **Focused tests and F-01..F-11 evidence matrix:** Met. S06 created the matrix and ran focused report-task proof, matrix validation, integrated pytest proof, and planning-path audit; closeout `gsd_exec f3623af4-11dd-426b-9045-38849d74b752` reconfirmed matrix completeness/freshness.
- **Validation attention resolved:** The previous `needs-attention` verdict reflected deferred medium/runtime scope and artifact/documentation caveats, not missing critical/high implementation evidence. Fresh reviewer/security/tester closeout found no blocking critical/high issue.

## Definition of Done Results

- **All slices checked complete:** Met. `gsd_milestone_status(M013)` reported S01-S06 complete with 24/24 tasks done; roadmap checkbox verification found 6 checked and 0 unchecked slice items.
- **Slice summaries and UAT artifacts exist:** Met. `gsd_exec f3623af4-11dd-426b-9045-38849d74b752` verified non-empty `S01` through `S06` SUMMARY and UAT files.
- **Integrations work together:** Met. S06 integrated proof `4f988569-f9c7-401d-b418-60f3415d9008` exited 0 across WhatsApp auth, WuzAPI SSRF/media, patient/message/flow ownership, quiz, uploads/reports, report ownership, report tasks, enhanced reports, and compatibility suites.
- **Horizontal Checklist:** No Horizontal Checklist section exists in `M013-ROADMAP.md`; closeout verification confirmed none to action.
- **Code changes exist:** Met. Closeout diff/commit evidence found non-.gsd implementation/test/doc files for M013, including backend auth, ownership, quiz, upload/report, SSRF, report task, and evidence matrix files.
- **Learnings and project state refreshed before closeout:** Met. `.gsd/PROJECT.md` and `.gsd/milestones/M013/M013-LEARNINGS.md` were updated, and durable patterns/lessons were captured in memory with duplicate-aware skips.

## Requirement Outcomes

- **R001-R011:** Validated. Evidence comes from S01-S06 slice summaries/UAT, Fresh S06 integrated proof, and the F-01..F-11 matrix. R001/R002 cover WhatsApp auth and SSRF; R003/R009 cover message/flow ownership; R004/R005 cover quiz ownership/session integrity; R006/R007 cover private upload/report storage; R008 covers report ownership; R010 covers reusable negative isolation proof; R011 covers fail-closed PHI-safe diagnostics.
- **R012-R014:** Deferred. Medium hardening, remaining proof gaps, and production-like runtime harness work are explicitly carried forward and do not block M013's critical/high scope.
- **R015-R018:** Out of scope/non-goals. M013 used fixture/mock/backend contract/integration proof only, avoided production exploitation/real patient data, did not rewrite dashboard/frontend beyond minimal security effects, did not treat git-ignored local files as committed secrets, and did not broaden scope to all medium findings.
- **Status updates during closeout:** No requirement update tool calls were needed because `.gsd/REQUIREMENTS.md` already records the validated/deferred/out-of-scope statuses verified by `gsd_exec 93decccd-d426-496f-97fe-8dd9e83259c2`.

## Deviations

- Existing validation artifact remained `needs-attention` because of documentation/process caveats, not because of unresolved critical/high security failures. Fresh closeout reviewer/security/tester checks resolved this as non-blocking for M013 completion.
- Several proof commands needed explicit `cd backend-hormonia` or root-cwd wrappers because backend test paths are backend-root relative.
- S03 needed a test-only transactional schema alignment fixture for legacy local Postgres schema drift.
- S04 added `Upload.deleted_at` mapping/migration beyond the initial file list to support DB-backed deleted-record authorization semantics.
- Standalone slice `*ASSESSMENT.md` artifacts were absent; slice SUMMARY/UAT artifacts, DB completion, matrix evidence, and fresh closeout checks were used as the available assessment evidence.

## Follow-ups

- Carry R012 medium hardening into M014 planning if still desired: ADK auth, RLS, DB TLS, reset replay, CSRF, webhook replay, PHI client cache, deployment secrets, and duplicate-oracle work.
- Carry R013 proof gaps into M014/M015 planning: upload stored-XSS, ADK session ownership, JWT revocation multi-worker behavior, X-Forwarded-For/rate-limit behavior, and incomplete quiz frontend lane coverage.
- Carry R014 runtime validation into M015 if safe production-like fixtures/providers are available: DB, queue, WuzAPI/Gemini, realistic fixtures, and broader dynamic exploitation validation.
- Clean up recurring pytest-asyncio `asyncio_default_fixture_loop_scope` warnings during maintenance.
- Decide before future milestones whether standalone `*ASSESSMENT.md` artifacts are mandatory closeout gates.
