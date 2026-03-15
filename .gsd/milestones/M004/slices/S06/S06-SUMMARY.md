---
id: S06
parent: M004
milestone: M004
provides:
  - Proved mounted runtime assembly without Firebase for auth/session and routed `/dashboard`, `/admin`, `/whatsapp` in one replay path.
  - Unified stack verification evidence (status/health/config/wuzapi) with masked proof artifacts in `/tmp`.
  - Closed T01–T03 verification surface and confirmed no Firebase legacy runtime traffic during official route smoke.
requires:
  - slice: S01
    provides: canonical residue boundaries and runtime-residue runtime guard contract
  - slice: S02
    provides: canonical session-first backend contract (`user_id`, cookie-only)
  - slice: S03
    provides: frontend auth/session contract aligned to canonical paths
  - slice: S04
    provides: legacy transport/formal retirement in official scope
  - slice: S05
    provides: adjacent Firebase-adjacent runtime surfaces aligned to session contract
affects:
  - M005 (indirect): residue remanescente de schema/migração e limpeza estrutural final permanece fora do stack
  - M006 (indirect): limpeza adicional de código morto/compatibilidade pode ser concluída com base em evidência acumulada
key_files:
  - .gsd/milestones/M004/slices/S06/run-mounted-proof.sh
  - .gsd/milestones/M004/slices/S06/seed-proof-user.py
  - frontend-hormonia/tests/e2e/runtime/no-firebase-runtime-smoke.spec.ts
  - frontend-hormonia/tests/e2e/test-results/e2e-results.json
  - frontend-hormonia/test-results/runtime-no-firebase-runtim-*/route-smoke-evidence.json
  - frontend-hormonia/test-results/runtime-no-firebase-runtim-*/attachments/route-smoke-evidence-*.json
  - /tmp/gsd-s06-mounted-proof/status.json
  - /tmp/gsd-s06-mounted-proof/health-ready.json
  - /tmp/gsd-s06-mounted-proof/system-config.json
  - /tmp/gsd-s06-mounted-proof/wuzapi-status.json
  - /tmp/gsd-s06-proof.env
  - /tmp/gsd-s06-browser-bootstrap
  - .gsd/milestones/M004/slices/S06/S06-UAT.md
  - .gsd/milestones/M004/slices/S06/tasks/T03-SUMMARY.md
observability_surfaces:
  - `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight && curl -fsS http://localhost:8000/health/ready && curl -fsS http://localhost:8000/api/v2/system/config`
  - `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth`
  - `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --smoke`
  - `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all`
  - `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all`
  - `cd backend-hormonia && pytest -q tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py`
  - `/tmp/gsd-s06-mounted-proof/status.json`
  - `/tmp/gsd-s06-mounted-proof/health-ready.json`
  - `/tmp/gsd-s06-mounted-proof/system-config.json`
  - `/tmp/gsd-s06-mounted-proof/wuzapi-status.json`
  - `frontend-hormonia/test-results/runtime-no-firebase-runtim-*/route-smoke-evidence.json`
  - `frontend-hormonia/test-results/runtime-no-firebase-runtim-*/attachments/route-smoke-evidence-*.json`
  - `/tmp/gsd-s06-proof.env`
  - `/tmp/gsd-s06-browser-bootstrap`
drill_down_paths:
  - .gsd/milestones/M004/slices/S06/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S06/tasks/T02-SUMMARY.md
  - .gsd/milestones/M004/slices/S06/tasks/T03-SUMMARY.md
  - frontend-hormonia/tests/e2e/test-results/e2e-results.json
duration: 2h25m
verification_result: passed
completed_at: 2026-03-15T07:55:00-03:00
blocker_discovered: false
---

# S06: Prova integrada de runtime sem Firebase

**What was actually shipped:** a mounted, replayable proof runner plus seeded contract and routed Playwright smoke that proves auth/session and `/dashboard`, `/admin`, `/whatsapp` on a single live no-Firebase runtime contract, with no lingering seeded secrets in repo/artifacts.

## What Happened

