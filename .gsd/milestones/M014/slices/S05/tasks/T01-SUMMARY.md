---
id: T01
parent: S05
milestone: M014
key_files:
  - backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py
  - backend-hormonia/app/config/settings/security.py
  - backend-hormonia/tests/config/test_production_config.py
key_decisions:
  - Production default-secret validation must not echo even a prefix of the configured/default secret; errors now name the variable and remediation only.
duration: 
verification_result: passed
completed_at: 2026-05-14T02:15:36.224Z
blocker_discovered: false
---

# T01: Added S05 JWT/config posture proof and removed production default-secret prefix disclosure.

**Added S05 JWT/config posture proof and removed production default-secret prefix disclosure.**

## What Happened

Added focused S05 posture proof for JWT token type/expiration/signature/subject validation, staff auth transport behavior, DB fallback session filters for active/unrevoked/unexpired sessions, and isolated production posture validation with synthetic env values. The focused test exposed that production default-secret rejection included the secret prefix in the error text; the shared security settings validator now removes that prefix disclosure. The existing production config regression tests were updated with synthetic required WuzAPI/Gemini/PHI env values so they test their target failures instead of being masked by unrelated startup requirements.

## Verification

Fresh verification passed after the final edits: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py backend-hormonia/tests/config/test_production_config.py` exited 0 with 8 passed in 1.16s.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py backend-hormonia/tests/config/test_production_config.py` | 0 | ✅ pass — 8 passed in 1.16s | 21700ms |

## Deviations

T01 also updated `backend-hormonia/tests/config/test_production_config.py` because the existing production-config regression fixtures were stale against mandatory WuzAPI/Gemini/PHI production env validation and masked their intended assertions.

## Known Issues

The pytest-asyncio loop-scope deprecation warning remains existing/non-fatal.

## Files Created/Modified

- `backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py`
- `backend-hormonia/app/config/settings/security.py`
- `backend-hormonia/tests/config/test_production_config.py`
