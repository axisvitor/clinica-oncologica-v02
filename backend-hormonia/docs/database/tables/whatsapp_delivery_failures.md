# Table: `whatsapp_delivery_failures`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **phone_number** | `VARCHAR(20)` | ❌ | - |  |  |
| **message_type** | `VARCHAR(50)` | ❌ | - |  |  |
| **message_content** | `TEXT` | ✅ | - |  |  |
| **error_message** | `TEXT` | ❌ | - |  |  |
| **error_code** | `VARCHAR(50)` | ✅ | - |  |  |
| **retry_count** | `INTEGER` | ❌ | `0` |  |  |
| **max_retries** | `INTEGER` | ❌ | `3` |  |  |
| **next_retry_at** | `TIMESTAMP` | ✅ | - |  |  |
| **last_retry_at** | `TIMESTAMP` | ✅ | - |  |  |
| **status** | `VARCHAR(20)` | ❌ | `'pending'::character varying` |  |  |
| **resolved_at** | `TIMESTAMP` | ✅ | - |  |  |
| **dlq_metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **reviewed_by** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **original_message_id** | `UUID` | ✅ | - |  | ➡️ [messages]( messages.md ).id |
| **created_at** | `TIMESTAMP` | ❌ | `timezone('utc'::text, now())` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `timezone('utc'::text, now())` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_whatsapp_delivery_failures_created_at | ❌ | `created_at` |
| idx_whatsapp_delivery_failures_patient | ❌ | `patient_id` |
| idx_whatsapp_delivery_failures_status_nextretry | ❌ | `status, next_retry_at` |
