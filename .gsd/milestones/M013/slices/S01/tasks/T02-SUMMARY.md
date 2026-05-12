---
id: T02
parent: S01
milestone: M013
key_files:
  - backend-hormonia/app/integrations/wuzapi/ssrf_guard.py
  - backend-hormonia/app/integrations/wuzapi/errors.py
  - backend-hormonia/app/integrations/wuzapi/__init__.py
  - backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py
key_decisions:
  - Use a generic `UnsafeMediaUrlError` message (`Blocked media URL`) so attacker-controlled URLs, query strings, tokens, cookies, PHI, and media paths are not emitted through exception text.
  - `validate_media_url` returns the original URL unchanged after validation and exposes an injectable async resolver(host, port) seam so tests and future media redirect handling avoid real network/DNS dependency.
  - Fail closed if any DNS answer is missing, malformed, blocked, or mixed with public answers; all block decisions use `ipaddress` classification plus explicit CGNAT and metadata ranges.
duration: 
verification_result: passed
completed_at: 2026-05-12T17:44:16.734Z
blocker_discovered: false
---

# T02: Added a reusable WuzAPI media URL SSRF guard with generic fail-closed errors and deterministic no-network tests.

**Added a reusable WuzAPI media URL SSRF guard with generic fail-closed errors and deterministic no-network tests.**

## What Happened

Created `app.integrations.wuzapi.ssrf_guard` with `validate_media_url`, an injectable async resolver seam, OS DNS resolver helper, and `ipaddress`-based classification for IP literals and DNS answers. The guard parses with `urlsplit`, allows only HTTP(S), rejects missing hosts, userinfo, invalid/zero ports, localhost-like names before DNS, DNS failures/empty/malformed answers, mixed public+blocked answers, and non-public or metadata IP ranges including private, loopback, link-local, multicast, unspecified, reserved, CGNAT, and IPv4-mapped blocked addresses. Added `UnsafeMediaUrlError` as a generic `WuzAPIError` subclass with message `Blocked media URL`, exported the error from the package, and added focused async tests that monkeypatch resolution through the resolver seam without real DNS/network access. Also repaired the auto-mode harness `python` resolution issue with an agent-local shim so the authoritative pytest commands run under Python 3.12.3 instead of failing with `python: Permission denied`.

## Verification

Verified the new guard test module independently with the authoritative T02 pytest command. Re-ran the current slice focused checks for WhatsApp auth, WuzAPI SSRF guard, and existing media behavior to confirm the previous auth verification command now resolves `python` and passes. Also syntax-checked touched Python files and confirmed no lines exceed the configured 120-character width.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py -q` | 0 | ✅ pass | 25237ms |
| 2 | `PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/integration/whatsapp/test_whatsapp_management_auth.py backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py backend-hormonia/tests/integrations/wuzapi/test_wuzapi_media.py -q` | 0 | ✅ pass | 25692ms |
| 3 | `python script: compile touched files and check >120-character lines` | 0 | ✅ pass | 68ms |

## Deviations

The repo implementation followed the T02 plan. An environment-only agent-local `python` shim was added outside the repository to resolve the pre-existing auto-mode shell PATH failure (`python: Permission denied`) and allow the specified verification commands to run unchanged.

## Known Issues

None. The planned follow-up T03 still owns wiring this reusable guard into `fetch_and_encode_media` and redirect handling.

## Files Created/Modified

- `backend-hormonia/app/integrations/wuzapi/ssrf_guard.py`
- `backend-hormonia/app/integrations/wuzapi/errors.py`
- `backend-hormonia/app/integrations/wuzapi/__init__.py`
- `backend-hormonia/tests/integrations/wuzapi/test_ssrf_guard.py`