- T01 and T02 were already completed, and this completion pass re-ran all slice verifications after confirming the runner and diagnostics remained truthful in current state.
- `run-mounted-proof.sh` consistently boots backend/frontend with blank Firebase vars, WuzAPI mock on, seeds proof credentials in `/tmp`, runs auth acceptance and route smoke, and persists phase/log/runtime artefacts.
- `seed-proof-user.py` continues to generate masked `/tmp/gsd-s06-proof.env` and bootstrap helper without persisting sensitive plaintext.
- `no-firebase-runtime-smoke.spec.ts` proved routed entry: `/admin` via `/login`, `/dashboard` via real `/api/v2/dashboard/main`, and `/whatsapp` via `/api/v2/monitoring/wuzapi/session/status` with `connected=true`, `logged_in=true`, `mock=true`.
- The mounted smoke was green only when invoked through the canonical runner path (`--smoke`, `--auth`, `--all`), preventing false skips from missing fixtures.

## Verification

- `bash .gsd/milestones/M004/slices/S01/verify-runtime-residue.sh --check all` — **PASS**
- `cd backend-hormonia && pytest -q tests/api/v2/test_system_auth_hard_cut_operational.py tests/integration/test_local_auth_core_flow.py tests/integration/test_auth_hard_cut_end_to_end.py` — **PASS**
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --auth` — **PASS**
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --smoke` — **PASS**
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all` — **PASS**
- `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --preflight && curl -fsS http://localhost:8000/health/ready && curl -fsS http://localhost:8000/api/v2/system/config` — **PASS**

Observed evidence:
- `frontend-hormonia/test-results/runtime-no-firebase-runtim-*/route-smoke-evidence.json` shows `phase: completed`, `lastSuccessfulRoute: /whatsapp`, and no `unexpectedFirebaseRequests`.
- `/tmp/gsd-s06-mounted-proof/health-ready.json` shows `dependencies.session_auth` healthy in session-first mode.
- `/tmp/gsd-s06-mounted-proof/system-config.json` has no `VITE_FIREBASE_*` and shows expected non-Firebase environment payload.
- `/tmp/gsd-s06-mounted-proof/wuzapi-status.json` returns `{connected: true, logged_in: true, mock: true}`.

## Requirements Advanced
- `R051`, `R052`: still active and out of scope for this slice.
- `R047`: now has mounted runtime evidence instead of only contract-level validation.
- `R053`: now has a replayable integrated runtime proof in the same running stack.

## Requirements Validated
- `R047` — Firebase sai de vez do runtime oficial.
- `R050` — O frontend oficial usa apenas o contrato canônico sem resíduo funcional de Firebase.
- `R053` — A convergência final fecha com prova integrada, não só com cleanup estático.

## Known Limitations
- `passlib` ainda loga um warning de compatibilidade com `bcrypt` durante bootstrap/seed; sem impacto de funcionalidade.
- O runner faz um encerramento curto após `--preflight` para o modo observabilidade; não mantém servidor longo além do necessário.

## Follow-ups
- `R051` e `R052` permanecem como dívida estruturural para M005/M006.
- Limpeza de compatibilidades e resíduos mortos fora do boundary operacional de S06 permanece para as próximas frentes.

## Forward Intelligence
### What the next slice should know
- Use `bash .gsd/milestones/M004/slices/S06/run-mounted-proof.sh --all` as the canonical replay for regressions touching auth/session + routed runtime proof.
- For direct Playwright reruns, use `/tmp/gsd-s06-browser-bootstrap` or `--all`; running the raw spec without seeded env vars is expected to skip.

### What's fragile
- The only reliable proof path is the mounted runner; ambient `/tmp/gsd-s06-proof.env` exists by design but is masked. Any direct spec-only replay without bootstrap helper will skip by design.

### Authoritative diagnostics
- `status.json` + `health-ready.json` + `wuzapi-status.json` are the fastest trust chain: they validate phase, liveness, and session/WuzAPI contract immediately after bootstrap.
- `route-smoke-evidence.json` is the route-proof source of truth for `/admin`, `/dashboard`, `/whatsapp` and whether any Firebase-like request leaked in.

### What assumptions changed
- Canonical reruns in this slice assume all smoke and auth acceptance must share the same mounted stack; a single browser-only spec replay is no longer considered sufficient unless seeded via `--auth/--smoke/--all` runner lifecycle.
