# [P1] Implement Saga Retry Scheduling with Exponential Backoff

Status: ✅ RESOLVED (implemented in `backend-hormonia/app/tasks/saga_retry.py`)

## Contexto
Retry scheduling is implemented via periodic tasks in `saga_retry.py`.

## Problema Atual
- No action required. Retry scheduling exists and runs via `scan_and_retry_failed_sagas`.

## Solucao Proposta
- Already implemented; keep for historical reference only.

## Criterios de Aceitacao
- [x] Failed sagas are scheduled for retry with exponential backoff.
- [x] `retry_count` increments on each retry attempt.
- [x] `next_retry_at` is set and persisted.
- [x] Retries stop at `max_retries` and mark saga as FAILED.
- [ ] Unit tests validate retry scheduling and backoff timing.

## Arquivos Afetados
- `backend-hormonia/app/orchestration/saga_orchestrator/orchestrator.py`
- `backend-hormonia/app/models/patient_onboarding_saga.py`
- `backend-hormonia/app/orchestration/saga_orchestrator/persistence.py`

## Estimativa
8 horas

## Prioridade
P1 - High impact on reliability and recovery

## Relacionado
- Finding #3 da revisao profunda
- `spec:2476b16c-c6a7-4898-b766-97a1afddde2d/d1332ecb-75e9-44fa-befe-84f61fd01514`
