---
date: 2026-03-14
triggering_slice: M004/S05
verdict: no-change
---

# Reassessment: M004/S05

## Changes Made

No changes.

### Success-Criterion Coverage Check
- O stack local autentica a equipe, restaura sessão e carrega `/dashboard`, `/admin` e `/whatsapp` sem depender de Firebase ou de superfícies legadas no caminho oficial. → S06
- `firebase_uid`, `/session/*`, `X-Session-ID` e fallbacks legados em escopo deixam de ser parte viva do runtime oficial ou passam a ser rejeitados/tombstonados explicitamente. → S06
- O frontend oficial para de depender funcionalmente de semântica/comentários de Firebase para auth/sessão. → S06
- O milestone fecha com prova montada de runtime sem Firebase, não só com grep, diff e testes unitários. → S06

Coverage check passed.

### Why the roadmap still holds
- S05 retirou o risco que prometia retirar: o resíduo funcional adjacente de Firebase saiu do runtime vivo em cache/sessão compartilhada, login/restore/websocket-adjacent, auditoria/admin/docs e tipos frontend adjacentes, e o guardrail de S01 foi republicado para refletir essa fronteira menor de forma honesta.
- Nada no handoff de S05 abriu um novo gap de slice ou mudou a ordem restante. Pelo contrário: a evidência agora reforça que **S06 continua sendo o próximo passo correto**, porque o que falta é prova montada do stack local sem Firebase Auth, não outro corte estrutural intermediário.
- O boundary map restante continua correto. S06 já consumia exatamente o que S04 e S05 produziram: a superfície oficial final de auth/sessão mais a limpeza adjacente que deixou só compatibilidade/rejeição passiva como resíduo backend permitido.
- As descrições das slices restantes não ficaram erradas com o que foi construído. A principal mudança foi de confiança: depois de S05, falha em S06 tende a indicar bootstrap/env/regressão montada ou algum resíduo realmente novo, não um vazio de ownership no roadmap.

## Requirement Coverage Impact

None.

Requirement coverage remains sound:
- **R047** continua ativo, mas ainda com cobertura crível: S05 fechou a dependência funcional adjacente de Firebase no runtime e **S06** segue como o replay montado que falta para tirar a requirement de Active.
- **R048** e **R049** permanecem validados pelas provas combinadas de S02–S05; **S06** continua sendo a rechecagem integrada do estado montado, não uma mudança de ownership.
- **R050** permanece validado pelo corte frontend já concluído e ainda tem cobertura final em **S06** para o replay das rotas oficiais no stack sem Firebase.
- **R053** continua corretamente dependente de **S06**, porque a frente ainda precisa fechar com prova integrada do runtime final, não só com guardrails e testes focados.

Nenhuma mudança de ownership ou status é necessária em `.gsd/REQUIREMENTS.md`.

## Decision References

- D6 — Adjacent Firebase residue proof shape
- D7 — Core staff-session identity pivot
- D8 — Adjacent audit/admin/docs runtime contract
- D9 — Adjacent frontend auth type boundary
- D10 — Post-S05 residue boundary meaning
- D11 — Shared auth/cache payload sanitization
