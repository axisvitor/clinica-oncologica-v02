# M011: Otimização de Carregamento e Redução de Stress no Banco

**Gathered:** 2026-03-17
**Status:** Ready for planning

## Project Description

Otimização cirúrgica dos hot paths do sistema: caching Redis/Dragonfly nos endpoints mais acessados pelo médico, index composto para a query mais pesada, e disciplina de requests no frontend para eliminar polling desnecessário.

## Why This Milestone

M010 construiu o dashboard patient-centric e a tela de preparo pré-consulta. Os endpoints que alimentam essas telas — `GET /api/v2/physicians/patients` (window function + 3 LEFT JOINs + subquery) e `GET /api/v2/dashboard/main` (múltiplos aggregates) — são chamados a cada 60-120s pelo médico mas não usam `@cache_response`. O frontend tem hooks com staleTime de 10s e refetchInterval de 30s que martelam o backend desnecessariamente. A infraestrutura de cache existe (CacheMiddleware, @cache_response, CacheManager) mas está subutilizada nos endpoints mais quentes.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Abrir o dashboard e navegar entre pacientes com response time visivelmente mais rápido (cache hit)
- O sistema suporta mais médicos simultâneos sem degradar porque o banco faz menos queries repetidas
- Frontend não martela o backend com requests redundantes

### Entry point / environment

- Entry point: mesmos endpoints existentes, mesma UI
- Environment: local dev + Dragonfly (Redis)
- Live dependencies involved: PostgreSQL (queries), Dragonfly (cache)

## Completion Class

- Contract complete means: @cache_response nos hot paths, index criado, staleTime normalizado, build green
- Integration complete means: cache hit verificável via headers ou logs
- Operational complete means: none

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- Endpoints physician/patients e dashboard/main retornam dados cacheados no segundo request (dentro do TTL)
- Index composto existe no banco (via Alembic migration)
- Frontend hooks de dashboard/pacientes usam staleTime ≥ 60s
- `tsc --noEmit` e `vite build` green
- Response shape dos endpoints inalterada

## Risks and Unknowns

- @cache_response com user-specific data precisa de cache key que inclui user_id — senão médico A vê pacientes do médico B (cache key collision)
- Alembic migration de index pode ser lenta em tabela grande — usar CREATE INDEX CONCURRENTLY se possível

## Existing Codebase / Prior Art

- `backend-hormonia/app/infrastructure/cache/cache_decorators.py` — @cache_response decorator, gera key a partir de args/kwargs, suporta TTL e key_prefix
- `backend-hormonia/app/infrastructure/cache/cache_manager.py` — CacheManager com Redis backend
- `backend-hormonia/app/middleware/cache_middleware.py` — CacheMiddleware HTTP-level (90s auth TTL)
- `backend-hormonia/app/api/v2/routers/physicians/patients.py` — endpoint physician/patients (M010/S01)
- `backend-hormonia/app/api/v2/routers/dashboard.py` — endpoint dashboard/main (560 linhas)
- `backend-hormonia/app/utils/database_optimization.py` — DatabaseOptimizer, slow query logging
- `backend-hormonia/app/models/flow.py` — PatientFlowState model, indexes existentes: `patient_id` (single), `status`, `(id, version)`

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions.

## Relevant Requirements

- R100 — Hot-path endpoints cacheados no Dragonfly
- R101 — Index composto para window function
- R102 — Frontend staleTime/refetchInterval normalizados

## Scope

### In Scope

- @cache_response nos endpoints physician/patients e dashboard/main
- Alembic migration para index composto em patient_flow_states(patient_id, started_at DESC)
- Normalização de staleTime/gcTime/refetchInterval nos hooks frontend
- Verificação de build green e response shape inalterada

### Out of Scope / Non-Goals

- Mudanças de comportamento funcional (R103)
- Rewrite de queries para async puro (27 sync-to-async bridges permanecem)
- Migração dos 18 arquivos com .query() legacy para select()
- Novas features de cache (cache warming, cache invalidation patterns)

## Technical Constraints

- @cache_response gera cache key a partir de args/kwargs do endpoint — inclui current_user automaticamente (tem user_id/role no key)
- Alembic migration precisa de down revision apontando para `m008_s01_t03_sessions_align`
- Frontend staleTime deve ser ≥ backend cache TTL para evitar request que retorna dado cacheado idêntico
- CacheMiddleware já roda em todas as GET requests com 90s TTL — o @cache_response é uma camada adicional endpoint-specific

## Integration Points

- **Dragonfly** — Redis cache backend (porta 6380)
- **PostgreSQL** — index creation via Alembic
- **React Query** — staleTime/gcTime/refetchInterval config

## Open Questions

- Nenhum — escopo claro e cirúrgico.
