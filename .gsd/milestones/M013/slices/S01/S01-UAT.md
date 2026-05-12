# S01: WhatsApp Auth + SSRF Guard — UAT

**Milestone:** M013
**Written:** 2026-05-12T18:12:13.662Z

## UAT Type
Automated security contract/integration UAT using FastAPI ASGI tests and mocked WuzAPI/aiohttp/DNS seams. No external WhatsApp or WuzAPI service is required.

## Preconditions
- Backend test dependencies are installed and commands are run from the repository root with `PYTHONPATH=backend-hormonia`.
- Tests use the real WhatsApp router, dependency overrides for session/user role behavior, CSRF test tokens for unsafe requests, monkeypatched WuzAPI DNS resolution, and mocked `aiohttp.ClientSession` responses.
- No production credentials, PHI, live WhatsApp account, or external network access is needed.

## Steps
1. Run the WhatsApp management auth target: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py -q`.
2. Confirm `/api/v2/whatsapp/health` remains public and returns success.
3. Confirm representative management routes such as messages, stats/history, contacts sync/list, queue stats/process, and instances reject anonymous or non-admin callers with 401/403 before message service, queue, or DB sentries run.
4. Confirm an admin-authenticated mocked `POST /api/v2/whatsapp/messages` reaches the router and returns the fake service response.
5. Run the WuzAPI SSRF/media targets: `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py -q`.
6. Confirm URL validation rejects malformed schemes, credentials/userinfo, missing hosts, invalid or zero ports, localhost-like names, DNS failures, mixed DNS answers, private/loopback/link-local/multicast/unspecified/reserved/CGNAT IPs, and cloud metadata targets.
7. Confirm blocked initial media URLs perform no `ClientSession.get`, all allowed GETs set `allow_redirects=False`, metadata/private redirects are blocked before the next GET, safe relative redirects still produce a data URI, and unsafe/oversize exception text omits full URLs/query strings/tokens/PHI.
8. Run the final combined slice check covering all three test files.

## Expected Outcomes
- Anonymous and non-admin WhatsApp management calls are rejected before control-plane or PHI-bearing work starts.
- Public health remains available for readiness checks.
- Admin-authenticated mocked management send remains functional.
- WuzAPI media fetching validates every initial and redirect destination before outbound fetch, blocks SSRF classes fail-closed, preserves legitimate data-URI behavior, and keeps diagnostics generic/sanitized.
- All commands exit 0.

## Edge Cases Covered
- Unsupported schemes, missing host, malformed/invalid port, embedded credentials/userinfo, localhost-style names.
- Private, loopback, link-local, multicast, unspecified, reserved, CGNAT and cloud metadata IPs, including DNS answer validation and mixed public+blocked answers.
- DNS validation failure/empty/malformed answers.
- Redirect targets including metadata/private destinations and safe relative redirects.
- Oversize media errors and unsafe URL errors without leaking attacker-controlled URLs.
- CSRF setup for POST tests so route auth ordering, not middleware short-circuiting, is exercised.

## Operational Readiness (Q8)
- Health signal: `/api/v2/whatsapp/health` remains public and returns 200 in tests.
- Failure signal: unauthorized management returns 401/403; unsafe WuzAPI media URLs raise a generic fail-closed `UnsafeMediaUrlError`/`Blocked media URL` without PHI, full URLs, tokens or cookies.
- Recovery procedure: inspect `backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py`, `backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py`, and `backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py`; re-run the final combined pytest target with `PYTHONPATH=backend-hormonia`.
- Monitoring gaps: no new production metrics or alerting were added in S01; S06 should consolidate evidence and list remaining medium/proof-gap observability follow-ups.

## Not Proven By This UAT
- Live WhatsApp provider behavior, live WuzAPI media servers, or production DNS/network egress policy enforcement.
- Patient ownership, quiz/session, private upload/report, and report ownership boundaries owned by S02-S05.
- Full milestone-level evidence matrix, owned by S06.
