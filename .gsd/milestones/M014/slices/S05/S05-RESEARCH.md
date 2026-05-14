# S05 — Research

**Date:** 2026-05-14

## Summary

S05 is the final M014 closure slice for JWT/config posture, evidence-matrix mapping, and touched-regression proof. S01–S04 already produced controlled command evidence for ingress/replay/rate-limit, ADK ownership, browser PHI cache/quiz frontend, upload stored-XSS, private artifact serving, and generated report/export artifact serving. S05 should not widen into R014's production-like runtime harness; it should add any missing controlled posture proof, map every R012/R013/R018 item to evidence/not-applicable/deferred status, and produce a reviewer-facing matrix that is itself executable-document validated.

The highest-risk remaining claim is JWT revocation multi-worker semantics. The safe M014 framing is controlled proof of whatever the current app actually enforces: signed token validation, expiration/type handling, and revocation/session state that is persisted or otherwise not process-local-only. If production-like multi-worker runtime proof cannot be exercised locally without DB+queue/provider harness expansion, S05 must document the exact deferral owner and avoid overstating coverage.

## Recommendation

Build S05 in three increments: first add/repair focused JWT/config posture tests; second write the M014 evidence matrix plus a pytest document validator; third run an integrated M014 command suite and update requirement evidence/status via GSD tools. Keep all proof controlled, local, PHI-safe, and explicit about R014/M015 deferrals.

## Implementation Landscape

### Key Files

- `backend-hormonia/app/utils/security.py` — JWT creation/verification helpers and token-type/expiration behavior.
- `backend-hormonia/app/api/v2/routers/users.py` — Session listing/logout/revocation behavior with `SessionModel.is_active` and `revoked_at` filters.
- `backend-hormonia/app/config/settings/security.py` — Security secret/algorithm posture and production validation surface.
- `backend-hormonia/app/config/settings/database.py` — Database URL/TLS posture surface, if present; otherwise inspect the current database settings module.
- `backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py` — New focused S05 proof for JWT/session/config posture.
- `backend-hormonia/docs/reports/security/m014-hardening-proof-evidence-matrix.md` — New reviewer-facing M014 evidence matrix.
- `backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py` — New executable validation for matrix row coverage, command references, deferrals, and redaction constraints.
- `.gsd/milestones/M014/slices/S01/S01-SUMMARY.md` through `S04/S04-SUMMARY.md` — Source summaries for evidence IDs, command classes, limitations, and downstream contracts.
- `.gsd/REQUIREMENTS.md` — Active R012/R013 and out-of-scope R015/R017/R018 contracts that S05 must close or map.

### Build Order

1. Prove JWT/config posture first so the matrix does not document an unverified claim.
2. Write the evidence matrix and validation test after all evidence IDs/commands are known.
3. Run the integrated command suite last so S05 can cite fresh whole-milestone proof rather than stale per-slice runs.

### Verification Approach

- Focused S05 posture command: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py`.
- Matrix validation command: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py`.
- Integrated M014 command suite: combine the focused S01–S05 backend security files plus supporting frontend/quiz command references as documented in the matrix. Frontend/quiz commands should remain separate npm invocations when needed.

## Constraints

- Do not claim production-like DB+queue+WuzAPI/Gemini/runtime behavior; that remains R014/M015 unless explicitly re-scoped.
- Do not include PHI, tokens, cookies, signed state values, secrets, private filesystem paths, prompts, answers, provider payloads, or patient identifiers in logs/docs/test failure messages.
- Evidence-matrix rows must map every R012/R013/R018-relevant item as closed, not applicable with evidence, or deferred with owner/rationale; silent omission is a failure.

## Common Pitfalls

- **Overclaiming JWT multi-worker revocation** — prove persisted/session-state semantics if present; otherwise mark production multi-worker runtime proof deferred to R014/M015.
- **Treating deployment posture as runtime proof** — config checks can prove defaults/validation and documented requirements, not live deployment state.
- **Leaking free-form evidence text** — matrix should use requirement IDs, command names, test paths, coarse reasons, and gsd_exec IDs only.

## Open Risks

- Current JWT/session enforcement may not have a single shared dependency for all token consumers. Execution should inspect both HTTP and WebSocket token paths before claiming revocation coverage.
- DB TLS/RLS may be configuration/documentation posture rather than enforced local runtime behavior; S05 should preserve that distinction in the matrix.
