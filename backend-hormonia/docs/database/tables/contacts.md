# Table: `contacts`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **name** | `VARCHAR(255)` | ❌ | - |  |  |
| **email** | `VARCHAR(255)` | ✅ | - |  |  |
| **phone** | `VARCHAR(20)` | ✅ | - |  |  |
| **contact_type** | `VARCHAR(50)` | ✅ | - |  |  |
| **related_patient_id** | `UUID` | ✅ | - |  | ➡️ [patients]( patients.md ).id |
| **related_user_id** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **notes** | `TEXT` | ✅ | - |  |  |
| **tags** | `ARRAY` | ✅ | - |  |  |
| **contact_metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **created_at** | `TIMESTAMP` | ✅ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ✅ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_contacts_email | ❌ | `email` |
| idx_contacts_phone | ❌ | `phone` |
| idx_contacts_type | ❌ | `contact_type` |
