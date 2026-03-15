# M005: Fechamento Definitivo de Schema e Migrações

**Vision:** Fechar a convergência estrutural pós-M004: tornar o grafo Alembic operável por si só, empurrar o legado Firebase para uma fronteira histórica explícita e entregar um head confiável para banco novo, banco existente e backend real.

## Success Criteria

- `alembic history`, `alembic heads`, `alembic current` e `alembic upgrade` deixam de exigir segredos de runtime não relacionados ao banco; o grafo pode ser inspecionado e percorrido só com configuração de banco.
- Um banco novo consegue ir de `base -> head` e termina num schema compatível com o runtime canônico pós-M004, sem `firebase_uid`, sync Firebase e modelagem de transição como parte viva obrigatória do sistema.
- Um banco existente com histórico legado consegue chegar ao mesmo head sem perder os rastros que a solução decidir preservar; o que permanecer de Firebase fica explicitamente histórico/arquival, não pivô funcional do runtime.
- As revisions merge/no-op/one-way que continuarem no grafo ficam honestas e replayáveis: não bloqueiam traversal, não fingem linearidade e não deixam ambiguidade de head/upgrade.
- O backend sobe nesse head consolidado e os checks críticos herdados de M004 continuam verdes contra o schema final.

## Key Risks / Unknowns

- `alembic/env.py` e revisions antigas ainda puxam settings/helpers da app e podem falhar por segredos não relacionados ao banco — sem corrigir isso, qualquer prova de migration fica acoplada ao runtime errado.
- `users`, `audit_logs` e `user_sync_log` ainda carregam rastro Firebase com possível valor histórico/forense — uma decisão ruim aqui ou mantém dependência viva ou apaga contexto operacional útil.
- O grafo já tem merge points, revisions neutralizadas e one-way migrations — reescrever passado por estética pode quebrar upgrade semantics sem melhorar a realidade operacional.
- Ainda existem ilhas compatíveis que tocam `firebase_uid` — cortar schema antes da prova integrada pode deixar o backend sem subir ou mascarar regressões pós-M004.

## Proof Strategy

- Alembic acoplado a segredos/runtime da app → retire in S01 by proving que `history`, `heads`, `current` e um upgrade real em banco de teste rodam com apenas configuração de banco.
- Retenção histórica de Firebase ambígua → retire in S02 by proving que o dado preservado fica atrás de uma fronteira histórica explícita enquanto os modelos/superfícies canônicas deixam de tratá-lo como contrato vivo.
- Convergência de models + schema + grafo ainda incerta → retire in S03 by proving que banco novo e banco existente chegam ao mesmo head com a mesma história canônica.
- Risco de o runtime quebrar depois do corte estrutural → retire in S04 by proving backend montado no head consolidado e rechecando os loops críticos herdados de M004 contra esse schema.

## Verification Classes

- Contract verification: suites focadas de migration/Alembic, checagens de `history`/`heads`/`current`/`upgrade`, introspecção de schema final e testes da fronteira live-vs-histórico.
- Integration verification: Postgres efêmero cobrindo `base -> head` e upgrade de banco existente/stamped, backend subindo no head consolidado e replay dos checks críticos pós-M004 nesse banco.
- Operational verification: comandos Alembic continuam replayáveis com apenas config de banco, e as revisions one-way/no-op remanescentes ficam explicitadas com comportamento honesto.
- UAT / human verification: none.

## Milestone Definition of Done

This milestone is complete only when all are true:

- Todas as slices S01–S04 foram concluídas com seus verificadores verdes.
- O grafo Alembic pode ser inspecionado e percorrido sem depender de segredos de runtime fora do banco.
- Banco novo e banco existente chegam ao mesmo head, e qualquer resíduo Firebase preservado fica explicitamente fora do contrato canônico vivo.
- O entrypoint real do backend foi exercitado no schema consolidado, não apenas suites isoladas de migration.
- Os critérios de sucesso foram rechecados contra comportamento vivo de upgrade/bootstrap e backend montado.
- Os cenários finais de aceitação integrada passam e deixam claro o que, se sobrar, pertence exclusivamente a M006.

## Requirement Coverage

- Covers: R051
- Partially covers: R053
- Leaves for later: R052
- Orphan risks: none

## Slices

- [x] **S01: Alembic operável sem segredos de runtime** `risk:high` `depends:[]`
  > After this: um mantenedor consegue rodar `alembic history`, `heads`, `current` e um upgrade real em banco de teste sem WuzAPI/Firebase env; o grafo volta a ser uma superfície operacional própria.
- [x] **S02: Legado Firebase isolado como histórico explícito** `risk:high` `depends:[S01]`
  > After this: um banco com rastros Firebase preserva apenas o que foi escolhido como histórico explícito, enquanto `users`, `audit_logs` e `user_sync_log` deixam de apresentar esses dados como contrato vivo do modelo canônico.
- [x] **S03: Head canônico de schema sem resíduo estrutural vivo** `risk:high` `depends:[S01,S02]`
  > After this: banco novo e banco existente chegam ao mesmo head com modelos, enums, índices e migrations contando a mesma história canônica sem resíduo Firebase estrutural necessário ao runtime oficial.
- [ ] **S04: Prova integrada de upgrade e backend no schema final** `risk:medium` `depends:[S03]`
  > After this: o backend sobe no head consolidado e a prova montada revalida os loops críticos pós-M004 sobre schema recém-bootstrapado e schema atualizado.

## Boundary Map

### S01 → S02

Produces:
- Superfície Alembic autocontida para `history`, `heads`, `current` e `upgrade`, dependente apenas de configuração de banco.
- Helpers/revisions ajustados para não puxar settings ou utilitários de runtime que não pertencem ao contrato de migration.

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- Harness reutilizável para provar `base -> head` e `existing/stamped -> head` sem segredos da app.
- Invariante operacional: o controle de migrations pode ser exercitado fora do bootstrap completo da aplicação.

Consumes:
- nothing (first slice)

### S02 → S03

Produces:
- Política implementada de retenção do legado Firebase (arquival explícito, tabela histórica imutável, export/backfill seguido de drop, ou equivalente) refletida em models e migrations.
- Invariante de modelo: `user_id` permanece identidade canônica; qualquer `firebase_uid` preservado deixa de ser coluna viva obrigatória do modelo canônico.

Consumes:
- Superfície Alembic operável produzida em S01.

### S03 → S04

Produces:
- Head final de schema com live tables/columns/indexes/enums alinhados ao runtime canônico e com revisions no-op/one-way remanescentes tratadas explicitamente.
- Caminhos de upgrade reexecutáveis para banco novo e banco existente convergindo ao mesmo head.

Consumes:
- Superfície Alembic operável produzida em S01.
- Limites histórico-vs-live definidos em S02.
