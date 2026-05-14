# S05: JWT/Config Posture, Evidence Matrix e Regression Closure — UAT

**Milestone:** M014
**Written:** 2026-05-14T02:38:39.888Z

# S05: JWT/Config Posture, Evidence Matrix e Regression Closure — UAT

**Milestone:** M014
**Written:** 2026-05-14

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: S05 ships controlled proof and a reviewer-facing evidence matrix, not a live UI/runtime feature. The acceptance surface is the document plus executable validators and command results.

## Preconditions

- Run from the repository root.
- Python and Node dependencies are installed as in the existing local/CI test environment.
- No production secrets, live providers, or real PHI are required.

## Smoke Test

Run the matrix validator:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py
```

Expected: exit 0 with 4 tests passed.

## Test Cases

### 1. Backend controlled M014 proof

1. Run the backend integrated command listed in the matrix closeout section.
2. Expected: exit 0 with 149 tests passed.

### 2. Dashboard persistence proof

1. Run `npm --prefix frontend-hormonia test -- tests/unit/react-query/persistencePolicy.test.ts`.
2. Expected: exit 0 with 1 file and 5 tests passed.

### 3. Quiz browser-storage proof

1. Run `npm --prefix quiz-mensal-interface test -- tests/security/quiz-progress-storage.test.tsx tests/security/no-phi-local-storage.test.tsx`.
2. Expected: exit 0 with 2 suites and 8 tests passed. Known non-fatal baseline-browser-mapping, punycode, and Jest worker teardown warnings may appear.

## Edge Cases

### Runtime proof not claimed

1. Read the deferred runtime and non-goal register in the matrix.
2. Expected: live multi-worker JWT/session revocation, live DB TLS/RLS enforcement, production CDN/object-storage behavior, live providers, and production-like harness validation are explicitly deferred to M015/R014.

## Failure Signals

- Matrix validator fails on missing rows, command references, deferral language, or unsafe sentinel strings.
- Any backend/frontend/quiz command exits non-zero.
- Matrix claims production-like runtime proof without a corresponding command.
- Evidence includes raw tokens, cookies, signed state values, secrets, provider payloads, private filesystem paths, or PHI.

## Requirements Proved By This UAT

- R012 — Controlled M014 hardening closure with explicit runtime deferrals.
- R013 — Proof-gap closure/mapping with command evidence and explicit owners for unsupported runtime proof.
- R018 — No independent medium finding is silently dropped.

## Not Proven By This UAT

- Production exploitation or real PHI behavior.
- Live DB+queue+WuzAPI/Gemini harness behavior.
- Live multi-worker JWT/session revocation.
- Live database TLS negotiation or RLS policy enforcement.
- Production CDN/object-storage artifact behavior.

## Notes for Tester

The matrix is the source of truth. Treat any runtime item marked M015/R014 as intentionally deferred, not as S05 proof.
