---
date: 2026-03-14
triggering_slice: M004/S02
verdict: no-change
---

# Reassessment: M004/S02

## Coverage Check

- O stack local autentica a equipe, restaura sessão e carrega `/dashboard`, `/admin` e `/whatsapp` sem depender de Firebase ou de superfícies legadas no caminho oficial. → S03, S04, S06
- `firebase_uid`, `/session/*`, `X-Session-ID` e fallbacks legados em escopo deixam de ser parte viva do runtime oficial ou passam a ser rejeitados/tombstonados explicitamente. → S04, S05
- O frontend oficial para de depender funcionalmente de semântica/comentários de Firebase para auth/sessão. → S03, S05
- O milestone fecha com prova montada de runtime sem Firebase, não só com grep, diff e testes unitários. → S06

Coverage check passed.

## Changes Made

No changes.

S02 retirou o risco que prometia retirar: o backend agora resolve identidade canônica por `id` / `user_id` primeiro nas helper families oficiais, e a fronteira de resíduo de S01 foi republicada para separar honestamente o que já convergiu do que ainda é transporte/compatibilidade viva.

O roadmap restante continua coerente com o que foi realmente construído:
- **S03 continua sendo o próximo passo correto.** O handoff de S02 deixa explícito que o frontend oficial ainda emite `X-Session-ID`, sessão como bearer e fallback de `session_id` em websocket, além de ainda carregar parte da narrativa Firebase no app oficial.
- **S04 continua necessário como slice distinto.** S02 preservou de propósito os transportes aceitos e sua precedência; aposentadoria, rejeição ou tombstone de `/session/*`, `X-Session-ID`, bearer fallback e websocket query fallback continuam sendo trabalho próprio de corte de superfície oficial.
- **S05 continua necessário como limpeza adjacente.** O relatório ficou semanticamente mais estreito, mas não numericamente menor; o resíduo restante de `firebase_uid`, cache, auditoria, tipos/docs operacionais e módulos adjacentes ainda precisa de um slice próprio depois do corte backend/frontend do caminho feliz.
- **S06 continua sendo o dono da prova montada final.** S02 provou convergência contratual de backend; ainda falta provar o stack local sem Firebase nas rotas críticas e no runtime montado.

A boundary map também continua correta após S02: o slice realmente produziu o contrato backend canônico e a lista concreta das seams legadas restantes para S03/S04/S05 consumirem. A principal nuance nova é semântica, não estrutural: contagem plana no verificador não significa ausência de shrink quando o significado das ocorrências mudou de happy path para compatibilidade. Isso já está capturado no handoff de S01/S02 e não exige reordenação.

## Requirement Coverage Impact

None.

Requirement coverage remains sound:
- **R048** continua avançado de forma crível por **S02**, mas ainda depende de **S03/S04/S06** para fechar a história de contrato oficial único sem caminhos duplos sobrevivendo por inércia.
- **R049** continua avançado de forma crível por **S02**, mas ainda depende de **S04/S05** para retirar o resíduo funcional/adjacente restante de `firebase_uid` do runtime oficial.
- **R050** continua corretamente ancorado em **S03**, com apoio de **S05** para o resíduo funcional/narrativo/tipado restante do frontend oficial.
- **R047** continua corretamente fechado por **S05**, com rechecagem viva em **S06**.
- **R053** continua exigindo **S06**; S02 não substitui a prova integrada do stack montado.

Nenhuma mudança de ownership ou status é necessária em `.gsd/REQUIREMENTS.md`.

## Decision References

- "M004/S02 starts with failing canonical-identity tests across `auth_session_cache`, `auth_session_shared`, and the override-sensitive dependency surface before helper convergence, so the slice proves backend identity shrinkage instead of only preserving already-green auth routes."
- "M004/S02 converges backend identity semantics on canonical `id` / `user_id` resolution while preserving current accepted transports and precedence; retiring root `/session/*`, `X-Session-ID`, session-as-Bearer, and websocket query fallback remains later-slice work."
- "M004/S02/T02 normalizes canonical session identity at the helper boundary (`id` or `user_id`) and consults `firebase_uid` cache/DB fallback only when canonical IDs are absent; request.state side effects and transport precedence stay unchanged."
- "M004/S02/T03 treats the S01 residue guard as a semantic contract, not just a count report: when helper behavior narrows from happy-path dependence to compatibility-only fallback, the allowlist labels/descriptions and slice handoff must be updated even if backend residue file counts stay flat."
