---
id: M014
title: "Hardening Médio e Proof Gaps"
status: complete
completed_at: 2026-05-14T02:42:15.003Z
key_decisions:
  - Validate R012/R013 within M014's controlled-proof boundary while explicitly deferring unsupported production-like runtime proof to M015/R014.
  - Do not echo production default-secret prefixes in validation errors; name only the variable and remediation.
key_files:
  - backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md
  - backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py
  - backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py
  - backend-hormonia/app/config/settings/security.py
  - backend-hormonia/tests/config/test_production_config.py
  - .gsd/REQUIREMENTS.md
  - .gsd/milestones/M014/M014-VALIDATION.md
lessons_learned:
  - A stale zero-byte `.git/index.lock` can crash GSD closeout after task/slice artifacts are already written; remove it only after confirming no active Git process.
  - S05-style evidence closure benefits from a validator test for matrix rows and unsafe sentinel strings, otherwise doc-only proof can drift.
  - Production config tests must include all mandatory synthetic production env values or they can mask the assertion under test with unrelated startup failures.
---

# M014: Hardening Médio e Proof Gaps

**M014 closed the controlled medium-hardening/proof-gap backlog with S01-S05 evidence, validated R012/R013, and explicit M015/R014 runtime deferrals.**

## What Happened

M014 transformed the medium-hardening/proof-gap backlog from M013 into controlled, reproducible proof and a validated evidence matrix. S01 closed ingress/replay/rate-limit gaps for CSRF, password reset replay, webhook replay/idempotency, duplicate oracle, and trusted-proxy rate limiting. S02 closed ADK route/runtime auth and ownership proof. S03 closed browser PHI cache and quiz frontend storage proof. S04 closed upload stored-XSS, private upload serving, and report/export artifact serving proof. S05 added JWT/config posture proof, removed production default-secret prefix disclosure, refreshed production config regression fixtures, created the M014 evidence matrix and validator, reran integrated backend/frontend/quiz proof, and updated R012/R013 validation.

The milestone intentionally preserves the boundary selected at planning: controlled local/CI proof only. Live multi-worker JWT/session revocation runtime proof, live DB TLS negotiation/RLS enforcement, production CDN/object-storage behavior, live providers, and a production-like DB+queue+WuzAPI/Gemini harness remain deferred to R014/M015 with explicit owner/rationale in the matrix.

## Success Criteria Results

- ✅ Every relevant R012/R013 item appears in the M014 matrix as closed, not applicable, or deferred with owner/rationale.
- ✅ Ingress controls deny CSRF/replay/idempotency/duplicate-oracle/rate-limit spoofing before side effects.
- ✅ ADK, browser cache/quiz, upload stored-XSS, JWT/config posture, and M013-touched regression lanes have controlled reproducible commands.
- ✅ Logs/errors/artifacts/docs remain PHI-safe; matrix validator and focused tests enforce this.
- ✅ M014 does not claim production-like runtime proof; R014/M015 deferrals are explicit.

## Definition of Done Results

- ✅ All slices S01-S05 are complete.
- ✅ Fresh integrated backend/frontend/quiz proof commands passed during S05/T03.
- ✅ M014 evidence matrix maps all R012/R013/R018-relevant rows and was validated mechanically.
- ✅ R012 and R013 were updated to validated within M014's controlled-proof boundary.
- ✅ R014/M015 runtime proof deferrals are explicit and not overclaimed.
- ✅ Validation verdict is pass in `.gsd/milestones/M014/M014-VALIDATION.md`.

## Requirement Outcomes

- R012 — validated by M014/S05 controlled proof and evidence matrix; live DB TLS/RLS runtime proof deferred to R014/M015.
- R013 — validated by M014/S05 evidence matrix and closeout commands; live multi-worker JWT/session runtime proof deferred to R014/M015.
- R014 — remains deferred to M015/R014.
- R015 — honored as an anti-feature; no production exploitation or real PHI.
- R017 — honored as an anti-feature; evidence and diagnostics avoid PHI/secrets/tokens/private paths.
- R018 — honored/validated through matrix row M014-17 and validator coverage.

## Deviations

S05 required manual execution because headless task dispatch repeatedly crash-recovered without activity artifacts after the original stale `.git/index.lock` commit failure. T01 also refreshed existing production config regression fixtures so mandatory WuzAPI/Gemini/PHI env validation no longer masked target assertions.

## Follow-ups

M015/R014 should own any production-like runtime validation that remains intentionally deferred: live JWT/session revocation across multiple workers, live DB TLS negotiation/RLS policy enforcement, CDN/object-storage behavior, and DB+queue+WuzAPI/Gemini harness proof.
