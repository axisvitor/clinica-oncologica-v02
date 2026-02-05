# Table: `users`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **email** | `VARCHAR(255)` | ❌ | - |  |  |
| **hashed_password** | `VARCHAR(255)` | ✅ | - |  |  |
| **full_name** | `VARCHAR(255)` | ✅ | - |  |  |
| **role** | `VARCHAR(6)` | ❌ | `'doctor'::user_role` |  |  |
| **is_active** | `BOOLEAN` | ❌ | `true` |  |  |
| **firebase_uid** | `VARCHAR(255)` | ✅ | - |  |  |
| **auth_provider** | `VARCHAR(8)` | ❌ | `'local'::auth_provider` |  |  |
| **firebase_last_sign_in** | `TIMESTAMP` | ✅ | - |  |  |
| **firebase_created_at** | `TIMESTAMP` | ✅ | - |  |  |
| **firebase_email_verified** | `BOOLEAN` | ❌ | `false` |  |  |
| **firebase_display_name** | `VARCHAR(255)` | ✅ | - |  |  |
| **firebase_photo_url** | `VARCHAR(500)` | ✅ | - |  |  |
| **firebase_custom_claims** | `JSONB` | ❌ | `'{}'::jsonb` |  |  |
| **last_firebase_sync** | `TIMESTAMP` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **permissions** | `JSONB` | ❌ | `'[]'::jsonb` |  |  |
| **failed_login_attempts** | `INTEGER` | ❌ | `0` |  |  |
| **is_locked** | `BOOLEAN` | ❌ | `false` |  |  |
| **locked_until** | `TIMESTAMP` | ✅ | - |  |  |
| **force_change_password** | `BOOLEAN` | ❌ | `false` |  |  |
| **last_password_change** | `TIMESTAMP` | ✅ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_users_auth_provider | ❌ | `auth_provider` |
| idx_users_email | ❌ | `email` |
| idx_users_firebase_uid | ❌ | `firebase_uid` |
| idx_users_firebase_uid_active_new | ❌ | `firebase_uid` |
| idx_users_is_active | ❌ | `is_active` |
| idx_users_role | ❌ | `role` |
| ix_users_permissions_gin | ❌ | `permissions` |
| users_email_key | ✅ | `email` |
| users_firebase_uid_key | ✅ | `firebase_uid` |
