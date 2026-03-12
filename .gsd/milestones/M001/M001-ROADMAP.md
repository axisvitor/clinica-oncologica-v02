# M001: Bulletproof Flow Pipeline

**Vision:** Sistema de acompanhamento oncologico via WhatsApp que envia questionarios humanizados aos pacientes entre consultas, permitindo que medicos acompanhem seus pacientes de forma continua.

## Success Criteria

- Sequential gate context mismatches recover via bounded retry/reset instead of leaving patients silently stuck.
- Failed outbound sends and deferred follow-ups retry automatically, and day advancement is atomic and verified.
- Stalled flows are detected/recovered automatically, while operators can inspect and intervene through admin APIs.
- Flow health, stall alerts, AI fallback metrics, and correlation IDs make the pipeline observable end-to-end.
- Integration tests prove the webhook -> gate -> continuation -> send pipeline plus recovery/retry paths.

## Slices

- [x] **S01: Pipeline Reliability** `risk:medium` `depends:[]`
  > After this: Fix silent patient stall when sequential gate encounters a context mismatch.
- [x] **S02: Flow Recovery** `risk:medium` `depends:[S01]`
  > After this: Detect stuck patient flows automatically and recover them via periodic Celery Beat task.
- [x] **S03: Flow Observability** `risk:medium` `depends:[S02]`
  > After this: Create a flow health API endpoint that returns real-time counts of active, stalled, failed, and completed flows, plus a stall alert mechanism that fires structured logs and optional webhook notifications when patients are stuck.
- [x] **S04: Pipeline Verification** `risk:medium` `depends:[S03]`
  > After this: Create integration tests that exercise the full pipeline from webhook arrival through sequential gate, continuation dispatch, and next question send.
