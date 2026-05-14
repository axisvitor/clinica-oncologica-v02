---
id: S03
parent: M015
milestone: M015
provides:
  - Network-real local WuzAPI/Gemini stub proof for downstream S05 matrix closure.
  - A configured Gemini base-URL seam that lets runtime validation route to controlled stubs.
  - A provider Taskiq worker proof pattern for future runtime security seams.
  - Redaction-validated provider artifacts suitable for M015 final evidence aggregation.
requires:
  - slice: S01
    provides: Runtime substrate: local TLS PostgreSQL, Dragonfly, FastAPI readiness, migrations/fixtures, redaction helpers, and runner patterns.
  - slice: S02
    provides: Session/worker substrate and Taskiq boundary patterns for runtime authorization proofs.
affects:
  - M015/S04 consumes the same runtime substrate and should preserve the synthetic-only, redaction-safe evidence posture.
  - M015/S05 must include S03 provider proof and non-goals in the final evidence matrix and strict closure gate.
key_files:
  - scripts/security/m015-runtime/provider_stub.py
  - scripts/security/m015-runtime/redaction.py
  - scripts/security/m015-runtime/provider_seam.py
  - scripts/security/m015-runtime/m015_provider_security_taskiq.py
  - scripts/security/verify-m015-runtime-security.sh
  - scripts/security/m015-runtime/docker-compose.yml
  - backend-hormonia/app/config/settings/integrations.py
  - backend-hormonia/app/ai/client.py
  - backend-hormonia/tests/security/test_m015_s03_provider_runtime_contract.py
  - backend-hormonia/tests/security/test_m015_runtime_harness.py
  - scripts/security/m015-runtime/tests/test_provider_stub_contract.py
  - scripts/security/m015-runtime/tests/test_runner_contract.py
  - backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/provider-seam-summary.md
  - backend-hormonia/docs/reports/security/m015/provider-stub-observations.jsonl
key_decisions:
  - Use controlled local HTTP provider stubs for S03 instead of live WuzAPI/Gemini providers or in-process mocks.
  - Expose Gemini routing through optional `AI_GEMINI_BASE_URL` while preserving default SDK routing when unset.
  - Make `provider` a first-class fail-closed runner seam with profile-scoped provider stub/probe/worker services.
  - Treat tools-profile Compose services as part of teardown before claiming runtime cleanup.
  - Persist provider evidence as sanitized status/count/hash/redaction metadata with explicit local-stub usage and non-goals.
patterns_established:
  - Runtime provider seams should prove network/env wiring with local stubs plus worker participation, not in-process fakes.
  - Provider evidence should record status classes, scenario names, hashed identifiers, redaction flags, and non-goals rather than raw request/response bodies.
  - Compose teardown for M015 must include the `tools` profile to remove provider probe/worker services.
  - Completion evidence should include both the root runner output and a post-teardown container/port check.
observability_surfaces:
  - Provider runner phase logs with correlation ID and sanitized failure classes.
  - `provider-seam-evidence.json` with redaction, provider-stub usage, worker boundary, non-goals, and teardown fields.
  - `provider-seam-summary.md` as the human-readable provider proof.
  - `provider-stub-observations.jsonl` with redaction-safe stub request metadata only.
drill_down_paths:
  - .gsd/milestones/M015/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M015/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M015/slices/S03/tasks/T03-SUMMARY.md
  - .gsd/milestones/M015/slices/S03/tasks/T04-SUMMARY.md
  - .gsd/milestones/M015/slices/S03/tasks/T05-SUMMARY.md
  - backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json
  - backend-hormonia/docs/reports/security/m015/provider-seam-summary.md
duration: ""
verification_result: passed
completed_at: 2026-05-14T15:51:43.843Z
blocker_discovered: false
---

# S03: Network-Real WuzAPI/Gemini Stub Boundary

**S03 proved the provider runtime seam through configured local WuzAPI/Gemini HTTP stubs, a real Taskiq worker boundary, redaction-validated evidence, and clean teardown.**

## What Happened

