# Table: `error_logs`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **error_type** | `VARCHAR(100)` | ❌ | - |  |  |
| **error_message** | `TEXT` | ❌ | - |  |  |
| **stack_trace** | `TEXT` | ✅ | - |  |  |
| **context** | `JSONB` | ❌ | `'{}'::jsonb` |  |  |
| **count** | `INTEGER` | ❌ | `1` |  |  |
| **first_seen** | `TIMESTAMP` | ❌ | `CURRENT_TIMESTAMP` |  |  |
| **last_seen** | `TIMESTAMP` | ❌ | `CURRENT_TIMESTAMP` |  |  |
| **resolved** | `BOOLEAN` | ❌ | `false` |  |  |
| **severity** | `VARCHAR(20)` | ❌ | `'ERROR'::character varying` |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `CURRENT_TIMESTAMP` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `CURRENT_TIMESTAMP` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_error_logs_context_gin | ❌ | `context` |
| idx_error_logs_count | ❌ | `count` |
| idx_error_logs_deduplication | ✅ | `error_type, <expr>` |
| idx_error_logs_error_type | ❌ | `error_type` |
| idx_error_logs_first_seen | ❌ | `first_seen` |
| idx_error_logs_last_seen | ❌ | `last_seen` |
| idx_error_logs_resolved | ❌ | `resolved` |
| idx_error_logs_severity | ❌ | `severity` |
| idx_error_logs_severity_time | ❌ | `severity, last_seen` |
| idx_error_logs_type_resolved | ❌ | `error_type, resolved` |
| idx_error_logs_unresolved_recent | ❌ | `resolved, last_seen` |
