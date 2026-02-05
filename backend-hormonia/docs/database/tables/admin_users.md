# Table: `admin_users`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **email** | `VARCHAR(255)` | ❌ | - |  |  |
| **password_hash** | `VARCHAR(255)` | ❌ | - |  |  |
| **first_name** | `VARCHAR(100)` | ❌ | - |  |  |
| **last_name** | `VARCHAR(100)` | ❌ | - |  |  |
| **role** | `VARCHAR(11)` | ❌ | `'supervisor'::admin_role_type` |  |  |
| **department** | `VARCHAR(100)` | ✅ | - |  |  |
| **phone_number** | `VARCHAR(20)` | ✅ | - |  |  |
| **is_active** | `BOOLEAN` | ✅ | `true` |  |  |
| **email_verified** | `BOOLEAN` | ✅ | `false` |  |  |
| **two_factor_enabled** | `BOOLEAN` | ✅ | `false` |  |  |
| **two_factor_secret** | `VARCHAR(255)` | ✅ | - |  |  |
| **must_change_password** | `BOOLEAN` | ✅ | `true` |  |  |
| **failed_login_attempts** | `INTEGER` | ✅ | `0` |  |  |
| **locked_until** | `TIMESTAMP` | ✅ | - |  |  |
| **last_login_at** | `TIMESTAMP` | ✅ | - |  |  |
| **last_login_ip** | `INET` | ✅ | - |  |  |
| **last_password_change** | `TIMESTAMP` | ✅ | `CURRENT_TIMESTAMP` |  |  |
| **max_concurrent_sessions** | `INTEGER` | ✅ | `3` |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `CURRENT_TIMESTAMP` |  |  |
| **updated_at** | `TIMESTAMP` | ✅ | `CURRENT_TIMESTAMP` |  |  |
| **created_by** | `UUID` | ✅ | - |  | ➡️ [admin_users]( admin_users.md ).id |
| **updated_by** | `UUID` | ✅ | - |  | ➡️ [admin_users]( admin_users.md ).id |
| **metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| admin_users_email_key | ✅ | `email` |
| idx_admin_users_active | ❌ | `is_active` |
| idx_admin_users_email | ❌ | `email` |
| idx_admin_users_last_login | ❌ | `last_login_at` |
| idx_admin_users_locked | ❌ | `locked_until` |
| idx_admin_users_role | ❌ | `role` |
