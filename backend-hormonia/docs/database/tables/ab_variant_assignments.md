# Table: `ab_variant_assignments`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **experiment_id** | `UUID` | ❌ | - |  | ➡️ [ab_experiments]( ab_experiments.md ).id |
| **anonymous_patient_id** | `VARCHAR(32)` | ❌ | - |  |  |
| **variant** | `VARCHAR(9)` | ❌ | - |  |  |
| **safety_level** | `VARCHAR(10)` | ❌ | - |  |  |
| **assignment_hash** | `VARCHAR(64)` | ❌ | - |  |  |
| **assignment_reason** | `VARCHAR(100)` | ✅ | - |  |  |
| **assigned_at** | `TIMESTAMP` | ❌ | - |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_ab_variant_assignments_anonymous_patient_id | ❌ | `anonymous_patient_id` |
| ix_ab_variant_assignments_assigned_at | ❌ | `assigned_at` |
| ix_ab_variant_assignments_assignment_hash | ❌ | `assignment_hash` |
| ix_ab_variant_assignments_experiment_id | ❌ | `experiment_id` |
| ix_ab_variant_assignments_id | ❌ | `id` |
| ix_ab_variant_assignments_safety_level | ❌ | `safety_level` |
| ix_ab_variant_assignments_variant | ❌ | `variant` |
| ix_ab_variant_exp_patient | ✅ | `experiment_id, anonymous_patient_id` |
| ix_ab_variant_exp_variant | ❌ | `experiment_id, variant` |
| ix_ab_variant_safety | ❌ | `safety_level, variant` |
