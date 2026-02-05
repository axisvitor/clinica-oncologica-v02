# Table: `flow_messages`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **flow_template_version_id** | `UUID` | ❌ | - |  | ➡️ [flow_template_versions]( flow_template_versions.md ).id |
| **step_number** | `INTEGER` | ❌ | - |  |  |
| **message_key** | `VARCHAR(100)` | ❌ | - |  |  |
| **message_text** | `TEXT` | ❌ | - |  |  |
| **message_type** | `VARCHAR(50)` | ✅ | `'text'::character varying` |  |  |
| **buttons** | `JSONB` | ✅ | - |  |  |
| **list_items** | `JSONB` | ✅ | - |  |  |
| **conditions** | `JSONB` | ✅ | - |  |  |
| **delay_seconds** | `INTEGER` | ✅ | `0` |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_flow_messages_step | ❌ | `flow_template_version_id, step_number` |
| idx_flow_messages_template | ❌ | `flow_template_version_id` |
| idx_flow_messages_template_step | ❌ | `flow_template_version_id, step_number` |
| idx_flow_messages_template_version_id | ❌ | `flow_template_version_id` |
| unique_flow_message | ✅ | `flow_template_version_id, step_number, message_key` |
