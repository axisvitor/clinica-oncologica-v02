# M005/S02 — Research

**Date:** 2026-03-15

## Summary

S02 avança diretamente o requisito ativo **R051**; não carrega ownership útil sobre **R052**. O trabalho real desta slice não é “remover Firebase do banco” em bloco, e sim publicar uma fronteira honesta entre **legado histórico preservado** e **contrato canônico vivo** em três superfícies: `users`, `audit_logs` e `user_sync_log`.

O achado principal é que essas três superfícies estão em estados bem diferentes. `user_sync_log` já é quase puramente histórico: hoje só o `FirebaseUserSyncService` escreve nela, e não encontrei routers/schemas canônicos que a exponham. `audit_logs.firebase_uid` já deixou de ser parte do caminho canônico de escrita — `AuditService` e os serializers admin removem `firebase_uid` dos payloads vivos — mas o campo ainda segue no model, no índice `idx_audit_firebase_time`, no serviço legado `app/services/audit_log.py` e em fixtures que o recriam à força. Já `users` mistura três coisas incompatíveis entre si: identidade legada (`firebase_uid`), **dados ainda vivos mas mal nomeados** (`firebase_custom_claims`, `firebase_last_sign_in`, `firebase_photo_url`, `firebase_display_name`) e trilha histórica/proveniência (`firebase_created_at`, `last_firebase_sync`).

A recomendação é executar S02 como uma **slice de boundary contract**, não de drop estrutural total. Primeiro, decidir explicitamente o que vira histórico imutável e o que ainda precisa de destino canônico novo; depois, ajustar models/schemas/serializers/testes para que `firebase_uid` e `user_sync_log` deixem de parecer parte viva do contrato oficial; só então S03 faz o corte estrutural final. Tentar fechar tudo em S02 arrisca quebrar preferências, perfis de médico, métricas de “last login” e compatibilidades de sessão ainda provadas por teste.

## Recommendation

Siga um plano em três blocos, nesta ordem:

1. **Separar o que é histórico do que é só mal nomeado em `users`.**
   - **Não tratar `firebase_custom_claims` como puramente histórico.** Hoje ele carrega preferências do usuário (`/api/v2/users/preferences`) e campos de perfil profissional do médico (`specialties`, `license_number`, `phone`, `bio`) usados pelos endpoints de physicians.
   - **Não tratar `firebase_last_sign_in` como dado morto.** Ele ainda abastece `last_login` em auth/users/physicians e a métrica `active_now` em `AdminStatsService`.
   - `firebase_photo_url` e `firebase_display_name` também seguem aparecendo em payloads canônicos/fallbacks.
   - Portanto, o recorte honesto para S02 é: classificar `firebase_uid` como compat/histórico; classificar `firebase_created_at` e `last_firebase_sync` como trilha histórica; e registrar que `firebase_custom_claims`, `firebase_last_sign_in`, `firebase_photo_url`, `firebase_display_name` e talvez `auth_provider` **precisam de destino canônico** antes de qualquer drop.

2. **Isolar o legado realmente histórico em superfícies explícitas.**
   - `user_sync_log` é o melhor candidato a virar superfície histórica explícita já em S02. As opções honestas são:
     - manter a tabela, mas renomear model/narrativa para algo como `firebase_user_sync_history` e tratá-la como histórico append-only; ou
     - criar nova tabela histórica explícita, copiar/backfill e deixar a antiga como ponte transitória até S03.
   - `audit_logs.firebase_uid` não é mais contrato vivo de escrita, então S02 deve tratá-lo como **campo histórico somente-leitura** ou migrá-lo para payload/tabela histórica explícita antes do drop futuro. O importante é que ele deixe de aparecer como parte do modelo canônico e que o caminho legado `AuditLogService` seja aposentado ou no mínimo alinhado ao saneamento do `AuditService`.

3. **Publicar a fronteira em provas focadas, não só em schema.**
   - Como o `runtime residue guard` de M004 exclui `app/models/**`, `app/schemas/**` e `tests/**`, esta slice não fecha com grep/allowlist.
   - S02 precisa de prova própria para mostrar que:
     - outputs canônicos deixam de expor `firebase_uid` como contrato vivo;
     - `user_sync_log` ficou explicitamente histórico/compat, não entidade de domínio viva;
     - `audit_logs` continua preservando valor forense escolhido sem que `firebase_uid` siga sendo parte do happy path canônico.

Em termos de migração, a recomendação é continuar seguindo a política de M005: **revision nova, honesta, com schema + data migration explícita**, sem reescrever revisões antigas. Alembic suporta bem `op.create_table`, `op.rename_table`, `op.execute` e `op.bulk_insert` para esse tipo de passo; use isso onde o backfill for pequeno/razoável e mantenha a estratégia one-way explícita quando a preservação histórica exigir cópia ou renomeação definitiva.

