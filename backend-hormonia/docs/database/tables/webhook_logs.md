# Table: `webhook_logs`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **webhook_id** | `UUID` | ❌ | - |  | ➡️ [webhook_endpoints]( webhook_endpoints.md ).id |
| **event_type** | `VARCHAR(100)` | ❌ | - |  |  |
| **action** | `VARCHAR(100)` | ❌ | - |  |  |
| **details** | `JSONB` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_webhook_log_created_at | ❌ | `created_at` |
| idx_webhook_log_webhook_id | ❌ | `webhook_id` |
