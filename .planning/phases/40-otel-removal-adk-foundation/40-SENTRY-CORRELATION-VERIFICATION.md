# Phase 40 Sentry Correlation Verification

## Probe Artifacts

- Baseline: `.planning/phases/40-otel-removal-adk-foundation/40-SENTRY-CORRELATION-BASELINE.json`
- Post-removal: `.planning/phases/40-otel-removal-adk-foundation/40-SENTRY-CORRELATION-POST.json`

## Baseline vs Post

| metric | baseline | post | check |
| --- | --- | --- | --- |
| trace_linked | true | true | PASS |
| span_depth | 3 | 3 | PASS (`post >= baseline`) |
| fastapi_transaction | `phase40.fastapi.request` | `phase40.fastapi.request` | PASS |
| celery_task_transaction | `phase40.celery.task` | `phase40.celery.task` | PASS |

## Verdict

correlation_continuity: PASS

Rationale: the post-removal probe preserves FastAPI->Celery linkage (`trace_linked=true`) and does not regress depth (`span_depth` unchanged at 3).
