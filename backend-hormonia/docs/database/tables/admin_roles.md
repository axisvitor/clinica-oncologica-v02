# Table: `admin_roles`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **name** | `VARCHAR(50)` | ❌ | - |  |  |
| **description** | `TEXT` | ✅ | - |  |  |
| **is_system_role** | `BOOLEAN` | ✅ | `false` |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `CURRENT_TIMESTAMP` |  |  |
| **updated_at** | `TIMESTAMP` | ✅ | `CURRENT_TIMESTAMP` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| admin_roles_name_key | ✅ | `name` |
