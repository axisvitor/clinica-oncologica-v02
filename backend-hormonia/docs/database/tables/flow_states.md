# Table: `flow_states`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **flow_type** | `VARCHAR(50)` | ❌ | - |  |  |
| **current_step** | `INTEGER` | ❌ | `0` |  |  |
| **started_at** | `TIMESTAMP` | ❌ | - |  |  |
| **completed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **state_data** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_flow_states_flow_type | ❌ | `flow_type` |
| idx_flow_states_patient_id | ❌ | `patient_id` |
