# Table: `user_sync_log`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | - | 🔑 |  |
| **firebase_uid** | `VARCHAR(255)` | ❌ | - |  |  |
| **error_message** | `TEXT` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **user_id** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **operation** | `VARCHAR(50)` | ❌ | - |  |  |
| **sync_direction** | `VARCHAR(20)` | ❌ | - |  |  |
| **changes** | `JSONB` | ❌ | - |  |  |
| **success** | `BOOLEAN` | ❌ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_user_sync_log_created_at | ❌ | `created_at` |
| ix_user_sync_log_firebase_uid | ❌ | `firebase_uid` |
| ix_user_sync_log_updated_at | ❌ | `updated_at` |
| ix_user_sync_log_user_id | ❌ | `user_id` |
