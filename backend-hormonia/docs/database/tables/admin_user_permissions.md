# Table: `admin_user_permissions`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **admin_user_id** | `UUID` | ❌ | - | 🔑 | ➡️ [admin_users]( admin_users.md ).id |
| **permission_id** | `UUID` | ❌ | - | 🔑 | ➡️ [admin_permissions]( admin_permissions.md ).id |
| **granted_at** | `TIMESTAMP` | ✅ | `CURRENT_TIMESTAMP` |  |  |
| **granted_by** | `UUID` | ✅ | - |  | ➡️ [admin_users]( admin_users.md ).id |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_admin_user_permissions_user | ❌ | `admin_user_id` |
