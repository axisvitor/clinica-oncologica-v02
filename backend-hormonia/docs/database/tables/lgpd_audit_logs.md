# Table: `lgpd_audit_logs`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **user_id** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **user_email** | `VARCHAR(255)` | ✅ | - |  |  |
| **user_role** | `VARCHAR(50)` | ✅ | - |  |  |
| **patient_id** | `UUID` | ✅ | - |  | ➡️ [patients]( patients.md ).id |
| **patient_identifier** | `VARCHAR(255)` | ✅ | - |  |  |
| **action** | `VARCHAR(50)` | ❌ | - |  |  |
| **data_category** | `VARCHAR(50)` | ❌ | - |  |  |
| **resource_type** | `VARCHAR(100)` | ❌ | - |  |  |
| **resource_id** | `VARCHAR(255)` | ✅ | - |  |  |
| **fields_accessed** | `JSONB` | ❌ | `'[]'::jsonb` |  |  |
| **fields_modified** | `JSONB` | ✅ | - |  |  |
| **purpose** | `VARCHAR(255)` | ✅ | - |  |  |
| **legal_basis** | `VARCHAR(100)` | ✅ | - |  |  |
| **ip_address** | `INET` | ✅ | - |  |  |
| **user_agent** | `VARCHAR(500)` | ✅ | - |  |  |
| **session_id** | `VARCHAR(255)` | ✅ | - |  |  |
| **request_id** | `VARCHAR(255)` | ✅ | - |  |  |
| **additional_data** | `JSONB` | ✅ | - |  |  |
| **success** | `BOOLEAN` | ❌ | - |  |  |
| **error_message** | `TEXT` | ✅ | - |  |  |
| **retention_until** | `TIMESTAMP` | ✅ | - |  |  |
| **can_be_deleted** | `BOOLEAN` | ❌ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_lgpd_audit_action_time | ❌ | `action, created_at` |
| ix_lgpd_audit_failures | ❌ | `created_at` |
| ix_lgpd_audit_logs_action | ❌ | `action` |
| ix_lgpd_audit_logs_data_category | ❌ | `data_category` |
| ix_lgpd_audit_logs_id | ❌ | `id` |
| ix_lgpd_audit_logs_patient_id | ❌ | `patient_id` |
| ix_lgpd_audit_logs_session_id | ❌ | `session_id` |
| ix_lgpd_audit_logs_user_id | ❌ | `user_id` |
| ix_lgpd_audit_patient_time | ❌ | `patient_id, created_at` |
| ix_lgpd_audit_session | ❌ | `session_id, created_at` |
| ix_lgpd_audit_user_time | ❌ | `user_id, created_at` |
