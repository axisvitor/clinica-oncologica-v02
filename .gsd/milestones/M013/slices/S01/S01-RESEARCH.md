# S01 Research — WhatsApp Auth + SSRF Guard

## Summary

Depth: targeted/deep security research. This slice owns R001 (WhatsApp management auth), R002 (SSRF prevention for WuzAPI media fetch), and R011 (fail-closed diagnostics without PHI/secrets).

Key finding: the WhatsApp management router is mounted under `/api/v2/whatsapp` with no route-level or handler-level auth, and the media fetch seam downloads attacker-controlled URLs with bare `aiohttp.ClientSession().get(...)`. The fix should be two narrow seams: an admin/session dependency on management routes before service construction, and a reusable SSRF guard in the WuzAPI media module before any outbound request or redirect follow.

## Prior Decisions / Memory

- M013 architecture memory: use shared auth/role/ownership helpers instead of endpoint-only patches.
- PHI boundary memory: fail closed; diagnostics must not log PHI, tokens, cookies, secrets, or full sensitive URLs.
- Applicable installed skills: `api-design`, `security-review`, `observability`, `test`, `verify-before-complete`.
- Skill discovery for FastAPI/security found promising optional installs, not installed: `npx skills add aj-geddes/useful-ai-prompts@api-security-hardening` (559 installs), `npx skills add aj-geddes/useful-ai-prompts@fastapi-development` (439), `npx skills add sickn33/antigravity-awesome-skills@python-fastapi-development` (338).

## Implementation Landscape

### WhatsApp management auth

- `backend-hormonia/app/api/v2/router.py:109` includes `whatsapp_router` without extra dependencies; the WhatsApp router already has prefix `/whatsapp`.
- `backend-hormonia/app/integrations/whatsapp/api/routes.py:27` defines `router = APIRouter(prefix="/whatsapp", tags=["WhatsApp"])` with no auth dependency.
- Management endpoints in `routes.py` currently have no principal dependency:
  - send/list/stats/history: `routes.py:109`, `:125`, `:147`, `:156`, `:179`
  - contacts: `routes.py:205`, `:222`
  - queue: `routes.py:273`, `:290`
  - health: `routes.py:309`
  - instances: `routes.py:320`
- `get_message_service()` at `routes.py:91-106` constructs `MessageQueue` and WuzAPI client dependencies. Auth must raise before this dependency is invoked for anonymous callers; otherwise F-01 still triggers side effects.
- Canonical auth seams already exist:
  - `backend-hormonia/app/dependencies/auth_dependencies.py:457` `get_current_user_from_session`
  - `auth_dependencies.py:600` `get_current_active_admin` for mapping-style admin session payloads
  - `backend-hormonia/app/dependencies/auth_role_dependencies.py:56` `require_admin_session_user`
  - `auth_dependencies.py:595` `get_admin_user` if a `User` model is needed
- Similar admin-only routers use `get_current_active_admin` or `get_admin_user` (e.g. webhooks/debug/monitoring), so prefer those over inventing a new auth scheme.
- There is no clear existing service-principal dependency. If service-principal support is mandatory later, it should be a deliberate new dependency; for S01 admin-only management is the least risky first closure.

### WuzAPI media SSRF

- `backend-hormonia/app/integrations/wuzapi/media.py:13-31` implements `fetch_and_encode_media(url)` and calls `aiohttp.ClientSession().get(url, timeout=...)` directly at `:15`; default aiohttp behavior follows redirects unless disabled.
- Size limiting exists (`MAX_MEDIA_BYTES = 16 MB`) and tests cover MIME/default/oversize behavior in `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py`.
- Existing tests monkeypatch `app.integrations.wuzapi.media.aiohttp.ClientSession`; adding `allow_redirects=False` or redirect loops will require updating the mock session signature.

## Recommendation

1. Protect WhatsApp management endpoints with the existing session admin dependency. Prefer either:
   - split routers: keep `/whatsapp/health` public if required, and put all management routes under an `APIRouter(..., dependencies=[Depends(get_current_active_admin)])`; or
   - attach `dependencies=[Depends(get_current_active_admin)]` to each management decorator except explicit public health.

   This satisfies “reject before service execution” better than adding an unused function parameter after `message_service` dependencies. Tests should patch/spy `get_message_service` to prove anonymous requests do not instantiate it.

