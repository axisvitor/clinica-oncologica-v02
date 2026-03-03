---
phase: 40-otel-removal-adk-foundation
verified: 2026-03-03T20:57:45Z
status: human_needed
score: 11/11 must-haves verified
human_verification:
  - test: "Validate real Sentry FastAPI->Celery correlation in configured environment"
    expected: "FastAPI and Celery transactions are linked in the same trace and preserve depth continuity"
    why_human: "External Sentry project visibility and runtime telemetry cannot be fully confirmed from repository-only checks"
---

# Phase 40: OTel Removal & ADK Foundation Verification Report

**Phase Goal:** OTel instrumentation packages removed and ADK installed cleanly — the pip conflict that blocked ADK since v1.2 is resolved, Sentry correlation verified intact, and the LGPD-compliant PIISafeADKWrapper exists before any patient data can reach ADK.
**Verified:** 2026-03-03T20:57:45Z
**Status:** human_needed
**Re-verification:** No - initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | `pip check` passes in clean Python 3.13 with `google-adk` + `pydantic-ai-slim[google,retries]` | ✓ VERIFIED | Re-ran in `python:3.13-slim`: `No broken requirements found.`; evidence doc at `.planning/phases/40-otel-removal-adk-foundation/40-ADK-COMPATIBILITY.md:39` |
| 2 | All 9 manual OTel instrumentation packages are removed from backend requirements | ✓ VERIFIED | `backend-hormonia/requirements.txt` has zero `opentelemetry-` lines; `google-adk` present at `backend-hormonia/requirements.txt:44` |
| 3 | Importing `app.core.tracing` fails fast with ImportError and no production caller imports it | ✓ VERIFIED | Tombstone raise at `backend-hormonia/app/core/tracing.py:8`; import command raises ImportError; search returned `NO_TRACING_IMPORTS` in `backend-hormonia/app/**/*.py` |
| 4 | Sentry setup includes FastAPI, SQLAlchemy, Redis, and Celery integrations after OTel cleanup | ✓ VERIFIED | Integration list includes `CeleryIntegration(monitor_beat_tasks=True)` at `backend-hormonia/app/core/setup/sentry.py:63`; module imports successfully |
| 5 | FastAPI->Celery Sentry correlation remains linked post-removal with non-regressed span depth | ✓ VERIFIED | Baseline/post both `trace_linked: true`, `span_depth: 3` in `.planning/phases/40-otel-removal-adk-foundation/40-SENTRY-CORRELATION-BASELINE.json:2` and `.planning/phases/40-otel-removal-adk-foundation/40-SENTRY-CORRELATION-POST.json:2`; PASS recorded at `.planning/phases/40-otel-removal-adk-foundation/40-SENTRY-CORRELATION-VERIFICATION.md:19` |
| 6 | All ADK Gemini calls in this phase route through `PIISafeADKWrapper.safe_run()` boundary | ✓ VERIFIED | Wrapper boundary implemented at `backend-hormonia/app/ai/adk/wrapper.py:27`; CI guard passes with no direct agent/runner `.run*` violations outside approved wrappers |
| 7 | Wrapper sanitizes prompt/context before ADK invocation and warns on output PII | ✓ VERIFIED | Sanitization call at `backend-hormonia/app/ai/adk/wrapper.py:37`; output scan warning at `backend-hormonia/app/ai/adk/wrapper.py:64` |
| 8 | Synthetic PHI test proves raw identifiers do not reach ADK call boundary | ✓ VERIFIED | Test asserts sanitized prompt boundary in `backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py:35`; test suite passed |
| 9 | CI guard fails when direct ADK run patterns appear outside approved wrappers | ✓ VERIFIED | ADK pattern present in guard at `backend-hormonia/scripts/check_agent_run_calls.py:24`; regression violation test at `backend-hormonia/tests/unit/test_adk_run_guard_regression.py:19` passed |
| 10 | Wrapper files are exempted from guard to avoid false positives | ✓ VERIFIED | Exemptions include `app/ai/agents/base.py` and `app/ai/adk/wrapper.py` at `backend-hormonia/scripts/check_agent_run_calls.py:32` |
| 11 | Regression fixture proves guard exits non-zero on violation | ✓ VERIFIED | Violation fixture asserts return code 1 in `backend-hormonia/tests/unit/test_adk_run_guard_regression.py:29`; test suite passed |

