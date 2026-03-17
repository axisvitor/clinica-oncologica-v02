# T01: Endpoint backend GET /api/v2/physician/patients

**Slice:** S01
**Milestone:** M010

## Goal
Criar endpoint FastAPI que retorna lista paginada de pacientes do médico logado com dados de fluxo enriquecidos (fase, dia, último contato, alertas não reconhecidos) numa única query.

## Must-Haves

### Truths
- `GET /api/v2/physician/patients` retorna JSON com `items[]` e `total`
- Cada item tem: `id`, `name`, `flow_phase`, `flow_current_day`, `flow_status`, `last_interaction`, `unacknowledged_alerts_count`
- `flow_phase` derivado de FlowKind.kind_key via JOIN FlowTemplateVersion → FlowKind
- `flow_current_day` derivado de PatientFlowState.step_data->'current_flow_day' ou current_step
- `last_interaction` é PatientFlowState.last_interaction_at
- `unacknowledged_alerts_count` é COUNT de alerts WHERE acknowledged=false
- Query filtrável por `search` (nome ILIKE), `flow_phase`, `flow_status`
- Paginação via `page` e `size` params
- Apenas pacientes do médico logado (filtro por doctor_id = current_user.id) ou todos se admin
- Resposta cacheável (60s TTL no Dragonfly)
- Endpoint requer autenticação via session

### Artifacts
- `backend-hormonia/app/api/v2/routers/physicians/patients.py` — endpoint (exports: router com GET /)
- `backend-hormonia/app/schemas/v2/physician_patients.py` — Pydantic schemas (exports: PhysicianPatientItem, PhysicianPatientListResponse)

### Key Links
- `physicians/patients.py` → `app.models.patient.Patient` via SQLAlchemy query
- `physicians/patients.py` → `app.models.flow.PatientFlowState` via outerjoin
- `physicians/patients.py` → `app.models.flow.FlowTemplateVersion` + `FlowKind` via outerjoin
- `physicians/patients.py` → `app.models.alert.Alert` via subquery count
- `physicians/__init__.py` → `patients.py` via router include

## Steps
1. Criar `app/schemas/v2/physician_patients.py` com PhysicianPatientItem e PhysicianPatientListResponse
2. Criar `app/api/v2/routers/physicians/patients.py` com endpoint GET / usando async query
3. Query: SELECT patient fields + LEFT JOIN patient_flow_states (latest por patient) + LEFT JOIN flow_template_versions + LEFT JOIN flow_kinds + subquery COUNT alerts WHERE acknowledged=false
4. Implementar filtros: search (ILIKE name), flow_phase (kind_key), flow_status (PatientFlowState.status)
5. Implementar paginação (page/size com OFFSET/LIMIT + COUNT total)
6. Filtrar por doctor_id = current_user.id (ou sem filtro se admin)
7. Registrar router em `physicians/__init__.py`
8. Verificar: endpoint parse (ast.parse), schema parse, response shape

## Context
- Patient.doctor_id é FK para users.id — filtra pacientes do médico
- PatientFlowState.current_day é property que lê step_data['current_flow_day'] ou current_step
- FlowKind.kind_key dá a fase: 'onboarding', 'daily_follow_up', 'quiz_mensal', 'custom'
- PatientFlowState pode não existir (paciente sem fluxo) — precisa LEFT JOIN
- Alert.acknowledged = False dá a contagem de alertas não reconhecidos
- A query precisa do flow state mais recente por paciente (pode ter vários FlowStates)
- Padrão existente: physicians/__init__.py agrega sub-routers com prefixo
- Auth: usar get_current_user_from_session do dependencies
