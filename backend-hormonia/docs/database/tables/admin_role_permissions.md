# Table: `admin_role_permissions`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **role_id** | `UUID` | ❌ | - | 🔑 | ➡️ [admin_roles]( admin_roles.md ).id |
| **permission_id** | `UUID` | ❌ | - | 🔑 | ➡️ [admin_permissions]( admin_permissions.md ).id |
| **created_at** | `TIMESTAMP` | ✅ | `CURRENT_TIMESTAMP` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_admin_role_permissions_role | ❌ | `role_id` |
