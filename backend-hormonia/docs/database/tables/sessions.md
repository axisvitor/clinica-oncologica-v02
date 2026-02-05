# Table: `sessions`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **user_id** | `UUID` | ❌ | - |  | ➡️ [users]( users.md ).id |
| **session_token** | `VARCHAR(500)` | ❌ | - |  |  |
| **refresh_token** | `VARCHAR(500)` | ✅ | - |  |  |
| **device_id** | `VARCHAR(200)` | ✅ | - |  |  |
| **device_name** | `VARCHAR(200)` | ✅ | - |  |  |
| **device_type** | `VARCHAR(50)` | ✅ | - |  |  |
| **ip_address** | `VARCHAR(45)` | ✅ | - |  |  |
| **user_agent** | `TEXT` | ✅ | - |  |  |
| **location** | `JSONB` | ✅ | - |  |  |
| **last_activity** | `TIMESTAMP` | ❌ | - |  |  |
| **expires_at** | `TIMESTAMP` | ❌ | - |  |  |
| **is_active** | `BOOLEAN` | ❌ | - |  |  |
| **revoked_at** | `TIMESTAMP` | ✅ | - |  |  |
| **revocation_reason** | `TEXT` | ✅ | - |  |  |
| **is_suspicious** | `BOOLEAN` | ❌ | - |  |  |
| **risk_score** | `VARCHAR(50)` | ✅ | - |  |  |
| **session_metadata** | `JSONB` | ✅ | - |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_sessions_device_id | ❌ | `device_id` |
| ix_sessions_expires_at | ❌ | `expires_at` |
| ix_sessions_id | ❌ | `id` |
| ix_sessions_is_active | ❌ | `is_active` |
| ix_sessions_is_suspicious | ❌ | `is_suspicious` |
| ix_sessions_last_activity | ❌ | `last_activity` |
| ix_sessions_refresh_token | ✅ | `refresh_token` |
| ix_sessions_session_token | ✅ | `session_token` |
| ix_sessions_user_id | ❌ | `user_id` |
