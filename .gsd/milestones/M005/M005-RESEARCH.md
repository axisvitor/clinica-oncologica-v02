# M005 — Research

**Date:** 2026-03-14

## Summary

M005 não deve começar derrubando colunas. A primeira prova que falta é mais básica: hoje o caminho Alembic ainda não é operacionalmente confiável o bastante para inspecionar e replayar o próprio grafo sem acoplar migração a runtime. O achado mais importante da pesquisa foi esse: `backend-hormonia/alembic/env.py` importa `app.config.settings` e o registry completo de models, e a revision `018_seed_flow_templates_for_onboarding.py` importa `app.utils.timezone.now_sao_paulo_naive`. Na prática, isso já foi suficiente para fazer `python3 -m alembic -c alembic.ini history --verbose` falhar localmente por falta de `WHATSAPP_WUZAPI_TOKEN`, mesmo sendo um comando de histórico. Enquanto isso não for corrigido ou isolado, qualquer “fechamento definitivo” de schema continua difícil de provar com honestidade.

Ao mesmo tempo, o schema ainda carrega Firebase como estrutura viva: `users` segue com `firebase_uid`, `auth_provider` e metadados Firebase; `audit_logs` ainda tem `firebase_uid` + índice dedicado; `user_sync_log` continua explicitamente modelado como trilha de sync Firebase. Isso contrasta com o runtime pós-M004, que já privilegia `id` / `user_id` como identidade canônica e em alguns pontos já sanitiza `firebase_uid` de payloads canônicos. O quadro geral é claro: o runtime oficial já andou, mas o schema e o grafo Alembic ainda contam uma história de transição.

A recomendação principal é ordenar M005 em quatro passos: (1) tornar o grafo Alembic inspecionável e executável sem segredos de runtime não relacionados; (2) decidir explicitamente o destino do histórico Firebase (`user_sync_log`, `audit_logs.firebase_uid`, metadados de `users`) como arquivo histórico, retenção imutável ou remoção após migração/backfill; (3) implementar migrações finais como revisões novas e honestas, sem reescrever a história sem necessidade; e (4) fechar com prova de `bootstrap -> head`, `upgrade de banco existente -> head` e backend subindo no schema final. Como candidatura de requirement, não auto-binding: a cadeia Alembic precisa voltar a ser operável sem depender de variáveis de runtime fora do banco.

## Recommendation

Siga uma estratégia de convergência estrutural, não de “embelezamento” do passado:

- Primeiro, conserte a superfície de prova do Alembic. O mínimo aceitável para M005 é conseguir percorrer histórico e executar upgrades sem depender de segredos como token da WuzAPI. Isso provavelmente exige reduzir side effects em revisions antigas de seed e/ou desacoplar imports de runtime em `alembic/env.py`.
- Depois, trate o resíduo Firebase por contrato de fronteira:
  - **Table stakes para R051/R053:** provar `upgrade head` em banco novo e em banco existente/stamped; provar backend subindo nesse head.
  - **Continuidade obrigatória:** `user_id` segue sendo a identidade canônica; qualquer dado Firebase remanescente vira histórico explícito, não pivô funcional.
  - **Opcional e precisa de decisão explícita:** preservar busca histórica por `firebase_uid` em auditoria/export.
  - **Fora de escopo, salvo acoplamento inevitável:** purga repo-wide de todo código Firebase residual; isso continua sendo frente de M006.
- Não reescreva migrations antigas só para deixar o grafo bonito. A exceção aceitável é corrigir revisões históricas que hoje impedem traversal/upgrade por side effects de import, desde que a semântica de banco não mude.
- Mantenha as revisions neutralizadas (`ac193e8656c1`, `e8c29fcb2be8`) como fato consumado e honesto. Se forem feias, tudo bem; pior seria esconder a cicatriz e perder rastreabilidade.