## Don't Hand-Roll

| Problem | Existing Solution | Why Use It |
|---------|------------------|------------|
| Tornar legado preservado explicitamente histórico | Padrão local de tabela imutável em `lgpd01_add_patient_deletion_audit.py` + `app/models/patient_deletion_audit.py` | Já existe no repo um precedente de “histórico preservado fora do contrato vivo” com índice e imutabilidade explícitos; melhor reutilizar essa narrativa do que inventar uma convenção nova |
| Fazer copy/backfill ou rename em migration | Alembic com revision nova usando `op.create_table`, `op.rename_table`, `op.execute` e `op.bulk_insert` | A documentação oficial já cobre schema + data migration em revision; isso mantém o histórico replayável e evita scripts SQL paralelos sem rastreabilidade |
| Provar que `firebase_uid` saiu do contrato canônico de sessão/cache | Suites focadas `tests/unit/test_auth_session_cache_canonical_identity.py`, `tests/api/v2/test_auth_session_shared_canonical_identity.py` e `tests/unit/test_session_cache.py` | Essas provas já codificam a fronteira certa: `user_id` é canônico e `firebase_uid` só entra como fallback compat quando a identidade canônica falta |
| Revalidar que o grafo continua operável enquanto a slice mexe em legado | `tests/migrations/test_alembic_operability.py` de S01 | O risco de regressão aqui não é só schema; é também reintroduzir acoplamento ou quebrar replay. O harness já existe |

## Existing Code and Patterns

- `backend-hormonia/app/models/user.py` — concentra o problema principal: `firebase_uid` e `auth_provider`, mas também `firebase_custom_claims`, `firebase_last_sign_in`, `firebase_display_name` e `firebase_photo_url`, que hoje ainda alimentam comportamento vivo.
- `backend-hormonia/app/api/v2/routers/users.py` — usa `firebase_custom_claims` como storage vivo de preferences e serializa `last_login`/`photo_url` a partir de campos Firebase-era.
- `backend-hormonia/app/api/v2/routers/physicians/crud.py` — usa `firebase_custom_claims` para `specialties`, `license_number`, `phone` e `bio`, faz fallback de `full_name` para `firebase_display_name` e ainda inclui `firebase_uid`/`firebase_*` no serializer.
- `backend-hormonia/app/schemas/v2/physicians.py` e `backend-hormonia/app/schemas/v2/admin.py` — ainda publicam `firebase_uid` e outros campos Firebase como parte do schema oficial.
- `backend-hormonia/app/services/auth.py` e `backend-hormonia/app/services/password_reset_service.py` — continuam mutando `auth_provider=LOCAL`; isso mostra que `auth_provider` ainda tem semântica viva no runtime atual.
- `backend-hormonia/app/services/analytics/admin_stats_service.py` — usa `firebase_last_sign_in` como métrica de atividade recente; mais um sinal de que esse campo ainda não pode ser simplesmente reclassificado como histórico.
- `backend-hormonia/app/models/audit_log.py` — ainda mantém `firebase_uid` e o índice `idx_audit_firebase_time` no model canônico.
- `backend-hormonia/app/services/audit/audit_service.py` — padrão a seguir: saneia `firebase_uid` dos payloads canônicos e persiste auditoria por `user_id` / `user_email` / contexto normalizado.
- `backend-hormonia/app/services/audit_log.py` — padrão a aposentar ou isolar: ainda aceita e grava `firebase_uid` diretamente no `AuditLog`.
- `backend-hormonia/app/api/v2/routers/admin_extensions/utils.py` — serializer admin de auditoria já filtra `firebase_uid` de `event_metadata`; boa base para a fronteira read-side.
- `backend-hormonia/tests/services/audit/test_audit_service.py` — prova explícita de que o caminho canônico de auditoria deve persistir `firebase_uid` como `None`.
- `backend-hormonia/app/models/user_sync_log.py` — tabela/model legado de sync Firebase; hoje representa mais histórico/compat do que domínio vivo.
- `backend-hormonia/app/services/firebase_user_sync_service.py` — único writer operacional de `user_sync_log`; qualquer archivalização precisa coordenar com este serviço.
- `backend-hormonia/tests/api/critical/conftest.py` e `backend-hormonia/tests/conftest.py` — recriam `audit_logs.firebase_uid` e `idx_audit_firebase_time` via schema patch; mostram que a dívida não é só do runtime, mas também do harness de testes.
- `backend-hormonia/app/dependencies/auth_session_cache.py`, `backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py` e `backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py` — estabelecem a regra útil para S02: `firebase_uid` só pode sobreviver como fallback compat/quarentenado quando não houver `user_id` canônico.
- `backend-hormonia/alembic/versions/lgpd01_add_patient_deletion_audit.py` — melhor precedente local para preservar trilha histórica sem mantê-la como contrato vivo.

