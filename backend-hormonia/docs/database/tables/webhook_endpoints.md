# Table: `webhook_endpoints`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | - | 🔑 |  |
| **url** | `VARCHAR(2048)` | ❌ | - |  |  |
| **description** | `VARCHAR(500)` | ✅ | - |  |  |
| **status** | `VARCHAR(20)` | ❌ | - |  |  |
| **secret** | `VARCHAR(255)` | ✅ | - |  |  |
| **events** | `JSONB` | ❌ | - |  |  |
| **headers** | `JSONB` | ✅ | - |  |  |
| **timeout** | `INTEGER` | ❌ | - |  |  |
| **retry_enabled** | `BOOLEAN` | ❌ | - |  |  |
| **max_retries** | `INTEGER` | ❌ | - |  |  |
| **success_count** | `INTEGER` | ❌ | - |  |  |
| **failure_count** | `INTEGER` | ❌ | - |  |  |
| **last_triggered_at** | `TIMESTAMP` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | - |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_webhook_status | ❌ | `status` |