**Candidate requirements (advisory only, not auto-binding):**
- **CR-M005-01:** O grafo Alembic pode ser inspecionado e percorrido sem segredos de runtime não relacionados ao banco.
- **CR-M005-02:** A prova de M005 cobre tanto banco novo (`base -> head`) quanto upgrade de banco existente até o head.
- **CR-M005-03:** Qualquer identidade Firebase preservada passa a ser explicitamente histórica/arquival, não parte do contrato canônico do sistema.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Convergir branches/histórico sem fingir linearidade | Merge revision explícita do Alembic (`lgpd01_add_patient_deletion_audit.py`) + padrão oficial de merge revisions | Alembic já trata múltiplos pais de forma honesta; isso preserva upgrade semantics sem “editar o passado” para parecer simples |
| Provar upgrade real de migration | `alembic.command` em teste de integração (`tests/migrations/test_drop_unused_quiz_tables_migration.py`) | Já existe harness real contra Postgres local; ampliar esse padrão é mais seguro do que inventar scripts SQL paralelos |
| Preservar histórico sem manter dependência viva no runtime | Padrão de tabela histórica imutável já usado em `lgpd01_add_patient_deletion_audit.py` | Se parte do legado Firebase tiver valor forense/auditável, é melhor isolá-lo como histórico explícito do que deixar coluna/índice vivos no modelo canônico |
| Encerrar limpeza estrutural irreversível | Migração one-way honesta com downgrade limitado/no-op documentado | Melhor admitir irreversibilidade do que manter downgrades falsos que não representam o estado real |

## Existing Code and Patterns

- `backend-hormonia/alembic/env.py` — importa `app.config.settings` e todo o registry de models; útil para autogenerate, mas hoje acopla traversal de migrations ao runtime da app.
- `backend-hormonia/alembic/versions/018_seed_flow_templates_for_onboarding.py` — seed histórica que importa helper da app (`now_sao_paulo_naive`); é o exemplo concreto de revision que hoje puxa settings e quebra inspeção do grafo.
- `backend-hormonia/alembic/versions/000_legacy_core_bootstrap.py` — bootstrap base ainda cria formas legadas/simplificadas de `users`, `audit_logs`, `user_sync_log` e `sessions`; M005 precisa provar `base -> head`, não só diff de models.
- `backend-hormonia/alembic/versions/f7d2c1b9a4e6_add_firebase_columns_to_users.py` — ponto de entrada dos campos Firebase em `users`, inclusive enum `auth_provider`; qualquer drop final deve ser feito por revision nova, não apagando esta.
- `backend-hormonia/alembic/versions/033_fix_user_sync_log_schema.py` — consolida `user_sync_log` como superfície Firebase-compatible; é o melhor candidato para virar histórico explícito ou ser removido por política clara.
- `backend-hormonia/alembic/versions/ac193e8656c1_create_sessions_table.py` — revision já neutralizada de propósito; manter honestidade arquitetural é mais importante que “limpar” o nome dela.
- `backend-hormonia/alembic/versions/e8c29fcb2be8_drift_check.py` — outra revision neutralizada de propósito; sinal de que o grafo já precisou estabilização e não deve ser retrabalhado ingenuamente.
- `backend-hormonia/alembic/versions/lgpd01_add_patient_deletion_audit.py` — já mostra merge revision explícita e padrão de retenção histórica imutável; é o melhor precedente local para M005.
- `backend-hormonia/app/models/user.py` — o model ainda declara `firebase_uid`, `auth_provider` e todo o bloco de metadata Firebase; schema e model continuam presos um ao outro aqui.
- `backend-hormonia/app/models/audit_log.py` — ainda persiste `firebase_uid` e `idx_audit_firebase_time`; a decisão aqui é retenção histórica versus remoção estrutural.
- `backend-hormonia/app/models/user_sync_log.py` — o model assume `firebase_uid` como coluna obrigatória e expõe o legado como entidade própria do domínio persistido.
- `backend-hormonia/app/services/audit/audit_service.py` — o runtime já remove `firebase_uid` de payloads canônicos de auditoria; evidência de que o contrato vivo já não quer essa identidade no happy path.
- `backend-hormonia/app/dependencies/auth_role_dependencies.py` — já trata `id` / `user_id` como autoridade e usa `firebase_uid` só como fallback compatível; essa é a boundary contract que M005 não deve reverter.
- `backend-hormonia/app/services/session_service.py` — ainda existe uma ilha compatível baseada em Firebase/session cache por `firebase_uid`; schema drop precipitado pode quebrar esses caminhos mesmo que o runtime oficial já tenha sido convergido.
- `backend-hormonia/tests/migrations/test_drop_unused_quiz_tables_migration.py` — único padrão explícito atual de teste de migração com Alembic real; ótimo ponto de partida para o pack de prova de M005.
- `backend-hormonia/tests/test_initialization.py` — os testes de inicialização pulam migrations (`skip_migrations=True`), então hoje não existe cobertura suficiente de saúde do grafo Alembic.

