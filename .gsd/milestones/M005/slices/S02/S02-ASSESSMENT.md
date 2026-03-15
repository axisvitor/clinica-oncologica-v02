---
date: 2026-03-15
triggering_slice: M005/S02
verdict: no-change
---

# Reassessment: M005/S02

## Changes Made

No changes.

### Success-Criterion Coverage Check
- `alembic history`, `alembic heads`, `alembic current` e `alembic upgrade` deixam de exigir segredos de runtime não relacionados ao banco; o grafo pode ser inspecionado e percorrido só com configuração de banco. → S03, S04
- Um banco novo consegue ir de `base -> head` e termina num schema compatível com o runtime canônico pós-M004, sem `firebase_uid`, sync Firebase e modelagem de transição como parte viva obrigatória do sistema. → S03, S04
- Um banco existente com histórico legado consegue chegar ao mesmo head sem perder os rastros que a solução decidir preservar; o que permanecer de Firebase fica explicitamente histórico/arquival, não pivô funcional do runtime. → S03, S04
- As revisions merge/no-op/one-way que continuarem no grafo ficam honestas e replayáveis: não bloqueiam traversal, não fingem linearidade e não deixam ambiguidade de head/upgrade. → S03, S04
- O backend sobe nesse head consolidado e os checks críticos herdados de M004 continuam verdes contra o schema final. → S04

Coverage check passed.

### Why the roadmap still holds
- S02 retirou o risco que prometia retirar. `user_sync_log` virou a superfície histórica explícita `firebase_sync_history`, `audit_logs.firebase_uid` ficou quarantined como resíduo histórico/read-only, e os payloads canônicos de users/admin/physicians/session deixaram de tratar `firebase_uid` como contrato vivo.
- A evidência de repo ainda combina com o escopo já planejado para **S03**. `backend-hormonia/app/models/user.py` ainda mantém `firebase_uid`, `auth_provider` e campos Firebase-era (`firebase_last_sign_in`, `firebase_email_verified`, `firebase_display_name`, `firebase_photo_url`, `firebase_custom_claims`, `last_firebase_sync`) como parte do schema/modelo vivo; `backend-hormonia/app/models/audit_log.py` ainda preserva `firebase_uid` e `idx_audit_firebase_time`; `backend-hormonia/app/schemas/v2/physicians.py` ainda expõe parte desses campos. A convergência do head/schema continua em aberto e segue sendo trabalho de S03, não um gap novo.
- Nada no que S02 descobriu pede reordenação. O aviso sobre testes destrutivos de migration precisarem rodar em série no mesmo `TEST_DATABASE_URL` é uma restrição operacional de verificação, não uma mudança de ownership ou de sequência.
- **S04** continua no lugar certo. Só faz sentido montar o backend e revalidar os loops críticos depois que **S03** entregar o head canônico único para banco novo e banco existente.
- O boundary map restante continua honesto: **S03** consome exatamente o que **S01** e **S02** produziram — harness Alembic autocontido + política implementada de fronteira histórico-vs-live — e **S04** continua consumindo o head consolidado produzido por S03.

## Requirement Coverage Impact

None.

Requirement coverage remains sound:
- **R051** continua com cobertura crível nas slices restantes. S01 fechou a operabilidade do controle plane, S02 publicou a fronteira histórica explícita, **S03** continua dono da convergência clean-db/existing-db para um head canônico único, e **S04** segue como prova montada do backend nesse schema final.
- **R052** não mudou de status nem de ownership. Continua corretamente deixado para M006; nada em S02 puxou esse escopo para dentro de M005.
- **R053** permanece sem mudança de ownership/status: já foi validado pela prova montada de M004/S06 e pela operabilidade real de M005/S01, enquanto o restante de M005 continua sendo fechamento estrutural do schema/migration graph.

Nenhuma mudança de status ou ownership é necessária em `.gsd/REQUIREMENTS.md`.

## Decision References

- D15 — M005 slice ordering
- D16 — Firebase-era data retention boundary
- D17 — Historical Alembic revision policy
- D21 — Firebase sync history publication
- D22 — Canonical `firebase_uid` quarantine
- D23 — Historical audit fixture truthfulness
