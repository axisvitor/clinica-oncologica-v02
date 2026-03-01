# Table: `users`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **email** | `VARCHAR(255)` | ❌ | - |  |  |
| **hashed_password** | `VARCHAR(255)` | ✅ | - |  |  |
| **full_name** | `VARCHAR(255)` | ✅ | - |  |  |
| **role** | `ENUM(user_role)` | ❌ | - |  |  |
| **is_active** | `BOOLEAN` | ❌ | - |  |  |
| **firebase_uid** | `VARCHAR(255)` | ✅ | - |  |  |
| **auth_provider** | `ENUM(auth_provider)` | ❌ | - |  |  |
| **firebase_last_sign_in** | `TIMESTAMP` | ✅ | - |  |  |
| **firebase_created_at** | `TIMESTAMP` | ✅ | - |  |  |
| **firebase_email_verified** | `BOOLEAN` | ❌ | - |  |  |
| **firebase_display_name** | `VARCHAR(255)` | ✅ | - |  |  |
| **firebase_photo_url** | `VARCHAR(500)` | ✅ | - |  |  |
| **firebase_custom_claims** | `JSONB` | ❌ | - |  |  |
| **last_firebase_sync** | `TIMESTAMP` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **permissions** | `JSONB` | ❌ | `'[]'::jsonb` |  |  |
| **failed_login_attempts** | `INTEGER` | ❌ | - |  |  |
| **is_locked** | `BOOLEAN` | ❌ | - |  |  |
| **locked_until** | `TIMESTAMP` | ✅ | - |  |  |
| **force_change_password** | `BOOLEAN` | ❌ | - |  |  |
| **last_password_change** | `TIMESTAMP` | ✅ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_users_email | ✅ | `email` |
| ix_users_firebase_uid | ✅ | `firebase_uid` |
| ix_users_id | ❌ | `id` |