## Constraints

- O caminho de banco novo importa tanto quanto o de upgrade: `000_legacy_core_bootstrap` ainda injeta formas legadas na base.
- O runtime oficial pós-M004 não pode voltar a depender de `firebase_uid`; qualquer preservação deve ser histórica, não funcional.
- O repo ainda contém ilhas compatíveis que consultam `User.firebase_uid`; remover coluna no banco antes de isolar/apagar essas ilhas quebra testes e caminhos residuais.
- Já existe pelo menos um merge point real (`lgpd01_add_patient_deletion_audit`); o grafo não é trivial e não deve ser tratado como linear por conveniência.
- Já existem revisions intencionalmente no-op; M005 precisa ser honesto sobre irreversibilidade e neutralização, não prometer downgrade simétrico fictício.
- `alembic/env.py` já amplia `alembic_version.version_num` para `VARCHAR(255)` por causa do histórico local; isso faz parte do contrato operacional atual do grafo.
- A superfície atual do Alembic depende de imports da app; sem desacoplamento mínimo, até comandos de leitura do grafo ficam presos a validação de settings.

## Common Pitfalls

- **Reescrever histórico só para deixar bonito** — preserve a semântica do grafo; altere revisions antigas apenas quando hoje elas bloqueiam traversal/upgrade por side effects de import ou runtime, e documente isso explicitamente.
- **Dropar `firebase_uid` antes de decidir retenção histórica** — primeiro decida se `audit_logs` e `user_sync_log` viram arquivo histórico, tabela imutável ou remoção após export/backfill; depois escreva a migration.
- **Tratar revisions neutralizadas como “erro a apagar”** — `ac193e8656c1` e `e8c29fcb2be8` já são parte da estabilização honesta do histórico; removê-las só mascara contexto.
- **Provar apenas model diff/autogenerate** — M005 precisa de `alembic upgrade head` real em banco novo e upgrade real em banco existente, além de backend montando nesse schema.
- **Deixar migration importar runtime da app** — seed/helper de migration deve ser autocontido o bastante para não exigir WuzAPI/Firebase/segredos operacionais em comandos de histórico.

## Open Risks

- `user_sync_log` pode conter o único rastro operacional útil de vinculação/sync legado; removê-lo sem política de retenção pode apagar valor forense real.
- `audit_logs.firebase_uid` pode ainda ter utilidade em investigação histórica, mesmo sem valor canônico no runtime atual.
- Corrigir o primeiro import side-effect (`018_seed_flow_templates_for_onboarding.py`) pode revelar outras revisions antigas com o mesmo problema quando o grafo voltar a ser percorrido por inteiro.
- Parte do código compatível ainda toca `firebase_uid` diretamente; se M005 avançar no schema sem coordenar mínimos ajustes de isolamento, o milestone pode invadir M006 por necessidade técnica.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Alembic / SQLAlchemy migrations | none found | Nenhuma skill instalada em `<available_skills>` é diretamente voltada a migrations/schema; usar docs oficiais + padrões locais |
| PostgreSQL schema cleanup | none found | Nenhuma skill instalada em `<available_skills>` cobre diretamente fechamento de schema/Alembic |
| FastAPI backend integration proof | none found | Há skill de debugging genérico, mas nenhuma skill específica instalada para este stack de migration proof |

