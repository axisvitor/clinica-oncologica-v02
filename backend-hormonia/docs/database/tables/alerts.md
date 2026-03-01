# Table: `alerts`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **type** | `VARCHAR(100)` | ❌ | - |  |  |
| **severity** | `ENUM(alertseverity)` | ❌ | - |  |  |
| **message** | `TEXT` | ❌ | - |  |  |
| **data** | `JSONB` | ✅ | - |  |  |
| **acknowledged** | `BOOLEAN` | ❌ | - |  |  |
| **acknowledged_by** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **acknowledged_at** | `TIMESTAMP` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_alerts_acknowledged_by | ❌ | `acknowledged_by` |
| ix_alerts_id | ❌ | `id` |
| ix_alerts_patient_id | ❌ | `patient_id` |
