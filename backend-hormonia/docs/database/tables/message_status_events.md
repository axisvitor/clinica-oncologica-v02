# Table: `message_status_events`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **message_id** | `UUID` | ❌ | - |  | ➡️ [messages]( messages.md ).id |
| **status** | `VARCHAR(50)` | ❌ | - |  |  |
| **previous_status** | `VARCHAR(50)` | ✅ | - |  |  |
| **whatsapp_id** | `VARCHAR(255)` | ✅ | - |  |  |
| **whatsapp_timestamp** | `TIMESTAMP` | ✅ | - |  |  |
| **error_code** | `VARCHAR(50)` | ✅ | - |  |  |
| **error_message** | `TEXT` | ✅ | - |  |  |
| **retry_count** | `INTEGER` | ✅ | `0` |  |  |
| **metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **evolution_event_type** | `VARCHAR(100)` | ✅ | - |  |  |
| **evolution_payload** | `JSONB` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_msg_status_error_time | ❌ | `error_code, created_at` |
| idx_msg_status_msg_created | ❌ | `message_id, created_at` |
| idx_msg_status_type_time | ❌ | `status, created_at` |
| idx_msg_status_whatsapp | ❌ | `whatsapp_id, status` |
