# Table: `user_sync_log`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **firebase_uid** | `VARCHAR(255)` | ❌ | - |  |  |
| **supabase_user_id** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **sync_action** | `VARCHAR(50)` | ✅ | - |  |  |
| **sync_status** | `VARCHAR(50)` | ✅ | - |  |  |
| **firebase_data** | `JSONB` | ✅ | - |  |  |
| **supabase_data** | `JSONB` | ✅ | - |  |  |
| **error_message** | `TEXT` | ✅ | - |  |  |
| **retry_count** | `INTEGER` | ✅ | `0` |  |  |
| **synced_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **user_id** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **operation** | `VARCHAR(50)` | ❌ | - |  |  |
| **sync_direction** | `VARCHAR(20)` | ❌ | - |  |  |
| **changes** | `JSONB` | ❌ | `'{}'::jsonb` |  |  |
| **success** | `BOOLEAN` | ❌ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_user_sync_log_firebase_uid | ❌ | `firebase_uid` |
| idx_user_sync_log_status | ❌ | `sync_status, synced_at` |
| idx_user_sync_log_supabase_user | ❌ | `supabase_user_id` |
| idx_user_sync_log_updated_at | ❌ | `updated_at` |
| ix_user_sync_log_created_at | ❌ | `created_at` |
| ix_user_sync_log_firebase_uid | ❌ | `firebase_uid` |
| ix_user_sync_log_user_id | ❌ | `user_id` |
