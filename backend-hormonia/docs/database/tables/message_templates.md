# Table: `message_templates`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **name** | `VARCHAR` | ❌ | - |  |  |
| **content** | `TEXT` | ❌ | - |  |  |
| **variables** | `JSONB` | ✅ | - |  |  |
| **message_type** | `VARCHAR` | ❌ | - |  |  |
| **media_url** | `VARCHAR` | ✅ | - |  |  |
| **is_active** | `BOOLEAN` | ❌ | - |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_message_templates_name | ✅ | `name` |
