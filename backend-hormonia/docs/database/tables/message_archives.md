# Table: `message_archives`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **original_id** | `UUID` | ❌ | - |  |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **direction** | `ENUM(message_direction)` | ❌ | - |  |  |
| **type** | `ENUM(messagetype)` | ❌ | - |  |  |
| **content** | `TEXT` | ✅ | - |  |  |
| **message_metadata** | `JSONB` | ✅ | - |  |  |
| **priority** | `ENUM(message_priority)` | ❌ | - |  |  |
| **idempotency_key** | `VARCHAR(255)` | ✅ | - |  |  |
| **whatsapp_id** | `VARCHAR(255)` | ✅ | - |  |  |
| **status** | `ENUM(message_status)` | ❌ | - |  |  |
| **scheduled_for** | `TIMESTAMP` | ✅ | - |  |  |
| **sent_at** | `TIMESTAMP` | ✅ | - |  |  |
| **delivered_at** | `TIMESTAMP` | ✅ | - |  |  |
| **read_at** | `TIMESTAMP` | ✅ | - |  |  |
| **delivery_status** | `ENUM(message_delivery_status)` | ✅ | - |  |  |
| **retry_count** | `INTEGER` | ❌ | `0` |  |  |
| **last_retry_at** | `TIMESTAMP` | ✅ | - |  |  |
| **failure_reason** | `TEXT` | ✅ | - |  |  |
| **archived_at** | `TIMESTAMP` | ❌ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_message_archives_id | ❌ | `id` |
| ix_message_archives_original_id | ❌ | `original_id` |
| ix_message_archives_patient_id | ❌ | `patient_id` |
| ix_message_archives_whatsapp_id | ❌ | `whatsapp_id` |
