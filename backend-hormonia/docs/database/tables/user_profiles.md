# Table: `user_profiles`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **user_id** | `UUID` | ❌ | - |  | ➡️ [users]( users.md ).id |
| **bio** | `TEXT` | ✅ | - |  |  |
| **avatar_url** | `VARCHAR(500)` | ✅ | - |  |  |
| **phone** | `VARCHAR(20)` | ✅ | - |  |  |
| **specialty** | `VARCHAR(255)` | ✅ | - |  |  |
| **license_number** | `VARCHAR(100)` | ✅ | - |  |  |
| **years_of_experience** | `INTEGER` | ✅ | - |  |  |
| **preferences** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **notification_settings** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ✅ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_user_profiles_user_id | ❌ | `user_id` |
| user_profiles_user_id_key | ✅ | `user_id` |
