# Table: `webhook_events`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **event_type** | `VARCHAR(100)` | ❌ | - |  |  |
| **source** | `VARCHAR(100)` | ❌ | - |  |  |
| **payload** | `JSONB` | ❌ | - |  |  |
| **processed** | `BOOLEAN` | ❌ | - |  |  |
| **processed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **retry_count** | `INTEGER` | ✅ | - |  |  |
| **max_retries** | `INTEGER` | ✅ | - |  |  |
| **next_retry_at** | `TIMESTAMP` | ✅ | - |  |  |
| **error_message** | `TEXT` | ✅ | - |  |  |
| **error_stack_trace** | `TEXT` | ✅ | - |  |  |
| **related_message_id** | `UUID` | ✅ | - |  |  |
| **related_patient_id** | `UUID` | ✅ | - |  |  |
| **event_hash** | `VARCHAR(64)` | ❌ | - |  |  |
| **is_duplicate** | `BOOLEAN` | ✅ | - |  |  |
| **original_event_id** | `UUID` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_webhook_events_created_at | ❌ | `created_at` |
| ix_webhook_events_event_hash | ✅ | `event_hash` |
| ix_webhook_events_event_type | ❌ | `event_type` |
| ix_webhook_events_id | ❌ | `id` |
| ix_webhook_events_is_duplicate | ❌ | `is_duplicate` |
| ix_webhook_events_next_retry_at | ❌ | `next_retry_at` |
| ix_webhook_events_processed | ❌ | `processed` |
| ix_webhook_events_related_message_id | ❌ | `related_message_id` |
| ix_webhook_events_related_patient_id | ❌ | `related_patient_id` |
| ix_webhook_events_source | ❌ | `source` |
| ix_webhook_pending | ❌ | `processed, retry_count, created_at` |
| ix_webhook_related_msg | ❌ | `related_message_id, event_type` |
| ix_webhook_related_patient | ❌ | `related_patient_id, event_type` |
| ix_webhook_retry_schedule | ❌ | `processed, next_retry_at` |
| ix_webhook_source_time | ❌ | `source, created_at` |
| ix_webhook_type_processed | ❌ | `event_type, processed, created_at` |
