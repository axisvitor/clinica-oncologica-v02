---
estimated_steps: 3
estimated_files: 6
skills_used: []
---

# T01: Add JWT and deployment-posture proof

Why: S05 owns the remaining JWT/config posture risk and must prove controlled guarantees before the evidence matrix can claim closure.
Do: Inspect the current JWT/session/auth consumers and config settings. Add or repair `backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py` to prove signed JWT type/expiration behavior, revoked/inactive session semantics where enforced, weak/default production secret rejection, database TLS/RLS posture classification, and explicit R014/M015 deferral boundaries without using live services or secrets. If implementation gaps are found, fix the shared helper/config seam rather than adding endpoint-local suppressions.
Done when: The focused S05 posture test passes and its assertions avoid PHI, raw tokens, cookies, private paths, and secrets in failure text.

## Inputs

- `.gsd/milestones/M014/slices/S05/S05-RESEARCH.md`
- `.gsd/REQUIREMENTS.md`
- `backend-hormonia/app/utils/security.py`
- `backend-hormonia/app/api/v2/routers/users.py`

## Expected Output

- `backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py`

## Verification

PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py

## Observability Impact

Adds focused pass/fail proof for JWT/config posture and explicit failure messages that should point to missing revocation/config semantics without leaking sensitive values.
