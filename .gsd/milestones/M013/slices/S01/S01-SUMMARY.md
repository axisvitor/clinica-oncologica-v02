---
id: S01
parent: M013
milestone: M013
provides:
  - Authenticated WhatsApp management boundary for downstream security slices and final evidence consolidation.
  - Reusable WuzAPI SSRF guard module and test corpus for initial URLs, DNS answers and redirects.
  - Verified no-network media-fetch seam with manual redirect handling and sanitized diagnostics.
requires:
  []
affects:
  - S02
  - S06
key_files:
  - backend-hormonia/app/integrations/whatsapp/api/routes.py
  - backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py
  - backend-hormonia/app/integrations/wuzapi/ssrf_guard.py
  - backend-hormonia/app/integrations/wuzapi/errors.py
  - backend-hormonia/app/integrations/wuzapi/__init__.py
  - backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py
  - backend-hormonia/app/integrations/wuzapi/media.py
  - backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py
key_decisions:
  - Use the existing canonical `get_current_active_admin` dependency for WhatsApp management rather than a new auth scheme.
  - Keep `/api/v2/whatsapp/health` public while moving management endpoints to an included admin-gated sub-router.
  - Use a generic `UnsafeMediaUrlError` message (`Blocked media URL`) so diagnostics do not expose full URLs, tokens, cookies, message bodies or PHI.
  - Expose an injectable resolver seam in `validate_media_url` for deterministic tests and redirect validation without real DNS/network dependencies.
  - Disable aiohttp automatic redirects and manually validate every redirect target before the next GET.
patterns_established:
  - Public health plus admin-only management router pattern for WhatsApp v2.
  - Auth-ordering tests with service/queue/DB sentries to prove unauthorized requests fail before side effects.
  - Reusable WuzAPI SSRF guard with fail-closed DNS/IP classification and sanitized errors.
  - Manual redirect loop using `allow_redirects=False`, `urljoin` for relative redirects, and validation before every outbound fetch.
observability_surfaces:
  - Public `/api/v2/whatsapp/health` remains available as a readiness signal.
  - Unauthorized management operations fail closed with 401/403 before control-plane side effects.
  - Unsafe media URLs fail closed with generic sanitized errors; oversize diagnostics omit attacker-controlled URL material.
  - No production metrics were added; S06 should capture observability gaps in the consolidated evidence matrix.
drill_down_paths:
  - .gsd/milestones/M013/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M013/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M013/slices/S01/tasks/T03-SUMMARY.md
  - .gsd/exec/af1fd56e-266a-44f6-91f3-f4b4fb948c14.stdout
  - .gsd/exec/5c8857c7-87d3-4d91-8853-b038a4d5c49f.stdout
  - .gsd/exec/75ac52dd-e00f-4c71-9f54-244766a9885b.stdout
duration: ""
verification_result: passed
completed_at: 2026-05-12T18:12:13.653Z
blocker_discovered: false
---

# S01: WhatsApp Auth + SSRF Guard

**Locked WhatsApp management operations behind the canonical admin session and added fail-closed SSRF validation for WuzAPI media fetches and redirects.**

## What Happened

S01 closed the critical WhatsApp control-plane and WuzAPI media SSRF seams. T01 split the WhatsApp v2 router into a public health surface and an admin-gated management sub-router using the existing `get_current_active_admin` dependency, with tests proving anonymous/non-admin callers are rejected before service, queue, or DB construction while an admin mocked send still succeeds. T02 introduced `app.integrations.wuzapi.ssrf_guard` plus `UnsafeMediaUrlError`, validating only HTTP(S) media URLs with an injectable resolver seam and fail-closed IP/DNS classification for localhost, private, loopback, link-local, multicast, unspecified, reserved, CGNAT and metadata destinations. T03 wired that guard into `fetch_and_encode_media`, disabled aiohttp auto-redirects, added bounded manual redirect validation for each `Location`, preserved existing MIME/default/oversize/data-URI behavior, and sanitized unsafe/oversize errors so attacker-controlled URLs, tokens, cookies, message bodies and PHI are not emitted.

## Verification

All slice-plan verification checks passed through `gsd_exec` using Python 3.12.3. Evidence: (1) `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py -q` target ran via closeout interpreter fallback in gsd_exec af1fd56e-266a-44f6-91f3-f4b4fb948c14, exit 0, `.... [100%]`. (2) `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py -q` target ran in gsd_exec 5c8857c7-87d3-4d91-8853-b038a4d5c49f, exit 0, `.................................................................... [100%]`. (3) Final slice check `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py -q` ran in gsd_exec 75ac52dd-e00f-4c71-9f54-244766a9885b, exit 0, `........................................................................ [100%]`. Only observed stderr was an unrelated pytest-asyncio deprecation warning about unset default fixture loop scope.

## Requirements Advanced

- R011 — Advanced fail-closed diagnostics for WhatsApp auth and WuzAPI SSRF with sanitized unsafe/oversize media errors; full cross-surface validation remains for S06.

## Requirements Validated

- R001 — WhatsApp management auth tests and final slice pytest evidence (gsd_exec af1fd56e-266a-44f6-91f3-f4b4fb948c14, 75ac52dd-e00f-4c71-9f54-244766a9885b) prove management routes reject anonymous/non-admin callers before service/queue/DB work while public health and admin mocked send still work.
- R002 — WuzAPI SSRF guard/media tests and final slice pytest evidence (gsd_exec 5c8857c7-87d3-4d91-8853-b038a4d5c49f, 75ac52dd-e00f-4c71-9f54-244766a9885b) prove blocked URL/DNS/IP classes, no pre-validation GET, manual redirect validation with `allow_redirects=False`, successful safe media behavior, and sanitized unsafe/oversize errors.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

No source-scope deviations. Closeout verification used a Python 3.12.3 interpreter fallback for the plan's pytest targets because earlier task evidence showed the environment's `python` command was unavailable or inconsistent.

## Known Limitations

No unresolved S01 blockers. Verification is intentionally mocked/no-network and does not prove live provider behavior; broader patient/report/quiz/file boundaries remain for S02-S05. Pytest emits an unrelated pytest-asyncio default loop-scope deprecation warning.

## Follow-ups

Proceed with S02-S05 for patient, quiz, upload/report and report ownership boundaries; S06 must consolidate F-01..F-11 evidence and list deferred medium/proof gaps. Consider setting pytest-asyncio's default fixture loop scope explicitly during broader test-maintenance work.

## Files Created/Modified

- `backend-hormonia/app/integrations/whatsapp/api/routes.py` — Split public health and admin-gated WhatsApp management routes using canonical admin dependency.
- `backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py` — Added integration tests for anonymous/non-admin rejection, auth-ordering sentries, public health, and admin mocked send.
- `backend-hormonia/app/integrations/wuzapi/ssrf_guard.py` — Added reusable fail-closed media URL SSRF validation with injectable resolver and IP/DNS classification.
- `backend-hormonia/app/integrations/wuzapi/errors.py` — Added generic sanitized `UnsafeMediaUrlError`.
- `backend-hormonia/app/integrations/wuzapi/__init__.py` — Exported WuzAPI error/guard surface.
- `backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py` — Added deterministic no-network SSRF guard corpus.
- `backend-hormonia/app/integrations/wuzapi/media.py` — Validated initial/redirect media URLs before GET, disabled auto-redirects, and sanitized oversize errors.
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py` — Expanded media tests for blocked initial URLs, redirect validation, `allow_redirects=False`, safe redirects, MIME/default/oversize behavior, and sanitized diagnostics.
