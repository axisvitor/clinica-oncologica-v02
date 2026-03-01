# Table: `patient_flow_states`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **flow_template_version_id** | `UUID` | ❌ | - |  | ➡️ [flow_template_versions]( flow_template_versions.md ).id |
| **current_step** | `INTEGER` | ✅ | - |  |  |
| **step_data** | `JSONB` | ✅ | - |  |  |
| **status** | `VARCHAR(50)` | ✅ | - |  |  |
| **started_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **last_interaction_at** | `TIMESTAMP` | ✅ | - |  |  |
| **completed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **next_scheduled_at** | `TIMESTAMP` | ✅ | - |  |  |
| **flow_metadata** | `JSONB` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **version** | `INTEGER` | ❌ | `0` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_patient_flow_states_version | ❌ | `id, version` |
| ix_patient_flow_states_flow_template_version_id | ❌ | `flow_template_version_id` |
| ix_patient_flow_states_id | ❌ | `id` |
| ix_patient_flow_states_patient_id | ❌ | `patient_id` |
| ix_patient_flow_states_status | ❌ | `status` |
| uq_patient_flow_state_version | ✅ | `patient_id, flow_template_version_id` |
