# M012: Override de Template por Paciente

**Vision:** Permitir ao médico personalizar o fluxo de acompanhamento para pacientes individuais — editar conteúdo, adicionar dias extras, ou pular dias — sobre o template global, sem afetar outros pacientes. Override persistido em tabela própria, injetado no pipeline de envio diário, com editor visual no PatientDetailPage.

## Success Criteria

- Médico abre PatientDetailPage, clica "Personalizar Fluxo", vê lista completa de dias com badge global/custom
- Edição de override persiste em `patient_flow_overrides` e invalida cache Redis
- `_get_day_config` retorna override quando existe, template global quando não
- Dias com `skip=true` no override são pulados pelo pipeline
- Pacientes sem overrides funcionam exatamente como antes
- `tsc --noEmit` + `vite build` green
- `ast.parse` green em todos os arquivos backend modificados

## Key Risks / Unknowns

- Performance do `_get_day_config` com consulta extra por paciente — precisa de cache Redis para não degradar
- Cache key collision com overrides — precisa incluir `patient_flow_state_id` para isolamento entre pacientes

## Proof Strategy

- Performance → retirar em S02 verificando que override é servido via cache Redis com hit/miss logging
- Cache collision → retirar em S02 verificando que cache key inclui patient_flow_state_id

## Verification Classes

- Contract verification: `tsc --noEmit`, `vite build`, `ast.parse` nos arquivos backend modificados
- Integration verification: `_get_day_config` prioriza override, dias skip=true são pulados, cache invalidado no PUT
- Operational verification: none
- UAT / human verification: none

## Milestone Definition of Done

This milestone is complete only when all are true:

- Tabela `patient_flow_overrides` existe via Alembic migration
- API GET retorna merge correto (global + overrides com indicador de origem)
- API PUT salva override e invalida cache Redis
- `_get_day_config` prioriza override do paciente sobre template global
- Dias com `skip=true` são pulados pelo pipeline
- Override é fixo (mudanças no template global não sobrescrevem overrides existentes)
- PatientDetailPage tem editor de override com badge visual global/custom
- Edição restrita a dias futuros (dias já enviados são read-only)
- `tsc --noEmit` + `vite build` green
- `ast.parse` green em todos os arquivos backend modificados
- Pacientes sem overrides funcionam exatamente como antes

## Requirement Coverage

- Covers: R104, R105, R106, R107, R108, R109
- Partially covers: none
- Leaves for later: none
- Orphan risks: none

## Slices

- [x] **S01: Tabela de overrides + API de merge** `risk:high` `depends:[]`
  > After this: Alembic migration cria patient_flow_overrides. GET /api/v2/patients/{id}/flow-overrides retorna lista mergeada (global + overrides) com indicador de origem. PUT salva override. ast.parse green.

- [ ] **S02: Injeção no pipeline de envio** `risk:high` `depends:[S01]`
  > After this: _get_day_config consulta override do paciente antes do template global. Dias com skip=true são pulados por process_daily_flows. Cache Redis com invalidação no PUT. ast.parse green.

- [ ] **S03: Editor de override no PatientDetailPage** `risk:medium` `depends:[S01]`
  > After this: Botão "Personalizar Fluxo" no PatientDetailPage abre editor com lista completa, badge visual global/custom, edição restrita a dias futuros. tsc + vite build green.

- [ ] **S04: Verificação integrada** `risk:low` `depends:[S01,S02,S03]`
  > After this: Script replayable prova todos os deliverables. Milestone verificado.

## Boundary Map

### S01 → S02

Produces:
- Alembic migration `m012_s01_patient_flow_overrides` creating table with columns: id, patient_flow_state_id (FK), day_number, content, message_type, expects_response, skip (bool), created_at, updated_at, created_by
- `PatientFlowOverride` SQLAlchemy model in `app/models/flow.py`
- `PatientFlowOverrideSchema` Pydantic schemas in `app/schemas/v2/patient_overrides.py`
- GET `/api/v2/patients/{patient_id}/flow-overrides` returning merged day list with `source: "global" | "override"` per day
- PUT `/api/v2/patients/{patient_id}/flow-overrides` accepting list of override day configs

Consumes:
- nothing (first slice)

### S01 → S03

Produces:
- Same API endpoints as above (S03 consumes them from the frontend)
- `DayConfigItem` extended with `source` and `skip` fields in response schema

Consumes:
- nothing (first slice)

### S02 → S04

Produces:
- Modified `_get_day_config` in `sequential_message_handler_pkg/state.py` that checks patient override first, falls back to global template
- Redis cache key pattern `flow_override:{patient_flow_state_id}:days` with invalidation on PUT
- Skip logic: days with `skip=true` return `None` from `_get_day_config`, causing `load_flow_context` to emit `status: "skip"`

Consumes from S01:
- `patient_flow_overrides` table and `PatientFlowOverride` model

### S03 → S04

Produces:
- `PatientFlowOverrideEditor` component in `features/patients/components/`
- "Personalizar Fluxo" button in PatientDetailPage
- `usePatientFlowOverrides` hook for GET/PUT
- Badge visual: global days show default style, overridden days show colored badge, skipped days show strikethrough
- Future-day restriction based on `current_flow_day` from patient flow state

Consumes from S01:
- GET/PUT API endpoints for overrides

### S04 (terminal)

Produces:
- Replayable `verify-m012.sh` proving all deliverables

Consumes from S01:
- Table, model, API
Consumes from S02:
- Pipeline injection, cache, skip logic
Consumes from S03:
- Frontend editor, build green
