---
estimated_steps: 4
estimated_files: 6
---

# T03: Remove websocket `session_id` fallback across the official realtime seams

**Slice:** S03 — Frontend oficial convergido para contrato session-first canônico
**Milestone:** M004

## Description

Finish the transport cut on the realtime side. The main websocket manager, the generic hook, and the metrics hook all assemble URLs, so S03 is incomplete if any of them keep appending `session_id` query fallback. This task aligns all official realtime paths to the cookie-first contract while preserving the existing auth diagnostics that later slices and debugging still need.

## Steps

1. Update `frontend-hormonia/src/lib/websocket.ts` so the shared websocket manager no longer appends `session_id` query fallback when bootstrapping official connections.
2. Update `frontend-hormonia/src/hooks/useWebSocket.ts` and `frontend-hormonia/src/hooks/useMetricsWebSocket.ts` to follow the same cookie-first URL assembly and not reintroduce the legacy query transport.
3. Tighten `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` plus the focused hook tests so they assert the absence of `?session_id=` while preserving stable auth/connection diagnostics.
4. Re-run the realtime proof and keep any failure messaging anchored on the existing websocket auth codes rather than inventing a new debug surface.

## Must-Haves

- [ ] No official websocket bootstrap path emits `?session_id=`.
- [ ] The shared manager, generic hook, and metrics hook all follow the same cookie-first bootstrap rule.
- [ ] Existing websocket auth/connection diagnostics remain stable and inspectable.
- [ ] Realtime proof catches regressions in both integration and hook-level seams.

## Verification

- `cd frontend-hormonia && npx vitest run tests/integration/realtime/session-websocket-cutover.test.ts tests/unit/hooks/useWebSocket.test.ts tests/unit/hooks/useWebSocket.comprehensive.test.ts`

## Observability Impact

- Signals added/changed: websocket auth remains inspectable through the existing stable error codes and connection diagnostics, but the legacy query transport disappears from the official happy path.
- How a future agent inspects this: run the focused realtime Vitest pack and inspect which builder path still leaked `session_id` if a regression appears.
- Failure state exposed: the proof should make it obvious whether drift lives in the shared manager, the generic hook, or the metrics-specific hook.

## Inputs

- `.gsd/milestones/M004/slices/S03/tasks/T01-PLAN.md` — proof contract that now rejects websocket query fallback.
- `.gsd/milestones/M004/slices/S03/tasks/T02-PLAN.md` — HTTP/session-storage transport cut that this realtime cut must align with.
- `.gsd/milestones/M004/slices/S03/S03-RESEARCH.md` — identifies the three websocket seams that currently duplicate the fallback.

## Expected Output

- `frontend-hormonia/src/lib/websocket.ts` — shared websocket manager aligned to cookie-first bootstrap only.
- `frontend-hormonia/src/hooks/useWebSocket.ts` — generic hook without legacy `session_id` query assembly.
- `frontend-hormonia/src/hooks/useMetricsWebSocket.ts` — metrics hook aligned to the same rule.
- `frontend-hormonia/tests/integration/realtime/session-websocket-cutover.test.ts` — integration proof for the realtime transport cut.
- `frontend-hormonia/tests/unit/hooks/useWebSocket.test.ts` — focused hook-level regression coverage.
- `frontend-hormonia/tests/unit/hooks/useWebSocket.comprehensive.test.ts` — broader hook behavior proof that preserves diagnostics while dropping the fallback.
