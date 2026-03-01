# Table: `lgpd_data_access_requests`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **patient_id** | `UUID` | ❌ | - |  | ➡️ [patients]( patients.md ).id |
| **requested_by** | `VARCHAR(255)` | ✅ | - |  |  |
| **verified** | `BOOLEAN` | ❌ | - |  |  |
| **request_type** | `VARCHAR(50)` | ❌ | - |  |  |
| **description** | `TEXT` | ✅ | - |  |  |
| **status** | `VARCHAR(50)` | ❌ | - |  |  |
| **received_at** | `TIMESTAMP` | ❌ | - |  |  |
| **deadline_at** | `TIMESTAMP` | ❌ | - |  |  |
| **responded_at** | `TIMESTAMP` | ✅ | - |  |  |
| **completed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **assigned_to_id** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **response** | `TEXT` | ✅ | - |  |  |
| **rejection_reason** | `TEXT` | ✅ | - |  |  |
| **evidence_url** | `VARCHAR(500)` | ✅ | - |  |  |
| **evidence_hash** | `VARCHAR(64)` | ✅ | - |  |  |
| **request_metadata** | `JSONB` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| ix_dsar_status_deadline | ❌ | `status, deadline_at` |
| ix_lgpd_data_access_requests_id | ❌ | `id` |
| ix_lgpd_data_access_requests_patient_id | ❌ | `patient_id` |
| ix_lgpd_data_access_requests_request_type | ❌ | `request_type` |
| ix_lgpd_data_access_requests_status | ❌ | `status` |
