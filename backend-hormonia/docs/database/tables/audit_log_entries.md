# Table: `audit_log_entries`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **event_type** | `VARCHAR(100)` | ❌ | - |  |  |
| **entity_type** | `VARCHAR(100)` | ✅ | - |  |  |
| **entity_id** | `UUID` | ✅ | - |  |  |
| **user_id** | `UUID` | ✅ | - |  |  |
| **old_values** | `JSONB` | ✅ | - |  |  |
| **new_values** | `JSONB` | ✅ | - |  |  |
| **metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **ip_address** | `INET` | ✅ | - |  |  |
| **user_agent** | `TEXT` | ✅ | - |  |  |
| **timestamp** | `TIMESTAMP` | ✅ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_audit_log_entries_entity | ❌ | `entity_type, entity_id` |
| idx_audit_log_entries_timestamp | ❌ | `timestamp` |
| idx_audit_log_entries_user | ❌ | `user_id, timestamp` |
