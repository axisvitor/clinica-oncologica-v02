# Table: `flow_template_versions`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **flow_kind_id** | `UUID` | ❌ | - |  | ➡️ [flow_kinds]( flow_kinds.md ).id |
| **version_number** | `INTEGER` | ❌ | - |  |  |
| **template_name** | `VARCHAR(255)` | ❌ | - |  |  |
| **description** | `TEXT` | ✅ | - |  |  |
| **steps** | `JSONB` | ✅ | - |  |  |
| **metadata** | `JSONB` | ✅ | - |  |  |
| **is_active** | `BOOLEAN` | ✅ | `false` |  |  |
| **is_draft** | `BOOLEAN` | ✅ | `true` |  |  |
| **published_at** | `TIMESTAMP` | ✅ | - |  |  |
| **deprecated_at** | `TIMESTAMP` | ✅ | - |  |  |
| **created_by** | `UUID` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_ftv_kind_active | ❌ | `flow_kind_id, is_active` |
| ix_flow_template_versions_flow_kind_id | ❌ | `flow_kind_id` |
| ix_flow_template_versions_id | ❌ | `id` |
| unique_flow_version | ✅ | `flow_kind_id, version_number` |
