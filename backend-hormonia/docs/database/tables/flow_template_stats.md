# Table: `flow_template_stats`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **flow_template_version_id** | `UUID` | ❌ | - |  | ➡️ [flow_template_versions]( flow_template_versions.md ).id |
| **total_uses** | `INTEGER` | ✅ | `0` |  |  |
| **active_instances** | `INTEGER` | ✅ | `0` |  |  |
| **completed_instances** | `INTEGER` | ✅ | `0` |  |  |
| **avg_completion_rate** | `NUMERIC(5, 2)` | ✅ | - |  |  |
| **avg_duration_hours** | `NUMERIC(10, 2)` | ✅ | - |  |  |
| **avg_rating** | `NUMERIC(3, 2)` | ✅ | - |  |  |
| **total_ratings** | `INTEGER` | ✅ | `0` |  |  |
| **last_calculated_at** | `TIMESTAMP` | ✅ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| flow_template_stats_flow_template_version_id_key | ✅ | `flow_template_version_id` |