## Constraints

- **R051 é o alvo ativo desta slice.** S02 precisa contribuir para “schema e migrações refletem o modelo final, não o legado de transição”.
- `firebase_custom_claims` não é só legado: hoje armazena preferences e perfil profissional. Sem destino canônico alternativo, qualquer archivalização quebra comportamento vivo.
- `firebase_last_sign_in` ainda é usado como `last_login` e como proxy de atividade em métricas admin.
- `auth_provider` ainda é escrito por login local, reset de senha e sync Firebase compat; não é seguro tratá-lo como morto sem estreitar primeiro o runtime.
- `user_sync_log` hoje só é usado por `FirebaseUserSyncService`, mas isso significa que qualquer rename/copy/drop precisa preservar esse writer até a fronteira histórica ficar explícita.
- `audit_logs.firebase_uid` já não é vivo no caminho canônico, mas fixtures críticas ainda o recriam e o `AuditLogService` legado ainda o escreve.
- O verifier de resíduo publicado em M004 exclui `app/models/**`, `app/schemas/**` e `backend-hormonia/tests/**`; esta slice precisa de prova focada própria para model/schema/test fallout.
- A política de M005 continua valendo: usar revisões novas e honestas; não reescrever passado por estética.
- A fallback chain de sessão ainda aceita `firebase_uid` apenas quando a identidade canônica não existe; S02 não pode fingir que essa compatibilidade já morreu, só pode explicitá-la/quarentená-la.

## Common Pitfalls

- **Tratar `firebase_custom_claims` como lixo histórico** — hoje ele carrega preferências e perfil profissional; separar naming ruim de dado morto antes de planejar o corte.
- **Dropar `audit_logs.firebase_uid` só porque o `AuditService` já o saneia** — ainda existe writer legado (`app/services/audit_log.py`) e fixtures que recriam coluna/índice.
- **Arquivar `user_sync_log` sem coordenar o `FirebaseUserSyncService`** — é a única writer surface viva; se o nome/tabela mudar, o serviço precisa acompanhar.
- **Esperar que o runtime residue guard capture tudo** — models, schemas e testes estão fora do escopo desse verifier; sem testes focados a slice pode “passar” e continuar mentindo no contrato.
- **Tentar fechar o problema estrutural inteiro de `users` em S02** — a slice parece melhor desenhada como boundary publication + isolamento histórico; o drop estrutural de campos ainda vivos tende a pertencer a S03 depois que houver destino canônico.

## Open Risks

- `audit_logs.firebase_uid` pode ter valor forense real para investigação histórica; a política de retenção precisa ser explícita antes de qualquer backfill/drop.
- Há forte chance de mais fixtures/helpers antigos recriarem ou assumirem `firebase_uid` fora dos arquivos já inspecionados; o impacto de teste pode ser maior que o impacto de runtime.
- Se `user_sync_log` tiver volume grande em bases reais, uma estratégia de copy/backfill para nova tabela histórica pode encarecer a migration; rename in-place pode ser mais barato, mas acopla mais o runtime transitório.
- A fronteira de `users` pode invadir S03 se a equipe tentar resolver naming canônico, archivalização e drop físico na mesma revisão.
- Existe dívida de compatibilidade espalhada em caches/repos/services Firebase (`SessionService`, `FirebaseRedisCache`, `UserRepository.get_by_firebase_uid`, `FirebaseUserSyncService`) que S02 provavelmente só vai conseguir cercar, não remover.

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Alembic + SQLAlchemy migrations | `wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` | available — 214 installs; install with `npx skills add wispbit-ai/skills@sqlalchemy-alembic-expert-best-practices-code-review` |
| SQLAlchemy ORM | `bobmatnyc/claude-mpm-skills@sqlalchemy-orm` | available — 405 installs; install with `npx skills add bobmatnyc/claude-mpm-skills@sqlalchemy-orm` |
| PostgreSQL historical/schema design | `wshobson/agents@postgresql-table-design` | available — 6.8K installs; install with `npx skills add wshobson/agents@postgresql-table-design` |
| FastAPI / migration-bound backend cleanup | none in `<available_skills>` | none found among installed skills; current installed set is not directly aimed at schema/migration boundary work |

## Sources

