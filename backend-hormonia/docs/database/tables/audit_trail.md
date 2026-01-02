# Table: `audit_trail`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **table_name** | `VARCHAR(255)` | ❌ | - |  |  |
| **record_id** | `UUID` | ❌ | - |  |  |
| **operation** | `VARCHAR(50)` | ❌ | - |  |  |
| **old_data** | `JSONB` | ✅ | - |  |  |
| **new_data** | `JSONB` | ✅ | - |  |  |
| **changes** | `JSONB` | ✅ | - |  |  |
| **actor_id** | `UUID` | ✅ | - |  |  |
| **actor_type** | `VARCHAR(50)` | ✅ | - |  |  |
| **actor_subject** | `VARCHAR(255)` | ✅ | - |  |  |
| **ip_address** | `INET` | ✅ | - |  |  |
| **user_agent** | `TEXT` | ✅ | - |  |  |
| **endpoint** | `VARCHAR(500)` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_audit_trail_actor | ❌ | `actor_id, created_at` |
| idx_audit_trail_created_at | ❌ | `created_at` |
| idx_audit_trail_operation | ❌ | `operation, created_at` |
| idx_audit_trail_table_record | ❌ | `table_name, record_id` |
