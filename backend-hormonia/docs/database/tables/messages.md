# Table: `messages`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **direction** | `ENUM(message_direction)` | ❌ | - |  |  |
| **type** | `ENUM(messagetype)` | ❌ | - |  |  |
| **content** | `TEXT` | ✅ | - |  |  |
| **message_metadata** | `JSONB` | ✅ | - |  |  |
| **whatsapp_id** | `VARCHAR(255)` | ✅ | - |  |  |
| **status** | `ENUM(message_status)` | ❌ | - |  |  |
| **scheduled_for** | `TIMESTAMP` | ✅ | - |  |  |
| **sent_at** | `TIMESTAMP` | ✅ | - |  |  |
| **delivered_at** | `TIMESTAMP` | ✅ | - |  |  |
| **read_at** | `TIMESTAMP` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **delivery_status** | `ENUM(message_delivery_status)` | ✅ | - |  |  |
| **retry_count** | `INTEGER` | ❌ | - |  |  |
| **last_retry_at** | `TIMESTAMP` | ✅ | - |  |  |
| **failure_reason** | `TEXT` | ✅ | - |  |  |
| **next_retry_at** | `TIMESTAMP` | ✅ | - |  |  |
| **idempotency_key** | `VARCHAR(255)` | ❌ | - |  |  |
| **priority** | `ENUM(message_priority)` | ❌ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_messages_idempotency_key | ❌ | `idempotency_key` |
| ix_messages_outbound_queue_pending | ❌ | `scheduled_for, id` |
| ix_messages_patient_created_desc | ❌ | `patient_id, created_at, id` |
| ix_messages_patient_id | ❌ | `patient_id` |
| ix_messages_status_pending_schedule | ❌ | `status, scheduled_for` |
| ix_messages_whatsapp_id | ❌ | `whatsapp_id` |
| ux_messages_patient_idempotency | ✅ | `patient_id, idempotency_key` |