S03 added and proved a network-real synthetic provider boundary for M015. The slice introduced controlled stdlib WuzAPI/Gemini stubs, an optional `AI_GEMINI_BASE_URL` product configuration seam, first-class `provider` runner/Compose support, a provider runtime probe, and a harness-only Taskiq provider task. The provider seam now exercises WuzAPI success/client-error/server-error/timeout/duplicate-or-replay outcomes, Gemini success/server-error outcomes, and worker participation through Taskiq while persisting only sanitized status classes, counts, hashes, redaction flags, provider-stub usage, failure classes, and non-goals. During operational verification, a stale M015 Compose project exposed a port-collision cleanup issue; the stale project was removed with the tools profile included, then the full provider gate was rerun successfully. The fresh completion evidence has correlation `m015-20260514T154638Z-1968863` and records teardown as complete with no active M015 runtime containers remaining.

## Verification

Fresh slice-completion gate ran after the last code/evidence change: `bash -n scripts/security/verify-m015-runtime-security.sh && docker compose -f scripts/security/m015-runtime/docker-compose.yml config --quiet && cd backend-hormonia && PYTHONPATH=. pytest tests/security/test_m015_s03_provider_runtime_contract.py tests/security/test_m015_runtime_harness.py tests/unit/test_gemini_client_stub_config.py -q && cd .. && ./scripts/security/verify-m015-runtime-security.sh --seam provider`. It exited 0 in 158.0s. Pytest reported `.......................................... [100%]` for 42 scoped tests, then the provider runner started isolated services, verified PostgreSQL TLS, Dragonfly, FastAPI, worker, provider-stub and provider-worker readiness, ran the provider probe, recorded WuzAPI/Gemini local-stub outcomes and Taskiq worker proof, wrote redaction-validated provider evidence/summary, and completed teardown. A follow-up container check returned `no active M015 runtime containers or M015 bound ports found`.

## Requirements Advanced

- R014 — Advanced the deferred runtime harness by proving the provider/queue portion through FastAPI/Dragonfly/Taskiq plus local WuzAPI/Gemini HTTP stubs and redaction-validated evidence; full R014 still waits for S04/S05 aggregation.
- R015 — Maintained the no-production/no-real-PHI anti-feature by using synthetic fixtures, local stubs, no live provider credentials, and redaction validation.
- R017 — Advanced PHI-safe evidence posture with durable provider evidence that omits raw provider bodies, prompts, cookies, tokens, DSNs, session IDs, and private paths.
- R018 — Advanced no-silent-drop accounting by recording S04/S05 downstream non-goals and explicit provider-seam limits in evidence and summary artifacts.

## Requirements Validated

None.

## New Requirements Surfaced

- None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

The first fresh completion rerun failed closed before provider execution because a stale M015 Compose project from an earlier run still held port 18080. I removed stale M015 runtime projects using `docker compose --profile tools down -v --remove-orphans`, verified the port was free, reran the exact gate, and received a passing result. No additional source code changes were made during slice completion.

## Known Limitations

S03 intentionally does not prove private artifact app-route runtime behavior, final all-seam evidence matrix closure, live WuzAPI/Gemini providers, production systems/data, browser/frontend flows, CDN/object storage, or broad DAST/fuzzing. Those remain S04/S05 or explicit non-goals.

## Follow-ups

S04 must prove private artifact app-route runtime access and header/static-path behavior. S05 must fold S01-S04 evidence into the unified runner, evidence matrix, strict validator, and final red-signal closure gate.

## Files Created/Modified

- `scripts/security/m015-runtime/provider_stub.py` — Controlled local WuzAPI/Gemini HTTP stub and redaction-safe observation support.
- `scripts/security/m015-runtime/redaction.py` — Shared denylist/redaction validation used by provider evidence.
- `scripts/security/m015-runtime/provider_seam.py` — Provider seam probe entrypoint.
- `scripts/security/m015-runtime/m015_provider_security_taskiq.py` — Provider probe and Taskiq worker participation proof implementation.
- `scripts/security/verify-m015-runtime-security.sh` — First-class provider seam orchestration, readiness, evidence, redaction, and tools-profile teardown.
- `scripts/security/m015-runtime/docker-compose.yml` — Provider-stub, provider-probe, and provider-worker runtime services.
- `backend-hormonia/app/config/settings/integrations.py` — Optional Gemini base-URL configuration seam.
- `backend-hormonia/app/ai/client.py` — Gemini client initialization now honors configured base URL without logging secrets/endpoints.
- `backend-hormonia/docs/reports/security/m015/provider-seam-evidence.json` — Fresh redaction-validated provider runtime evidence.
- `backend-hormonia/docs/reports/security/m015/provider-seam-summary.md` — Human-readable provider seam summary.