**Score:** 11/11 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `backend-hormonia/requirements.txt` | Dependency set without manual OTel block + ADK dependency | ✓ VERIFIED | Exists, substantive, includes `google-adk`; no `opentelemetry-` entries |
| `backend-hormonia/app/core/tracing.py` | Tombstone module raising ImportError | ✓ VERIFIED | Exists, substantive tombstone, ImportError verified at runtime |
| `.planning/phases/40-otel-removal-adk-foundation/40-ADK-COMPATIBILITY.md` | Python 3.13 compatibility evidence (`pip check`) | ✓ VERIFIED | Exists with resolved-version table and PASS |
| `backend-hormonia/app/core/setup/sentry.py` | Sentry integrations include CeleryIntegration | ✓ VERIFIED | Exists, substantive integration config, wired from app factory |
| `backend-hormonia/scripts/sentry_correlation_probe.py` | Probe emits correlation metrics including linkage/depth | ✓ VERIFIED | Exists, substantive, probe executed successfully |
| `.planning/phases/40-otel-removal-adk-foundation/40-SENTRY-CORRELATION-VERIFICATION.md` | Baseline vs post continuity verdict | ✓ VERIFIED | Exists with explicit `correlation_continuity: PASS` |
| `backend-hormonia/app/ai/adk/wrapper.py` | LGPD-safe ADK boundary wrapper | ✓ VERIFIED | Exists, substantive sanitization + scan logic, wired via export/tests |
| `backend-hormonia/app/ai/adk/__init__.py` | Public ADK wrapper export | ✓ VERIFIED | Exists and exports `PIISafeADKWrapper` |
| `backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py` | Synthetic PHI wrapper regression coverage | ✓ VERIFIED | Exists, tests pass |
| `backend-hormonia/scripts/check_agent_run_calls.py` | CI lint guarding pydantic-ai + ADK direct runs | ✓ VERIFIED | Exists, substantive dual-pattern guard, executable and passing in tree |
| `backend-hormonia/tests/unit/test_adk_run_guard_regression.py` | Regression tests with failing fixture path | ✓ VERIFIED | Exists, subprocess-based violation and clean-path assertions pass |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `backend-hormonia/app/integrations/whatsapp/services/message_service.py` | `backend-hormonia/app/core/tracing.py` | import deletion | ✓ WIRED | No `from app.core.tracing import` in app code |
| `backend-hormonia/app/services/unified_whatsapp_service.py` | `backend-hormonia/app/core/tracing.py` | import deletion | ✓ WIRED | No `from app.core.tracing import` in app code |
| `backend-hormonia/app/core/setup/sentry.py` | `sentry_sdk.integrations.celery.CeleryIntegration` | integrations list entry | ✓ WIRED | `CeleryIntegration(monitor_beat_tasks=True)` present and importable |
| `backend-hormonia/scripts/sentry_correlation_probe.py` | `.planning/phases/40-otel-removal-adk-foundation/40-SENTRY-CORRELATION-POST.json` | probe output capture | ✓ WIRED | Post artifact contains `"trace_linked": true` |
| `backend-hormonia/app/ai/adk/wrapper.py` | `backend-hormonia/app/ai/pii_redaction.py` | `sanitize_prompt_text_for_external_ai` | ✓ WIRED | Sanitizer import + call present |
| `backend-hormonia/app/ai/adk/wrapper.py` | `backend-hormonia/app/ai/agents/deps.py` | `AIDeps` input | ✓ WIRED | `AIDeps` typing contract present via `TYPE_CHECKING` import |
| `backend-hormonia/tests/unit/test_adk_run_guard_regression.py` | `backend-hormonia/scripts/check_agent_run_calls.py` | subprocess invocation | ✓ WIRED | Test invokes guard script path and asserts exit behavior |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| ADK-01 | `40-01-PLAN.md` | OTel instrumentation packages removidos de requirements.txt sem quebrar Sentry | ✓ SATISFIED | `requirements.txt` cleaned; Sentry setup imports and includes CeleryIntegration |
| ADK-02 | `40-01-PLAN.md` | `app/core/tracing.py` tombstoned com ImportError (fallback mock ja existe) | ✓ SATISFIED | Tombstone file raises ImportError; no app imports remain |
| ADK-03 | `40-01-PLAN.md` | google-adk instalado e resolvido com pydantic-ai-slim[google] no Python 3.13 | ✓ SATISFIED | Docker Python 3.13 compatibility check passed with `pip check` |
| ADK-04 | `40-02-PLAN.md` | PIISafeADKWrapper criado com sanitizacao PII antes de qualquer chamada Gemini via ADK | ✓ SATISFIED | Wrapper boundary + synthetic PHI tests passing |
| ADK-05 | `40-03-PLAN.md` | CI guard estendido para patterns de chamada ADK | ✓ SATISFIED | Guard script blocks ADK run patterns; regression tests pass |

Orphaned requirements for Phase 40: none (all IDs mapped in plans and accounted for).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| N/A | N/A | No TODO/FIXME/placeholders/empty stub returns in phase-modified code artifacts | ℹ️ Info | No blocker or warning anti-pattern detected |

### Human Verification Required

### 1. Real Sentry Correlation Check

**Test:** Trigger one real FastAPI flow that dispatches a Celery task in an environment with valid Sentry DSN and inspect resulting trace in Sentry UI.
**Expected:** FastAPI transaction and downstream Celery task appear in the same trace with depth continuity matching or exceeding phase baseline behavior.
**Why human:** External Sentry tenant visibility and live telemetry ingestion are outside static repository/programmatic local checks.

### Gaps Summary

No code or wiring gaps found against declared must-haves. Automated verification passed; remaining validation is external-service human confirmation only.

---

_Verified: 2026-03-03T20:57:45Z_
_Verifier: Claude (gsd-verifier)_
