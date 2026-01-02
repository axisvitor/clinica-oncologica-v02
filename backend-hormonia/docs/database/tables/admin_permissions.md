# Table: `admin_permissions`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **name** | `VARCHAR(100)` | ❌ | - |  |  |
| **description** | `TEXT` | ✅ | - |  |  |
| **category** | `VARCHAR(50)` | ❌ | - |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `CURRENT_TIMESTAMP` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| admin_permissions_name_key | ✅ | `name` |
| idx_admin_permissions_category | ❌ | `category` |