## Sources

- Alembic trata múltiplos heads por merge revision explícita; `down_revision` pode ser uma tupla e a merge revision pode ser no-op quando a convergência é só do grafo (source: [Alembic branches docs](https://github.com/sqlalchemy/alembic/blob/main/docs/build/branches.rst))
- O ambiente Alembic local importa settings da app e registry completo de models antes de rodar migrations, acoplando traversal de migrations a runtime config (source: [backend-hormonia/alembic/env.py](backend-hormonia/alembic/env.py))
- A revision `018_seed_flow_templates_for_onboarding.py` importa `app.utils.timezone.now_sao_paulo_naive`; em execução local isso já foi suficiente para `python3 -m alembic -c alembic.ini history --verbose` falhar por exigir `WHATSAPP_WUZAPI_TOKEN` (source: [backend-hormonia/alembic/versions/018_seed_flow_templates_for_onboarding.py](backend-hormonia/alembic/versions/018_seed_flow_templates_for_onboarding.py))
- O bootstrap base ainda cria `user_sync_log`, `audit_logs`, `sessions` e `users` em formas legadas/simplificadas, então prova de banco novo é obrigatória (source: [backend-hormonia/alembic/versions/000_legacy_core_bootstrap.py](backend-hormonia/alembic/versions/000_legacy_core_bootstrap.py))
- Os campos Firebase em `users` ainda estão formalmente no schema/migration path via `f7d2c1b9a4e6` e no model atual (source: [backend-hormonia/alembic/versions/f7d2c1b9a4e6_add_firebase_columns_to_users.py](backend-hormonia/alembic/versions/f7d2c1b9a4e6_add_firebase_columns_to_users.py), [backend-hormonia/app/models/user.py](backend-hormonia/app/models/user.py))
- `user_sync_log` segue modelado como superfície Firebase-compatible tanto no model quanto em migration específica (source: [backend-hormonia/app/models/user_sync_log.py](backend-hormonia/app/models/user_sync_log.py), [backend-hormonia/alembic/versions/033_fix_user_sync_log_schema.py](backend-hormonia/alembic/versions/033_fix_user_sync_log_schema.py))
- `audit_logs` ainda carrega `firebase_uid` e índice dedicado, apesar de o serviço de auditoria já sanitizar essa identidade de payloads canônicos (source: [backend-hormonia/app/models/audit_log.py](backend-hormonia/app/models/audit_log.py), [backend-hormonia/app/services/audit/audit_service.py](backend-hormonia/app/services/audit/audit_service.py))
- A dependência admin/session já prefere `id` / `user_id` e só recorre a `firebase_uid` como fallback compatível, reforçando que o contrato canônico vivo já mudou (source: [backend-hormonia/app/dependencies/auth_role_dependencies.py](backend-hormonia/app/dependencies/auth_role_dependencies.py))
- O grafo já contém revisions propositalmente neutralizadas; isso é parte do estado atual honesto e não bug cosmético (source: [backend-hormonia/alembic/versions/ac193e8656c1_create_sessions_table.py](backend-hormonia/alembic/versions/ac193e8656c1_create_sessions_table.py), [backend-hormonia/alembic/versions/e8c29fcb2be8_drift_check.py](backend-hormonia/alembic/versions/e8c29fcb2be8_drift_check.py))
- O padrão local de prova de migration real usa `alembic.command` contra Postgres local, mas hoje só cobre uma frente específica de quiz tables (source: [backend-hormonia/tests/migrations/test_drop_unused_quiz_tables_migration.py](backend-hormonia/tests/migrations/test_drop_unused_quiz_tables_migration.py))
