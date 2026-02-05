# Table: `ab_experiment_monitoring`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **experiment_id** | `UUID` | ❌ | - |  | ➡️ [ab_experiments]( ab_experiments.md ).id |
| **monitoring_period_start** | `TIMESTAMP` | ❌ | - |  |  |
| **monitoring_period_end** | `TIMESTAMP` | ❌ | - |  |  |
| **control_response_rate** | `DOUBLE PRECISION` | ✅ | - |  |  |
| **treatment_response_rate** | `DOUBLE PRECISION` | ✅ | - |  |  |
| **control_error_rate** | `DOUBLE PRECISION` | ✅ | - |  |  |
| **treatment_error_rate** | `DOUBLE PRECISION` | ✅ | - |  |  |
| **safety_violations_count** | `INTEGER` | ❌ | - |  |  |
| **medical_content_alerts** | `INTEGER` | ❌ | - |  |  |
| **patient_complaints** | `INTEGER` | ❌ | - |  |  |
| **response_rate_threshold_breached** | `BOOLEAN` | ❌ | - |  |  |
| **error_rate_threshold_breached** | `BOOLEAN` | ❌ | - |  |  |
| **engagement_threshold_breached** | `BOOLEAN` | ❌ | - |  |  |
| **alerts_sent** | `JSONB` | ✅ | - |  |  |
| **emergency_stop_triggered** | `BOOLEAN` | ❌ | - |  |  |
| **monitoring_data** | `JSONB` | ✅ | - |  |  |
| **processed_at** | `TIMESTAMP` | ❌ | - |  |  |
| **next_check_at** | `TIMESTAMP` | ✅ | - |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_ab_experiment_monitoring_experiment_id | ❌ | `experiment_id` |
| ix_ab_experiment_monitoring_id | ❌ | `id` |
| ix_ab_experiment_monitoring_monitoring_period_end | ❌ | `monitoring_period_end` |
| ix_ab_experiment_monitoring_monitoring_period_start | ❌ | `monitoring_period_start` |
| ix_ab_experiment_monitoring_next_check_at | ❌ | `next_check_at` |
| ix_ab_monitoring_alerts | ❌ | `emergency_stop_triggered, response_rate_threshold_breached` |
| ix_ab_monitoring_next_check | ❌ | `next_check_at` |
| ix_ab_monitoring_period | ❌ | `monitoring_period_start, monitoring_period_end` |
