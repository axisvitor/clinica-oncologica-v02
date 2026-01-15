# [P2] Align Compensation Backoff and Failure TTL with Spec

Status: ✅ RESOLVED

## Contexto
The spec defines compensation backoff (1s, 2s, 4s) and failure TTL (30 days). Alignment is now complete.

## Problema Atual
- No action required; backoff and TTL align with the spec.

## Solucao Proposta
- Already implemented; keep for historical reference only.

## Criterios de Aceitacao
- [x] Backoff matches 1s, 2s, 4s.
- [x] Redis failure TTL is 30 days.
- [ ] Tests cover backoff timing expectations.

## Arquivos Afetados
- `backend-hormonia/app/orchestration/saga_orchestrator/compensation.py`

## Estimativa
3 horas

## Prioridade
P2 - Spec compliance and observability retention

## Relacionado
- Finding #4 da revisao profunda
- `spec:2476b16c-c6a7-4898-b766-97a1afddde2d/d1332ecb-75e9-44fa-befe-84f61fd01514`
