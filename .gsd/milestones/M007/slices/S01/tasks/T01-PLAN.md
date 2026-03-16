---
estimated_steps: 5
estimated_files: 2
---

# T01: Criar suite de testes focada em expects_response e diagnosticar o bug de bulk

**Slice:** S01 — Corrigir sequenciamento e espera de resposta
**Milestone:** M007

## Description

Criar uma suite de testes que isola o comportamento de `expects_response` por mensagem em cada send_mode, especialmente `sequential_auto`. Reproduzir o bug de disparo em bulk como um teste que falha, confirmando o diagnóstico antes de qualquer fix.

## Steps

1. Ler `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py` para entender as fixtures/mocks existentes e reutilizar o padrão.
2. Criar `test_sequencing_expects_response.py` com fixtures mínimas: mock `SequentialMessageHandler` com `whatsapp_service.send_message` retornando True, mock `db.commit`, mock `flow_state` com `step_data={}`.
3. Implementar `test_sequential_auto_stops_at_expects_response`: 3 mensagens, msg[1] com `expects_response=true`. Chamar `_send_all_sequential`. Verificar que `send_message` foi chamado exatamente 2 vezes, e `step_data` tem `awaiting_response=True` e `current_day_message_index=1`.
4. Implementar `test_sequential_auto_all_false_sends_all`: 3 mensagens todas com `expects_response=false`. Verificar que `send_message` foi chamado 3 vezes e dia avança.
5. Implementar `test_continuation_after_response_respects_expects_response`: chamar `_send_remaining_after_response` com start_index=2, msg[2] com `expects_response=true`. Verificar que para e espera.
6. Implementar `test_wait_each_stops_at_first_expects_response`: usar `_send_wait_each_with_auto_advance` com msg[0] `expects_response=false`, msg[1] `expects_response=true`. Verificar que envia msg[0], avança, envia msg[1], e para.
7. Rodar todos os testes e documentar quais passam/falham no código atual (pre-fix).

## Must-Haves

- [ ] `test_sequencing_expects_response.py` existe com pelo menos 4 testes
- [ ] `test_sequential_auto_stops_at_expects_response` falha no código atual (reprodução do bug)
- [ ] `test_sequential_auto_all_false_sends_all` passa no código atual
- [ ] `test_wait_each_stops_at_first_expects_response` passa no código atual

## Verification

- `cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py -vv` — executa sem erros de import, testes de reprodução do bug falham como esperado
- `cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequential_message_handler.py -vv` — testes existentes continuam verdes

## Inputs

- `backend-hormonia/tests/unit/services/flow/test_sequential_message_handler.py` — padrão de fixtures existente
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py` — código a ser testado

## Expected Output

- `backend-hormonia/tests/unit/services/flow/test_sequencing_expects_response.py` — suite nova com reprodução confirmada do bug

## Observability Impact

- **Signals changed:** None (test-only task). No runtime code modified.
- **How to inspect:** Run the test suite — `test_sequential_auto_stops_at_expects_response` failing confirms the bulk-send bug is active. After T02 fix, it passing confirms the bug is resolved.
- **Failure state:** If the bug test passes pre-fix, the diagnosis is wrong and the slice plan needs revision. If tests fail with import errors, the shim pattern needs updating.
