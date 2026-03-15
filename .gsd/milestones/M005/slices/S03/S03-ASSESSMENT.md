---
date: 2026-03-15
triggering_slice: M005/S03
verdict: no-change
---

# Reassessment: M005/S03

## Changes Made

No changes.

### Success-Criterion Coverage Check
- `alembic history`, `alembic heads`, `alembic current` e `alembic upgrade` deixam de exigir segredos de runtime não relacionados ao banco; o grafo pode ser inspecionado e percorrido só com configuração de banco. → S04
- Um banco novo consegue ir de `base -> head` e termina num schema compatível com o runtime canônico pós-M004, sem `firebase_uid`, sync Firebase e modelagem de transição como parte viva obrigatória do sistema. → S04
- Um banco existente com histórico legado consegue chegar ao mesmo head sem perder os rastros que a solução decidir preservar; o que permanecer de Firebase fica explicitamente histórico/arquival, não pivô funcional do runtime. → S04
- As revisions merge/no-op/one-way que continuarem no grafo ficam honestas e replayáveis: não bloqueiam traversal, não fingem linearidade e não deixam ambiguidade de head/upgrade. → S04
- O backend sobe nesse head consolidado e os checks críticos herdados de M004 continuam verdes contra o schema final. → S04

Coverage check passed.

### Why the roadmap still holds
- S03 retirou o risco que prometia retirar: `base -> head` e `m005_s02_t01_publish_firebase_history_boundary -> head` agora convergem para o mesmo head canônico, com `users` republicado sob storage neutro, `audit_logs` sem `firebase_uid` vivo e `firebase_sync_history` preso à fronteira histórica explícita.
- Nada no fechamento de S03 cria um novo gap entre schema e runtime que peça outra slice estrutural. O principal achado novo foi operacional: a harness compartilhada em Postgres precisava provisionar via `alembic upgrade head` quando `TEST_DATABASE_URL` está definido. Isso fortalece **S04**, não muda sua ordem.
- **S04** continua sendo o dono natural de todas as provas restantes do milestone: reexecutar upgrade/bootstrap no head consolidado, subir o backend real nesse schema e replayar os loops críticos herdados de M004 em banco novo e banco atualizado.
- O boundary map restante continua honesto. **S04** consome exatamente o que S03 publicou: um head final único para clean replay e existing upgrade, mais a harness Alembic/Postgres já alinhada ao head real.
- As limitações que sobraram em S03 — espelhos de compatibilidade ainda vivos em `users` e a necessidade de rodar suites destrutivas em série quando compartilham `TEST_DATABASE_URL` — são restrições conhecidas de prova/cleanup posterior, não evidência de que o roadmap ficou com ownership errado.

## Requirement Coverage Impact

None.

Requirement coverage remains sound:
- **R051** permanece validado por S03; **S04** não precisa mudar ownership, só rechecá-lo no backend montado sobre o head final.
- **R052** continua corretamente fora de M005 e dono provisório de M006. Os espelhos de compatibilidade restantes em `users` reforçam essa separação, mas não puxam o requisito para dentro de S04.
- **R053** permanece sem mudança de status/ownership: já foi validado pelas provas integradas anteriores, e **S04** segue como fechamento operacional de M005, não como novo requisito.

Nenhuma mudança de status ou ownership é necessária em `.gsd/REQUIREMENTS.md`.

## Decision References

- D15 — M005 slice ordering
- D16 — Firebase-era data retention boundary
- D17 — Historical Alembic revision policy
- D24 — Canonical head convergence scope
- D26 — Shared Postgres runtime test provisioning
- D27 — Canonical archival residue boundary at the S03 head
