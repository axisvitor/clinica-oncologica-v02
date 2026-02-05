# Table: `flow_template_shares`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **flow_template_version_id** | `UUID` | ❌ | - |  | ➡️ [flow_template_versions]( flow_template_versions.md ).id |
| **shared_by** | `UUID` | ❌ | - |  | ➡️ [users]( users.md ).id |
| **shared_with** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **can_view** | `BOOLEAN` | ✅ | `true` |  |  |
| **can_edit** | `BOOLEAN` | ✅ | `false` |  |  |
| **can_reshare** | `BOOLEAN` | ✅ | `false` |  |  |
| **share_notes** | `TEXT` | ✅ | - |  |  |
| **shared_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **expires_at** | `TIMESTAMP` | ✅ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| unique_share | ✅ | `flow_template_version_id, shared_by, shared_with` |
