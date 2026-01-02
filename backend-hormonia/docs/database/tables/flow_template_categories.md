# Table: `flow_template_categories`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **category_key** | `VARCHAR(50)` | ❌ | - |  |  |
| **display_name** | `VARCHAR(255)` | ❌ | - |  |  |
| **description** | `TEXT` | ✅ | - |  |  |
| **icon** | `VARCHAR(100)` | ✅ | - |  |  |
| **sort_order** | `INTEGER` | ✅ | `0` |  |  |
| **is_active** | `BOOLEAN` | ✅ | `true` |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| flow_template_categories_category_key_key | ✅ | `category_key` |
