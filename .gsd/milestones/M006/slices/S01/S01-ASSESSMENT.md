---
date: 2026-03-14
triggering_slice: M006/S01
verdict: no-change
---

# Reassessment: M006/S01

## Changes Made

No changes.

### Success-Criterion Coverage Check
- `Requests sem cookie de sessão não entram mais em fallback Firebase/bearer; o runtime autentica apenas pelo contrato canônico ou responde com rejeição/tombstone explícita.` → S04
- `O head canônico e o backend montado operam sem os resíduos Firebase restantes em auth/session e users, com replay fresh e existing ainda convergindo.` → S02, S04
- `Superfícies em escopo do repositório — bridges frontend, tombstones/backend dead services, workflows, env templates e docs operacionais — descrevem apenas o sistema canônico atual ou ficam claramente classificadas como histórico.` → S03, S04
- `O próximo mantenedor consegue rerodar um pack M006 publicado e observar ausência verde de resíduo em escopo mais prova montada verde do sistema final.` → S04

Coverage check passed.

### Why the roadmap still holds
- S01 retirou exatamente o risco que prometia retirar: o seam vivo de staff auth/session saiu do runtime aceito, e o guardrail backend agora publica zero approved hits nessas categorias com fronteiras `proof_only` explícitas.
- A evidência concreta do repo ainda combina com o escopo de **S02**. `backend-hormonia/app/models/user.py` ainda mantém `firebase_uid`, `auth_provider` e as colunas espelho Firebase como parte do modelo vivo, e `backend-hormonia/app/utils/user_cache.py` ainda usa `firebase_uid` como pivô de cache/rate-limit. Isso continua sendo resíduo estrutural/runtime, não só narrativa, então S02 permanece necessário e na ordem certa.
- A evidência concreta do repo ainda combina com o escopo de **S03**. `docs/compatibility/backward-compatibility-inventory.md` ainda descreve `X-Session-ID`, `Authorization` fallback e `/session/*` como shims ativos, e o repo-wide scan ainda encontra superfícies operacionais/compat legadas fora do seam fechado em S01. Isso continua sendo purga de superfície e narrativa operacional, então S03 segue como slice separada e de risco menor após S02.
- O boundary map restante continua honesto. **S02** ainda consome exatamente o que S01 publicou: contrato cookie-only e guardrail backend com zero approved hits para auth/session. **S03** ainda consome a fronteira honesta live-vs-retired criada em S01 para classificar menções restantes como históricas, tombstone ou mortas. **S04** continua sendo o dono natural da rechecagem integrada pós-purga.
- Nada em S01 introduziu um novo risco que peça reorder, split ou merge. O principal achado novo foi de publicação/diagnóstico — separar `proof_only` de resíduo aprovado — e isso reforça o plano atual em vez de abrir um gap de ownership.

## Requirement Coverage Impact

None.

Requirement coverage remains sound:
- **R052** continua com cobertura crível nas slices restantes. S01 aposentou o seam vivo de auth/session; **S02** ainda é a dona do resíduo estrutural/runtime preso a `users` e leitores adjacentes; **S03** continua dona da purga repo-wide de bridges/tombstones/docs/workflows/env/templates; **S04** continua dona do pack replayable que revalida ausência, final-schema `fresh|existing` e stack montado.
- Nenhuma mudança de status ou ownership é necessária em `.gsd/REQUIREMENTS.md`.

## Decision References

- D31 — M006 slice ordering for final residue purge
- D32 — Backend auth/session residue contract after M006
- D33 — Final closeout proof topology
- D34 — Staff auth chokepoint hard cut shape
- D35 — Runtime residue zero-approved publication
