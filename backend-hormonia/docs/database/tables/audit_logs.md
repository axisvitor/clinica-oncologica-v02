# Table: `audit_logs`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **event_type** | `ENUM(audit_event_type)` | ❌ | - |  |  |
| **event_status** | `VARCHAR(50)` | ❌ | - |  |  |
| **user_id** | `UUID` | ✅ | - |  |  |
| **user_email** | `VARCHAR(255)` | ✅ | - |  |  |
| **firebase_uid** | `VARCHAR(255)` | ✅ | - |  |  |
| **ip_address** | `INET` | ✅ | - |  |  |
| **user_agent** | `TEXT` | ✅ | - |  |  |
| **resource** | `VARCHAR(255)` | ✅ | - |  |  |
| **action** | `VARCHAR(255)` | ✅ | - |  |  |
| **event_metadata** | `JSONB` | ❌ | - |  |  |
| **message** | `TEXT` | ✅ | - |  |  |
| **error_details** | `TEXT` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **updated_at** | `TIMESTAMP` | ❌ | `now()` |  |  |
| **session_id** | `VARCHAR(255)` | ✅ | - |  |  |
| **session_token_hash** | `VARCHAR(64)` | ✅ | - |  |  |
| **device_fingerprint** | `VARCHAR(64)` | ✅ | - |  |  |
| **geolocation** | `JSONB` | ✅ | - |  |  |
| **user_role** | `VARCHAR(50)` | ✅ | - |  |  |
| **event_category** | `VARCHAR(50)` | ✅ | - |  |  |
| **resource_type** | `VARCHAR(50)` | ✅ | - |  |  |
| **resource_id** | `UUID` | ✅ | - |  |  |
| **resource_identifiers** | `JSONB` | ✅ | - |  |  |
| **operation** | `VARCHAR(20)` | ✅ | - |  |  |
| **http_method** | `VARCHAR(10)` | ✅ | - |  |  |
| **endpoint** | `VARCHAR(500)` | ✅ | - |  |  |
| **changes_before** | `JSONB` | ✅ | - |  |  |
| **changes_after** | `JSONB` | ✅ | - |  |  |
| **changed_fields** | `ARRAY` | ✅ | - |  |  |
| **description** | `TEXT` | ✅ | - |  |  |
| **query_params** | `JSONB` | ✅ | - |  |  |
| **request_body_hash** | `VARCHAR(64)` | ✅ | - |  |  |
| **status** | `VARCHAR(20)` | ✅ | - |  |  |
| **http_status_code** | `INTEGER` | ✅ | - |  |  |
| **error_code** | `VARCHAR(50)` | ✅ | - |  |  |
| **error_stack_trace** | `TEXT` | ✅ | - |  |  |
| **duration_ms** | `INTEGER` | ✅ | - |  |  |
| **checksum** | `VARCHAR(64)` | ✅ | - |  |  |
| **previous_checksum** | `VARCHAR(64)` | ✅ | - |  |  |
| **integrity_verified** | `BOOLEAN` | ✅ | - |  |  |
| **reviewed** | `BOOLEAN` | ✅ | - |  |  |
| **reviewed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **reviewed_by** | `UUID` | ✅ | - |  |  |
| **review_notes** | `TEXT` | ✅ | - |  |  |
| **is_anomalous** | `BOOLEAN` | ✅ | - |  |  |
| **anomaly_score** | `NUMERIC(5, 2)` | ✅ | - |  |  |
| **anomaly_reasons** | `ARRAY` | ✅ | - |  |  |
| **alert_generated** | `BOOLEAN` | ✅ | - |  |  |
| **alert_sent_at** | `TIMESTAMP` | ✅ | - |  |  |
| **alert_recipients** | `ARRAY` | ✅ | - |  |  |
| **retention_period_years** | `INTEGER` | ✅ | - |  |  |
| **archive_eligible_at** | `TIMESTAMP` | ✅ | - |  |  |
| **archived** | `BOOLEAN` | ✅ | - |  |  |
| **archived_at** | `TIMESTAMP` | ✅ | - |  |  |
| **archive_location** | `VARCHAR(500)` | ✅ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_audit_email_time | ❌ | `user_email, created_at` |
| idx_audit_event_status_time | ❌ | `event_type, event_status, created_at` |
| idx_audit_firebase_time | ❌ | `firebase_uid, created_at` |
| idx_audit_ip_time | ❌ | `ip_address, created_at` |
| idx_audit_user_event_time | ❌ | `user_id, event_type, created_at` |
| ix_audit_logs_event_category | ❌ | `event_category` |
| ix_audit_logs_event_type | ❌ | `event_type` |
| ix_audit_logs_firebase_uid | ❌ | `firebase_uid` |
| ix_audit_logs_id | ❌ | `id` |
| ix_audit_logs_ip_address | ❌ | `ip_address` |
| ix_audit_logs_user_email | ❌ | `user_email` |
| ix_audit_logs_user_id | ❌ | `user_id` |
