# Table: `admin_ip_blacklist`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **ip_address** | `INET` | ❌ | - |  |  |
| **reason** | `VARCHAR(255)` | ❌ | - |  |  |
| **blocked_at** | `TIMESTAMP` | ✅ | `CURRENT_TIMESTAMP` |  |  |
| **blocked_by** | `UUID` | ✅ | - |  | ➡️ [admin_users]( admin_users.md ).id |
| **expires_at** | `TIMESTAMP` | ✅ | - |  |  |
| **is_permanent** | `BOOLEAN` | ✅ | `false` |  |  |
| **incident_id** | `UUID` | ✅ | - |  |  |
| **threat_level** | `VARCHAR(8)` | ✅ | `'medium'::severity_type` |  |  |
| **block_count** | `INTEGER` | ✅ | `1` |  |  |
| **details** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **notes** | `TEXT` | ✅ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| admin_ip_blacklist_ip_address_key | ✅ | `ip_address` |
| idx_ip_blacklist_active | ❌ | `ip_address, expires_at` |
