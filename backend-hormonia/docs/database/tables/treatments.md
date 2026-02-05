# Table: `treatments`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **doctor_id** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **treatment_type** | `VARCHAR(15)` | ❌ | - |  |  |
| **status** | `VARCHAR(9)` | ❌ | - |  |  |
| **start_date** | `DATE` | ✅ | - |  |  |
| **end_date** | `DATE` | ✅ | - |  |  |
| **planned_sessions** | `VARCHAR(100)` | ✅ | - |  |  |
| **completed_sessions** | `VARCHAR(100)` | ✅ | - |  |  |
| **diagnosis** | `TEXT` | ✅ | - |  |  |
| **protocol** | `VARCHAR(200)` | ✅ | - |  |  |
| **notes** | `TEXT` | ✅ | - |  |  |
| **is_active** | `BOOLEAN` | ❌ | - |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_treatments_doctor_id | ❌ | `doctor_id` |
| ix_treatments_id | ❌ | `id` |
| ix_treatments_is_active | ❌ | `is_active` |
| ix_treatments_patient_id | ❌ | `patient_id` |
| ix_treatments_start_date | ❌ | `start_date` |
| ix_treatments_status | ❌ | `status` |
| ix_treatments_treatment_type | ❌ | `treatment_type` |
