---
id: T02
parent: S04
milestone: M008
provides:
  - Patient onboarding saga now supports AsyncSession during flow initialization/activation
  - Real patient + active onboarding flow created in local runtime
  - Welcome message persisted and manually dispatched through send_scheduled_message to WuzAPI
key_files:
  - backend-hormonia/app/services/patient/flow_service.py
  - backend-hormonia/app/api/v2/routers/patients/crud.py
  - backend-hormonia/tests/unit/services/test_patient_flow_service_async.py
key_decisions:
  - Adapt PatientFlowService to work with AsyncSession in saga paths instead of assuming synchronous repositories/query()
  - Refresh/reload created patient before serialization in POST /api/v2/patients to avoid MissingGreenlet after async commit
patterns_established:
  - For mixed sync/async runtime code paths, add resolver helpers instead of awaiting Session methods/results directly
  - Manual welcome recovery path: send pending message via app.tasks.messaging.send_scheduled_message when beat is not running
observability_surfaces:
  - SQL: patient_onboarding_saga, patients, patient_flow_states (+ flow_kinds join), messages
  - Runtime logs: saga step logs in backend, send_scheduled_message + process_daily_flows logs in celery
  - Persisted flow state: patient_flow_states.step_data / next_scheduled_at
  - Persisted message state: messages.status / delivery_status / sent_at
duration: 1h15m
verification_result: partial
completed_at: 2026-03-16 13:33 GMT-3
blocker_discovered: false
---

# T02: Trigger manual de process_daily_flows e mensagem do dia

**Corrigi o primeiro bloqueio real do slice (saga com AsyncSession), criei o paciente/flow reais e enviei o welcome via worker; o trigger manual de process_daily_flows ainda falha no FlowCore híbrido e a mensagem diária não foi entregue nesta execução.**

Além disso, iniciei a adaptação do caminho do FlowCore/EnhancedFlowEngine usado por `process_daily_flows` para aceitar `Session` síncrona no mesmo padrão híbrido (`_resolve/_execute/_commit`) em:
- `backend-hormonia/app/services/flow/core/operations.py`
- `backend-hormonia/app/services/flow/core/transitions.py`
- `backend-hormonia/app/services/enhanced_flow_engine_pkg/service.py`
- `backend-hormonia/app/services/enhanced_flow_engine_pkg/orchestration.py`
- `backend-hormonia/app/services/enhanced_flow_engine_pkg/conversation.py`

Esses edits ficaram **compilando** (`py_compile`), mas não foram revalidados no runtime antes do timeout duro.

## What Happened

O arquivo `.gsd/milestones/M008/slices/S04/tasks/T02-PLAN.md` não existia no worktree, então executei usando o contrato do `S04-PLAN.md` e o estado real do runtime.

Ao tentar cumprir o T02, o pré-requisito do T01 estava ausente: não havia paciente ativo no banco. Reproduzi o fluxo real via `POST /api/v2/patients` e encontrei o primeiro bug concreto do slice: `PatientFlowService` recebia `AsyncSession` da saga, mas ainda chamava `query()/flush()/commit()` síncronos. Isso quebrava o step `initialize_flow` com `AttributeError: 'AsyncSession' object has no attribute 'query'`.

Corrigi `backend-hormonia/app/services/patient/flow_service.py` para suportar o caminho híbrido sync/async no onboarding:
- seleção de `FlowKind` via `select(...)` quando a sessão é async
- `flush/commit/rollback/refresh` via helper que aceita awaitable ou resultado síncrono
- `activate_patient()` e `pause_patient()` atualizando o `Patient` sem depender do repository síncrono quando a sessão é async
- `delete_flow()` também passou a tolerar sessão async

Adicionei testes unitários cobrindo esse regressão path em `backend-hormonia/tests/unit/services/test_patient_flow_service_async.py`.

Depois disso, a saga completou os 4 steps e persistiu:
- `patients.flow_state = active`
- `patient_flow_states.current_step = 1`
- `messages` com a welcome message em `pending`
- `patient_onboarding_saga.status = COMPLETED`

A rota ainda devolveu `400` após a saga por causa de serialização pós-commit (`MissingGreenlet` ao acessar atributos expirados do paciente retornado). Corrigi o ponto em `backend-hormonia/app/api/v2/routers/patients/crud.py` para refrescar/recarregar o paciente antes de `serialize_patient(created)`. Esse ajuste ficou em disco, mas não consegui revalidar completamente a resposta HTTP final antes do timeout duro.

