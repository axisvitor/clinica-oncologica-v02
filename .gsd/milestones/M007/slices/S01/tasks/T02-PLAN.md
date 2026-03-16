---
estimated_steps: 4
estimated_files: 1
---

# T02: Corrigir `_send_all_sequential` para respeitar `expects_response` por mensagem

**Slice:** S01 — Corrigir sequenciamento e espera de resposta
**Milestone:** M007

## Description

Corrigir o root cause do bug de disparo em bulk: `_send_all_sequential` verifica `expects_response` apenas na última mensagem da lista. Uma mensagem no meio com `expects_response=true` é ignorada e as seguintes são disparadas. O fix faz cada iteração do loop verificar a flag e parar quando encontra `expects_response=true`.

## Steps

1. Ler `_send_all_sequential` em `sequencing.py`. Identificar a seção no final que verifica `messages[-1].get("expects_response", False)` — este é o check que acontece **depois** de já ter enviado tudo.
2. Mover a verificação de `expects_response` para **dentro do loop**, logo após o envio de cada mensagem. Quando `msg.get("expects_response", False)` for True: chamar `_set_flow_progress` com `awaiting_response=True` no index atual, e retornar `{"status": "waiting", "message_index": i, "awaiting_response": True, "sent_count": sent_count}`.
3. Se nenhuma mensagem tinha `expects_response=true`, manter o comportamento atual: chamar `advance_day_atomic` ao final.
4. Review `_send_remaining_after_response` — confirmar que já respeita `expects_response` por mensagem (o código existente já faz isso corretamente com o check dentro do loop).
5. Adicionar log structurado quando o envio para por `expects_response`: logger.info com patient_id, flow_kind, day_number, stopped_at_index.

## Must-Haves

- [ ] `_send_all_sequential` verifica `expects_response` em cada mensagem durante o loop, não só na última
- [ ] Quando `expects_response=true` no meio da sequência, o envio para e retorna `status: "waiting"`
- [ ] Quando nenhuma mensagem espera resposta, o dia avança normalmente
- [ ] `_send_remaining_after_response` continua funcionando corretamente (sem regressão)

## Verification

- `cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequencing_expects_response.py -vv` — TODOS passam (incluindo o que antes falhava)
- `cd backend-hormonia && .venv/bin/pytest -q tests/unit/services/flow/test_sequential_message_handler.py -vv` — existentes verdes

## Observability Impact

- **New structured log**: `logger.info("Sequential send stopped at expects_response message", ...)` in `_send_all_sequential` emits `patient_id`, `flow_kind`, `day_number`, `stopped_at_index`, `sent_count` whenever the loop halts mid-sequence.
- **State persistence**: `PatientFlowState.step_data` now correctly records `awaiting_response=True` and `current_day_message_index` at the exact index where sending stopped (not just at the end).
- **Inspection**: `SELECT step_data->'awaiting_response', step_data->'current_day_message_index' FROM patient_flow_states WHERE status='active'` shows per-patient wait state. Before this fix, mid-sequence waits were invisible.
- **Failure shape**: If a message with `expects_response=True` fails to send, the method returns `{"status": "error"}` before persisting any wait state — no orphaned awaiting flags.

## Inputs

- T01: suite de testes com reprodução confirmada do bug (testes que falhavam)
- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py` — código a corrigir

## Expected Output

- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/sequencing.py` — `_send_all_sequential` corrigido
