# M005: Fechamento Definitivo de Schema e Migrações — Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

## Project Description

Segundo milestone da lapidação final da base. Depois de convergir o runtime oficial em M004, esta fase realiza as migrações definitivas que ainda precisam ser feitas, remove resíduo estrutural de Firebase/legado do banco e deixa o grafo Alembic, os modelos e o schema em um estado final confiável.

## Why This Milestone

Enquanto o runtime ainda convive com compatibilidades, mexer no schema é cedo demais. Mas, uma vez que M004 feche o caminho canônico, continuar carregando colunas, enums, tabelas, logs e migrations legadas de Firebase transforma o banco num arquivo-morto vivo. O usuário explicitou que quer realizar as migrações definitivas que ainda faltam; então M005 existe para transformar a convergência de runtime em convergência estrutural de verdade.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Subir um banco novo ou atualizar um banco existente até o head com um caminho de migração coerente com o sistema real.
- Manter o sistema sem depender de schema legado de Firebase para auth, auditoria ou sincronização de usuários.

### Entry point / environment

- Entry point: Alembic em `backend-hormonia/alembic/versions`, modelos SQLAlchemy e stack backend montado contra banco atualizado.
- Environment: local dev + banco de teste/integração + comandos Alembic + suites backend focadas.
- Live dependencies involved: PostgreSQL, Alembic, modelos SQLAlchemy, backend FastAPI e dados operacionais persistidos.

## Completion Class

- Contract complete means: modelos, migrations e schema ativo contam a mesma história canônica; o que era legado de Firebase ou transição deixa de ser parte estrutural necessária do banco.
- Integration complete means: o banco atualiza para o head com sucesso, o backend sobe nesse schema e os fluxos críticos continuam verdes.
- Operational complete means: a política para migrations irreversíveis ou one-way fica explícita e honesta; não sobra drift ambíguo neutralizado fingindo ser estado final.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- Um banco atualizado até o head fica compatível com o runtime canônico vindo de M004.
- Colunas, índices, enums, logs e tabelas legadas em escopo deixam de ser necessários ao sistema real.
- O estado final de Alembic é confiável o bastante para bootstrap de ambiente novo e upgrade de ambiente existente.

## Risks and Unknowns

- O grafo Alembic já contém migrations neutralizadas, one-way e herança histórica de diferentes fases — uma limpeza ingênua pode quebrar upgrades ou mascarar drift.
- `firebase_uid` e campos afins aparecem em `users`, auditoria e logs de sync — removê-los exige separar dado histórico de dependência estrutural viva.
- Algumas migrations já assumem downgrade no-op ou canonicalização irreversível — o milestone precisa ser honesto sobre isso em vez de prometer reversibilidade falsa.
- Dados históricos podem precisar preservação sem continuar modelando o runtime atual.

## Existing Codebase / Prior Art

- `backend-hormonia/alembic/versions/f7d2c1b9a4e6_add_firebase_columns_to_users.py` — introduziu colunas de Firebase no schema de usuários.
- `backend-hormonia/alembic/versions/033_fix_user_sync_log_schema.py` — mantém o rastro da fase de sync Firebase.
- `backend-hormonia/alembic/versions/ac193e8656c1_create_sessions_table.py` e `e8c29fcb2be8_drift_check.py` — migrations neutralizadas que precisam ser tratadas com honestidade arquitetural.
- `backend-hormonia/app/models/user.py`, `app/models/audit_log.py`, `app/models/user_sync_log.py` — modelos onde o resíduo estrutural de Firebase ainda aparece.
- Context7 `/sqlalchemy/alembic` — documentação atual reforça tratar heads/merge revisions explicitamente e não presumir linearidade quando o grafo não é trivial.

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R051 — schema e migrações precisam refletir o modelo final, não o legado de transição.
- R049 — a identidade canônica não pode voltar a depender de `firebase_uid` quando o schema for consolidado.
- R053 — a convergência final precisa ser provada em estado montado, não só no diff das migrations.

## Scope

### In Scope

- Inventário do resíduo estrutural de Firebase e legado em models + Alembic.
- Definição e execução das migrações definitivas necessárias para alinhar schema ao runtime canônico.
- Limpeza ou consolidação de revisions neutralizadas/ambíguas quando isso for seguro e honesto.
- Prova de upgrade/head compatível com o backend real.

### Out of Scope / Non-Goals

- Refazer novamente o runtime oficial de auth/sessão — isso pertence a M004.
- Purga repo-wide de bridges, aliases, docs e mortos fora da frente de schema — isso pertence a M006.
- Redesenho amplo de domínio ou de produto sob o pretexto de limpeza de banco.

## Technical Constraints

- Toda remoção estrutural precisa respeitar dado histórico e blast radius operacional.
- Se uma migration for intencionalmente one-way, isso deve ficar explícito na solução e na prova.
- O milestone deve preferir convergência confiável a estética do grafo Alembic.
- O schema final não pode reintroduzir dependência funcional de Firebase para manter o backend de pé.

## Integration Points

- PostgreSQL/Alembic — atualização até o head e compatibilidade com ambiente novo/existente.
- Modelos SQLAlchemy de usuário, auditoria, sync e sessão — precisam convergir com o runtime final.
- Backend FastAPI — deve subir e rodar no schema consolidado sem camadas escondidas de compatibilidade.

## Open Questions

- Quais resíduos de Firebase precisam virar histórico preservado e quais podem ser eliminados por completo? — pensamento atual: preservar apenas o que ainda tem valor operacional/auditável, não dependência estrutural ativa.
- Até onde vale mexer no histórico Alembic versus aceitar algumas migrations antigas como fato consumado? — pensamento atual: tratar o que gera ambiguidade real de upgrade/head e deixar o resto documentado, sem “embelezamento” do passado.
- Existe algum dado histórico em `user_sync_log` ou auditoria que exige estratégia própria antes de drop/rename? — pensamento atual: isso precisa ser respondido na pesquisa de M005 antes da execução.
