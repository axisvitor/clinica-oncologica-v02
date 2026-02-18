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
| **retry_count** | `INTEGER` | ❌ | - |  |  |
| **max_retries** | `INTEGER` | ❌ | - |  |  |
| **next_retry_at** | `TIMESTAMP` | ✅ | - |  |  |
| **last_retry_at** | `TIMESTAMP` | ✅ | - |  |  |
| **status** | `ENUM(dlq_status)` | ❌ | - |  |  |
| **resolved_at** | `TIMESTAMP` | ✅ | - |  |  |
| **dlq_metadata** | `JSONB` | ✅ | - |  |  |
| **reviewed_by** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **original_message_id** | `UUID` | ✅ | - |  | ➡️ [messages]( messages.md ).id |
| **created_at** | `TIMESTAMP` | ❌ | `timezone('utc'::text, now())` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `timezone('utc'::text, now())` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_whatsapp_delivery_failures_id | ❌ | `id` |
| ix_whatsapp_delivery_failures_original_message_id | ❌ | `original_message_id` |
| ix_whatsapp_delivery_failures_patient_id | ❌ | `patient_id` |
