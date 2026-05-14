---
estimated_steps: 10
estimated_files: 2
skills_used: []
---

# T02: Build private upload app-route runtime probe

Why: The private upload boundary is the clearest app-route artifact seam; S04 must prove it through the running app with real cookie sessions and without exposing the private storage root through `/uploads`.

Do:
1. Implement `artifact_seam.py` fixture/bootstrap helpers for owner doctor, foreign doctor, admin, and owner patient using the M015 runtime database/session pattern from S02.
2. Create private and public synthetic upload cases through real FastAPI HTTP routes where possible; do not seed through dependency overrides or in-process clients.
3. Prove private upload status/URLs use the gated API route rather than `/uploads`.
4. Prove owner/admin private downloads return bytes with `attachment`, `nosniff`, and `no-store` headers.
5. Prove anonymous and foreign-user private download attempts fail closed without private bytes, paths, or redirect/location leakage.
6. Prove direct `/uploads/<private-relative-path>` does not expose private bytes while intentionally public uploads remain accessible through the public static mount.
7. Cover traversal/unsafe private metadata as generic denial if runtime setup can create such a synthetic row safely.

Done when: upload runtime probe code and static/runtime contract tests prove the private/public split and owner/admin/anonymous/cross-owner outcomes.

## Inputs

- ``scripts/security/m015-runtime/m015_session_security_taskiq.py``
- ``scripts/security/m015-runtime/session_seam.py``
- ``scripts/security/m015-runtime/redaction.py``
- ``backend-hormonia/app/api/v2/routers/upload/config.py``
- ``backend-hormonia/app/api/v2/routers/upload/handlers.py``
- ``backend-hormonia/app/utils/download_responses.py``
- ``backend-hormonia/tests/api/v2/test_private_upload_serving.py``
- ``backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py``

## Expected Output

- ``scripts/security/m015-runtime/artifact_seam.py` — upload runtime probe helpers and result builders.`
- ``backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py` — upload probe and evidence-shape contracts.`

## Verification

python3 -m py_compile scripts/security/m015-runtime/artifact_seam.py && cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_s04_artifact_runtime_contract.py tests/api/v2/test_private_upload_serving.py tests/security/test_m014_s04_private_artifact_serving.py -q

## Observability Impact

Records upload route labels, status classes, safe-header booleans, direct-static denial booleans, redirect/location absence, byte-match booleans, and redaction-safe hashed identifiers only.
