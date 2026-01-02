# Table: `webhook_idempotency`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **event_id** | `VARCHAR(255)` | ❌ | - | 🔑 |  |
| **provider** | `VARCHAR(50)` | ❌ | - |  |  |
| **event_type** | `VARCHAR(100)` | ❌ | - |  |  |
| **received_at** | `TIMESTAMP` | ❌ | `CURRENT_TIMESTAMP` |  |  |
| **processed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **expires_at** | `TIMESTAMP` | ❌ | - |  |  |
| **status** | `VARCHAR(20)` | ❌ | - |  |  |
| **retry_count** | `INTEGER` | ❌ | - |  |  |
| **payload** | `JSONB` | ✅ | - |  |  |
| **response_data** | `JSONB` | ✅ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_webhook_idempotency_expires_at | ❌ | `expires_at` |
| idx_webhook_idempotency_provider_type | ❌ | `provider, event_type` |
| idx_webhook_idempotency_received_at | ❌ | `received_at` |
| idx_webhook_idempotency_status | ❌ | `status` |
| ix_webhook_idempotency_event_type | ❌ | `event_type` |
| ix_webhook_idempotency_expires_at | ❌ | `expires_at` |
| ix_webhook_idempotency_provider | ❌ | `provider` |
