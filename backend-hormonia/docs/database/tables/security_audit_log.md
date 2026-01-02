# Table: `security_audit_log`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **event_type** | `VARCHAR(100)` | ❌ | - |  |  |
| **phone_number** | `VARCHAR(20)` | ❌ | - |  |  |
| **patient_id** | `UUID` | ✅ | - |  | ➡️ [patients]( patients.md ).id |
| **message_content** | `TEXT` | ✅ | - |  |  |
| **source_metadata** | `JSONB` | ✅ | - |  |  |
| **risk_score** | `INTEGER` | ❌ | `0` |  |  |
| **ip_address** | `VARCHAR(45)` | ✅ | - |  |  |
| **user_agent** | `VARCHAR(500)` | ✅ | - |  |  |
| **session_id** | `VARCHAR(32)` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `CURRENT_TIMESTAMP` |  |  |
| **additional_data** | `JSONB` | ✅ | - |  |  |
| **alert_sent** | `BOOLEAN` | ❌ | `false` |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_security_audit_additional_data_gin | ❌ | `additional_data` |
| idx_security_audit_created_at | ❌ | `created_at` |
| idx_security_audit_event_type | ❌ | `event_type` |
| idx_security_audit_ip_address | ❌ | `ip_address` |
| idx_security_audit_patient_id | ❌ | `patient_id` |
| idx_security_audit_phone_event_time | ❌ | `phone_number, event_type, created_at` |
| idx_security_audit_phone_number | ❌ | `phone_number` |
| idx_security_audit_risk_score | ❌ | `risk_score` |
| idx_security_audit_risk_time | ❌ | `risk_score, created_at` |
| idx_security_audit_session_id | ❌ | `session_id` |
| idx_security_audit_source_metadata_gin | ❌ | `source_metadata` |
