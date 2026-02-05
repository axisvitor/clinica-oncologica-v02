# Table: `ab_experiment_metrics`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **experiment_id** | `UUID` | ❌ | - |  | ➡️ [ab_experiments]( ab_experiments.md ).id |
| **message_id** | `INTEGER` | ✅ | - |  |  |
| **anonymous_patient_id** | `VARCHAR(32)` | ❌ | - |  |  |
| **variant** | `VARCHAR(9)` | ❌ | - |  |  |
| **event_type** | `VARCHAR(100)` | ❌ | - |  |  |
| **response_time_seconds** | `DOUBLE PRECISION` | ✅ | - |  |  |
| **engagement_score** | `DOUBLE PRECISION` | ✅ | - |  |  |
| **error_details** | `TEXT` | ✅ | - |  |  |
| **event_data** | `JSONB` | ✅ | - |  |  |
| **event_timestamp** | `TIMESTAMP` | ❌ | - |  |  |
| **processed** | `BOOLEAN` | ❌ | - |  |  |
| **included_in_analysis** | `BOOLEAN` | ❌ | - |  |  |
| **exclusion_reason** | `VARCHAR(255)` | ✅ | - |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_ab_experiment_metrics_anonymous_patient_id | ❌ | `anonymous_patient_id` |
| ix_ab_experiment_metrics_event_timestamp | ❌ | `event_timestamp` |
| ix_ab_experiment_metrics_event_type | ❌ | `event_type` |
| ix_ab_experiment_metrics_experiment_id | ❌ | `experiment_id` |
| ix_ab_experiment_metrics_id | ❌ | `id` |
| ix_ab_experiment_metrics_message_id | ❌ | `message_id` |
| ix_ab_experiment_metrics_processed | ❌ | `processed` |
| ix_ab_experiment_metrics_variant | ❌ | `variant` |
| ix_ab_metrics_analysis | ❌ | `experiment_id, included_in_analysis, processed` |
| ix_ab_metrics_event_time | ❌ | `event_type, event_timestamp` |
| ix_ab_metrics_exp_variant | ❌ | `experiment_id, variant` |
| ix_ab_metrics_patient_event | ❌ | `anonymous_patient_id, event_type` |
