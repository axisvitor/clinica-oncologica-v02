# Table: `appointments`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **doctor_id** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **appointment_type** | `ENUM(appointment_type)` | ❌ | - |  |  |
| **status** | `ENUM(appointment_status)` | ❌ | - |  |  |
| **scheduled_at** | `TIMESTAMP` | ✅ | - |  |  |
| **duration_minutes** | `INTEGER` | ✅ | - |  |  |
| **completed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **cancelled_at** | `TIMESTAMP` | ✅ | - |  |  |
| **pre_appointment_notes** | `TEXT` | ✅ | - |  |  |
| **post_appointment_notes** | `TEXT` | ✅ | - |  |  |
| **appointment_metadata** | `TEXT` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **reminder_sent** | `BOOLEAN` | ❌ | - |  |  |
| **confirmation_sent** | `BOOLEAN` | ❌ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_appointments_appointment_type | ❌ | `appointment_type` |
| ix_appointments_doctor_id | ❌ | `doctor_id` |
| ix_appointments_id | ❌ | `id` |
| ix_appointments_patient_id | ❌ | `patient_id` |
| ix_appointments_scheduled_at | ❌ | `scheduled_at` |
| ix_appointments_status | ❌ | `status` |
