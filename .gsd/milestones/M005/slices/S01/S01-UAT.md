# S01: Alembic operável sem segredos de runtime — UAT

**Milestone:** M005
**Written:** 2026-03-14T16:09:58-03:00

## UAT Type

- UAT mode: live-runtime
- Why this mode is sufficient: o comportamento-alvo da slice é operacional de CLI+migração contra Postgres real; não é uma prova estática nem uma revisão manual de código.

## Preconditions

- Dependências Python do backend instaladas e executáveis em `backend-hormonia`.
- Um Postgres local descartável acessível em `postgresql://postgres:postgres@localhost:55432/hormonia_test`, ou outro URL equivalente substituído nos comandos abaixo.
- A shell consegue executar comandos com ambiente scrubbed via `env -i PATH="$PATH" HOME="$HOME" ...`.
- Não configure WuzAPI/Firebase env vars para os checks scrubbed; a UAT existe justamente para provar que eles não são necessários.

## Smoke Test

- Execute: `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py`
- Esperado: o pack termina verde (`9 passed` no fechamento da slice) e não há falha mencionando segredos/runtime de WuzAPI, Firebase ou `app.config.settings`.

## Test Cases

### 1. Pack completo de operabilidade em Postgres real

1. Execute: `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py`
2. Observe o resultado final da suíte.
3. **Expected:** a suíte fica verde e cobre bootstrap scrubbed, graph load, `history`, `heads`, `upgrade head` e `current`.

### 2. Inspeção scrubbed do grafo pela CLI real

1. Execute: `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini history`
2. Execute: `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini heads`
3. **Expected:** `history` imprime o encadeamento completo desde `<base>` até `lgpd03_add_ai_audit_event_types`; `heads` imprime exatamente `lgpd03_add_ai_audit_event_types (head)`.

### 3. Replay limpo até o head sem segredos de runtime

1. Garanta que o banco usado é descartável; se houver dúvida, rode antes o smoke test da suíte, que já reseta schema dentro do harness.
2. Execute: `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini upgrade head`
3. Execute: `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini current`
4. **Expected:** `upgrade head` completa sem pedir WuzAPI/Firebase env; `current` reporta `lgpd03_add_ai_audit_event_types (head)`.

### 4. Falha nomeada quando não existe fonte de DB URL

1. Execute: `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" python3 -m pytest -q tests/migrations/test_alembic_operability.py -k missing_source_has_named_failure`
2. **Expected:** o teste passa confirmando uma falha nomeada `db_url_resolution`, não uma explosão genérica de settings/import.

### 5. Resolução de URL continua restrita ao contrato de banco

1. Execute: `cd backend-hormonia && python3 -m pytest -q tests/migrations/test_alembic_operability.py -k db_url_resolution`
2. **Expected:** o check fica verde sem exigir segredos/runtime fora da configuração de banco.

## Edge Cases

### Ambiente scrubbed sem WuzAPI/Firebase

1. Rode qualquer um dos comandos CLI acima apenas com `env -i PATH="$PATH" HOME="$HOME" DATABASE_URL=...`.
2. **Expected:** `history`, `heads`, `upgrade head` e `current` seguem funcionais; qualquer falha pedindo env de runtime é regressão.

### Regressão de import histórico acoplado ao runtime

1. Após alterar/rebasear migrations antigas, execute de novo: `cd backend-hormonia && TEST_DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' pytest -q tests/migrations/test_alembic_operability.py`
2. **Expected:** se houver regressão, a falha nomeia `command`, `phase`, `offending_revision` e `offending_import_path`, com URL mascarada.

### Head ambíguo reaparecendo no grafo

1. Execute: `cd backend-hormonia && env -i PATH="$PATH" HOME="$HOME" DATABASE_URL='postgresql://postgres:postgres@localhost:55432/hormonia_test' python3 -m alembic -c alembic.ini heads`
2. **Expected:** existe um único head; qualquer head adicional é regressão desta slice.

## Failure Signals

- `alembic history`, `heads`, `upgrade head` ou `current` falham sob `env -i ... DATABASE_URL=...`.
- A saída volta a mencionar `app.config.settings`, `app.database`, `app.utils`, ou pede segredos/runtime de WuzAPI/Firebase.
- As mensagens de falha deixam de nomear `db_url_resolution`, `graph-load`, `upgrade` ou `current`.
- `heads` imprime mais de um head ou um head diferente de `lgpd03_add_ai_audit_event_types`.

## Requirements Proved By This UAT

- `R051` — prova a parte de S01: o controle plane do Alembic carrega, percorre e faz replay em Postgres real sem depender de segredos/runtime não relacionados ao banco.

## Not Proven By This UAT

- A fronteira live-vs-histórico para `users`, `audit_logs` e `user_sync_log` que pertence à S02.
- A convergência canônica entre banco limpo e banco existente/stamped no mesmo contrato final, que pertence à S03.
- A prova montada do backend no head final consolidado, que pertence à S04.

## Notes for Tester

- No fechamento da slice, `TEST_DATABASE_URL` não estava exportado na shell do agente; a verificação foi repetida com o URL explícito `postgresql://postgres:postgres@localhost:55432/hormonia_test`.
- `pytest-asyncio` ainda emite um warning conhecido sobre `asyncio_default_fixture_loop_scope`; ele não afetou o resultado da slice.