2. Add `app/integrations/wuzapi/ssrf_guard.py` or equivalent with async URL validation:
   - parse with `urllib.parse.urlsplit`; only allow `http` and `https`.
   - require hostname; reject credentials/userinfo, empty host, invalid port.
   - resolve host via a seam (e.g. async `resolve_host(host, port)`) so tests can monkeypatch DNS.
   - reject loopback, private, link-local, multicast, unspecified, reserved, carrier-grade, IPv6 ULA/link-local, and explicit metadata targets (`169.254.169.254`, `[fd00::]/8`, etc.) using `ipaddress`, not regex-only matching.
   - reject if any resolved address is blocked; ambiguity fails closed.
   - set bounded timeout and `allow_redirects=False`; manually follow up to a small limit (e.g. 3), validating every `Location` target with `urljoin` before the next request.

3. Keep error messages generic (`Blocked media URL`) and log only hostname hash/classification or sanitized host prefix; do not log full media URL.

## Natural Seams / Work Units

1. **Auth wiring:** `backend-hormonia/app/integrations/whatsapp/api/routes.py`; maybe router split to preserve health. Tests for anonymous 401/403 and admin success.
2. **SSRF guard module:** new/updated code under `backend-hormonia/app/integrations/wuzapi/`; unit tests for URL parsing, DNS resolution, IP classification, redirect validation.
3. **Media integration:** update `fetch_and_encode_media()` to call the guard, disable automatic redirects, preserve size/MIME behavior.
4. **Test helpers:** extend `tests/integrations/wuzapi/test_wuzapi_media.py`; add focused WhatsApp API tests under `tests/integrations/whatsapp/` or `tests/api/v2/`.

## First Proof

Write failing tests first:

- `test_whatsapp_management_rejects_anonymous_before_service_execution`: call representative routes (`POST /api/v2/whatsapp/messages`, `GET /api/v2/whatsapp/messages`, `GET /api/v2/whatsapp/contacts/{instance}`, `GET /api/v2/whatsapp/queue/stats`, `GET /api/v2/whatsapp/instances`) without auth; assert 401/403 and `get_message_service`/WuzAPI factory spy not called.
- `test_whatsapp_management_allows_admin_with_mocked_service`: override `get_current_user_from_session` as admin and `get_message_service` with a fake service; assert handler behavior still reachable.
- `test_fetch_and_encode_media_blocks_private_resolution_before_get`: monkeypatch resolver for `attacker.test -> 127.0.0.1` and assert `ClientSession.get` is never called.
- `test_fetch_and_encode_media_blocks_redirect_to_metadata`: allowed first host returns 302 to `http://169.254.169.254/latest/meta-data`; assert blocked before second outbound request.

## Verification Commands

- `cd backend-hormonia && pytest tests/integrations/wuzapi/test_wuzapi_media.py -q`
- `cd backend-hormonia && pytest tests/integration/whatsapp/test_whatsapp_management_auth.py -q` (new focused file)
- If using existing broader suites: `cd backend-hormonia && pytest tests/integrations/whatsapp tests/integrations/wuzapi -q`

## Forward Intelligence / Watch-outs

- FastAPI dependency order matters for “before service execution”. Route-level dependencies or router-level dependencies are safer than appending `current_user=Depends(...)` after `message_service` parameters.
- `sync_contacts` currently returns 501 without service dependencies; still must reject anonymous if treated as management.
- Decide whether `/api/v2/whatsapp/health` remains public. If public, document it and test it separately; do not accidentally leave queue/instances public.
- `MediaTooLargeError` currently includes `url!r` in its message. Consider removing full URL from exceptions/logs as part of R011.
- SSRF tests should not perform real network/DNS. Keep resolver and session as injectable seams.

## Sources

- `backend-hormonia/app/api/v2/router.py`
- `backend-hormonia/app/integrations/whatsapp/api/routes.py`
- `backend-hormonia/app/integrations/wuzapi/media.py`
- `backend-hormonia/app/dependencies/auth_dependencies.py`
- `backend-hormonia/app/dependencies/auth_role_dependencies.py`
- `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py`
