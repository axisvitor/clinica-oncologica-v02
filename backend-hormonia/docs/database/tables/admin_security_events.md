# Table: `admin_security_events`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **event_type** | `VARCHAR(100)` | ❌ | - |  |  |
| **severity** | `VARCHAR(8)` | ❌ | `'medium'::severity_type` |  |  |
| **ip_address** | `INET` | ✅ | - |  |  |
| **user_agent** | `TEXT` | ✅ | - |  |  |
| **admin_user_id** | `UUID` | ✅ | - |  | ➡️ [admin_users]( admin_users.md ).id |
| **session_id** | `UUID` | ✅ | - |  | ➡️ [admin_sessions]( admin_sessions.md ).id |
| **description** | `TEXT` | ✅ | - |  |  |
| **details** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **endpoint** | `VARCHAR(500)` | ✅ | - |  |  |
| **detected_at** | `TIMESTAMP` | ✅ | `CURRENT_TIMESTAMP` |  |  |
| **resolved_at** | `TIMESTAMP` | ✅ | - |  |  |
| **resolution_notes** | `TEXT` | ✅ | - |  |  |
| **auto_resolved** | `BOOLEAN` | ✅ | `false` |  |  |
| **risk_score** | `INTEGER` | ✅ | `0` |  |  |
| **threat_level** | `VARCHAR(8)` | ✅ | `'low'::severity_type` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_security_events_ip | ❌ | `ip_address` |
| idx_security_events_resolved | ❌ | `resolved_at` |
| idx_security_events_severity | ❌ | `severity` |
| idx_security_events_timestamp | ❌ | `detected_at` |
| idx_security_events_user_id | ❌ | `admin_user_id` |
