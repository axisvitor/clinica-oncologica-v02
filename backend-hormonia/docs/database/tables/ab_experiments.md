# Table: `ab_experiments`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **name** | `VARCHAR(255)` | ❌ | - |  |  |
| **description** | `TEXT` | ✅ | - |  |  |
| **message_template** | `VARCHAR(100)` | ❌ | - |  |  |
| **target_population** | `JSONB` | ✅ | - |  |  |
| **duration_days** | `INTEGER` | ❌ | - |  |  |
| **traffic_split** | `DOUBLE PRECISION` | ❌ | - |  |  |
| **primary_metric** | `VARCHAR(100)` | ❌ | - |  |  |
| **secondary_metrics** | `JSONB` | ✅ | - |  |  |
| **status** | `VARCHAR(10)` | ❌ | - |  |  |
| **start_date** | `TIMESTAMP` | ✅ | - |  |  |
| **end_date** | `TIMESTAMP` | ✅ | - |  |  |
| **safety_checks_enabled** | `BOOLEAN` | ❌ | - |  |  |
| **medical_keyword_check** | `BOOLEAN` | ❌ | - |  |  |
| **manual_review_required** | `BOOLEAN` | ❌ | - |  |  |
| **emergency_stop_enabled** | `BOOLEAN` | ❌ | - |  |  |
| **statistical_config** | `JSONB` | ✅ | - |  |  |
| **encrypted_config** | `TEXT` | ✅ | - |  |  |
| **created_by** | `VARCHAR(255)` | ❌ | - |  |  |
| **started_by** | `VARCHAR(255)` | ✅ | - |  |  |
| **terminated_by** | `VARCHAR(255)` | ✅ | - |  |  |
| **termination_reason** | `TEXT` | ✅ | - |  |  |
| **terminated_at** | `TIMESTAMP` | ✅ | - |  |  |
| **total_participants** | `INTEGER` | ❌ | - |  |  |
| **control_participants** | `INTEGER` | ❌ | - |  |  |
| **treatment_participants** | `INTEGER` | ❌ | - |  |  |
| **results** | `JSONB` | ✅ | - |  |  |
| **is_statistically_significant** | `BOOLEAN` | ✅ | - |  |  |
| **winner** | `VARCHAR(50)` | ✅ | - |  |  |
| **effect_size** | `DOUBLE PRECISION` | ✅ | - |  |  |
| **p_value** | `DOUBLE PRECISION` | ✅ | - |  |  |
| **confidence_interval** | `JSONB` | ✅ | - |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_ab_experiments_end_date | ❌ | `end_date` |
| ix_ab_experiments_id | ❌ | `id` |
| ix_ab_experiments_message_template | ❌ | `message_template` |
| ix_ab_experiments_name | ❌ | `name` |
| ix_ab_experiments_start_date | ❌ | `start_date` |
| ix_ab_experiments_status | ❌ | `status` |
