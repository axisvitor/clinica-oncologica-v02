# S01: WhatsApp Auth + SSRF Guard

**Goal:** Close the critical/high WhatsApp control-plane exposure by requiring an existing admin session for `/api/v2/whatsapp` management operations, and close the WuzAPI media SSRF seam by validating attacker-controlled media URLs before every outbound request and redirect. Demo: anonymous management calls fail before WhatsApp service/queue work starts; an admin can still reach a mocked send operation; unsafe media URLs and redirects are blocked without real network access.
**Demo:** Anonymous WhatsApp management calls are rejected, authorized mocked operations still work, and SSRF vectors against media fetch are blocked by tests.

## Must-Haves

- ## Threat Surface (Q3)
- **Abuse**: Anonymous callers can currently send/list WhatsApp messages, inspect contacts/queues/instances, and trigger outbound media fetches to internal infrastructure. SSRF inputs include schemes, userinfo, hostnames, IP literals, DNS answers and redirect `Location` headers.
- **Data exposure**: WhatsApp messages/contacts may contain PHI; WuzAPI media fetch can expose internal metadata or services if not blocked. Diagnostics must not include full media URLs, tokens, cookies, message bodies or PHI.
- **Input trust**: `/api/v2/whatsapp/*` request bodies/query params and WuzAPI media URLs are untrusted; DNS and redirect targets are untrusted until validated.
- ## Requirement Impact (Q4)
- **Requirements touched**: R001 and R002 are owned by this slice; R011 is supported by generic fail-closed diagnostics.
- **Re-verify**: WhatsApp management API auth contract, authorized admin mocked send path, WuzAPI media MIME/default/oversize behavior, and blocked SSRF corpus.
- **Decisions honored/revisited**: D002 shared auth helpers, D003 fail-closed PHI boundaries, D006 public health plus admin-only management, D007 reusable WuzAPI SSRF guard.
- ## Verification
- `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py -q`
- `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py -q`
- Final slice check: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py -q`
- ## Done When
- Anonymous requests to representative management endpoints (`/messages`, `/messages/stats`, `/messages/{instance}/statistics`, `/messages/{instance}/history/{chat}`, `/contacts/{instance}/sync`, `/contacts/{instance}`, `/queue/stats`, `/queue/process`, `/instances`) return 401/403 and spies prove WhatsApp service/queue construction is not invoked.
- `/api/v2/whatsapp/health` remains public and returns 200 because it exposes no PHI/control operation.
- A mocked admin session can call at least `POST /api/v2/whatsapp/messages` through the real router and receive the fake service response.
- URL guard tests reject malformed schemes, credentials/userinfo, missing hosts, invalid ports, localhost, private/loopback/link-local/multicast/unspecified/reserved/CGNAT addresses, mixed DNS answers with any blocked address, DNS validation failures, and metadata redirects.
- `fetch_and_encode_media` performs no `ClientSession.get` for blocked destinations, sends requests with `allow_redirects=False`, manually validates redirects, preserves successful data-URI behavior, and does not put full media URLs into oversize/blocked exception messages.

## Proof Level

- This slice proves: Contract + integration proof. Runtime required: no external service; FastAPI ASGI tests and async WuzAPI tests use dependency overrides, monkeypatched DNS resolution and mocked `aiohttp.ClientSession`. Human/UAT required: no.

## Integration Closure

Upstream surfaces consumed: canonical session/admin dependencies in `backend-hormonia/app/dependencies/auth_dependencies.py` and `backend-hormonia/app/dependencies/auth_role_dependencies.py`, existing WhatsApp router mounted by `backend-hormonia/app/api/v2/router.py`, WuzAPI media fetch used by `backend-hormonia/app/integrations/whatsapp/services/message_service.py` and `backend-hormonia/app/services/unified_whatsapp_service.py`. New wiring introduced: management-only WhatsApp sub-router with `Depends(get_current_active_admin)` and reusable `app.integrations.wuzapi.ssrf_guard` invoked by `fetch_and_encode_media`. Remaining milestone work: S02-S05 own patient/report/quiz/file ownership boundaries; S06 consolidates evidence.

## Verification

- Failure visibility improves through generic fail-closed auth/SSRF responses and sanitized exception/logging boundaries. SSRF diagnostics may identify only a sanitized hostname/IP classification or hash if logging is needed; they must not emit full media URLs, query strings, tokens, cookies, PHI or message content. Future agents inspect the focused pytest files and router/guard seams rather than production network calls.

## Tasks

- [x] **T01: Require admin sessions for WhatsApp management routes** `est:1h30m`
  Executor metadata:
  - estimated_steps: 8
  - estimated_files: 2
  - skills_used: api-design, security-review, tdd, verify-before-complete
  - Files: `backend-hormonia/app/integrations/whatsapp/api/routes.py`, `backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py -q

- [ ] **T02: Add reusable SSRF validation for WuzAPI media URLs** `est:1h45m`
  Executor metadata:
  - estimated_steps: 9
  - estimated_files: 4
  - skills_used: security-review, tdd, verify-before-complete
  - Files: `backend-hormonia/app/integrations/wuzapi/ssrf_guard.py`, `backend-hormonia/app/integrations/wuzapi/errors.py`, `backend-hormonia/app/integrations/wuzapi/__init__.py`, `backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py -q

- [ ] **T03: Wire SSRF guard into media fetch and redirect handling** `est:1h45m`
  Executor metadata:
  - estimated_steps: 10
  - estimated_files: 2
  - skills_used: security-review, tdd, verify-before-complete
  - Files: `backend-hormonia/app/integrations/wuzapi/media.py`, `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py`
  - Verify: PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py -q

## Files Likely Touched

- backend-hormonia/app/integrations/whatsapp/api/routes.py
- backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py
- backend-hormonia/app/integrations/wuzapi/ssrf_guard.py
- backend-hormonia/app/integrations/wuzapi/errors.py
- backend-hormonia/app/integrations/wuzapi/__init__.py
- backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py
- backend-hormonia/app/integrations/wuzapi/media.py
- backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py
