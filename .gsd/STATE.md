# GSD State

**Active Milestone:** M004 — Convergência Canônica de Runtime
**Active Slice:** None
**Phase:** planning
**Requirements Status:** 7 active · 18 validated · 7 deferred · 11 out of scope

## Milestone Registry
- ✅ **M001:** Bulletproof Flow Pipeline
- ✅ **M002:** First-Party Authentication Cutover
- ✅ **M003:** Structural Refactor And Dead-Code Cleanup
- 🟡 **M004:** Convergência Canônica de Runtime
- ⏳ **M005:** Fechamento Definitivo de Schema e Migrações
- ⏳ **M006:** Purga Final de Código Morto e Resíduo Legado

## Recent Decisions
- Firebase deve sair de vez do sistema; não há consumidor externo real além do app oficial para justificar compatibilidade viva por padrão.
- A lapidação final foi dividida em três milestones: runtime canônico → schema/migrações → purga final repo-wide.
- M004 fecha com uma slice final explícita de prova integrada no stack local sem Firebase Auth.

## Blockers
- None

## Next Action
Planejar `M004/S01` a partir do roadmap recém-criado, começando pelo mapa executável de resíduos vivos do runtime oficial e pelos guardrails de reintrodução.
