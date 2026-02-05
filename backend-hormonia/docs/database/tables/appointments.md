# Table: `appointments`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **doctor_id** | `UUID` | ❌ | - |  | ➡️ [users]( users.md ).id |
| **appointment_type** | `VARCHAR(100)` | ❌ | - |  |  |
| **status** | `VARCHAR(50)` | ✅ | `'scheduled'::character varying` |  |  |
| **scheduled_at** | `TIMESTAMP` | ❌ | - |  |  |
| **duration_minutes** | `INTEGER` | ✅ | `60` |  |  |
| **completed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **cancelled_at** | `TIMESTAMP` | ✅ | - |  |  |
| **pre_appointment_notes** | `TEXT` | ✅ | - |  |  |
| **post_appointment_notes** | `TEXT` | ✅ | - |  |  |
| **appointment_metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ✅ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_appointments_doctor | ❌ | `doctor_id` |
| idx_appointments_patient | ❌ | `patient_id` |
| idx_appointments_patient_id | ❌ | `patient_id` |
| idx_appointments_scheduled | ❌ | `scheduled_at` |
| idx_appointments_scheduled_at | ❌ | `scheduled_at` |
| idx_appointments_status | ❌ | `status, scheduled_at` |
