# Table: `patient_flow_states`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **flow_template_version_id** | `UUID` | ❌ | - |  | ➡️ [flow_template_versions]( flow_template_versions.md ).id |
| **current_step** | `INTEGER` | ✅ | `0` |  |  |
| **step_data** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **status** | `VARCHAR(50)` | ✅ | `'active'::character varying` |  |  |
| **started_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **last_interaction_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **completed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **next_scheduled_at** | `TIMESTAMP` | ✅ | - |  |  |
| **flow_metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **version** | `INTEGER` | ❌ | `0` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_patient_flow_states_next_scheduled | ❌ | `next_scheduled_at` |
| idx_patient_flow_states_patient | ❌ | `patient_id` |
| idx_patient_flow_states_patient_completed | ❌ | `patient_id, completed_at` |
| idx_patient_flow_states_patient_id | ❌ | `patient_id` |
| idx_patient_flow_states_patient_template | ❌ | `patient_id, flow_template_version_id` |
| idx_patient_flow_states_started_at | ❌ | `started_at` |
| idx_patient_flow_states_status | ❌ | `status, last_interaction_at` |
| idx_patient_flow_states_template | ❌ | `flow_template_version_id` |
| idx_patient_flow_states_version | ❌ | `id, version` |
| ix_patient_flow_states_cursor | ❌ | `patient_id, created_at, id` |
| unique_patient_flow | ✅ | `patient_id, flow_template_version_id` |
