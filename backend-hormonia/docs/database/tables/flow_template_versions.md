# Table: `flow_template_versions`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **flow_kind_id** | `UUID` | ❌ | - |  | ➡️ [flow_kinds]( flow_kinds.md ).id |
| **version_number** | `INTEGER` | ❌ | - |  |  |
| **template_name** | `VARCHAR(255)` | ❌ | - |  |  |
| **description** | `TEXT` | ✅ | - |  |  |
| **steps** | `JSONB` | ❌ | - |  |  |
| **metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **is_active** | `BOOLEAN` | ✅ | `false` |  |  |
| **is_draft** | `BOOLEAN` | ✅ | `true` |  |  |
| **published_at** | `TIMESTAMP` | ✅ | - |  |  |
| **deprecated_at** | `TIMESTAMP` | ✅ | - |  |  |
| **created_by** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **created_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ✅ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_flow_template_versions_active | ❌ | `flow_kind_id, is_active` |
| idx_flow_template_versions_flow_kind | ❌ | `flow_kind_id` |
| idx_flow_template_versions_version | ❌ | `flow_kind_id, version_number` |
| unique_flow_version | ✅ | `flow_kind_id, version_number` |
