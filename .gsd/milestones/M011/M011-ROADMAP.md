# M011: Otimização de Carregamento e Redução de Stress no Banco

**Vision:** Reduzir stress no banco e acelerar carregamento das telas do médico com caching Redis nos hot paths, index composto para a query mais pesada, e disciplina de requests no frontend — otimização pura, zero mudança funcional.

## Success Criteria

- Endpoints physician/patients e dashboard/main usam @cache_response com TTL adequado (60s physician, 120s dashboard)
- Index composto em patient_flow_states(patient_id, started_at DESC) existe via Alembic migration
- Frontend hooks de dashboard usam staleTime ≥ 60s e refetchInterval ≥ 120s
- Response shape dos endpoints inalterada (mesmos campos, mesmos tipos)
- `tsc --noEmit` e `vite build` green

## Key Risks / Unknowns

- @cache_response cache key collision com user-specific data — precisa incluir user_id
- Alembic CREATE INDEX em tabela com dados pode ser lento — usar IF NOT EXISTS

## Proof Strategy

- Cache key collision → retirar em S01 verificando que a key inclui user_id/role nos args
- Index creation → retirar em S01 verificando migration aplica sem erro

## Verification Classes

- Contract verification: `tsc --noEmit`, `vite build`, ast.parse nos arquivos backend modificados
- Integration verification: @cache_response decorator presente nos endpoints, Alembic migration parseable
- Operational verification: none
- UAT / human verification: none

## Milestone Definition of Done

This milestone is complete only when all are true:

- @cache_response em physician/patients e dashboard/main
- Index composto criado via Alembic
- Frontend hooks normalizados (staleTime ≥ 60s nos hot paths)
- `tsc --noEmit` + `vite build` green
- Response shape inalterada

## Requirement Coverage

- Covers: R100, R101, R102
- Partially covers: none
- Leaves for later: none
- Orphan risks: none

## Slices

- [ ] **S01: Backend caching + index composto** `risk:high` `depends:[]`
  > After this: physician/patients e dashboard/main retornam dados cacheados no Dragonfly. Index composto em patient_flow_states criado. ast.parse green em todos os arquivos modificados.

- [ ] **S02: Frontend request discipline** `risk:low` `depends:[]`
  > After this: hooks de dashboard/pacientes usam staleTime ≥ 60s e refetchInterval ≥ 120s. tsc + vite build green. Menos requests ao backend.

- [ ] **S03: Verificação integrada** `risk:low` `depends:[S01,S02]`
  > After this: tsc + vite build green, ast.parse green no backend, response shape inalterada. Milestone verificado.

## Boundary Map

### S01 → S03

Produces:
- @cache_response decorator em `physicians/patients.py` (TTL 60s, key_prefix "physician:patients")
- @cache_response decorator em `dashboard.py` (TTL 120s, key_prefix "dashboard:main")
- Alembic migration `m011_s01_patient_flow_states_index` com index composto
- Todos os arquivos backend modificados passam ast.parse

Consumes:
- nothing (first slice)

### S02 → S03

Produces:
- Frontend hooks com staleTime normalizado (≥ 60s para dashboard, ≥ 120s para admin)
- refetchInterval reduzido (≥ 120s para dashboard, removido onde desnecessário)
- `tsc --noEmit` + `vite build` green

Consumes:
- nothing (independent)

### S03 (terminal)

Produces:
- Verificação final: backend + frontend green, response shape validada

Consumes from S01:
- Backend caching + index
Consumes from S02:
- Frontend hooks normalizados
