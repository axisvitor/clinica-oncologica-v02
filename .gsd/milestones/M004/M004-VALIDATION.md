---
verdict: pass
remediation_round: 0
---

# Milestone Validation: M004

## Success Criteria Checklist

- [x] **O stack local autentica a equipe, restaura sessão e carrega `/dashboard`, `/admin` e `/whatsapp` sem depender de Firebase ou de superfícies legadas no caminho oficial.** — evidence: S06 `run-mounted-proof.sh --all` passed with backend+frontend booted on blank Firebase envs. `health-ready.json` shows `session_auth` healthy in session-first mode. `system-config.json` has no `VITE_FIREBASE_*`. `route-smoke-evidence.json` shows `phase: completed`, `lastSuccessfulRoute: /whatsapp`, and no `unexpectedFirebaseRequests`. Auth acceptance (`--auth`) and route smoke (`--smoke`) both green on the mounted no-Firebase stack.

- [x] **`firebase_uid`, `/session/*`, `X-Session-ID` e fallbacks legados em escopo deixam de ser parte viva do runtime oficial ou passam a ser rejeitados/tombstonados explicitamente.** — evidence: S02 converged backend identity resolution to `user_id`-first (focused helper proof + acceptance pack green). S04 retired `/session/*` as explicit 410 tombstone (`test_session_validation.py` — 5 tests green), rejected `X-Session-ID` and session-as-Bearer at HTTP and websocket chokepoints (`test_auth_session_priority.py`, `test_auth_hard_cut_cleanup.py`, `test_auth_hard_cut_end_to_end.py` — 60+ tests green). S05 removed `firebase_uid` from adjacent runtime surfaces (session/cache/login payloads, audit/admin/docs, frontend types). `verify-runtime-residue.sh --check all` passes with only passive compatibility/rejection bookkeeping approved.

- [x] **O frontend oficial para de depender funcionalmente de semântica/comentários de Firebase para auth/sessão.** — evidence: S03 converged the official frontend to the canonical cookie-backed session-first contract. `AuthContext`, `api-client/core.ts`, `api-client/auth.ts`, `enhanced-analytics.ts`, `websocket.ts`, hooks, and admin/shared types all cut over. Focused proof (29 integration tests + 108 unit tests green), `npm run build` green, `verify-runtime-residue.sh --check frontend` reports `no approved residue`. S05 further cleaned adjacent frontend type barrels (`api.ts`, `rbac.ts`) with 91 type-level tests green.

- [x] **O milestone fecha com prova montada de runtime sem Firebase, não só com grep, diff e testes unitários.** — evidence: S06 is the dedicated mounted-proof slice. `run-mounted-proof.sh --all` boots the real backend+frontend stack with Firebase Auth envs blank, seeds a proof user in `/tmp`, runs auth acceptance (login/restore/logout), and runs Playwright route smoke against `/admin`, `/dashboard`, `/whatsapp`. Evidence artifacts: `status.json`, `health-ready.json`, `wuzapi-status.json` (connected=true, logged_in=true, mock=true), `route-smoke-evidence.json`. This is live assembled-stack proof, not structural analysis.

## Slice Delivery Audit

| Slice | Claimed | Delivered | Status |
|-------|---------|-----------|--------|
| S01 | Executable verifier showing where Firebase/legacy residue exists in official runtime; suite fails on new residue | `verify-runtime-residue.sh` (`--report`/`--check`), `runtime-residue-allowlist.json`, `test_runtime_residue_guard.py` regression harness. Boundary republished through S05 to reflect reduced post-cleanup state. Frontend scope at `approved: []`. | pass |
| S02 | Login, verify-session, restore, logout on canonical `user_id` contract; `firebase_uid` off happy path | `auth_session_cache.py`, `auth_session_shared.py`, `user_cache_shared.py` converged to `user_id`-first identity resolution. Focused helper proof pack (7 test files) + acceptance pack green. Residue boundary republished with updated semantics. | pass |
| S03 | `/login`, `/dashboard`, `/admin` on session-first contract; no Firebase functional semantics on official frontend | `AuthContext`, api-client core/auth/analytics, websocket manager, hooks, admin/shared types all converged. 29 integration + 108 unit tests green. Zero frontend residue in verifier. Routed `/admin/*` proof via shipped router tree. Build green. | pass |
| S04 | App stops needing `/session/*`, `X-Session-ID`, fallbacks; rejected/tombstoned | Cookie-only backend at HTTP+websocket chokepoints. `/session/*` → explicit 410 tombstone with `AUTH_LEGACY_SESSION_ROUTE_RETIRED`. Focused rejection proofs (clear cookies → assert header-only failure). 65 tests green. Residue boundary republished. | pass |
| S05 | Cache, audit, types/docs, adjacent modules stop treating Firebase as live | Redis session creation/listing/invalidation on `user_id`. Shared restore/cache sanitized. Audit/admin/docs aligned to canonical semantics. Frontend-adjacent types cleaned. 4 focused proof packs green. Residue boundary republished to exclude cleaned hotspots. | pass |
| S06 | Stack boots without Firebase Auth; reproves login/restore/logout + smoke `/dashboard`, `/admin`, `/whatsapp` | `run-mounted-proof.sh` replayable runner, `seed-proof-user.py` with masked `/tmp` artifacts, `no-firebase-runtime-smoke.spec.ts` Playwright spec. `--all` green. Evidence chain: `status.json` → `health-ready.json` → `wuzapi-status.json` → `route-smoke-evidence.json`. | pass |

