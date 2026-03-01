# Table: `flow_analytics`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **flow_template_version_id** | `UUID` | ✅ | - |  | ➡️ [flow_template_versions]( flow_template_versions.md ).id |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **total_steps** | `INTEGER` | ✅ | - |  |  |
| **completed_steps** | `INTEGER` | ✅ | - |  |  |
| **success_rate** | `NUMERIC(5, 2)` | ✅ | - |  |  |
| **avg_response_time_seconds** | `INTEGER` | ✅ | - |  |  |
| **step_analytics** | `JSONB` | ✅ | - |  |  |
| **interaction_patterns** | `JSONB` | ✅ | - |  |  |
| **period_start** | `TIMESTAMP` | ✅ | - |  |  |
| **period_end** | `TIMESTAMP` | ✅ | - |  |  |
| **calculated_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_flow_analytics_flow_template_version_id | ❌ | `flow_template_version_id` |
| ix_flow_analytics_id | ❌ | `id` |
| ix_flow_analytics_patient_id | ❌ | `patient_id` |
