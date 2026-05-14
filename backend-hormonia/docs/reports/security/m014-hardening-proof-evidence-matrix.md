# M014 Hardening and Proof Evidence Matrix

## Scope

M014 closes the medium-hardening and proof-gap backlog carried out of M013 as R012, R013, and R018. It uses controlled local/CI evidence only: backend pytest, frontend unit tests, quiz Jest tests, synthetic users, mocked providers, local temporary storage, and documented command output. It does not claim production exploitation, real PHI handling, live WuzAPI/Gemini behavior, CDN/browser telemetry, real object storage, or a production-like DB+queue harness.

This matrix is the reviewer-facing inspection surface. Each row is marked `Closed`, `Not applicable`, or `Deferred` with evidence and owner. Rows with controlled proof plus a broader runtime unknown say so explicitly; the unsupported runtime portion remains owned by M015/R014.

The artifact intentionally uses requirement IDs, coarse finding labels, command lines, test paths, and GSD evidence IDs only. It must not copy PHI, prompts, quiz answers, raw tokens, cookies, signed state values, provider payloads, private filesystem paths, secrets, or sensitive URLs.

## Fresh Evidence Sources

### S01 — Ingress, replay, duplicate-oracle, and rate-limit identity

Focused proof: `gsd_exec 3b14ac02-38eb-48c5-8303-f9cf467b5d54` ran:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py backend-hormonia/tests/security/test_m014_s01_webhook_replay.py backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py
```

Result: exit 0, 39 passed. Supporting regression proof: `gsd_exec 9efe8dad-808b-46fe-8c62-633744214262`, exit 0, 169 passed.

### S02 — ADK auth and session ownership

Focused proof:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py
```

Result: exit 0, 19 passed. Supporting ADK regression proof ran `backend-hormonia/tests/api/v2/test_adk.py`, `backend-hormonia/tests/unit/test_pii_safe_adk_wrapper.py`, `backend-hormonia/tests/unit/test_adk_runner_integration.py`, `backend-hormonia/tests/unit/test_adk_tools_runtime.py`, and `backend-hormonia/tests/unit/test_adk_metrics.py`; result: exit 0, 61 passed and 7 expected local dependency skips.

### S03 — Browser PHI cache and quiz frontend persistence

Backend cache proof: `gsd_exec a7192f1b-7943-4c8a-be7a-121e377a621f` ran:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s03_cache_headers.py
```

Result: exit 0, 7 passed.

Dashboard persistence proof: `gsd_exec 09a0a6b5-5a04-498d-a850-d6b6d5be1f31` ran:

```bash
npm --prefix frontend-hormonia test -- tests/unit/react-query/persistencePolicy.test.ts
```

Result: exit 0, 5 passed.

Quiz storage proof: `gsd_exec 0bece41c-9df5-473b-8c3e-50082f6bd878` ran:

```bash
npm --prefix quiz-mensal-interface test -- tests/security/quiz-progress-storage.test.tsx tests/security/no-phi-local-storage.test.tsx
```

Result: exit 0, 8 passed with known non-fatal Node/Jest warnings.

### S04 — Upload stored-XSS and private artifact serving

Focused proof: `gsd_exec 55eacbb1-957e-4ddb-93b3-dcf1cadf6eff` ran:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py
```

Result: exit 0, 75 passed. Supporting regression proof: `gsd_exec cba439b4-eb1a-4141-883f-7426323e29fb`, exit 0, 18 passed. Full combined S04 closeout: `gsd_exec d6c102d6-e4cb-494f-ab66-259ddd31b4e7`, exit 0, 93 passed. Report/export sanitizer regression: `gsd_exec a59f3ea2-74e1-46bb-a4f6-23c22a6fa564`, exit 0, 32 passed.

### S05 — JWT/config posture

