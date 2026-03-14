---
date: 2026-03-14
triggering_slice: M004/S03
verdict: no-change
---

# Reassessment: M004/S03

## Coverage Check

- O stack local autentica a equipe, restaura sessão e carrega `/dashboard`, `/admin` e `/whatsapp` sem depender de Firebase ou de superfícies legadas no caminho oficial. → S04, S06
- `firebase_uid`, `/session/*`, `X-Session-ID` e fallbacks legados em escopo deixam de ser parte viva do runtime oficial ou passam a ser rejeitados/tombstonados explicitamente. → S04, S05
- O frontend oficial para de depender funcionalmente de semântica/comentários de Firebase para auth/sessão. → S05, S06
- O milestone fecha com prova montada de runtime sem Firebase, não só com grep, diff e testes unitários. → S06

Coverage check passed.

## Changes Made

No changes.

S03 retirou o risco que prometia retirar: o frontend oficial agora usa apenas o contrato canônico cookie-backed/session-first em `/login`, `/dashboard` e na árvore roteada `/admin/*`, e o verificador de resíduo ficou com `frontend` em zero aprovado.

O roadmap restante continua coerente com a evidência atual:
- **S04 continua sendo o próximo passo correto.** Depois de S03, `/session/*`, `X-Session-ID`, session-as-Bearer e o fallback websocket `?session_id=` não são mais necessidade do app oficial; o trabalho restante é aposentadoria, rejeição ou tombstone dessas superfícies backend.
- **S05 continua necessário como slice distinto.** Ainda existe resíduo backend/adjacente de `firebase_uid`, cache, auditoria e narrativa operacional fora do frontend oficial; isso continua sendo limpeza funcional posterior ao estreitamento da superfície oficial.
- **S06 continua sendo o dono da prova montada final.** S03 provou o boundary do frontend com testes, build e guardrail; ainda falta a prova do stack local sem Firebase nas rotas críticas e no runtime montado.

O boundary map também continua correto após S03. A principal mudança foi de evidência, não de ownership: agora ficou explícito que qualquer legado restante de auth/sessão é inércia backend/adjacente, exatamente a fronteira que S04 e S05 já descreviam.

## Requirement Coverage Impact

None.

Requirement coverage remains sound:
- **R048** continua com fechamento crível em **S04** e rechecagem integrada em **S06**, agora que o frontend oficial não depende mais de transportes paralelos.
- **R049** continua dependendo de **S04/S05** para retirar o resíduo funcional restante de `firebase_uid` e dos caminhos legados fora do happy path canônico.
- **R047** continua corretamente ancorado em **S05** e revalidado por **S06** no stack montado.
- **R050** foi validado por **S03** e não exige mudança de ownership.
- **R053** continua exigindo **S06**, porque a promessa do milestone ainda inclui prova integrada do runtime final.

Nenhuma mudança de ownership ou status é necessária em `.gsd/REQUIREMENTS.md`.

## Decision References

- Decision #1 — Canonical frontend admin/user contract: a remoção dos campos e da narrativa Firebase-shaped do frontend oficial confirma que o restante do trabalho não precisa de outra reabertura do contrato do app oficial.
- Decision #2 — Post-cut residue publication: manter os escopos `frontend` com `approved: []` preserva um gate duro contra regressão e sustenta o veredito de roadmap sem mudanças.
