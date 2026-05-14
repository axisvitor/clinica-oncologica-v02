---
estimated_steps: 8
estimated_files: 5
skills_used: []
---

# T04: Write redaction-safe artifact evidence and summary

Why: The operational proof is only useful if durable evidence is safe for review and final S05 aggregation; S04 must reject artifacts that contain raw cookies, private paths, bytes, IDs, or PHI-shaped data.

Do:
1. Implement artifact evidence and summary writers using the M015 redaction helper.
2. Add artifact-specific denylist checks where the shared redaction helper is insufficient for private paths, raw `/uploads/private`-style URLs, raw `download_urls`, raw cookies/session IDs, Authorization/Cookie/Set-Cookie headers, and uploaded/report bytes.
3. Persist only command, correlation ID, route labels, status codes/classes, safe-header booleans, redirect/location booleans, byte-match booleans, redaction verdicts, hashed identifiers, failure classes, teardown state, and explicit non-goals.
4. Add tests that malicious evidence samples are rejected and valid S04 evidence is accepted.
5. Ensure the summary states S05 downstream non-goals and avoids CDN/object-storage/browser/live-provider claims.

Done when: artifact evidence JSON/summary generation is test-covered and redaction rejects unsafe sentinel values.

## Inputs

- ``scripts/security/m015-runtime/artifact_seam.py``
- ``scripts/security/m015-runtime/redaction.py``
- ``backend-hormonia/docs/reports/security/m015/db-seam-evidence.json``
- ``backend-hormonia/docs/reports/security/m015/session-seam-evidence.json``
- ``backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json``

## Expected Output

- ``scripts/security/m015-runtime/artifact_seam.py` — artifact evidence/summary writers.`
- ``scripts/security/m015-runtime/redaction.py` — artifact-specific redaction hardening if needed.`
- ``backend-hormonia/tests/security/test_m015_s04_artifact_runtime_contract.py` — evidence and denylist tests.`
- ``backend-hormonia/docs/reports/security/m015/artifact-seam-evidence.json` — runtime-generated durable evidence after T05.`
- ``backend-hormonia/docs/reports/security/m015/artifact-seam-summary.md` — runtime-generated human summary after T05.`

## Verification

cd backend-hormonia && PYTHONPATH=.:../scripts/security/m015-runtime pytest tests/security/test_m015_s04_artifact_runtime_contract.py tests/security/test_m015_runtime_harness.py -q

## Observability Impact

Produces the machine-readable and reviewer-readable artifact seam surfaces that S05 can consume; failures name redaction phase, rejected field class, and correlation ID without logging the rejected sensitive value.
