# M012: Override de Template por Paciente

**Gathered:** 2026-03-17
**Status:** Ready for planning

## Project Description

Sistema de overrides individuais por paciente no fluxo de acompanhamento. Hoje, todo paciente de um médico segue o mesmo template global (onboarding 15 dias, follow-up até dia 45). Com M012, o médico pode personalizar o fluxo de um paciente individual — mudar conteúdo de dias específicos, adicionar dias extras, ou pular dias — sem afetar outros pacientes do mesmo template.

## Why This Milestone

O template global por médico (M007/S03) cobre o caso geral, mas pacientes oncológicos têm situações únicas — efeitos colaterais diferentes, preocupações específicas, velocidades de recuperação distintas. O médico conhece o paciente e precisa de controle fino. R064 está deferred desde M007 — agora é hora de implementar.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Abrir a tela de detalhe de um paciente e clicar "Personalizar Fluxo"
- Ver a lista completa de dias (herdados do template global), com badge visual mostrando quais foram customizados
- Editar conteúdo, tipo (pergunta/motivação/lembrete), e expects_response de dias futuros para aquele paciente
- Adicionar dias extras ou desabilitar (skip) dias específicos
- No dia seguinte, o pipeline process_daily_flows usa o override em vez do template global para esse paciente
- Outros pacientes do mesmo médico continuam recebendo o template global inalterado

### Entry point / environment

- Entry point: PatientDetailPage → botão "Personalizar Fluxo" → editor de override
- Environment: local dev + Dragonfly (Redis) + PostgreSQL
- Live dependencies involved: PostgreSQL (tabela de overrides), Dragonfly (cache invalidation no _get_day_config)

## Completion Class

- Contract complete means: API retorna merge correto, ast.parse green, tsc + vite build green
- Integration complete means: _get_day_config prioriza override sobre template global, dias skip=true são pulados
- Operational complete means: none

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- API GET para um paciente com overrides retorna lista mergeada com indicador de origem (global vs. custom)
- API PUT salva override e invalida cache Redis do _get_day_config
- _get_day_config retorna override quando existe, template global quando não existe override
- Dias com skip=true são pulados pelo pipeline (não geram mensagem)
- Pacientes sem overrides funcionam exatamente como antes (zero regressão)
- Frontend editor funciona: badge visual, edição restrita a dias futuros, tsc + vite build green

## Risks and Unknowns

- _get_day_config performance: consulta extra por paciente — precisa de cache Redis com invalidação cirúrgica no PUT, senão N pacientes = N queries
- Cache key do override precisa incluir patient_id + flow_state_id para não vazar overrides entre pacientes (mesmo padrão do M011 physician cache)
- DayConfigEditor existente (243 linhas) é para template global — precisa de adaptação para mostrar herança visual e restringir edição a dias futuros

## Existing Codebase / Prior Art

- `backend-hormonia/app/services/flow/sequential_message_handler_pkg/state.py` — `_get_day_config()` é o ponto de injeção do override. Hoje consulta `flow_template_versions.steps` + Redis cache. Override precisa ser consultado primeiro.
- `backend-hormonia/app/schemas/v2/templates.py` — `DayConfigItem`, `DayConfigListResponse`, `DayConfigListUpdate` já existem como schemas Pydantic para o editor global.
- `frontend-hormonia/src/features/templates/flows/DayConfigEditor.tsx` — Editor de dias do template global (243 linhas). Padrão visual e de interação para reusar.
- `frontend-hormonia/src/pages/PatientDetailPage.tsx` — Ponto de entrada para o botão "Personalizar Fluxo".
- `backend-hormonia/app/api/v2/routers/flow_templates.py` — GET/PUT `/flows/{template_id}/days` existentes para template global. Padrão de API para reusar.
- `backend-hormonia/app/services/flow/core/template_binding.py` — `FlowCoreTemplateBindingMixin.get_message_template_for_day()` usa `template_loader.load_flow_template()` — camada acima do `_get_day_config`, não precisa de mudança se a injeção for no nível do `_get_day_config`.

> See `.gsd/DECISIONS.md` for all architectural and pattern decisions.

## Relevant Requirements

- R104 — Tabela de overrides
- R105 — API GET/PUT com merge
- R106 — Injeção no _get_day_config
- R107 — Skip de dias
- R108 — Editor no PatientDetailPage
- R109 — Override fixo (não sobrescrito por global)
- R110 — Zero mudança funcional para pacientes sem overrides
- R111 — Sem bulk overrides

## Scope

### In Scope

- Tabela `patient_flow_overrides` via Alembic migration
- API GET/PUT para overrides por paciente com merge (global + overrides)
- Injeção no `_get_day_config` para priorizar override
- Skip de dias via flag
- Editor de override no PatientDetailPage com badge visual
- Cache Redis com invalidação cirúrgica

### Out of Scope / Non-Goals

- Bulk overrides (aplicar mesmo override a vários pacientes)
- Versionamento de overrides (histórico de mudanças)
- Override de templates que o paciente já passou (só dias futuros)
- Mudanças no pipeline funcional existente (process_daily_flows, response handling, etc.)

## Technical Constraints

- Alembic migration precisa de down_revision apontando para `m011_s01_patient_flow_states_index` (head atual)
- `_get_day_config` usa `flow_kind` (string) + `day` (int) para resolver template — override precisa resolver por `patient_flow_state_id` + `day`
- Cache key do override: `flow_override:{patient_flow_state_id}:day:{day}` — invalidado no PUT
- DayConfigItem schema Pydantic é reusável para overrides (mesmos campos: day_number, content, message_type, expects_response) + campo extra `skip`
- O editor de override no frontend precisa saber o `current_flow_day` do paciente para restringir edição a dias futuros

## Integration Points

- **PostgreSQL** — tabela `patient_flow_overrides` (FK para `patient_flow_states`)
- **Dragonfly/Redis** — cache de overrides por paciente para performance do `_get_day_config`
- **React Query** — hook para GET/PUT overrides com staleTime alinhado ao TTL do cache

## Open Questions

- Nenhum — escopo claro e cirúrgico.
