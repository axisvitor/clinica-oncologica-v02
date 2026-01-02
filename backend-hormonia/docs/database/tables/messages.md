# Table: `messages`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **direction** | `VARCHAR(8)` | ❌ | - |  |  |
| **type** | `VARCHAR(22)` | ❌ | `'text'::message_type` |  |  |
| **content** | `TEXT` | ✅ | - |  |  |
| **message_metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **whatsapp_id** | `VARCHAR(255)` | ✅ | - |  |  |
| **status** | `VARCHAR(9)` | ❌ | `'pending'::message_status` |  |  |
| **scheduled_for** | `TIMESTAMP` | ✅ | - |  |  |
| **sent_at** | `TIMESTAMP` | ✅ | - |  |  |
| **delivered_at** | `TIMESTAMP` | ✅ | - |  |  |
| **read_at** | `TIMESTAMP` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **delivery_status** | `VARCHAR(9)` | ✅ | - |  |  |
| **retry_count** | `INTEGER` | ❌ | `0` |  |  |
| **last_retry_at** | `TIMESTAMP` | ✅ | - |  |  |
| **failure_reason** | `TEXT` | ✅ | - |  |  |
| **next_retry_at** | `TIMESTAMP` | ✅ | - |  |  |
| **idempotency_key** | `VARCHAR(255)` | ❌ | - |  |  |
| **priority** | `VARCHAR(8)` | ❌ | `'normal'::message_priority` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_message_cursor_pagination | ❌ | `created_at, id` |
| idx_messages_created_at | ❌ | `created_at` |
| idx_messages_cursor_optimized | ❌ | `patient_id, created_at, id` |
| idx_messages_direction | ❌ | `direction` |
| idx_messages_direction_created_desc | ❌ | `direction, created_at` |
| idx_messages_direction_created_new | ❌ | `direction, created_at` |
| idx_messages_direction_created_opt | ❌ | `direction, created_at` |
| idx_messages_idempotency_key | ❌ | `idempotency_key` |
| idx_messages_patient_created | ❌ | `patient_id, created_at` |
| idx_messages_patient_created_desc | ❌ | `patient_id, created_at` |
| idx_messages_patient_created_opt | ❌ | `patient_id, created_at` |
| idx_messages_patient_direction_created_desc | ❌ | `patient_id, direction, created_at` |
| idx_messages_patient_direction_created_opt | ❌ | `patient_id, direction, created_at` |
| idx_messages_patient_id | ❌ | `patient_id` |
| idx_messages_patient_id_created_new | ❌ | `patient_id, created_at` |
| idx_messages_patient_idempotency | ✅ | `patient_id, idempotency_key` |
| idx_messages_patient_status | ❌ | `patient_id, status` |
| idx_messages_scheduled_for | ❌ | `scheduled_for` |
| idx_messages_status | ❌ | `status` |
| idx_messages_status_created | ❌ | `status, created_at` |
| idx_messages_status_created_desc | ❌ | `status, created_at` |
| idx_messages_whatsapp_id | ❌ | `whatsapp_id` |
| ix_messages_cursor_pagination | ❌ | `created_at, id` |
| ix_messages_patient_cursor | ❌ | `patient_id, created_at, id` |
