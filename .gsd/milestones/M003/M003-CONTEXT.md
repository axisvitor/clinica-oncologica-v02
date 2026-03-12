# M003: Structural Refactor And Dead-Code Cleanup — Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

## Project Description

Refatorar os hotspots mais misturados do backend e frontend, reduzir arquivos grandes demais, remover código morto comprovadamente morto e limpar camadas de compatibilidade obsoletas sem transformar o trabalho em reescrita ou em redesign amplo de contrato.

## Why This Milestone

Depois de M001 e M002, o sistema está mais funcional e verificável, mas a base ainda carrega muitos hotspots de 700–1500 linhas, re-exports/aliases de compatibilidade e resíduos de migrações/refactors anteriores. Isso aumenta o custo de qualquer mudança segura justamente nas superfícies mais sensíveis. O momento certo para atacar isso é agora: os loops críticos já têm provas melhores, então dá para refatorar com guardrails reais em vez de mexer às cegas.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Evoluir os hotspots centrais do sistema com menos medo, porque responsabilidades e fronteiras estarão mais claras.
- Confiar que auth/sessão, dashboard/admin e superfícies críticas do fluxo WhatsApp continuam funcionando após a limpeza estrutural.

### Entry point / environment

- Entry point: repositório local, principais módulos de `backend-hormonia/app/**` e `frontend-hormonia/src/**`, além dos loops críticos `/login`, dashboard/admin e superfícies de fluxo/WhatsApp afetadas.
- Environment: local dev + suites focadas + smoke checks em stack local quando necessário.
- Live dependencies involved: PostgreSQL, Redis/Dragonfly, WuzAPI, frontend Vite/React, websocket bootstrap, módulos AI/ADK sensíveis ao import graph.

## Completion Class

- Contract complete means: existe inventário explícito de hotspots e candidatos a remoção; os módulos-alvo foram repartidos em seams menores; e as camadas de compatibilidade em escopo foram removidas ou isoladas com justificativa clara.
- Integration complete means: os caminhos críticos afetados pelo refactor ainda funcionam de ponta a ponta nas superfícies de auth/sessão, dashboard/admin e fluxo/WhatsApp em escopo.
- Operational complete means: backend/frontend continuam inicializando e executando os loops críticos afetados sem exigir hacks novos, aliases improvisados ou regressão visível de contrato.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- O hotspot principal de backend auth/session foi fatiado em módulos menores sem mudar o contrato funcional percebido pelos chamadores críticos.
- O hotspot principal de frontend api-client/type surface foi simplificado sem espalhar drift de payload ou regressão de navegação/auth/session restore.
- O cleanup final removeu ou isolou compatibilidades obsoletas comprovadamente desnecessárias e os smoke checks críticos continuam verdes.

## Risks and Unknowns

- Código apenas feio vs. código realmente morto — se essa fronteira for inferida errado, o milestone vira regressão disfarçada de cleanup.
- `backend-hormonia/app/dependencies/auth_dependencies.py` e seams vizinhos de auth/session são grandes e sensíveis — uma divisão ruim pode quebrar login, sessão, websocket ou admin.
- `frontend-hormonia/src/lib/api-client/index.ts` e a superfície de tipos/re-exports têm espalhamento alto — limpar sem estratégia pode gerar churn enorme e pouco ganho real.
- O repo já usa shims, tombstones e aliases por decisão histórica — nem todo resíduo aparente é descartável no curto prazo.
- Integrações Redis/Postgres, WuzAPI e AI/ADK ampliam o blast radius de mudanças estruturais em módulos centrais.

## Existing Codebase / Prior Art

- `backend-hormonia/app/dependencies/auth_dependencies.py` — hotspot crítico de auth/session com múltiplos caminhos, compatibilidades e helpers acumulados.
- `backend-hormonia/app/api/v2/routers/auth.py` — router central de auth com contratos sensíveis já estabilizados em M002.
- `frontend-hormonia/src/lib/api-client/index.ts` — cliente frontend grande, com namespaces inline, tipos e muito acoplamento transversal.
- `frontend-hormonia/src/types/api.ts` e `frontend-hormonia/src/lib/types/api.ts` — superfícies de tipo/re-export com resíduo de compatibilidade e duplicação conceitual.
- `backend-hormonia/app/services/webhook/handlers/message_handler.py` e áreas de fluxo/WhatsApp — exemplos de hotspots grandes que não podem ser quebrados sem prova e foco.
- `backend-hormonia/Makefile` — já menciona tooling útil para qualidade como `ruff` e `vulture`.

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions — it is an append-only register; read it during planning, append to it during execution.

## Relevant Requirements

- R034 — reduzir hotspots críticos em módulos menores.
- R035 — provar dead code com evidência antes de remover.
- R036 — remover ou isolar compatibilidades obsoletas.
- R037 — preservar contratos visíveis durante o cleanup.
- R038 — deixar a base realmente mais segura de manter.
- R039 — fechar o milestone com prova forte, não só com arquivos mais bonitos.

## Scope

### In Scope

- Inventário objetivo dos maiores hotspots e do resíduo de compatibilidade/dead code relacionado.
- Refactor estrutural do hotspot principal de backend auth/session.
- Refactor estrutural do hotspot principal de frontend api-client/type surface.
- Remoção ou isolamento de código morto/compatibilidade obsoleta comprovadamente em desuso dentro do escopo.
- Verificação focada + smoke crítico das superfícies sensíveis afetadas.

### Out of Scope / Non-Goals

- Adicionar features novas durante o cleanup.
- Redesenhar contratos públicos sem necessidade real.
- Fazer replatform ou reescrita ampla da arquitetura.
- Expandir o milestone para modularização profunda de AI/ADK ou para unificação total de tipos no repo inteiro.
- Redesenhar banco/esquemas além do que for incidental ao cleanup em escopo.

## Technical Constraints

- Preservar comportamento percebido e contratos visíveis nas superfícies críticas em escopo.
- Tratar remoção de código morto como exercício guiado por evidência, não por opinião estética.
- Priorizar hotspots com maior valor prático para manutenção, começando por backend auth/session e frontend client/types.
- Respeitar as decisões já tomadas em M001/M002 sobre auth session-first, WuzAPI como provedor único e guardrails operacionais existentes.
- Incluir uma slice final explícita de prova integrada porque o milestone cruza backend + frontend + integrações sensíveis.

## Integration Points

- Redis/PostgreSQL de sessão — o cleanup não pode introduzir drift em validação, revogação ou restore de sessão.
- Frontend `apiClient` / superfícies de tipo — mudanças estruturais precisam manter o consumo das telas críticas coerente.
- WuzAPI / fluxo WhatsApp — módulos grandes e críticos não podem sofrer regressão silenciosa enquanto o repo é limpo.
- AI/ADK import graph — parte do resíduo aparente existe por fallback, compatibilidade ou lazy loading; remover isso sem prova é arriscado.
- Test/verification surface — o milestone depende de suites focadas e smoke checks para distinguir cleanup seguro de churn perigoso.

## Open Questions

- Quais compat layers do escopo ainda têm chamadores legítimos fora do caminho principal? — hipótese atual: várias podem cair, mas isso precisa ser provado por inventário e grep/call graph antes da exclusão.
- Até onde vale ir além dos primeiros hotspots sem transformar o milestone em churn difuso? — pensamento atual: limitar a poucos hotspots de alto valor e um cleanup final bem justificado.
- Quais resíduos devem ser removidos e quais devem ser apenas isolados? — pensamento atual: remover quando morto for provado; isolar quando a compatibilidade ainda tiver uso real ou risco alto de exclusão imediata.
