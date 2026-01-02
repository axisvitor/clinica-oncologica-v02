# Table: `audit_logs`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **event_type** | `VARCHAR(50)` | ❌ | - |  |  |
| **event_status** | `VARCHAR(20)` | ❌ | `'success'::character varying` |  |  |
| **user_id** | `UUID` | ✅ | - |  | ➡️ [users]( users.md ).id |
| **user_email** | `VARCHAR(255)` | ✅ | - |  |  |
| **firebase_uid** | `VARCHAR(255)` | ✅ | - |  |  |
| **ip_address** | `INET` | ✅ | - |  |  |
| **user_agent** | `VARCHAR(500)` | ✅ | - |  |  |
| **resource** | `VARCHAR(255)` | ✅ | - |  |  |
| **action** | `VARCHAR(100)` | ✅ | - |  |  |
| **event_metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **message** | `VARCHAR(500)` | ✅ | - |  |  |
| **error_details** | `VARCHAR(1000)` | ✅ | - |  |  |
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
| **status** | `VARCHAR(20)` | ✅ | `'SUCCESS'::character varying` |  |  |
| **http_status_code** | `INTEGER` | ✅ | - |  |  |
| **error_code** | `VARCHAR(50)` | ✅ | - |  |  |
| **error_stack_trace** | `TEXT` | ✅ | - |  |  |
| **duration_ms** | `INTEGER` | ✅ | - |  |  |
| **checksum** | `VARCHAR(64)` | ✅ | - |  |  |
| **previous_checksum** | `VARCHAR(64)` | ✅ | - |  |  |
| **integrity_verified** | `BOOLEAN` | ✅ | `true` |  |  |
| **reviewed** | `BOOLEAN` | ✅ | `false` |  |  |
| **reviewed_at** | `TIMESTAMP` | ✅ | - |  |  |
| **reviewed_by** | `UUID` | ✅ | - |  |  |
| **review_notes** | `TEXT` | ✅ | - |  |  |
| **is_anomalous** | `BOOLEAN` | ✅ | `false` |  |  |
| **anomaly_score** | `NUMERIC(5, 2)` | ✅ | - |  |  |
| **anomaly_reasons** | `ARRAY` | ✅ | - |  |  |
| **alert_generated** | `BOOLEAN` | ✅ | `false` |  |  |
| **alert_sent_at** | `TIMESTAMP` | ✅ | - |  |  |
| **alert_recipients** | `ARRAY` | ✅ | - |  |  |
| **retention_period_years** | `INTEGER` | ✅ | `6` |  |  |
| **archive_eligible_at** | `TIMESTAMP` | ✅ | - |  |  |
| **archived** | `BOOLEAN` | ✅ | `false` |  |  |
| **archived_at** | `TIMESTAMP` | ✅ | - |  |  |
| **archive_location** | `VARCHAR(500)` | ✅ | - |  |  |

## Indexes

| Name | Unique | Columns |
| :--- | :--- | :--- |
| idx_audit_anomalous | ❌ | `is_anomalous, created_at` |
| idx_audit_archive_eligible | ❌ | `archive_eligible_at` |
| idx_audit_changes_after_gin | ❌ | `changes_after` |
| idx_audit_changes_before_gin | ❌ | `changes_before` |
| idx_audit_event_category_timestamp | ❌ | `event_category, created_at` |
| idx_audit_event_type_timestamp | ❌ | `event_type, created_at` |
| idx_audit_integrity | ❌ | `integrity_verified, created_at` |
| idx_audit_ip_timestamp | ❌ | `ip_address, created_at` |
| idx_audit_logs_created_at | ❌ | `created_at` |
| idx_audit_logs_event_status | ❌ | `event_status` |
| idx_audit_logs_event_type | ❌ | `event_type` |
| idx_audit_logs_ip_address | ❌ | `ip_address` |
| idx_audit_logs_resource_action | ❌ | `resource, action` |
| idx_audit_logs_user_email | ❌ | `user_email` |
| idx_audit_logs_user_id | ❌ | `user_id` |
| idx_audit_metadata_gin | ❌ | `event_metadata` |
| idx_audit_phi_access | ❌ | `event_category, resource_type, created_at` |
| idx_audit_resource_type_id | ❌ | `resource_type, resource_id` |
| idx_audit_session_id | ❌ | `session_id, created_at` |
| idx_audit_status_timestamp | ❌ | `status, created_at` |
| idx_audit_timestamp_desc | ❌ | `created_at` |
| idx_audit_unreviewed | ❌ | `reviewed, created_at` |
| idx_audit_user_email_timestamp | ❌ | `user_email, created_at` |
| idx_audit_user_event_time | ❌ | `user_id, event_type, created_at` |
| idx_audit_user_id_timestamp | ❌ | `user_id, created_at` |
| idx_audit_user_resource | ❌ | `user_id, resource_type, resource_id, created_at` |
| ix_audit_logs_cursor_pagination | ❌ | `created_at, id` |
