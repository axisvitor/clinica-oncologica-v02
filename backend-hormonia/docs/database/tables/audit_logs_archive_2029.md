# Table: `audit_logs_archive_2029`

## Columns

| Name | Type | Nullable | Default | PK | FK |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **id** | `UUID` | ❌ | `gen_random_uuid()` | 🔑 |  |
| **event_type** | `VARCHAR(50)` | ❌ | - |  |  |
| **event_status** | `VARCHAR(20)` | ❌ | `'success'::character varying` |  |  |
| **user_id** | `UUID` | ✅ | - |  |  |
| **user_email** | `VARCHAR(255)` | ✅ | - |  |  |
| **firebase_uid** | `VARCHAR(255)` | ✅ | - |  |  |
| **ip_address** | `INET` | ✅ | - |  |  |
| **user_agent** | `VARCHAR(500)` | ✅ | - |  |  |
| **resource** | `VARCHAR(255)` | ✅ | - |  |  |
| **action** | `VARCHAR(100)` | ✅ | - |  |  |
| **event_metadata** | `JSONB` | ✅ | `'{}'::jsonb` |  |  |
| **message** | `VARCHAR(500)` | ✅ | - |  |  |
| **error_details** | `VARCHAR(1000)` | ✅ | - |  |  |
| **created_at** | `TIMESTAMP` | ❌ | `now()` | 🔑 |  |
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