Focused proof:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py backend-hormonia/tests/config/test_production_config.py
```

Result: exit 0, 8 passed. The proof covers JWT signature/type/subject/expiration checks, staff auth transport selection, DB fallback filters for active unrevoked unexpired sessions, production default-secret redaction, strong synthetic production posture, and existing production config regressions.

## Evidence Matrix

| Row | Risk surface | Requirements | Status | Evidence | PHI-safe diagnostics and limits |
|---|---|---|---|---|---|
| M014-01 | CSRF on session-backed browser mutations. | R012, R017 | Closed | S01 focused proof includes `test_m014_s01_csrf_fail_closed.py`; denied paths return before route side effects. | Denials expose route, method, reason, request metadata, and hashed client identity only. |
| M014-02 | Password reset replay before credential/session mutation. | R012, R017 | Closed | S01 focused proof includes `test_m014_s01_password_reset_replay.py`; reset JTI consumption is asserted before mutation. | Diagnostics use outcome/status/reason only and omit token material. |
| M014-03 | WuzAPI/generic webhook replay, timestamp, signature, and idempotency uncertainty. | R012, R017 | Closed | S01 focused proof includes `test_m014_s01_webhook_replay.py`; duplicate and infrastructure-uncertain paths fail closed before provider/queue/DB work. | Diagnostics use event type, route, reason, status, and hashed identifiers only. |
| M014-04 | Duplicate patient oracle through CPF/email/phone/name-like probes. | R012, R017 | Closed | S01 focused proof includes `test_m014_s01_duplicate_oracle.py`; duplicate probes collapse into a generic conflict before saga/provider work. | External responses and logs avoid raw identifying fields. |
| M014-05 | X-Forwarded-For spoofing and rate-limit infrastructure fail-open behavior. | R012, R013, R017 | Closed | S01 focused proof includes `test_m014_s01_rate_limit_fail_closed.py`; supporting rate-limit regressions passed in `gsd_exec 9efe8dad-808b-46fe-8c62-633744214262`. | Logs use trusted-proxy decision metadata and redacted client identifiers. |
| M014-06 | ADK route and runtime calls trusting payload identity or foreign session ownership. | R012, R013, R017 | Closed | S02 focused proof includes `test_m014_s02_adk_auth_session_ownership.py`; supporting ADK regression command passed. | Denial diagnostics include low-cardinality route/tool/lifecycle reason fields and exclude prompts, provider payloads, tokens, and secrets. |
| M014-07 | PHI-bearing backend GETs and dashboard state persisted through reusable HTTP/browser caches. | R012, R017 | Closed | S03 backend proof `test_m014_s03_cache_headers.py`; dashboard proof `persistencePolicy.test.ts`. | Evidence uses headers, cache diagnostics, and sanitized query metadata only. |
| M014-08 | Public quiz frontend lane storing answers, free text, session labels, token-like state, or signed state in browser storage. | R013, R017 | Closed | S03 quiz proof runs `quiz-progress-storage.test.tsx` and `no-phi-local-storage.test.tsx`. | Tests inspect synthetic storage keys/values only and do not log answers, prompts, tokens, cookies, or signed state values. |
| M014-09 | Upload stored-XSS through HTML/SVG/XML/script payloads or avatar bypass before durable persistence. | R013, R012, R017 | Closed | S04 focused proof includes `test_m014_s04_active_content_validation.py` and `test_m014_s04_upload_xss_private_serving.py`. | Denials use coarse active-content reasons and avoid uploaded bytes, filenames with PHI, storage paths, and tokens. |
| M014-10 | Legacy private uploads or generated report/export artifacts executing inline or bypassing owner/admin access. | R012, R013, R017 | Closed | S04 proof includes `test_m014_s04_private_artifact_serving.py`, `test_m014_s04_report_artifact_serving.py`, and supporting report/private upload regressions. | Downloads use attachment, nosniff, no-store, and octet-stream downgrade where required; denials avoid body bytes and private paths. |
| M014-11 | Unsafe generated report/export URLs using external, protocol-relative, encoded private, or malformed locations. | R012, R017, R018 | Closed | S04 report/export sanitizer regression `gsd_exec a59f3ea2-74e1-46bb-a4f6-23c22a6fa564` passed with encoded and external denial cases. | Status payloads withhold unsafe download URLs and downloads deny without redirects. |
| M014-12 | JWT validation accepting wrong signature, wrong token type, expired token, or missing subject. | R012, R013, R017 | Closed | S05 focused proof includes `test_m014_s05_jwt_config_posture.py`; 8-test posture command passed. | Test assertions never print raw JWTs; failure text names behavior only. |
| M014-13 | Staff auth accepting legacy bearer or X-Session-ID transports instead of the canonical session cookie. | R012, R013, R017 | Closed | S05 focused proof checks `resolve_request_session_id` rejects legacy bearer and X-Session-ID when no session cookie is present. | The row proves staff auth transport selection, not public quiz token behavior. |
| M014-14 | Session revocation semantics during Redis outage or worker-local state loss. | R013, R012 | Closed for controlled proof; Deferred for production-like multi-worker runtime proof | S05 focused proof verifies DB fallback query filters active, unrevoked, unexpired persisted sessions. Live multi-worker runtime proof remains M015/R014. | Controlled proof avoids a live DB+queue harness; the unexercised runtime portion is explicitly owned by M015/R014. |
| M014-15 | Production deployment secret posture: weak/default JWT, CSRF, encryption, PHI, and hash keys. | R012, R017 | Closed | S05 focused proof and existing production config tests verify weak/default secret rejection and redacted default-secret errors with synthetic required env values. | Errors name variable/remediation only; the production default-secret prefix is no longer echoed. |
| M014-16 | DB TLS and RLS posture. | R012, R014, R018 | Deferred to M015/R014 for runtime proof; documented for M014 | S05 posture proof accepts a synthetic production database URL containing `sslmode=require` and `sslminversion=TLSv1.2`; no live TLS handshake or RLS policy execution is claimed. | M014 does not claim live database TLS negotiation, RLS enforcement, or production isolation. Owner: M015/R014 if runtime validation is required. |
| M014-17 | R018 risk that independent medium findings silently disappear after M013. | R018, R013 | Closed | This matrix and `test_m014_s05_evidence_matrix.py` enumerate every M014 R012/R013/R018 lane and fail on missing rows, placeholders, or unsafe sentinel strings. | The document is validated as an artifact; future changes should update both row content and validator requirements. |

## Deferred Runtime and Non-Goal Register

| Item | Status | Owner | Rationale |
|---|---|---|---|
| Production-like DB+queue+WuzAPI/Gemini harness | Deferred | M015/R014 | M014 intentionally uses controlled local proof. Live provider lifecycle, worker orchestration, and realistic runtime exploitation would expand the milestone beyond its selected proof boundary. |
| Live JWT/session revocation across multiple worker processes | Deferred for runtime proof | M015/R014 | M014 proves persisted fallback filters and canonical staff session transport. It does not run a multi-process deployment or live cache/DB failover scenario. |
| Live database TLS negotiation and RLS policy enforcement | Deferred | M015/R014 | M014 documents expected TLS posture and avoids overclaiming without a live database harness. |
| Production CDN/browser/object-storage rendering of private artifacts | Deferred | M015/R014 | S03/S04 prove local response headers and route behavior, not production CDN policy or real object-storage signed URL behavior. |
| Production exploitation or real PHI data | Not applicable | R015 | Explicit anti-feature: all M014 evidence is controlled synthetic proof. |
| Treating local git-ignored files as committed secrets | Not applicable | R017 | M014 validates evidence redaction and runtime boundary behavior; it does not reclassify local ignored files as repository secrets. |

## Closeout Commands

A reviewer can rerun the backend controlled proof from the repository root with:

```bash
PYTHONPATH=backend-hormonia python -m pytest -c backend-hormonia/pyproject.toml backend-hormonia/tests/security/test_m014_s01_rate_limit_fail_closed.py backend-hormonia/tests/security/test_m014_s01_csrf_fail_closed.py backend-hormonia/tests/security/test_m014_s01_password_reset_replay.py backend-hormonia/tests/security/test_m014_s01_webhook_replay.py backend-hormonia/tests/security/test_m014_s01_duplicate_oracle.py backend-hormonia/tests/security/test_m014_s02_adk_auth_session_ownership.py backend-hormonia/tests/security/test_m014_s03_cache_headers.py backend-hormonia/tests/security/test_m014_s04_active_content_validation.py backend-hormonia/tests/security/test_m014_s04_upload_xss_private_serving.py backend-hormonia/tests/security/test_m014_s04_private_artifact_serving.py backend-hormonia/tests/security/test_m014_s04_report_artifact_serving.py backend-hormonia/tests/security/test_m014_s05_jwt_config_posture.py backend-hormonia/tests/security/test_m014_s05_evidence_matrix.py
```

Supporting frontend/quiz commands from S03 remain separate because they use npm test runners:

```bash
npm --prefix frontend-hormonia test -- tests/unit/react-query/persistencePolicy.test.ts
npm --prefix quiz-mensal-interface test -- tests/security/quiz-progress-storage.test.tsx tests/security/no-phi-local-storage.test.tsx
```

S05 T03 is responsible for replacing this section's current command plan with fresh integrated closeout results after rerunning the commands.
