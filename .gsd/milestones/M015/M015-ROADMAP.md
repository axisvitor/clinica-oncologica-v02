# M015: Runtime Security Validation

**Vision:** Prove the runtime-only security gaps deferred from M014 with a synthetic-only, production-like backend harness. The milestone delivers a single local/CI-ready runner that starts FastAPI, TLS-enabled PostgreSQL, Dragonfly, Taskiq workers, and controlled WuzAPI/Gemini stubs, validates the selected seams end to end, captures PHI-safe evidence, and tears down cleanly without production data, live provider credentials, or overclaimed guarantees.

## Success Criteria

- A single committed M015 runner starts a synthetic production-like backend stack, waits for readiness, applies migrations/fixtures, runs selected runtime security checks, captures evidence, and tears down cleanly.
- The selected M014-deferred seams are exercised through process/network boundaries: DB TLS/RLS, multi-process session revocation/cache/DB fallback, Dragonfly/Taskiq worker wiring, WuzAPI/Gemini stub boundaries, and private artifact app routes.
- The M015 evidence matrix maps every deferred runtime item to fresh evidence, explicit non-goal, or fixed outcome, and a validator rejects missing rows, placeholders, stale commands, and unsafe sensitive content.
- No live provider credentials, production systems, real PHI, browser/frontend flows, CDN/object-storage guarantees, or production exploitation claims are introduced.
- Selected runtime security red signals found during M015 are fixed before milestone close rather than documented away as green.

## Slices

- [x] **S01: S01** `risk:Highest risk: local TLS PostgreSQL, generated test certs, migrations, readiness, and RLS execution are brittle and establish the runtime substrate for every downstream seam.` `depends:[]`
  > After this: Run `./scripts/security/verify-m015-runtime-security.sh --seam db` to start the isolated backend runtime stack, apply migrations and synthetic fixtures, prove TLS negotiation and RLS allow/deny behavior, capture sanitized DB evidence, and tear down.

- [x] **S02: S02** `risk:High risk: the proof can accidentally collapse into an in-process shortcut unless it forces separate API/cache/DB/worker boundaries and cache-fallback behavior.` `depends:[]`
  > After this: Run the M015 session seam through the harness to show a current synthetic session succeeds, revoked/expired sessions fail closed across cache and DB fallback, and a queued worker scenario participates without accepting stale authorization.

- [ ] **S03: S03** `risk:High risk: provider checks must prove real network/env wiring and fail-closed behavior while staying synthetic-only and avoiding live side effects or payload leakage.` `depends:[]`
  > After this: Run the provider seam to show the backend and workers use configured local WuzAPI/Gemini stub URLs, handle controlled failure modes safely, and record only redacted synthetic request evidence.

- [ ] **S04: Private Artifact App-Route Runtime Proof** `risk:Medium-high risk: deployed-style artifact access may expose route/header/ownership gaps or accidental static/private path leakage under the running app.` `depends:[S01,S02]`
  > After this: Run the artifact seam against the harness to show owner/admin access succeeds, anonymous and cross-owner access fail closed, response headers are safe, and no redirect or static path exposes private artifacts.

- [ ] **S05: Unified Runner, Evidence Matrix, and Strict Closure Gate** `risk:Medium risk: final closure can become report-only unless the runner, matrix validator, redaction checks, teardown, and red-signal policy mechanically block false green results.` `depends:[S01,S02,S03,S04]`
  > After this: Run `./scripts/security/verify-m015-runtime-security.sh` with no seam filter and receive a pass/fail result plus an M015 evidence matrix that maps every M014-deferred runtime item to fresh evidence, an explicit non-goal, or a fixed outcome.

## Boundary Map

### Runtime boundaries
- Entrypoint: `./scripts/security/verify-m015-runtime-security.sh` orchestrates compose/profile startup, readiness, seam execution, evidence capture, and teardown.
- Database: local TLS-enabled PostgreSQL with generated test material, Alembic migrations, synthetic fixtures, TLS posture checks, and RLS execution proof.
- Cache/session: Dragonfly plus DB fallback verifies current/revoked/expired session behavior across process boundaries.
- Queue/worker: Taskiq workers communicate through Dragonfly and participate in selected security scenarios.
- Providers: local HTTP WuzAPI/Gemini stubs receive real network calls and simulate controlled success/failure/replay/timeout cases.
- Artifacts: private upload/report files live under an unmounted private harness root and are accessed only through authenticated app routes.
- Evidence: matrix, logs, stub captures, and summaries are redaction-checked before a green result.

### Horizontal checklist considered
- Requirements: R012/R013/R014/R015/R017/R018 mapped; unrelated product requirements are outside this backend-runtime validation scope.
- Decisions: synthetic-only harness, TLS local PostgreSQL, network-real provider stubs, app-route artifact proof, and strict red-signal closure are honored.
- Shutdown: runner must tear down services and temporary test material idempotently while preserving only sanitized evidence.
- Revenue: no billing, subscription, or revenue flow is touched.
- Auth: session and ownership boundaries fail closed for revoked, expired, anonymous, cross-owner, and provider-failure cases.
- Shared resources: use isolated Docker project names/ports/volumes and synthetic fixtures to avoid contaminating developer or production data.
- Reconnection/retry: readiness waits, cache fallback, provider timeout/replay, and worker/broker failure classes are explicitly exercised or classified.
