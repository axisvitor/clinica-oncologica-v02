---
id: T02
parent: S03
milestone: M015
key_files:
  - backend-hormonia/app/config/settings/integrations.py
  - backend-hormonia/app/ai/client.py
  - backend-hormonia/tests/unit/test_gemini_client_stub_config.py
key_decisions:
  - Use optional `AI_GEMINI_BASE_URL` as the controlled non-production/runtime-validation seam while leaving SDK default routing unchanged when unset.
  - Log only a boolean `custom_base_url_configured` decision signal during Gemini initialization, not API keys or base URLs.
duration: 
verification_result: mixed
completed_at: 2026-05-14T12:53:44.075Z
blocker_discovered: false
---

# T02: Added a test-covered optional Gemini base-URL seam so S03 can route app Gemini calls to the local provider stub without changing default live-provider behavior.

**Added a test-covered optional Gemini base-URL seam so S03 can route app Gemini calls to the local provider stub without changing default live-provider behavior.**

## What Happened

Added `AI_GEMINI_BASE_URL` as an optional integrations setting for synthetic/runtime validation and controlled non-production routing. Updated `GeminiClient._initialize_model()` to pass `types.HttpOptions(base_url=...)` into `genai.Client` only when the setting is configured, preserving default SDK routing when unset and keeping existing model/config generation behavior. The initialization log now records only whether a custom base URL is configured, avoiding API key or endpoint leakage. Added `test_gemini_client_stub_config.py` to prove configured base URLs are passed through to `google-genai`, default behavior omits `http_options`, settings-provided API keys still work, and log extras do not include the API key or stub host. Existing Gemini PII redaction tests were rerun alongside the new config seam tests.

## Verification

Fresh verification after the last code change: `cd backend-hormonia && PYTHONPATH=. pytest tests/unit/test_gemini_client_stub_config.py tests/unit/test_gemini_client_pii_redaction.py -q` completed successfully with all 8 scoped tests reaching `[100%]`. LSP diagnostics were attempted for edited Python files but no Python language server is available in this environment.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `cd backend-hormonia && PYTHONPATH=. pytest tests/unit/test_gemini_client_stub_config.py tests/unit/test_gemini_client_pii_redaction.py -q` | 0 | ✅ pass — 8 scoped tests reached 100% | 22100ms |
| 2 | `lsp diagnostics backend-hormonia/app/ai/client.py backend-hormonia/app/config/settings/integrations.py backend-hormonia/tests/unit/test_gemini_client_stub_config.py` | 1 | ⚠️ unavailable — no Python language server found | 0ms |

## Deviations

None.

## Known Issues

Python language-server diagnostics are unavailable in this environment (`No language server found`), so syntax/type confidence comes from the scoped pytest import/execution gate.

## Files Created/Modified

- `backend-hormonia/app/config/settings/integrations.py`
- `backend-hormonia/app/ai/client.py`
- `backend-hormonia/tests/unit/test_gemini_client_stub_config.py`
