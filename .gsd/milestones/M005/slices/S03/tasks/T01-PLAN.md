---
estimated_steps: 4
estimated_files: 8
---

# T01: Republicar o contrato vivo de `users` sob nomes canônicos

**Slice:** S03 — Head canônico de schema sem resíduo estrutural vivo
**Milestone:** M005

## Description

Convergir `users` para o contrato canônico real: o que hoje ainda é dado vivo de produto sob nomes `firebase_*` ou dentro de `firebase_custom_claims` precisa ser republicado em storage neutro e consumido assim pelas superfícies oficiais. O objetivo não é apagar compatibilidade à força, e sim parar de chamar de “Firebase” o que continua sendo profile/settings do runtime oficial.

## Steps

1. Adicionar uma revision linear a partir de `m005_s02_t01_publish_firebase_history_boundary` que crie e backfille colunas neutras de login/profile/settings em `users`, com guards idempotentes para clean replay e upgrade de banco existente.
2. Atualizar `app.models.user` para expor o storage neutro como contrato vivo e deixar `firebase_uid` / `auth_provider` explicitamente como compatibilidade enquanto ainda houver leitores e testes que dependem deles.
3. Reescrever `users`, `auth` e `physicians` para ler e gravar os campos canônicos, incluindo preferências/perfil hoje pendurados em `firebase_custom_claims`, mantendo dual-read/write apenas onde a transição do slice exigir.
4. Adicionar testes focados para `/api/v2/users/me`, preferências, payload autenticado de auth/session e superfícies de physician, com falhas nomeadas por surface para impedir regressão silenciosa do contrato.

## Must-Haves

- [ ] As superfícies oficiais de user/auth/physician expõem e persistem nomes canônicos, não `firebase_*`, para os dados vivos que continuam existindo no produto.
- [ ] A revision de `users` funciona tanto em `base -> head` quanto em upgrade de um banco no head de S02 sem derrubar `firebase_uid` / `auth_provider` antes da hora.

## Verification

- `cd backend-hormonia && pytest -q tests/api/v2/test_canonical_user_profile_contracts.py`
- `cd backend-hormonia && pytest -q tests/api/v2/test_auth_session_shared_canonical_identity.py -k canonical_identity`

## Observability Impact

- Signals added/changed: asserts nomeados por `canonical_profile` e `canonical_preferences`, além de payloads de cache/session já apontando para os campos neutros.
- How a future agent inspects this: `tests/api/v2/test_canonical_user_profile_contracts.py` e os payloads serializados por `users.py` / `auth.py`.
- Failure state exposed: a falha mostra a surface (`users_me`, `preferences`, `auth_user_payload`, `physician_detail`) e qual campo ainda vazou ou ficou sem backfill.

## Inputs

- `backend-hormonia/app/models/user.py` — ainda modela profile/login/settings vivos como `firebase_*` e `firebase_custom_claims`.
- `backend-hormonia/app/api/v2/routers/users.py` — já publica `last_login` / `photo_url`, mas ainda lê preferências de `firebase_custom_claims`.
- `backend-hormonia/app/api/v2/routers/auth.py` — ainda serializa/grava profile metadata através das colunas e bag legadas.
- `backend-hormonia/app/api/v2/routers/physicians/crud.py` — ainda publica `firebase_display_name`, `firebase_photo_url` e `firebase_email_verified` como contrato oficial.
- `.gsd/milestones/M005/slices/S02/S02-SUMMARY.md` — fixa que `firebase_uid` já saiu das superfícies canônicas e que o próximo passo é convergência estrutural, não nova fronteira histórica.

## Expected Output

- `backend-hormonia/alembic/versions/<s03_users_alignment>.py` — revision linear que republica/backfilla o storage canônico de `users`.
- `backend-hormonia/app/models/user.py` — modelo com campos neutros como contrato vivo e compatibilidade restante explicitada.
- `backend-hormonia/app/api/v2/routers/users.py` — profile/preferences usando o storage neutro.
- `backend-hormonia/app/api/v2/routers/auth.py` — payload autenticado e writes de perfil ancorados no contrato canônico.
- `backend-hormonia/app/api/v2/routers/physicians/crud.py` — serializers de physician contando a mesma história canônica.
- `backend-hormonia/app/schemas/v2/auth.py` — schemas oficiais alinhados ao novo contrato.
- `backend-hormonia/app/schemas/v2/physicians.py` — schema oficial sem nomenclatura Firebase para campos vivos.
- `backend-hormonia/tests/api/v2/test_canonical_user_profile_contracts.py` — prova focada do contrato canônico de user/profile/preferences.
