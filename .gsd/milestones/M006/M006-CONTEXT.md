# M006: Purga Final de Código Morto e Resíduo Legado — Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

## Project Description

Terceiro milestone da lapidação final da base. Depois que runtime e schema estiverem convergidos, esta fase faz a varrida final do repositório: limpar todos os códigos mortos restantes, remover bridges, aliases, shims, tombstones e documentação errada que ainda sustentam a narrativa antiga do sistema.

## Why This Milestone

Se M004 e M005 fecharem, o que restar de legado tende a ser ruído puro: código morto, bridges temporários que não precisavam sobreviver, aliases históricos, comentários mentirosos, docs desatualizadas e testes presos ao contrato errado. O usuário foi explícito ao pedir limpar todos os códigos mortos; M006 existe para que a lapidação não pare no runtime e no schema, mas chegue ao repositório como um todo.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Evoluir a base sem tropeçar em caminhos antigos, bridges ambíguas ou documentação que descreve um sistema que já não existe.
- Confiar que o repositório mostra o estado canônico atual, e não uma mistura de presente com resíduos de migração passada.

### Entry point / environment

- Entry point: repositório completo (`backend-hormonia`, `frontend-hormonia`, docs, scripts, testes e manifests de cleanup).
- Environment: leitura estática, suites focadas, typecheck/build, smoke final e guardrails de ausência.
- Live dependencies involved: backend, frontend, docs operacionais, scripts internos e verificadores vivos herdados dos milestones anteriores.

## Completion Class

- Contract complete means: bridges, aliases, tombstones e mortos remanescentes em escopo deixam de existir ou ficam explicitamente justificados; o repositório passa a refletir só o sistema canônico atual.
- Integration complete means: backend/frontend/docs/scripts relevantes continuam coerentes entre si e o smoke final prova o sistema montado.
- Operational complete means: os verificadores de ausência e os artefatos de closeout final deixam claro o que foi removido, o que permaneceu e por quê.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- O sistema montado continua verde depois da purga final.
- O repositório não carrega mais código morto ou narrativa operacional de Firebase/legado nas superfícies em escopo.
- O closeout final deixa uma prova integrada e replayável para o próximo mantenedor.

## Risks and Unknowns

- Parte do que parece morto pode ainda estar preso a testes, scripts ou docs operacionais não óbvias.
- Uma purga repo-wide sem disciplina pode virar churn cosmético e perder a régua de valor real.
- Ainda existem áreas grandes e sensíveis fora do foco principal (por exemplo AI/ADK) que não devem ser puxadas para dentro se não forem realmente legado morto.

## Existing Codebase / Prior Art

- `.gsd/milestones/M003/slices/S04/S04-CLEANUP-MANIFEST.md` — modelo de boundary entre removido, mantido e prova exigida.
- `.gsd/milestones/M003/M003-VERIFY.json` — modelo de closeout com prova replayável em vez de só diffs.
- `frontend-hormonia/lib/types/*`, `frontend-hormonia/lib/flow-engine/*`, docs e relatórios históricos — exemplos prováveis de bridges e narrativa antiga ainda a reavaliar.
- Resíduos documentais e de teste que ainda citam Firebase, `X-Session-ID`, compatibilidade velha ou comportamento já aposentado.

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R052 — remover código morto e compatibilidades restantes com prova.
- R053 — fechar a convergência com prova integrada final, não só com cleanup estático.
- R041/R042 continuam fora do corte automático: modularização profunda de AI/ADK e unificação ampla de tipos só entram se houver evidência clara de que são legado morto em escopo.

## Scope

### In Scope

- Inventário final de mortos, bridges, aliases, shims, tombstones e docs erradas em escopo.
- Remoção dos resíduos restantes depois que runtime e schema já estiverem convergidos.
- Guardrails de ausência e closeout final com prova integrada.

### Out of Scope / Non-Goals

- Reabrir auth/runtime ou schema por gosto depois que M004/M005 tiverem fechado.
- Transformar a purga final em nova rodada de replatform ou refactor amplo de AI/ADK sem evidência.
- Adicionar funcionalidade nova enquanto a meta é fechar a lapidação.

## Technical Constraints

- Toda remoção precisa continuar sendo guiada por evidência, não por preferência estética.
- O milestone deve preservar a distinção entre “morto” e “sensível mas ainda vivo”.
- O closeout precisa herdar a disciplina de prova estabelecida em M003, agora aplicada ao estado final M004→M006.

## Integration Points

- Backend + frontend montados — prova final precisa mostrar que a purga não reabriu regressões.
- Docs operacionais e scripts internos — precisam refletir o sistema canônico atual.
- Verificadores vivos herdados de milestones anteriores — devem ser atualizados para o estado final, não deixados quebrados por bookkeeping antigo.

## Open Questions

- Quais bridges/tombstones ainda terão justificativa legítima depois de M004 e M005? — pensamento atual: poucas; a tendência é remover quase tudo que continuar sem valor operacional real.
- Quanto da limpeza documental entra junto com a purga final versus ao longo de M004/M005? — pensamento atual: docs que bloqueiam entendimento do runtime/schema entram antes; o restante consolida em M006.
- Vale transformar parte da purga final em guardas contínuos de CI? — pensamento atual: provavelmente sim para ausências críticas, mas isso precisa ser dimensionado na pesquisa do milestone.
