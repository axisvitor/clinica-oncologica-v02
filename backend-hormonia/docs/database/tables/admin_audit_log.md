# Table: `admin_audit_log`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **admin_user_id** | `UUID` | ✅ | - |  | ➡️ [admin_users]( admin_users.md ).id |
| **session_id** | `UUID` | ✅ | - |  | ➡️ [admin_sessions]( admin_sessions.md ).id |
| **event_type** | `VARCHAR(100)` | ❌ | - |  |  |
| **event_category** | `VARCHAR(50)` | ❌ | - |  |  |
| **action** | `VARCHAR(255)` | ❌ | - |  |  |
| **resource_type** | `VARCHAR(100)` | ✅ | - |  |  |
| **resource_id** | `VARCHAR(255)` | ✅ | - |  |  |
| **ip_address** | `INET` | ✅ | - |  |  |
| **user_agent** | `TEXT` | ✅ | - |  |  |
| **endpoint** | `VARCHAR(500)` | ✅ | - |  |  |
| **http_method** | `VARCHAR(7)` | ✅ | - |  |  |
| **details** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **changes** | `JSONB` | ✅ | - |  |  |
| **success** | `BOOLEAN` | ✅ | `true` |  |  |
| **error_message** | `TEXT` | ✅ | - |  |  |
| **timestamp** | `TIMESTAMP` | ✅ | `CURRENT_TIMESTAMP` |  |  |
| **duration_ms** | `INTEGER` | ✅ | - |  |  |
| **severity** | `VARCHAR(8)` | ✅ | `'low'::severity_type` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_admin_audit_event_type | ❌ | `event_type` |
| idx_admin_audit_ip | ❌ | `ip_address` |
| idx_admin_audit_resource | ❌ | `resource_type, resource_id` |
| idx_admin_audit_severity | ❌ | `severity` |
| idx_admin_audit_timestamp | ❌ | `timestamp` |
| idx_admin_audit_user_id | ❌ | `admin_user_id` |
