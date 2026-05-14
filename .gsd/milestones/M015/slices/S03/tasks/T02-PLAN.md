---
estimated_steps: 8
estimated_files: 4
skills_used: []
---

# T02: Add a test-covered Gemini base-URL configuration seam

Why: WuzAPI already has a base URL setting, but Gemini currently initializes `google-genai` without a configurable local endpoint; without a product config seam, S03 cannot honestly prove app-to-Gemini-stub network wiring.

Steps:
1. Add an optional `AI_GEMINI_BASE_URL` setting in the integrations settings model with safe default `None` and documentation that it is for synthetic/runtime validation or controlled non-production routing.
2. Update `GeminiClient._initialize_model()` to pass `types.HttpOptions(base_url=...)` to `genai.Client` when the setting is configured, while preserving existing API-key/model/temperature behavior.
3. Add focused unit tests that monkeypatch settings and the `genai.Client` constructor to prove base URL is passed only when configured and never logged with API keys.
4. Keep existing PII redaction behavior in front of external calls and add a provider-runtime contract test for redaction/endpoint configuration if needed.
5. Do not introduce live provider credentials, production defaults, or a fallback that silently calls the public Gemini endpoint during the provider seam.

Done when Gemini has a test-covered local-stub endpoint seam and existing Gemini redaction tests still pass.

## Inputs

- `backend-hormonia/app/config/settings/integrations.py`
- `backend-hormonia/app/ai/client.py`
- `backend-hormonia/tests/unit/test_gemini_client_pii_redaction.py`

## Expected Output

- `backend-hormonia/app/config/settings/integrations.py`
- `backend-hormonia/app/ai/client.py`
- `backend-hormonia/tests/unit/test_gemini_client_stub_config.py`

## Verification

cd backend-hormonia && PYTHONPATH=. pytest tests/unit/test_gemini_client_stub_config.py tests/unit/test_gemini_client_pii_redaction.py -q

## Observability Impact

Preserves existing Gemini initialization diagnostics while avoiding secrets and adds tests for the routing decision that future provider seam failures depend on.
