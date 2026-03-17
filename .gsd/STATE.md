# GSD State

**Active Milestone:** M012: Override de Template por Paciente
**Active Slice:** None
**Phase:** ready-for-planning
**Requirements Status:** 7 active · 60 validated · 9 deferred · 22 out of scope

## Milestone Registry
- ✅ **M001:** Bulletproof Flow Pipeline
- ✅ **M002:** First-Party Authentication Cutover
- ✅ **M003:** Structural Refactor And Dead-Code Cleanup
- ✅ **M004:** Convergência Canônica de Runtime
- ✅ **M005:** Fechamento Definitivo de Schema e Migrações
- ✅ **M006:** Purga Final de Código Morto e Resíduo Legado
- ✅ **M007:** Refinamento dos Fluxos de Acompanhamento
- ✅ **M008:** Onboarding Real de Pacientes — Ponta a Ponta
- ✅ **M009:** Substituição do Celery por Taskiq
- ✅ **M010:** Refinamento do Dashboard Médico
- ✅ **M011:** Otimização de Carregamento e Redução de Stress no Banco
- 🔄 **M012:** Override de Template por Paciente

## Recent Decisions
- D021: Override persistence — dedicated table, not step_data JSONB
- D022: Override immutability — global template changes don't overwrite overrides
- D023: Only future days editable
- D024: Full override granularity (content, type, expects_response, add, skip)

## Blockers
- None

## Next Action
Plan S01 (Tabela de overrides + API de merge).
