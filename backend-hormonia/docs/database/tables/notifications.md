# Table: `notifications`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **user_id** | `UUID` | ❌ | - |  | ➡️ [users]( users.md ).id |
| **related_patient_id** | `UUID` | ✅ | - |  | ➡️ [patients]( patients.md ).id |
| **notification_type** | `VARCHAR(50)` | ❌ | - |  |  |
| **priority** | `VARCHAR(50)` | ❌ | `'medium'::character varying` |  |  |
| **title** | `VARCHAR(200)` | ❌ | - |  |  |
| **message** | `TEXT` | ❌ | - |  |  |
| **action_url** | `VARCHAR(500)` | ✅ | - |  |  |
| **action_label** | `VARCHAR(100)` | ✅ | - |  |  |
| **notification_metadata** | `JSONB` | ✅ | - |  |  |
| **is_read** | `BOOLEAN` | ❌ | `false` |  |  |
| **read_at** | `TIMESTAMP` | ✅ | - |  |  |
| **is_archived** | `BOOLEAN` | ❌ | `false` |  |  |
| **archived_at** | `TIMESTAMP` | ✅ | - |  |  |
| **expires_at** | `TIMESTAMP` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `CURRENT_TIMESTAMP` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `CURRENT_TIMESTAMP` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_notifications_expires_at | ❌ | `expires_at` |
| idx_notifications_is_archived | ❌ | `is_archived` |
| idx_notifications_is_read | ❌ | `is_read` |
| idx_notifications_priority | ❌ | `priority` |
| idx_notifications_related_patient_id | ❌ | `related_patient_id` |
| idx_notifications_type | ❌ | `notification_type` |
| idx_notifications_user_id | ❌ | `user_id` |
| idx_notifications_user_unread | ❌ | `user_id, is_read, is_archived` |
