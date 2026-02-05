# Table: `consents`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **consented_by_id** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **consent_type** | `VARCHAR(13)` | ❌ | - |  |  |
| **status** | `VARCHAR(7)` | ❌ | - |  |  |
| **title** | `VARCHAR(200)` | ❌ | - |  |  |
| **description** | `TEXT` | ❌ | - |  |  |
| **legal_text** | `TEXT` | ✅ | - |  |  |
| **granted_at** | `TIMESTAMP` | ✅ | - |  |  |
| **revoked_at** | `TIMESTAMP` | ✅ | - |  |  |
| **expires_at** | `TIMESTAMP` | ✅ | - |  |  |
| **version** | `VARCHAR(20)` | ✅ | - |  |  |
| **previous_consent_id** | `UUID` | ✅ | - |  |  |
| **signature_data** | `JSONB` | ✅ | - |  |  |
| **witness_id** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **revocation_reason** | `TEXT` | ✅ | - |  |  |
| **is_required** | `BOOLEAN` | ❌ | - |  |  |
| **is_active** | `BOOLEAN` | ❌ | - |  |  |
| **consent_metadata** | `JSONB` | ✅ | - |  |  |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_consents_consent_type | ❌ | `consent_type` |
| ix_consents_consented_by_id | ❌ | `consented_by_id` |
| ix_consents_expires_at | ❌ | `expires_at` |
| ix_consents_granted_at | ❌ | `granted_at` |
| ix_consents_id | ❌ | `id` |
| ix_consents_is_active | ❌ | `is_active` |
| ix_consents_patient_id | ❌ | `patient_id` |
| ix_consents_previous_consent_id | ❌ | `previous_consent_id` |
| ix_consents_status | ❌ | `status` |
