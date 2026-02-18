# Table: `flow_kinds`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **kind_key** | `VARCHAR(100)` | ❌ | - |  |  |
| **display_name** | `VARCHAR(255)` | ❌ | - |  |  |
| **description** | `TEXT` | ✅ | - |  |  |
| **is_active** | `BOOLEAN` | ✅ | `true` |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| flow_kinds_kind_key_key | ✅ | `kind_key` |
| ix_flow_kinds_id | ❌ | `id` |
| ix_flow_kinds_kind_key | ✅ | `kind_key` |