- `users` ainda mistura identidade Firebase, preferences vivas, perfil profissional e metadados de login em colunas Firebase-era; isso impede tratar o bloco inteiro como histórico sem uma etapa de canonicalização prévia (source: [backend-hormonia/app/models/user.py](backend-hormonia/app/models/user.py))
- `firebase_custom_claims` é storage vivo de preferences em `/api/v2/users/preferences` (source: [backend-hormonia/app/api/v2/routers/users.py](backend-hormonia/app/api/v2/routers/users.py))
- `firebase_custom_claims`, `firebase_display_name`, `firebase_photo_url` e `firebase_uid` ainda aparecem na serialização de physicians e suportam dados profissionais vivos (source: [backend-hormonia/app/api/v2/routers/physicians/crud.py](backend-hormonia/app/api/v2/routers/physicians/crud.py), [backend-hormonia/app/schemas/v2/physicians.py](backend-hormonia/app/schemas/v2/physicians.py))
- `auth_provider` e `firebase_last_sign_in` ainda são escritos no fluxo local e não podem ser tratados como puro arquivo morto sem mexer no runtime (source: [backend-hormonia/app/services/auth.py](backend-hormonia/app/services/auth.py), [backend-hormonia/app/services/password_reset_service.py](backend-hormonia/app/services/password_reset_service.py))
- `firebase_last_sign_in` ainda sustenta a métrica admin de usuários “ativos agora” (source: [backend-hormonia/app/services/analytics/admin_stats_service.py](backend-hormonia/app/services/analytics/admin_stats_service.py))
- O caminho canônico de auditoria já saneia `firebase_uid` dos payloads vivos antes de persistir (source: [backend-hormonia/app/services/audit/audit_service.py](backend-hormonia/app/services/audit/audit_service.py))
- O model `AuditLog` ainda mantém `firebase_uid` e o índice `idx_audit_firebase_time`, então o schema continua contando uma história mais viva do que o runtime canônico (source: [backend-hormonia/app/models/audit_log.py](backend-hormonia/app/models/audit_log.py))
- O serviço legado `AuditLogService` ainda aceita e grava `firebase_uid`, então a coluna não pode ser tratada como morta só com base no `AuditService` novo (source: [backend-hormonia/app/services/audit_log.py](backend-hormonia/app/services/audit_log.py))
- O serializer admin de auditoria já filtra `firebase_uid` de `event_metadata`, bom precedente para a fronteira read-side (source: [backend-hormonia/app/api/v2/routers/admin_extensions/utils.py](backend-hormonia/app/api/v2/routers/admin_extensions/utils.py), [backend-hormonia/app/schemas/v2/admin_extensions.py](backend-hormonia/app/schemas/v2/admin_extensions.py))
- Os testes focados de auditoria exigem que `firebase_uid` seja persistido como `None` no caminho canônico (source: [backend-hormonia/tests/services/audit/test_audit_service.py](backend-hormonia/tests/services/audit/test_audit_service.py))
- `user_sync_log` hoje só aparece no model e no writer `FirebaseUserSyncService`, sinal de que é forte candidato a superfície histórica explícita (source: [backend-hormonia/app/models/user_sync_log.py](backend-hormonia/app/models/user_sync_log.py), [backend-hormonia/app/services/firebase_user_sync_service.py](backend-hormonia/app/services/firebase_user_sync_service.py))
- O contrato canônico de sessão/cache já exige `user_id` e só recorre a `firebase_uid` quando a identidade canônica está ausente; isso define a quarentena compatível que S02 precisa respeitar (source: [backend-hormonia/app/dependencies/auth_session_cache.py](backend-hormonia/app/dependencies/auth_session_cache.py), [backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py](backend-hormonia/tests/unit/test_auth_session_cache_canonical_identity.py), [backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py](backend-hormonia/tests/api/v2/test_auth_session_shared_canonical_identity.py), [backend-hormonia/tests/unit/test_session_cache.py](backend-hormonia/tests/unit/test_session_cache.py))
- Fixtures críticas ainda recriam `audit_logs.firebase_uid` e o índice `idx_audit_firebase_time`, então parte do trabalho desta slice é desalojar suposições do harness de testes, não só do runtime (source: [backend-hormonia/tests/api/critical/conftest.py](backend-hormonia/tests/api/critical/conftest.py), [backend-hormonia/tests/conftest.py](backend-hormonia/tests/conftest.py))
- O repo já tem um precedente local para preservar histórico fora do contrato vivo com tabela explícita e imutável (`patient_deletion_audit`) (source: [backend-hormonia/alembic/versions/lgpd01_add_patient_deletion_audit.py](backend-hormonia/alembic/versions/lgpd01_add_patient_deletion_audit.py), [backend-hormonia/app/models/patient_deletion_audit.py](backend-hormonia/app/models/patient_deletion_audit.py))
- A documentação oficial do Alembic cobre migrations com schema + data backfill usando `op.create_table`, `op.bulk_insert` e `op.execute`, então a fronteira histórica pode ser implementada por revision nova sem script paralelo fora do grafo (source: [Alembic cookbook](https://github.com/sqlalchemy/alembic/blob/main/docs/build/cookbook.rst), [Alembic docs via Context7](https://context7.com/sqlalchemy/alembic/llms.txt))
