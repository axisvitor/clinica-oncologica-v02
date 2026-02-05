# Table: `quiz_response_migration_log`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **quiz_response_id** | `UUID` | ❌ | - |  |  |
| **original_value** | `TEXT` | ✅ | - |  |  |
| **converted_value** | `JSONB` | ✅ | - |  |  |
| **conversion_status** | `TEXT` | ❌ | - |  |  |
| **error_message** | `TEXT` | ✅ | - |  |  |
| **migrated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_migration_log_errors | ❌ | `quiz_response_id` |
| idx_migration_log_status | ❌ | `conversion_status` |
