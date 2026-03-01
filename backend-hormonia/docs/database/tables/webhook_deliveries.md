# Table: `webhook_deliveries`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **webhook_id** | `UUID` | ❌ | - |  | ➡️ [webhook_endpoints]( webhook_endpoints.md ).id |
| **event_type** | `VARCHAR(100)` | ❌ | - |  |  |
| **payload** | `JSONB` | ✅ | - |  |  |
| **status** | `ENUM(webhook_delivery_status)` | ❌ | - |  |  |
| **attempt** | `INTEGER` | ❌ | - |  |  |
| **status_code** | `INTEGER` | ✅ | - |  |  |
| **response_time_ms** | `DOUBLE PRECISION` | ✅ | - |  |  |
| **response_body** | `TEXT` | ✅ | - |  |  |
| **error** | `TEXT` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | - |  |  |
| **completed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **next_retry_at** | `TIMESTAMP` | ✅ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_webhook_delivery_created_at | ❌ | `created_at` |
| idx_webhook_delivery_status | ❌ | `status` |
| idx_webhook_delivery_webhook_id | ❌ | `webhook_id` |
