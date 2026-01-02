# Table: `medications`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **prescribed_by_id** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **treatment_id** | `UUID` | ✅ | - |  | ➡️ [treatments]( treatments.md ).id |
| **name** | `VARCHAR(200)` | ❌ | - |  |  |
| **active_ingredient** | `VARCHAR(200)` | ✅ | - |  |  |
| **dosage** | `VARCHAR(100)` | ❌ | - |  |  |
| **frequency** | `VARCHAR(100)` | ❌ | - |  |  |
| **route** | `VARCHAR(50)` | ✅ | - |  |  |
| **prescription_date** | `DATE` | ❌ | - |  |  |
| **start_date** | `DATE` | ❌ | - |  |  |
| **end_date** | `DATE` | ✅ | - |  |  |
| **quantity** | `NUMERIC(10, 2)` | ✅ | - |  |  |
| **refills_allowed** | `INTEGER` | ❌ | - |  |  |
| **refills_remaining** | `INTEGER` | ❌ | - |  |  |
| **instructions** | `TEXT` | ✅ | - |  |  |
| **warnings** | `TEXT` | ✅ | - |  |  |
| **side_effects** | `TEXT` | ✅ | - |  |  |
| **is_active** | `BOOLEAN` | ❌ | - |  |  |
| **discontinued_date** | `DATE` | ✅ | - |  |  |
| **discontinuation_reason** | `TEXT` | ✅ | - |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_medications_id | ❌ | `id` |
| ix_medications_is_active | ❌ | `is_active` |
| ix_medications_patient_id | ❌ | `patient_id` |
| ix_medications_prescribed_by_id | ❌ | `prescribed_by_id` |
| ix_medications_prescription_date | ❌ | `prescription_date` |
| ix_medications_treatment_id | ❌ | `treatment_id` |
