---
estimated_steps: 4
estimated_files: 2
---

# T03: Validar edge cases e confirmar testes existentes verdes

**Slice:** S01 — Corrigir sequenciamento e espera de resposta
**Milestone:** M007

## Description

Após o fix principal em T02, validar edge cases que poderiam causar regressões e confirmar que toda a suite existente de testes de fluxo continua verde.

## Steps

1. Adicionar testes de edge case ao `test_sequencing_expects_response.py`:
   - `test_default_send_mode_single_sends_only_first`: day_config sem `send_mode` (default `"single"`) com 3 mensagens — verifica que só a primeira é enviada.
   - `test_idempotent_when_already_awaiting`: chamar `send_day_messages` quando `step_data` já tem `awaiting_response=true` e `current_flow_day` igual — verifica que retorna `status: "waiting"` sem enviar nada.
   - `test_expects_response_on_first_message_stops_immediately`: msg[0] com `expects_response=true` — verifica que apenas msg[0] é enviada e estado fica `awaiting_response=true` no index 0.
   - `test_expects_response_on_last_message_sends_all_then_waits`: msg[2] (última) com `expects_response=true` — verifica que as 3 são enviadas e estado fica `awaiting_response=true` no index 2 (este caso deve funcionar igual ao código original, confirmando não-regressão).
2. Rodar a suite completa de testes existentes de fluxo para confirmar não-regressão.
3. Rodar testes adjacentes que validam o fluxo: `test_flow_advance_awaiting_response_block`, `test_sequential_response_gate`, `test_flow_functions_split_contract`.
4. Documentar resultado final no summary.

## Must-Haves

- [ ] Edge cases cobertos: default single, idempotência, expects_response na primeira, expects_response na última
- [ ] Todos os testes existentes de fluxo continuam verdes
- [ ] Nenhuma regressão em testes adjacentes

## Verification

- `cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py tests/unit/services/flow/test_sequential_message_handler.py tests/unit/services/test_flow_advance_awaiting_response_block.py tests/unit/services/flow/test_sequential_response_gate.py tests/unit/services/flow/test_flow_functions_split_contract.py -vv` — tudo verde
- `cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/ -vv` — diretório inteiro verde

## Inputs

- T02: fix em `_send_all_sequential`
- Suites existentes de teste

## Expected Output

- `backend-hormonia/tests/unit/services/flow/test_sequencing_expects_response.py` — edge cases adicionados
- Confirmação de que toda a suite de testes de fluxo está verde