Como o stack local não estava com beat enviando a welcome automaticamente, disparei manualmente `app.tasks.messaging.send_scheduled_message` para a mensagem pendente. O worker real consumiu o task e a welcome foi marcada como `sent` no banco.

Na etapa central do T02, chamei `process_daily_flows_async` manualmente via script Python. O processamento encontrou o flow real, mas falhou com:
- `object ChunkedIteratorResult can't be used in 'await' expression`

Esse erro ocorre no caminho de `process_daily_flows` que ainda passa por partes do FlowCore/EnhancedFlowEngine que assumem `AsyncSession` e fazem `await self.db.execute(...)` mesmo quando o batch está rodando com `Session` síncrona. Cheguei a iniciar a adaptação desse caminho, mas não finalizei nem revalidei a mensagem diária antes do timeout.

## Verification

### Passes confirmados

- `PYTHONPATH=backend-hormonia backend-hormonia/.venv/bin/pytest -q backend-hormonia/tests/unit/services/test_patient_flow_service_async.py`
  - **PASS** — 3 testes cobrindo `initialize_default_flow()` e `activate_patient()` com sessão async.

- Runtime real de criação do paciente
  - **PASS (persistência/saga)** — patient e flow reais criados no banco.
  - Evidência observada em SQL:
    - `patients`: paciente `b316f644-e253-47f3-9b1f-189786942ec6` com `flow_state=active`, `current_day=1`
    - `patient_flow_states`: flow onboarding associado ao paciente com `current_step=1`
    - `patient_onboarding_saga`: saga `9210fa75-b674-453a-a533-beccc34b0c0b` com `status=COMPLETED`, `current_step=4`

- Welcome message via worker real
  - Task disparado manualmente: `app.tasks.messaging.send_scheduled_message.delay('eb165744-3ea7-4288-9e9c-5d3aa8fb5441')`
  - **PASS** no worker: log `Successfully sent scheduled message eb165744-3ea7-4288-9e9c-5d3aa8fb5441`
  - **PASS** no banco: `messages.status = sent`, `delivery_status = sent`, `sent_at` preenchido

### Falhas / não concluído

- Trigger manual do ciclo diário
  - Script executado: `async_to_sync(process_daily_flows_async)(10)`
  - **FAIL** — retorno:
    - `processed_count: 1`
    - `success_count: 0`
    - `error_count: 1`
    - erro: `object ChunkedIteratorResult can't be used in 'await' expression`
  - Consequência: nenhuma mensagem diária nova foi criada/enviada.

- Slice-level verification
  - `SELECT id, name, flow_state FROM patients WHERE phone_hash IS NOT NULL` — **PASS** (com adaptação factual: agora há paciente ativo)
  - `SELECT patient_id, flow_type, status, current_step FROM patient_flow_states WHERE status = 'active'` — **FAIL no SQL do plano** porque a tabela real não tem coluna `flow_type`; usei join com `flow_template_versions` + `flow_kinds` para observar `kind_key`
  - `SELECT content, status, direction FROM messages WHERE patient_id = '<id>' ORDER BY created_at` — **PASS parcial** para welcome; **FAIL** para daily message (a segunda mensagem não existe)
  - Verificação visual no WhatsApp — **não registrada nesta execução**; eu só confirmei a saída do worker e o status `sent` no banco

## Diagnostics

### Como reinspecionar rapidamente

- Paciente ativo:
  - `SELECT id, name, flow_state, current_day FROM patients ORDER BY created_at DESC LIMIT 5`

- Flow ativo com flow_type real:
  - ```sql
    SELECT pfs.patient_id, fk.kind_key AS flow_type, pfs.status, pfs.current_step, pfs.next_scheduled_at, pfs.step_data
    FROM patient_flow_states pfs
    JOIN flow_template_versions ftv ON ftv.id = pfs.flow_template_version_id
    JOIN flow_kinds fk ON fk.id = ftv.flow_kind_id
    WHERE pfs.patient_id = 'b316f644-e253-47f3-9b1f-189786942ec6';
    ```

