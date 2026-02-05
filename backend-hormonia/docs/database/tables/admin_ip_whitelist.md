# Table: `admin_ip_whitelist`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **ip_address** | `INET` | ✅ | - |  |  |
| **ip_range** | `CIDR` | ✅ | - |  |  |
| **description** | `TEXT` | ✅ | - |  |  |
| **added_by** | `UUID` | ✅ | - |  | ➡️ [admin_users]( admin_users.md ).id |
| **added_at** | `TIMESTAMP` | ✅ | `CURRENT_TIMESTAMP` |  |  |
| **is_active** | `BOOLEAN` | ✅ | `true` |  |  |
| **expires_at** | `TIMESTAMP` | ✅ | - |  |  |
| **last_used_at** | `TIMESTAMP` | ✅ | - |  |  |
| **usage_count** | `INTEGER` | ✅ | `0` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_ip_whitelist_active | ❌ | `is_active, ip_address` |
| idx_ip_whitelist_range | ❌ | `ip_range` |
| unique_ip_or_range | ✅ | `ip_address, ip_range` |
