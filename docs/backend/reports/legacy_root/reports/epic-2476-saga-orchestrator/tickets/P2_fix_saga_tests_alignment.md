# [P2] Fix Saga Test Suite Alignment (Fixtures + Retry/Error Coverage)

## Contexto
Integration and orchestration tests are out of sync with current models/fixtures, and retry/error paths lack coverage.

## Problema Atual
- Concurrency tests refer to missing fixture `saga_orchestrator`.
- Compensation integration test uses `User(username=...)` which is not a model field.
- No retry/error tests are selected in orchestration suite.

## Solucao Proposta
- Update integration fixtures to use `real_saga_orchestrator` and current User fields.
- Update compensation tests to align with `SagaCompensator` or orchestrator API.
- Add retry scheduling tests and error path tests in orchestration suite.

## Criterios de Aceitacao
- [ ] Concurrency tests execute using valid fixture.
- [ ] Compensation integration tests create User with valid fields.
- [ ] Orchestration suite includes retry/error tests.
- [ ] Tests pass with a test database configured.

## Arquivos Afetados
- `backend-hormonia/tests/integration/test_saga_concurrency.py`
- `backend-hormonia/tests/integration/test_saga_compensation.py`
- `backend-hormonia/tests/orchestration/test_saga_orchestrator.py`
- `backend-hormonia/tests/services/test_saga_compensation.py`

## Estimativa
7 horas

## Prioridade
P2 - Test reliability and coverage

## Relacionado
- Finding #6 e #7 da revisao profunda
- `spec:2476b16c-c6a7-4898-b766-97a1afddde2d/d1332ecb-75e9-44fa-befe-84f61fd01514`
