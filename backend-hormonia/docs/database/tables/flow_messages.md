# Table: `flow_messages`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **flow_template_version_id** | `UUID` | ❌ | - |  | ➡️ [flow_template_versions]( flow_template_versions.md ).id |
| **step_number** | `INTEGER` | ❌ | - |  |  |
| **message_key** | `VARCHAR(100)` | ❌ | - |  |  |
| **message_text** | `TEXT` | ❌ | - |  |  |
| **message_type** | `VARCHAR(50)` | ✅ | - |  |  |
| **buttons** | `JSONB` | ✅ | - |  |  |
| **list_items** | `JSONB` | ✅ | - |  |  |
| **conditions** | `JSONB` | ✅ | - |  |  |
| **delay_seconds** | `INTEGER` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_flow_messages_flow_template_version_id | ❌ | `flow_template_version_id` |
| ix_flow_messages_id | ❌ | `id` |
