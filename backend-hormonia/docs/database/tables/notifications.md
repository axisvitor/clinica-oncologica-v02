# Table: `notifications`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **user_id** | `UUID` | ❌ | - |  | ➡️ [users]( users.md ).id |
| **related_patient_id** | `UUID` | ✅ | - |  | ➡️ [patients]( patients.md ).id |
| **notification_type** | `ENUM(notificationtype)` | ❌ | - |  |  |
| **priority** | `ENUM(notificationpriority)` | ❌ | - |  |  |
| **title** | `VARCHAR(200)` | ❌ | - |  |  |
| **message** | `TEXT` | ❌ | - |  |  |
| **action_url** | `VARCHAR(500)` | ✅ | - |  |  |
| **action_label** | `VARCHAR(100)` | ✅ | - |  |  |
| **notification_metadata** | `JSONB` | ✅ | - |  |  |
| **is_read** | `BOOLEAN` | ❌ | - |  |  |
| **read_at** | `TIMESTAMP` | ✅ | - |  |  |
| **is_archived** | `BOOLEAN` | ❌ | - |  |  |
| **archived_at** | `TIMESTAMP` | ✅ | - |  |  |
| **expires_at** | `TIMESTAMP` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `CURRENT_TIMESTAMP` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `CURRENT_TIMESTAMP` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_notifications_expires_at | ❌ | `expires_at` |
| ix_notifications_id | ❌ | `id` |
| ix_notifications_is_archived | ❌ | `is_archived` |
| ix_notifications_is_read | ❌ | `is_read` |
| ix_notifications_notification_type | ❌ | `notification_type` |
| ix_notifications_priority | ❌ | `priority` |
| ix_notifications_related_patient_id | ❌ | `related_patient_id` |
| ix_notifications_user_id | ❌ | `user_id` |
