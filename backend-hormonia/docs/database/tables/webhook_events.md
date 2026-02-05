# Table: `webhook_events`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **event_type** | `VARCHAR(100)` | ❌ | - |  |  |
| **source** | `VARCHAR(100)` | ❌ | `'evolution_api'::character varying` |  |  |
| **payload** | `JSONB` | ❌ | - |  |  |
| **processed** | `BOOLEAN` | ❌ | `false` |  |  |
| **processed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **retry_count** | `INTEGER` | ✅ | `0` |  |  |
| **max_retries** | `INTEGER` | ✅ | `3` |  |  |
| **next_retry_at** | `TIMESTAMP` | ✅ | - |  |  |
| **error_message** | `TEXT` | ✅ | - |  |  |
| **error_stack_trace** | `TEXT` | ✅ | - |  |  |
| **related_message_id** | `UUID` | ✅ | - |  | ➡️ [messages]( messages.md ).id |
| **related_patient_id** | `UUID` | ✅ | - |  | ➡️ [patients]( patients.md ).id |
| **event_hash** | `VARCHAR(64)` | ❌ | - |  |  |
| **is_duplicate** | `BOOLEAN` | ✅ | `false` |  |  |
| **original_event_id** | `UUID` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_webhook_events_cursor_pagination | ❌ | `created_at, id` |
| idx_webhook_pending | ❌ | `processed, retry_count, created_at` |
| idx_webhook_related_msg | ❌ | `related_message_id, event_type` |
| idx_webhook_related_patient | ❌ | `related_patient_id, event_type` |
| idx_webhook_retry_schedule | ❌ | `processed, next_retry_at` |
| idx_webhook_source_time | ❌ | `source, created_at` |
| idx_webhook_type_processed | ❌ | `event_type, processed, created_at` |
| webhook_events_event_hash_key | ✅ | `event_hash` |
