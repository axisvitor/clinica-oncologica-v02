---
date: 2026-03-14
triggering_slice: M006/S02
verdict: no-change
---

# Reassessment: M006/S02

## Changes Made

No changes.

### Success-Criterion Coverage Check
- `Requests sem cookie de sessão não entram mais em fallback Firebase/bearer; o runtime autentica apenas pelo contrato canônico ou responde com rejeição/tombstone explícita.` → S04
- `O head canônico e o backend montado operam sem os resíduos Firebase restantes em auth/session e users, com replay fresh e existing ainda convergindo.` → S04
- `Superfícies em escopo do repositório — bridges frontend, tombstones/backend dead services, workflows, env templates e docs operacionais — descrevem apenas o sistema canônico atual ou ficam claramente classificadas como histórico.` → S03, S04
- `O próximo mantenedor consegue rerodar um pack M006 publicado e observar ausência verde de resíduo em escopo mais prova montada verde do sistema final.` → S04

Coverage check passed.

### Why the roadmap still holds
- S02 retirou o risco estrutural/runtime que prometia retirar: o head canônico de `users` deixou de carregar as colunas/index Firebase-prefixed, os readers tocados foram republicados no contrato canônico e o ajuste de leitura tolerante em admin audit/activity absorveu o desvio de labels históricos uppercase sem abrir uma nova frente de schema.
- O novo bloqueio é estreito e não muda ownership de slice: o único vermelho conhecido continua sendo a asserção Postgres-only de timeout-log em `backend-hormonia/tests/api/v2/test_auth_timeout.py::test_get_current_user_from_session_db_timeout_logs_error`. Isso é dívida de prova/observabilidade, não evidência de um novo seam Firebase vivo ou de reorder.
- **S03** continua necessário com evidência concreta de repo surface restante. `docs/compatibility/backward-compatibility-inventory.md` ainda narra `X-Session-ID`, `Authorization` fallback e `/session/*` como shims ativos, e os scans repo-wide ainda encontram guidance Firebase/legado em superfícies operacionais como `backend-hormonia/.env.example`, `backend-hormonia/.env.production.template`, `backend-hormonia/worker/.env.example`, `backend-hormonia/scripts/validate_env.py` e `docs/backend/guides/environment-validation.md`.
- O boundary map restante continua honesto. **S03** ainda consome a fronteira live-vs-historical publicada em S01 mais o naming/storage canônico publicado em S02 para purgar bridges/docs/env/workflows sem reabrir o contrato. **S04** continua sendo o dono natural do replay integrado pós-purga: absence pack, final-schema `fresh|existing` e prova montada no estado final do repo.
- A hipótese implícita de que S02 fecharia toda a prova verde dentro da própria slice caiu, mas isso não cria um buraco no roadmap. O que sobrou para fechar é exatamente o tipo de rechecagem integrada que **S04** já existe para publicar.

## Requirement Coverage Impact

None.

Requirement coverage remains sound:
- **R052** continua com ownership crível e sem mudança de status. S02 avançou materialmente o requisito ao remover o resíduo estrutural/runtime de `users`, mas não o validou porque a prova da slice segue bloqueada; **S03** continua dona da purga repo-wide e **S04** continua dono do pack replayable final.
- Nenhuma mudança de status ou ownership é necessária em `.gsd/REQUIREMENTS.md`.

## Decision References

- D31 — M006 slice ordering for final residue purge
- D33 — Final closeout proof topology
- D36 — Firebase-prefixed `users` residue removal scope
- D38 — Canonical session identity restore boundary
- D39 — Canonical profile/admin/physician activity contract
- D40 — Post-drop `users` ORM compatibility seam
- D41 — Admin audit read compatibility on canonical head
