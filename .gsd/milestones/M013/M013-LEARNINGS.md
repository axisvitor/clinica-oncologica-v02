---
phase: complete-milestone
phase_name: "Remediação de Segurança Crítica/Alta"
project: "clinica-oncologica-v02-1"
generated: "2026-05-13T03:50:13Z"
counts:
  decisions: 5
  lessons: 5
  patterns: 6
  surprises: 4
missing_artifacts:
  - "Standalone slice *ASSESSMENT.md artifacts were not present; slice SUMMARY/UAT artifacts, DB completion, matrix proof, and reviewer/security/tester closeout evidence were used instead."
---

# M013 Learnings

### Decisions

- **Centralize authorization controls instead of patching endpoint-by-endpoint.** M013 chose canonical auth/role/patient ownership helpers and report access guards over local per-route fixes, reducing inconsistent IDOR/BOLA behavior across messages, flows, quiz, uploads, and reports.
  Source: DECISIONS.md/D002
- **Fail closed while keeping denial diagnostics PHI-safe.** Authentication, ownership, SSRF, private-file, quiz, and report boundaries deny unsafe states first and log only structured IDs/reasons/status rather than PHI, tokens, cookies, private paths, report data, or secrets.
  Source: DECISIONS.md/D003
- **Treat private uploads and generated reports as application resources, not static files.** The shipped storage model mounts only public assets at `/uploads`, stores private files under unmounted roots, and serves private bytes through authenticated owner/admin checks.
  Source: DECISIONS.md/D004
- **Make persisted/signed quiz state authoritative for public quiz actions.** Public quiz access and submit validate stored token hash, link state, patient/template/session binding, effective expiration, revocation, and signed HttpOnly session state; raw `quiz_session_id` is only a compatibility hint.
  Source: DECISIONS.md/D005
- **Use opaque report-id artifacts and allowlisted report diagnostics.** Generated report PDFs use report-id-only filenames and Taskiq diagnostics omit free-form `report_type`, preserving debugging through stable IDs/status while avoiding sanitized-PHI leakage.
  Source: DECISIONS.md/D014

### Lessons

- **Verification commands must preserve the backend working directory contract.** Several proofs only became reliable after running from `backend-hormonia` or adding explicit root-cwd wrappers, because backend pytest paths are backend-root relative.
  Source: S05-SUMMARY.md/Deviations
- **Task-level verification artifacts can become stale even when summaries and DB status are correct.** S03 had stale failed VERIFY.json records from earlier runner attempts; closeout repaired/audited them against passed summaries and current evidence.
  Source: S03-SUMMARY.md/What Happened
- **Sanitization is not redaction for clinical strings.** S06 showed that even sanitized free-form `report_type` can preserve patient-identifying content in artifact names/logs, so opaque IDs or strict allowlists are safer for PHI-adjacent metadata.
  Source: S06-SUMMARY.md/What Happened
- **Local schema drift can masquerade as a security regression.** The full S03 proof exposed legacy Postgres schema drift in quiz extension tests; a test-only transactional alignment fixture restored reproducible proof without weakening production checks.
  Source: S03-SUMMARY.md/Deviations
- **Validation gates need explicit artifact-shape rules.** The M013 validation verdict became `needs-attention` for documentation/process gaps despite no critical/high implementation blocker, so future milestones should state whether standalone ASSESSMENT artifacts and cross-slice consumption notes are hard gates.
  Source: M013-VALIDATION.md/Verdict Rationale

### Patterns

- **Two-doctor/two-patient negative fixture pattern.** Reuse paired authorized/foreign doctors and patients to prove cross-doctor denials while preserving assigned-doctor/admin positive behavior across patient-bound endpoints.
  Source: S02-SUMMARY.md/patterns_established
- **Auth-ordering sentries for side-effectful management routes.** Unauthorized requests should be tested with service/queue/DB sentries that prove 401/403 occurs before handler construction, outbound calls, queueing, or persistence.
  Source: S01-SUMMARY.md/patterns_established
- **Validate untrusted cache/raw metadata before normalization.** Report IDs, export IDs, and cached resources are authorized from raw owner/patient evidence before formatting, service calls, redirect generation, or URL disclosure.
  Source: S05-SUMMARY.md/patterns_established
- **Reviewer-facing security evidence matrix.** Map every finding to requirements, fixed controls, focused tests, integrated commands, PHI-safe notes, and explicit deferrals in one artifact so closeout can verify coverage without re-auditing all code.
  Source: S06-SUMMARY.md/patterns_established
- **Shared public quiz validator plus authoritative signed state.** Public quiz routes should share one persisted session/token validator and require signed state for compatibility endpoints, preventing raw cookie/session ID replay.
  Source: S03-SUMMARY.md/patterns_established
- **Public-only static mount plus gated private roots.** Keep `/uploads` limited to public files, store private artifacts under unmounted roots, resolve paths relative to the private root, and serve through application authorization.
  Source: S04-SUMMARY.md/patterns_established

### Surprises

- **The closeout validation was non-pass for non-functional attention items.** Reviewer findings flagged S01→S02 consumption wording, deferred medium/runtime requirements, and absent standalone ASSESSMENT files even though no critical/high requirement or implementation boundary was missing.
  Source: M013-VALIDATION.md/Verdict Rationale
- **The pytest-asyncio loop-scope warning appeared across many otherwise-passing suites.** It did not block M013 but repeatedly added noise to security proof output and should be cleaned up in maintenance.
  Source: S04-SUMMARY.md/Known Limitations
- **Full quiz proof surfaced local schema drift outside the intended security change.** The issue appeared only under the broader regression command, not in the narrow ownership/session tests.
  Source: S03-SUMMARY.md/Deviations
- **Root-level automation needed a wrapper for report-task tests.** S06 added `tests/tasks/test_reports_tasks.py` because the automation path invoked root-relative tests; the wrapper delegates to the canonical backend suite and marks async tests explicitly.
  Source: S06-SUMMARY.md/Deviations
