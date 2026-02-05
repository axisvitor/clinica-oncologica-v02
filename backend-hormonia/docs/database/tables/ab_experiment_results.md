# Table: `ab_experiment_results`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **experiment_id** | `UUID` | ❌ | - |  | ➡️ [ab_experiments]( ab_experiments.md ).id |
| **analysis_timestamp** | `TIMESTAMP` | ❌ | - |  |  |
| **analysis_version** | `VARCHAR(50)` | ❌ | - |  |  |
| **analyst_id** | `VARCHAR(255)` | ✅ | - |  |  |
| **control_sample_size** | `INTEGER` | ❌ | - |  |  |
| **treatment_sample_size** | `INTEGER` | ❌ | - |  |  |
| **total_sample_size** | `INTEGER` | ❌ | - |  |  |
| **primary_metric_name** | `VARCHAR(100)` | ❌ | - |  |  |
| **control_primary_value** | `DOUBLE PRECISION` | ❌ | - |  |  |
| **treatment_primary_value** | `DOUBLE PRECISION` | ❌ | - |  |  |
| **primary_metric_difference** | `DOUBLE PRECISION` | ❌ | - |  |  |
| **primary_metric_relative_change** | `DOUBLE PRECISION` | ❌ | - |  |  |
| **statistical_test_type** | `VARCHAR(100)` | ❌ | - |  |  |
| **p_value** | `DOUBLE PRECISION` | ❌ | - |  |  |
| **alpha** | `DOUBLE PRECISION` | ❌ | - |  |  |
| **is_statistically_significant** | `BOOLEAN` | ❌ | - |  |  |
| **cohens_d** | `DOUBLE PRECISION` | ✅ | - |  |  |
| **effect_size_magnitude** | `VARCHAR(50)` | ✅ | - |  |  |
| **confidence_level** | `DOUBLE PRECISION` | ❌ | - |  |  |
| **ci_lower_bound** | `DOUBLE PRECISION` | ✅ | - |  |  |
| **ci_upper_bound** | `DOUBLE PRECISION` | ✅ | - |  |  |
| **ci_margin_of_error** | `DOUBLE PRECISION` | ✅ | - |  |  |
| **winner** | `VARCHAR(50)` | ✅ | - |  |  |
| **winner_confidence** | `DOUBLE PRECISION` | ✅ | - |  |  |
| **recommendation** | `TEXT` | ✅ | - |  |  |
| **secondary_metrics_results** | `JSONB` | ✅ | - |  |  |
| **detailed_results** | `JSONB` | ✅ | - |  |  |
| **variant_performance** | `JSONB` | ✅ | - |  |  |
| **data_quality_score** | `DOUBLE PRECISION` | ✅ | - |  |  |
| **anomalies_detected** | `JSONB` | ✅ | - |  |  |
| **quality_warnings** | `JSONB` | ✅ | - |  |  |
| **projected_impact** | `JSONB` | ✅ | - |  |  |
| **cost_benefit_analysis** | `JSONB` | ✅ | - |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_ab_experiment_results_analysis_timestamp | ❌ | `analysis_timestamp` |
| ix_ab_experiment_results_experiment_id | ✅ | `experiment_id` |
| ix_ab_experiment_results_id | ❌ | `id` |
| ix_ab_experiment_results_is_statistically_significant | ❌ | `is_statistically_significant` |
| ix_ab_experiment_results_p_value | ❌ | `p_value` |
| ix_ab_experiment_results_winner | ❌ | `winner` |
