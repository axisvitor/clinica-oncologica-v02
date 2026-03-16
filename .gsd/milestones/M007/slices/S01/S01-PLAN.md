# S01: Corrigir sequenciamento e espera de resposta

**Goal:** Garantir que o envio de mensagens do dia respeite rigorosamente a flag `expects_response` por mensagem — quando uma mensagem espera resposta, nenhuma mensagem seguinte é enviada até o paciente responder. Eliminar o bug de disparo em bulk.
**Demo:** Testes focados provam que: (1) com 3 mensagens onde a segunda tem `expects_response=true`, apenas as 2 primeiras são enviadas e o estado fica `awaiting_response=true` no index 1; (2) após resposta, a terceira mensagem é enviada; (3) com todas `expects_response=false`, todas são enviadas numa sequência com delay entre elas.

## Must-Haves

- Mensagens com `expects_response=true` bloqueiam o envio das seguintes até o paciente responder
- Mensagens com `expects_response=false` são enviadas em sequência com delay entre elas
- O estado `awaiting_response` é persistido atomicamente em `PatientFlowState.step_data`
- O `send_mode=sequential_auto` (o modo que dispara tudo de uma vez) trata `expects_response` por mensagem, não bloqueia apenas na última
- A continuação após resposta (`_send_remaining_after_response`) respeita `expects_response` em cada mensagem restante
- Testes cobrindo: disparo sequencial sem espera, disparo com espera no meio, continuação pós-resposta, idempotência em re-envio

## Proof Level

- This slice proves: contract
- Real runtime required: no (testes unitários com mocks de WhatsApp e DB)
- Human/UAT required: no

## Verification

- `cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py -vv` — todos os testes passam
- `cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequential_message_handler.py -vv` — testes existentes continuam verdes
- `cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/test_flow_advance_awaiting_response_block.py -vv` — testes existentes continuam verdes

## Observability / Diagnostics

- Runtime signals: `awaiting_response`, `current_day_message_index`, `pending_response_context` persistidos em `PatientFlowState.step_data`; structured logs em `_send_all_sequential` e `_send_remaining_after_response` com `expects_response` por mensagem
- Inspection surfaces: `PatientFlowState.step_data` no banco (query direto)
- Failure visibility: se o estado ficar inconsistente, `load_flow_context` retorna `status: "waiting"` impedindo envio duplicado
- Redaction constraints: `patient_id` como UUID, sem PII em logs de fluxo

## Integration Closure

- Upstream surfaces consumed: nenhuma (primeiro slice)
- New wiring introduced in this slice: nenhum — refinamento de lógica existente
- What remains before the milestone is truly usable end-to-end: editor de templates (S03), armazenamento de respostas (S04), resumo IA (S06)

## Tasks

- [ ] **T01: Criar suite de testes focada em expects_response e diagnosticar o bug de bulk** `est:45m`
  - Why: O bug de disparo em bulk precisa primeiro de uma reprodução precisa via testes, antes de qualquer fix. A suite existente (`test_sequential_message_handler.py`, 610 linhas) cobre cenários gerais mas não isola o comportamento de `expects_response` no meio da sequência com `send_mode=sequential_auto`.
  - Files: `backend-hormonia/tests/unit/services/flow/test_sequencing_expects_response.py` (novo), `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py`
  - Do: Criar `test_sequencing_expects_response.py` com fixtures mínimas (mock WhatsApp, mock DB, mock flow_state). Testes: (1) `test_sequential_auto_stops_at_expects_response` — 3 mensagens, segunda com `expects_response=true`, verifica que só 2 são enviadas e estado fica `awaiting_response=true` no index 1; (2) `test_sequential_auto_all_false_sends_all` — 3 mensagens sem espera, todas enviadas; (3) `test_wait_each_stops_at_first_expects_response` — já existente mas re-confirmar; (4) `test_continuation_after_response_respects_expects_response` — após resposta, se mensagem 3 tem `expects_response=true`, para e espera de novo. Rodar contra o código atual para identificar exatamente onde falha.
  - Verify: `cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py -vv` — os testes que reproduzem o bug devem FALHAR (reprodução confirmada)
  - Done when: Suite criada com pelo menos 4 testes, testes de reprodução do bug de bulk falham demonstrando o comportamento incorreto, testes de comportamento correto em `wait_each` passam.

- [ ] **T02: Corrigir `_send_all_sequential` para respeitar `expects_response` por mensagem** `est:30m`
  - Why: O método `_send_all_sequential` itera todas as mensagens e só verifica `expects_response` na última (`messages[-1].get("expects_response", False)`). Uma mensagem no meio com `expects_response=true` é ignorada. Este é o root cause do bug de disparo em bulk.
  - Files: `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py`
  - Do: Modificar `_send_all_sequential` para verificar `expects_response` em cada mensagem do loop. Quando `msg.get("expects_response", False)` for True, parar o loop, persistir `awaiting_response=true` no index atual via `_set_flow_progress`, e retornar `status: "waiting"` com o `message_index`. Garantir que `_send_remaining_after_response` já está correto (review mostra que ele já verifica `expects_response` por mensagem — confirmar). Atualizar logging para incluir `expects_response` em cada iteração.
  - Verify: `cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py -vv` — TODOS os testes passam incluindo o que antes reproduzia o bug. `cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequential_message_handler.py -vv` — testes existentes continuam verdes.
  - Done when: `_send_all_sequential` para no primeiro `expects_response=true`, suite de testes toda verde, testes existentes não quebrados.

- [ ] **T03: Validar edge cases e confirmar testes existentes verdes** `est:20m`
  - Why: O fix precisa ser validado contra edge cases e não pode quebrar o suite existente de 610 linhas. Edge cases: day_config sem `send_mode` (default `single`), re-envio idempotente quando já em `awaiting_response`, `_send_wait_each_with_auto_advance` com mix de `expects_response` true/false.
  - Files: `backend-hormonia/tests/unit/services/flow/test_sequencing_expects_response.py`, `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py`
  - Do: Adicionar testes de edge case ao `test_sequencing_expects_response.py`: (1) day_config com `send_mode` omitido (default "single") — deve enviar só a primeira mensagem; (2) chamada a `send_day_messages` quando já em `awaiting_response` — deve retornar `status: "waiting"` sem enviar nada (idempotência); (3) sequência com `expects_response` no primeiro e último — verificar que para no primeiro. Rodar full suite de testes existentes para confirmar nada quebrou.
  - Verify: `cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py tests/unit/services/flow/test_sequential_message_handler.py tests/unit/services/test_flow_advance_awaiting_response_block.py -vv` — tudo verde
  - Done when: Todos os edge cases cobertos e verdes, suites existentes inalteradas.

## Files Likely Touched

- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py` — fix principal no `_send_all_sequential`
- `backend-hormonia/tests/unit/services/flow/test_sequencing_expects_response.py` — suite nova de testes focados
