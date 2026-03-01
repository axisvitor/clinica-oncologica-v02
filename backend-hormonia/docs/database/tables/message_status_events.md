# Table: `message_status_events`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **message_id** | `UUID` | ❌ | - |  | ➡️ [messages]( messages.md ).id |
| **status** | `ENUM(message_status)` | ❌ | - |  |  |
| **previous_status** | `ENUM(message_status)` | ✅ | - |  |  |
| **whatsapp_id** | `VARCHAR(255)` | ✅ | - |  |  |
| **whatsapp_timestamp** | `TIMESTAMP` | ✅ | - |  |  |
| **error_code** | `VARCHAR(50)` | ✅ | - |  |  |
| **error_message** | `TEXT` | ✅ | - |  |  |
| **retry_count** | `INTEGER` | ✅ | - |  |  |
| **metadata** | `JSONB` | ✅ | - |  |  |
| **evolution_event_type** | `VARCHAR(100)` | ✅ | - |  |  |
| **evolution_payload** | `JSONB` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_msg_status_error_time | ❌ | `error_code, created_at` |
| idx_msg_status_msg_created | ❌ | `message_id, created_at` |
| idx_msg_status_type_time | ❌ | `status, created_at` |
| idx_msg_status_whatsapp | ❌ | `whatsapp_id, status` |
| ix_message_status_events_created_at | ❌ | `created_at` |
| ix_message_status_events_error_code | ❌ | `error_code` |
| ix_message_status_events_id | ❌ | `id` |
| ix_message_status_events_message_id | ❌ | `message_id` |
| ix_message_status_events_status | ❌ | `status` |
| ix_message_status_events_whatsapp_id | ❌ | `whatsapp_id` |
