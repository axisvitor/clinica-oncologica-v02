# Table: `alerts`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **type** | `VARCHAR(100)` | ❌ | - |  |  |
| **severity** | `VARCHAR(8)` | ❌ | - |  |  |
| **message** | `TEXT` | ❌ | - |  |  |
| **data** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **acknowledged** | `BOOLEAN` | ❌ | `false` |  |  |
| **acknowledged_by** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **acknowledged_at** | `TIMESTAMP` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_alerts_acknowledged | ❌ | `acknowledged` |
| idx_alerts_acknowledged_by | ❌ | `acknowledged_by` |
| idx_alerts_patient_acknowledged | ❌ | `patient_id, acknowledged` |
| idx_alerts_patient_created | ❌ | `patient_id, created_at` |
| idx_alerts_patient_id | ❌ | `patient_id` |
| idx_alerts_severity | ❌ | `severity` |
| idx_alerts_type | ❌ | `type` |
| ix_alerts_cursor_pagination | ❌ | `created_at, id` |