- Mensagens do paciente:
  - ```sql
    SELECT id, content, status, direction, sent_at, delivery_status, created_at
    FROM messages
    WHERE patient_id = 'b316f644-e253-47f3-9b1f-189786942ec6'
    ORDER BY created_at;
    ```

- Saga:
  - `SELECT id, patient_id, status, current_step, error_message, error_type, created_at FROM patient_onboarding_saga ORDER BY created_at DESC LIMIT 5`

- Logs úteis:
  - backend atual: processo uvicorn do worktree M008
  - celery: `.gsd/runtime-logs/m008-celery.log`
  - procurar por:
    - `Successfully sent scheduled message`
    - `Starting async daily flow processing`
    - `object ChunkedIteratorResult can't be used in 'await' expression`

## Deviations

- O plano específico `T02-PLAN.md` não existia no worktree; executei pelo `S04-PLAN.md`.
- O T01 não havia deixado um paciente pronto; precisei cumprir o pré-requisito dentro desta execução para conseguir chegar ao T02.
- A query de verificação do slice para `patient_flow_states.flow_type` não corresponde ao schema real; a observação correta exigiu join com `flow_template_versions` e `flow_kinds`.
- Como não havia beat entregando a welcome automaticamente durante a janela da execução, enviei a welcome pendente manualmente via `send_scheduled_message` para avançar a prova operacional.

## Known Issues

- `process_daily_flows` ainda quebra no caminho híbrido sync/async do FlowCore/EnhancedFlowEngine com `object ChunkedIteratorResult can't be used in 'await' expression`.
- A correção do `POST /api/v2/patients` para evitar `MissingGreenlet` ficou escrita em disco, mas a resposta HTTP final (`201`/payload) não foi revalidada antes do timeout.
- A mensagem diária do onboarding **não foi enviada** nesta execução.
- A confirmação visual no telefone para welcome/daily **não foi coletada** nesta execução.

## Files Created/Modified

- `backend-hormonia/app/services/patient/flow_service.py` — compatibilizei `PatientFlowService` com `AsyncSession` na saga (seleção de flow kind, flush/commit/rollback/refresh, activate/pause/delete flow)
- `backend-hormonia/app/api/v2/routers/patients/crud.py` — refresco/reload do paciente criado antes de serialização para evitar `MissingGreenlet` após commit async
- `backend-hormonia/app/services/flow/core/operations.py` — iniciei helper `_resolve/_execute/_commit/_flush/_refresh` para compatibilidade sync/async no FlowCore
- `backend-hormonia/app/services/flow/core/transitions.py` — passei queries/rollback do mixin de transições para os helpers híbridos do FlowCore
- `backend-hormonia/app/services/enhanced_flow_engine_pkg/service.py` — resolução de `flow_type` passou a usar helper híbrido `_execute`
- `backend-hormonia/app/services/enhanced_flow_engine_pkg/orchestration.py` — consultas do `generate_flow_message()` migradas para `_execute`
- `backend-hormonia/app/services/enhanced_flow_engine_pkg/conversation.py` — histórico/conversas do gerador migrados para `_execute`
- `backend-hormonia/tests/unit/services/test_patient_flow_service_async.py` — testes de regressão para `initialize_default_flow()` e `activate_patient()` com sessão async

## Resume Notes

1. Revalidar `POST /api/v2/patients` com um paciente novo ou via cenário controlado para confirmar que o fix de serialização removeu o `400`.
2. Finalizar a compatibilidade sync/async no caminho do FlowCore usado por `process_daily_flows`:
   - `backend-hormonia/app/services/flow/core/operations.py`
   - `backend-hormonia/app/services/flow/core/transitions.py`
   - `backend-hormonia/app/services/enhanced_flow_engine_pkg/service.py`
   - `backend-hormonia/app/services/enhanced_flow_engine_pkg/orchestration.py`
   - `backend-hormonia/app/services/enhanced_flow_engine_pkg/conversation.py`
3. Reexecutar `process_daily_flows_async(10)` ou o equivalente via Celery.
4. Confirmar no banco:
   - novo registro em `messages` para o paciente `b316f644-e253-47f3-9b1f-189786942ec6`
   - `patient_flow_states.step_data.last_message_sent` preenchido
5. Solicitar confirmação visual ao usuário no WhatsApp para welcome + daily message.
