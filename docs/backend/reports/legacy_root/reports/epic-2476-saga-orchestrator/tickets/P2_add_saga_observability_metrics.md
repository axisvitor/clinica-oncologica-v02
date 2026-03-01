# [P2] Add Saga Orchestrator Observability Metrics

## Contexto
Saga execution and compensation lack Prometheus metrics, limiting operational visibility.

## Problema Atual
- No counters/histograms for saga execution, compensation, or duration.
- No active saga gauge.

## Solucao Proposta
- Add metrics:
  - `saga_executions_total{status=success|failed}`
  - `saga_compensations_total{status=success|failed}`
  - `saga_duration_seconds{step=1|2|3|4}`
  - `saga_active_count`

## Criterios de Aceitacao
- [ ] Metrics emitted for saga start, completion, failure.
- [ ] Compensation metrics emitted on success/failure.
- [ ] Duration histogram captured per step.
- [ ] Metrics visible in `/metrics` endpoint.

## Arquivos Afetados
- `backend-hormonia/app/orchestration/saga_orchestrator/orchestrator.py`
- `backend-hormonia/app/orchestration/saga_orchestrator/compensation.py`

## Estimativa
5 horas

## Prioridade
P2 - Observability improvement

## Relacionado
- Finding #5 da revisao profunda
- `spec:2476b16c-c6a7-4898-b766-97a1afddde2d/d1332ecb-75e9-44fa-befe-84f61fd01514`
