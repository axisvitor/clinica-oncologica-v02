# M006: Purga Final de Código Morto e Resíduo Legado

**Vision:** Encerrar a trilha M004→M006 com um repositório que expõe só o sistema canônico atual: auth/session honestos, schema final sem espelhos Firebase restantes, e superfícies de código/docs/scripts/workflows sem bridges ou narrativa legado fora de fronteiras explicitamente históricas.

## Success Criteria

- Requests sem cookie de sessão não entram mais em fallback Firebase/bearer; o runtime autentica apenas pelo contrato canônico ou responde com rejeição/tombstone explícita.
- O head canônico e o backend montado operam sem os resíduos Firebase restantes em auth/session e `users`, com replay `fresh` e `existing` ainda convergindo.
- Superfícies em escopo do repositório — bridges frontend, tombstones/backend dead services, workflows, env templates e docs operacionais — descrevem apenas o sistema canônico atual ou ficam claramente classificadas como histórico.
- O próximo mantenedor consegue rerodar um pack M006 publicado e observar ausência verde de resíduo em escopo mais prova montada verde do sistema final.

## Key Risks / Unknowns

- A costura lazy de bearer/Firebase no backend ainda pode ser o ponto oculto de acoplamento de callers esquecidos; limpar o resto antes dela só deslocaria a falha para outro lugar.
- As colunas Firebase remanescentes em `users` podem ainda estar espelhadas por leitores/testes/runtime; removê-las sem replay Alembic e prova montada falsificaria o head canônico.
- A purga repo-wide cruza código, docs, workflows, env templates e bridges frontend; sem uma fronteira clara entre vivo, histórico e fora de escopo, o milestone vira churn cosmético ou puxa AI/ADK/deferred work por engano.

## Proof Strategy

- Dependência oculta no seam quebrado de auth/session → aposentar em S01 provando que os fluxos de staff auth/session e o verificador de resíduo continuam verdes depois que `get_current_user()` deixa de lazy-loadar o bearer legado/Firebase.
- Resíduo Firebase estrutural ainda vivo em `users` → aposentar em S02 provando replay Alembic `fresh`/`existing` e auth montado no head pós-limpeza.
- Deriva narrativa entre bridges/scripts/docs/workflows → aposentar em S03 provando checks de ausência/import/build/typecheck depois da remoção ou classificação explícita dessas superfícies.
- Honestidade do estado final do repositório → aposentar em S04 publicando e passando um pack replayable que combina resíduo de runtime, ausência repo-wide, prova final de schema e smoke montado do stack pós-purga.

## Verification Classes

- Contract verification: `.gsd/milestones/M004/slices/S01/verify-runtime-residue.sh`, packs focados de pytest para auth/session backend, import-graph/build/typecheck, scans exatos de ausência para docs/workflows/env/templates/bridge barrels/tombstones e replay Alembic no head canônico.
- Integration verification: `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh`, `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --existing`, mais a prova montada do stack publicada em `.gsd/milestones/M004/slices/S06/run-mounted-proof.sh` no estado pós-purga.
- Operational verification: script/status artifacts de closeout M006 que localizam falhas por fase e distinguem ausente vs. histórico explícito.
- UAT / human verification: none.

## Milestone Definition of Done

This milestone is complete only when all are true:

- Todas as classes de resíduo em escopo do roadmap foram removidas ou republicadas como fronteiras históricas explícitas com justificativa escrita.
- Backend auth/session, schema, superfícies oficiais de import/frontend e docs/workflows operacionais contam a mesma história canônica pós-Firebase.
- O runtime montado é exercitado depois da purga pelos entrypoints publicados em M004/M005, não apenas por grep ou diffs.
- Os success criteria são rechecados a partir do estado pós-cleanup pelos comandos do pack M006 e pelos runners montados.
- O cenário final integrado passa: pack de ausência verde, final-schema `fresh`/`existing` verde e stack montado verde.

## Requirement Coverage

- Covers: R052
- Partially covers: none
- Leaves for later: R041, R042 permanecem deferred a menos que prova exata dentro de M006 mostre que algum trecho dessas áreas é resíduo morto diretamente em escopo
- Orphan risks: none; R052 primary owner = S04, supporting slices = S01, S02, S03
- Coverage summary: 1 active requirement · 1 mapped · 0 orphaned

## Slices

- [x] **S01: Fechar a costura auth/session legado ainda “viva”** `risk:high` `depends:[]`
  > After this: o backend autentica staff só pelo contrato cookie-first canônico ou rejeita explicitamente o legado, e o verificador de resíduo deixa de aprovar os hotspots backend de auth/session que ainda tratavam Firebase/header/bearer/query como compatibilidade “ativa”.
- [x] **S02: Remover o resíduo de schema que ainda prende o runtime ao passado** `risk:high` `depends:[S01]`
  > After this: o head canônico de `users` e os leitores/runtime/testes alinhados deixam de depender das colunas Firebase restantes, com replay `fresh`/`existing` e backend montado ainda verdes.
- [x] **S03: Purga final de bridges, tombstones, serviços mortos e narrativa operacional errada** `risk:medium` `depends:[S01]`
  > After this: imports oficiais, barrels de compatibilidade, serviços mortos, env/workflows/docs em escopo e tombstones sem valor operacional deixam de poluir o repositório, com build/typecheck/scans mostrando apenas o que é canônico ou explicitamente histórico.
- [x] **S04: Publicar o closeout final e provar o sistema montado pós-purga** `risk:medium` `depends:[S02,S03]`
  > After this: existe um pack replayable de fechamento M006 que comprova ausência em escopo, schema final `fresh`/`existing` e stack montado pós-purga sem Firebase/legado funcional remanescente.

## Boundary Map

### S01 → S02

Produces:
- `backend-hormonia/app/dependencies/auth_dependencies.py` com resolução canônica cookie-only para `get_current_user()` e rejeição/tombstone explícita em vez de lazy fallback Firebase bearer.
- Contrato republished em `.gsd/milestones/M004/slices/S01/runtime-residue-allowlist.json` / `verify-runtime-residue.sh` com zero aprovado para `firebase_uid`, `x_session_id`, `session_bearer_fallback` e `websocket_session_id_query` nas superfícies backend de auth/session.

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- Fronteira honesta live-vs-dead para código backend adjacente a auth/session, permitindo classificar menções restantes a Firebase como morto, histórico ou deferred — não como “talvez runtime”.
- Diagnósticos estáveis de rejeição/tombstone para transportes aposentados e `/session/*`.

Consumes:
- nothing (first slice)

### S02 → S04

Produces:
- Revisions Alembic, ORM/models e fixtures compartilhadas alinhados a um head canônico que não depende mais das colunas Firebase restantes de `users`.
- `bash .gsd/milestones/M005/slices/S04/run-final-schema-proof.sh --fresh|--existing` verdes no head pós-purga.

Consumes:
- Contrato cookie-only e guardrail de resíduo publicados em S01.

### S03 → S04

Produces:
- Bridges frontend, serviços mortos backend, tombstones sem valor, superfícies de env/workflow/docs operacionais removidas ou explicitamente arquivadas, com entrypoints focados de absence-check para elas.
- Build/typecheck/prova de imports verdes sobre as superfícies repo-wide pós-cleanup.

Consumes:
- Fronteira honesta live-vs-historical estabelecida em S01.
- Naming canônico pós-schema de S02 onde docs/examples ainda descrevem termos vivos de runtime/storage.