## Cross-Slice Integration

All boundary map entries reconcile against delivered artifacts:

| Boundary | Producer → Consumer | Verified |
|----------|---------------------|----------|
| S01 → S02 | Verifier + residue map → consumed for backend convergence and republished | ✓ S02 used S01 categories; republished with updated semantics |
| S02 → S03 | Canonical backend `user_id` contract → consumed for frontend cutover | ✓ S03 frontend tests depend on S02's cookie-backed session semantics |
| S02 → S04 | Remaining legacy surface list → consumed for transport retirement | ✓ S04 retired exactly the surfaces S02 left as live transport |
| S03 → S04 | Frontend on canonical contract → enabled backend legacy transport removal | ✓ S04 retired backend acceptance only after S03 proved frontend independence |
| S04 → S05 | Narrowed official boundary → consumed for adjacent cleanup | ✓ S05 cleaned surfaces outside the S04-reduced transport boundary |
| S04 → S06 | Final auth/session surface → exercised in mounted stack | ✓ S06 replayed cookie-only auth across routed surfaces |
| S05 → S06 | Aligned adjacent runtime → consumed for assembled-stack proof | ✓ S06 ran with S05's cleaned runtime; no Firebase leakage in smoke evidence |

No boundary mismatches found.

## Requirement Coverage

| Requirement | Status | Covered By | Evidence |
|-------------|--------|------------|----------|
| R047 — O runtime oficial do sistema deixa de depender de Firebase | validated | S01, S02, S03, S04, S05, S06 | S06 mounted proof with blank Firebase envs; `verify-runtime-residue.sh --check all` green; residue boundary shows only passive compatibility/rejection |
| R048 — Auth/sessão por um único contrato canônico | validated | S02, S01, S03, S04 | Combined S02+S03+S04 proof: cookie-backed `user_id` login/verify/restore/logout green; frontend consumes only that contract; `/session/*`, `X-Session-ID`, session-as-Bearer retired |
| R049 — Runtime resolve identidade por `user_id`, sem `firebase_uid` no happy path | validated | S02, S01, S04, S05 | Combined S02+S05 proof: Redis session identity, shared auth/cache, login payloads, audit/admin/docs, frontend types all on canonical `user_id`; residue guard shows only passive compatibility |
| R050 — Frontend oficial usa apenas o contrato session-first canônico | validated | S03, S01, S04, S05, S06 | S03 focused proof packs (137 tests), routed `/login`→`/admin/*`, websocket diagnostics, build, zero frontend residue in verifier; S06 route smoke green |

Deferred to later milestones (per roadmap):
- R051 (schema/migration cleanup) → M005 ✓
- R052 (dead code/bridges/aliases removal) → M006 ✓
- R053 (integrated proof for M004–M006 arc) → M005/S04 ✓

No orphan risks. No unaddressed in-scope requirements.

## Definition of Done Checklist

- [x] Todas as slices S01–S06 foram concluídas com seus verificadores verdes — all six slices report `verification_result: passed`.
- [x] O runtime oficial de auth/sessão e o frontend oficial estão de fato ligados ao caminho canônico sem Firebase — S02+S03+S04+S05 prove the canonical contract; verifier confirms the live boundary.
- [x] O entrypoint real existe e foi exercitado no stack local montado sem Firebase Auth — S06 `run-mounted-proof.sh --all` exercises the real mounted stack.
- [x] Os critérios de sucesso foram rechecados contra comportamento vivo, não apenas contra diffs estruturais — S06's Playwright route smoke + auth acceptance are live behavioral proof, not structural analysis.
- [x] Os cenários finais de aceitação integrada passam e deixam claro o que ficou para M005 como dívida exclusivamente de schema/migração — S06 summary explicitly states M005 owns schema/model debt only; S01 boundary makes this distinction machine-readable.

## Verdict Rationale

**Verdict: pass** — all four success criteria are met with concrete evidence, all six slices delivered their claimed outputs with green verification, cross-slice boundary contracts aligned without mismatches, all four in-scope requirements (R047–R050) are validated, and the definition of done is fully satisfied.

The milestone achieved its stated vision: the official runtime converged to a single canonical path without Firebase, legacy auth/session compatibility surfaces were retired or tombstoned, and the assembled local stack was proven green on the canonical contract. The debt left for M005 (schema/migration) and M006 (dead code purge) is explicitly scoped and does not overlap with runtime behavior.

## Remediation Plan

None required — verdict is pass.
