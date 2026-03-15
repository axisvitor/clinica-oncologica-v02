---
date: 2026-03-14
triggering_slice: M005/S01
verdict: no-change
---

# Reassessment: M005/S01

## Changes Made

No changes.

### Success-Criterion Coverage Check
- `alembic history`, `alembic heads`, `alembic current` e `alembic upgrade` deixam de exigir segredos de runtime não relacionados ao banco; o grafo pode ser inspecionado e percorrido só com configuração de banco. → S03, S04
- Um banco novo consegue ir de `base -> head` e termina num schema compatível com o runtime canônico pós-M004, sem `firebase_uid`, sync Firebase e modelagem de transição como parte viva obrigatória do sistema. → S02, S03, S04
- Um banco existente com histórico legado consegue chegar ao mesmo head sem perder os rastros que a solução decidir preservar; o que permanecer de Firebase fica explicitamente histórico/arquival, não pivô funcional do runtime. → S02, S03, S04
- As revisions merge/no-op/one-way que continuarem no grafo ficam honestas e replayáveis: não bloqueiam traversal, não fingem linearidade e não deixam ambiguidade de head/upgrade. → S03, S04
- O backend sobe nesse head consolidado e os checks críticos herdados de M004 continuam verdes contra o schema final. → S04

Coverage check passed.

### Why the roadmap still holds
- S01 retirou exatamente o primeiro risco do milestone: o controle plane do Alembic agora carrega, inspeciona e faz replay em Postgres real só com configuração de banco. Isso confirma a ordem já escolhida em vez de enfraquecê-la.
- A evidência de repo ainda combina com o escopo declarado de **S02**. `backend-hormonia/app/models/user.py` mantém `firebase_uid`, `auth_provider` e metadados Firebase como parte do modelo vivo; `backend-hormonia/app/models/audit_log.py` ainda expõe `firebase_uid` como coluna indexada; `backend-hormonia/app/models/user_sync_log.py` continua sendo um trilho Firebase→PostgreSQL com `firebase_uid` obrigatório. A fronteira histórico-vs-live ainda precisa ser decidida e implementada, não só documentada.
- **S03** continua necessário como slice separado. O próprio handoff de S01 registra que o replay limpo ainda deixa `audit_logs.event_type` como `varchar`; isso prova que operabilidade do grafo e convergência canônica do head não são a mesma coisa.
- Nada no que foi descoberto em S01 sugere puxar **S04** para antes. A prova integrada de upgrade + backend continua mais confiável depois que S02 fechar a fronteira histórica e S03 entregar o head canônico.
- O boundary map restante continua honesto: S01 já produz exatamente o que S02 e S03 consomem — superfície Alembic autocontida e harness reutilizável de replay sem segredos da app.

## Requirement Coverage Impact

None.

Requirement coverage remains sound:
- **R051** continua com cobertura crível nas slices restantes: S01 fechou a operabilidade do controle plane; **S02** ainda é o dono natural da fronteira histórica Firebase; **S03** continua dono da convergência do head/schema; **S04** segue como rechecagem montada do runtime nesse schema final.
- **R053** já está validado pela prova montada de M004/S06 e pela operabilidade real acrescentada em S01; o restante de M005 continua funcionando como fechamento estrutural/replay honesto, sem exigir mudança de ownership.
- Nenhuma mudança de status ou ownership é necessária em `.gsd/REQUIREMENTS.md`.

## Decision References

- D15 — M005 slice ordering
- D16 — Firebase-era data retention boundary
- D17 — Historical Alembic revision policy
- D18 — Alembic bootstrap import boundary
- D19 — Historical migration helper import seam
- D20 — Clean-replay migration operability guardrails
