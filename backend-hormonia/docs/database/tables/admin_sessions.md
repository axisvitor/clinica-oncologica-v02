# Table: `admin_sessions`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **admin_user_id** | `UUID` | ❌ | - |  | ➡️ [admin_users]( admin_users.md ).id |
| **session_token** | `VARCHAR(255)` | ❌ | - |  |  |
| **refresh_token** | `VARCHAR(255)` | ✅ | - |  |  |
| **ip_address** | `INET` | ✅ | - |  |  |
| **user_agent** | `TEXT` | ✅ | - |  |  |
| **device_fingerprint** | `VARCHAR(255)` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `CURRENT_TIMESTAMP` |  |  |
| **last_activity** | `TIMESTAMP` | ✅ | `CURRENT_TIMESTAMP` |  |  |
| **expires_at** | `TIMESTAMP` | ❌ | - |  |  |
| **is_active** | `BOOLEAN` | ✅ | `true` |  |  |
| **logout_reason** | `VARCHAR(100)` | ✅ | - |  |  |
| **metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| admin_sessions_refresh_token_key | ✅ | `refresh_token` |
| admin_sessions_session_token_key | ✅ | `session_token` |
| idx_admin_sessions_active | ❌ | `is_active, last_activity` |
| idx_admin_sessions_expires | ❌ | `expires_at` |
| idx_admin_sessions_ip | ❌ | `ip_address` |
| idx_admin_sessions_token | ❌ | `session_token` |
| idx_admin_sessions_user_id | ❌ | `admin_user_id` |
