---
id: S05
parent: M014
milestone: M014
provides:
  - M014 can proceed to milestone validation with S01-S05 complete and R012/R013 validated within the controlled-proof boundary.
  - Reviewers have one matrix that maps each R012/R013/R018 row to command evidence, not-applicable rationale, or explicit M015/R014 deferral.
  - M015/R014 has a clear runtime-proof backlog for live multi-worker JWT/session revocation, DB TLS/RLS, CDN/object storage, and production-like harness validation.
requires:
  - slice: S01
    provides: Ingress/replay/rate-limit evidence and S01 command IDs used in the matrix.
  - slice: S02
    provides: ADK auth/session ownership evidence used in the matrix.
  - slice: S03
    provides: Browser PHI cache and quiz frontend evidence used in the matrix.
  - slice: S04
    provides: Upload stored-XSS/private artifact/report-export evidence used in the matrix.
affects:
  - Milestone validation/completion
  - M015/R014 runtime validation scope
key_files:
  - backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py
  - backend-hormonia/app/config/settings/security.py
  - backend-hormonia/tests/config/test_production_config.py
  - backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md
  - backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py
  - .gsd/REQUIREMENTS.md
key_decisions:
  - R012/R013 are validated for M014's controlled-proof boundary; unsupported production-like runtime proof remains explicitly deferred to M015/R014.
  - Production default-secret validation must name the variable/remediation without echoing even a secret prefix.
patterns_established:
  - Evidence matrices must be mechanically validated for required rows, command references, explicit deferrals, and unsafe sentinel absence.
  - Controlled-proof closure can validate a requirement boundary while explicitly deferring production-like runtime proof without overclaiming.
observability_surfaces:
  - `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md` maps every closure/deferred row for reviewers.
  - `backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py` fails on missing rows, missing command references, missing deferrals, placeholders, or unsafe sentinel strings.
  - Fresh closeout commands provide health signals: backend integrated 149 tests, frontend 5 tests, quiz 8 tests.
drill_down_paths:
  - .gsd/milestones/M014/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M014/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M014/slices/S05/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-05-14T02:38:39.882Z
blocker_discovered: false
---

# S05: JWT/Config Posture, Evidence Matrix e Regression Closure

**Closed M014's JWT/config posture and evidence-matrix gap with controlled proof, validated requirements, and explicit runtime deferrals.**

## What Happened

S05 closed the final M014 evidence and posture lane. T01 added focused JWT/config posture proof for JWT signature/type/subject/expiration checks, staff session transport behavior, persisted active/unrevoked/unexpired session fallback filters, strong synthetic production posture, and production default-secret redaction. That proof exposed a shared config issue where the production default-secret error included a secret prefix; the validator now names the variable and remediation only. Existing production config tests were refreshed so mandatory WuzAPI/Gemini/PHI env validation no longer masks their intended assertions.

T02 created the reviewer-facing M014 hardening/proof evidence matrix and an executable pytest validator. The matrix maps 17 rows across CSRF, reset replay, webhook replay, duplicate oracle, X-Forwarded-For/rate-limit, ADK ownership, PHI client cache, quiz frontend storage, upload stored-XSS, report/export artifact serving, JWT validation, staff session transport, session revocation fallback, production secret posture, DB TLS/RLS posture, and R018 no-silent-drop coverage. It explicitly marks unsupported runtime proof as deferred to M015/R014.

T03 ran the integrated M014 closeout commands and updated the matrix with fresh results. R012 and R013 were updated to validated within M014's controlled-proof boundary; R018 notes now point at the matrix validator as the no-silent-drop proof.

## Verification

Fresh closeout verification passed in this turn: backend integrated M014 security suite exited 0 with 149 passed in 4.20s; frontend persistence command exited 0 with 5 passed; quiz storage command exited 0 with 8 passed; matrix validator after closeout edit exited 0 with 4 passed in 0.91s.

## Requirements Advanced

- R012 — Mapped and proved the remaining controlled hardening lanes, including JWT/config posture, while explicitly deferring live DB TLS/RLS runtime proof.
- R013 — Closed proof-gap tracking via a validated matrix that covers upload stored-XSS, ADK ownership, JWT/session posture, XFF/rate-limit, and quiz frontend lanes.
- R018 — Validated the no-silent-drop requirement through matrix row coverage and an executable validator.

## Requirements Validated

- R012 — M014 evidence matrix plus fresh T3 closeout: backend integrated suite passed with 149 tests, frontend persistence passed with 5 tests, quiz storage passed with 8 tests; unsupported DB TLS/RLS runtime proof remains explicitly deferred to R014/M015.
- R013 — M014 evidence matrix plus fresh T3 closeout maps every proof gap to command evidence or explicit M015/R014 deferral; backend, frontend, and quiz commands exited 0.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

None.

## Known Limitations

S05 does not prove live multi-worker JWT/session revocation, live database TLS negotiation, RLS policy execution, production CDN/object-storage behavior, live providers, real PHI, or a production-like DB+queue+WuzAPI/Gemini harness. These are deliberately deferred to M015/R014 and not overclaimed.

## Follow-ups

M015/R014 should own production-like runtime proof if needed: live JWT/session revocation across multiple workers, live DB TLS negotiation/RLS policy enforcement, production CDN/object-storage behavior, and DB+queue+WuzAPI/Gemini harness validation.

## Files Created/Modified

- `backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py` — Focused S05 JWT/session/config posture tests.
- `backend-hormonia/app/config/settings/security.py` — Removed production default-secret prefix disclosure from validation errors.
- `backend-hormonia/tests/config/test_production_config.py` — Updated production config regression fixtures to provide synthetic required production env values.
- `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md` — Reviewer-facing M014 matrix with closure rows, fresh T03 results, and explicit R014/M015 deferrals.
- `backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py` — Executable validator for matrix coverage and redaction constraints.
- `.gsd/REQUIREMENTS.md` — Requirement validation updates for R012/R013 and R018 notes.
