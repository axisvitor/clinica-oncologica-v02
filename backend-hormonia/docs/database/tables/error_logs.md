# Table: `error_logs`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **error_type** | `VARCHAR(100)` | ❌ | - |  |  |
| **error_message** | `TEXT` | ❌ | - |  |  |
| **stack_trace** | `TEXT` | ✅ | - |  |  |
| **context** | `JSONB` | ❌ | - |  |  |
| **count** | `INTEGER` | ❌ | - |  |  |
| **first_seen** | `TIMESTAMP` | ❌ | `CURRENT_TIMESTAMP` |  |  |
| **last_seen** | `TIMESTAMP` | ❌ | `CURRENT_TIMESTAMP` |  |  |
| **resolved** | `BOOLEAN` | ❌ | - |  |  |
| **severity** | `VARCHAR(20)` | ❌ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `CURRENT_TIMESTAMP` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `CURRENT_TIMESTAMP` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_error_logs_error_type | ❌ | `error_type` |
| ix_error_logs_id | ❌ | `id` |
