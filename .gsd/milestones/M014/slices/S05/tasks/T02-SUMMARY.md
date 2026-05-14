---
id: T02
parent: S05
milestone: M014
key_files:
  - backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md
  - backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py
key_decisions:
  - Use a validated reviewer-facing matrix with explicit M015/R014 deferrals rather than claiming unsupported production-like runtime proof for JWT multi-worker, DB TLS/RLS, CDN/object storage, or live provider behavior.
duration: 
verification_result: passed
completed_at: 2026-05-14T02:27:39.349Z
blocker_discovered: false
---

# T02: Created the M014 evidence matrix and executable validator.

**Created the M014 evidence matrix and executable validator.**

## What Happened

Created the M014 hardening/proof evidence matrix using the M013 matrix pattern and S01-S05 summaries. The matrix maps 17 R012/R013/R018-relevant rows across CSRF, reset replay, webhook replay, duplicate oracle, XFF/rate-limit, ADK ownership, PHI cache, quiz frontend, upload stored-XSS, report/export artifacts, JWT validation, staff session transport, persisted session revocation fallback, production secret posture, DB TLS/RLS posture, and no-silent-drop coverage. Added a focused pytest validator that checks required rows, requirements, command references, evidence IDs, explicit M015/R014 deferrals, npm/frontend command references, and unsafe placeholder/sensitive sentinel absence.

## Verification

Fresh T02 verification passed: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py` exited 0 with 4 passed in 1.16s.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py` | 0 | ✅ pass — 4 passed in 1.16s | 25600ms |

## Deviations

Executed manually because repeated headless task dispatches for S05 crash-recovered without writing activity artifacts.

## Known Issues

The matrix still marks live multi-worker/session revocation runtime proof, live DB TLS/RLS enforcement, production CDN/object-storage behavior, and production-like DB+queue+WuzAPI/Gemini harness as deferred to M015/R014.

## Files Created/Modified

- `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md`
- `backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py`
