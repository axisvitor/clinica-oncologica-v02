# Tables Reference

## Admin & Security
### `admin_audit_log`
_Log de auditoria de ações administrativas_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `admin_user_id` | `uuid` | True | `None` |  | -> admin_users.id |  |
| `session_id` | `uuid` | True | `None` |  | -> admin_sessions.id |  |
| `event_type` | `character varying` | False | `None` |  |  |  |
| `event_category` | `character varying` | False | `None` |  |  |  |
| `action` | `character varying` | False | `None` |  |  |  |
| `resource_type` | `character varying` | True | `None` |  |  |  |
| `resource_id` | `character varying` | True | `None` |  |  |  |
| `ip_address` | `inet` | True | `None` |  |  |  |
| `user_agent` | `text` | True | `None` |  |  |  |
| `endpoint` | `character varying` | True | `None` |  |  |  |
| `http_method` | `USER-DEFINED` | True | `None` |  |  |  |
| `details` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `changes` | `jsonb` | True | `None` |  |  |  |
| `success` | `boolean` | True | `true` |  |  |  |
| `error_message` | `text` | True | `None` |  |  |  |
| `timestamp` | `timestamp with time zone` | True | `CURRENT_TIMESTAMP` |  |  |  |
| `duration_ms` | `integer` | True | `None` |  |  |  |
| `severity` | `USER-DEFINED` | True | `'low'::severity_type` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `admin_audit_log_pkey` | id | True |
| `idx_admin_audit_event_type` | event_type | False |
| `idx_admin_audit_ip` | ip_address | False |
| `idx_admin_audit_resource` | resource_type, resource_id | False |
| `idx_admin_audit_severity` | severity | False |
| `idx_admin_audit_timestamp` | timestamp | False |
| `idx_admin_audit_user_id` | admin_user_id | False |

---

### `admin_ip_blacklist`
_IPs bloqueados para acesso admin_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `ip_address` | `inet` | False | `None` |  |  |  |
| `reason` | `character varying` | False | `None` |  |  |  |
| `blocked_at` | `timestamp with time zone` | True | `CURRENT_TIMESTAMP` |  |  |  |
| `blocked_by` | `uuid` | True | `None` |  | -> admin_users.id |  |
| `expires_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `is_permanent` | `boolean` | True | `false` |  |  |  |
| `incident_id` | `uuid` | True | `None` |  |  |  |
| `threat_level` | `USER-DEFINED` | True | `'medium'::severity_type` |  |  |  |
| `block_count` | `integer` | True | `1` |  |  |  |
| `details` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `notes` | `text` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `admin_ip_blacklist_ip_address_key` | ip_address | True |
| `admin_ip_blacklist_pkey` | id | True |
| `idx_ip_blacklist_active` | ip_address, expires_at | False |

---

### `admin_ip_whitelist`
_IPs permitidos para acesso admin_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `ip_address` | `inet` | True | `None` |  |  |  |
| `ip_range` | `cidr` | True | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `added_by` | `uuid` | True | `None` |  | -> admin_users.id |  |
| `added_at` | `timestamp with time zone` | True | `CURRENT_TIMESTAMP` |  |  |  |
| `is_active` | `boolean` | True | `true` |  |  |  |
| `expires_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `last_used_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `usage_count` | `integer` | True | `0` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `admin_ip_whitelist_pkey` | id | True |
| `idx_ip_whitelist_active` | is_active, ip_address | False |
| `idx_ip_whitelist_range` | ip_range | False |
| `unique_ip_or_range` | ip_address, ip_range | True |

---

### `admin_permissions`
_Permissões disponíveis no sistema_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `name` | `character varying` | False | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `category` | `character varying` | False | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | True | `CURRENT_TIMESTAMP` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `admin_permissions_name_key` | name | True |
| `admin_permissions_pkey` | id | True |
| `idx_admin_permissions_category` | category | False |

---

### `admin_role_permissions`
_Permissões associadas a roles_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `role_id` | `uuid` | False | `None` |  | -> admin_roles.id |  |
| `permission_id` | `uuid` | False | `None` | ✅ | -> admin_permissions.id |  |
| `created_at` | `timestamp with time zone` | True | `CURRENT_TIMESTAMP` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `admin_role_permissions_pkey` | role_id, permission_id | True |
| `idx_admin_role_permissions_role` | role_id | False |

---

### `admin_roles`
_Roles do sistema admin_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `name` | `character varying` | False | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `is_system_role` | `boolean` | True | `false` |  |  |  |
| `created_at` | `timestamp with time zone` | True | `CURRENT_TIMESTAMP` |  |  |  |
| `updated_at` | `timestamp with time zone` | True | `CURRENT_TIMESTAMP` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `admin_roles_name_key` | name | True |
| `admin_roles_pkey` | id | True |

---

### `admin_security_events`
_Eventos de segurança detectados no sistema admin_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `event_type` | `character varying` | False | `None` |  |  |  |
| `severity` | `USER-DEFINED` | False | `'medium'::severity_type` |  |  |  |
| `ip_address` | `inet` | True | `None` |  |  |  |
| `user_agent` | `text` | True | `None` |  |  |  |
| `admin_user_id` | `uuid` | True | `None` |  | -> admin_users.id |  |
| `session_id` | `uuid` | True | `None` |  | -> admin_sessions.id |  |
| `description` | `text` | True | `None` |  |  |  |
| `details` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `endpoint` | `character varying` | True | `None` |  |  |  |
| `detected_at` | `timestamp with time zone` | True | `CURRENT_TIMESTAMP` |  |  |  |
| `resolved_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `resolution_notes` | `text` | True | `None` |  |  |  |
| `auto_resolved` | `boolean` | True | `false` |  |  |  |
| `risk_score` | `integer` | True | `0` |  |  |  |
| `threat_level` | `USER-DEFINED` | True | `'low'::severity_type` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `admin_security_events_pkey` | id | True |
| `idx_security_events_ip` | ip_address | False |
| `idx_security_events_resolved` | resolved_at | False |
| `idx_security_events_severity` | severity | False |
| `idx_security_events_timestamp` | detected_at | False |
| `idx_security_events_user_id` | admin_user_id | False |

---

### `admin_sessions`
_Sessões ativas de administradores_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `admin_user_id` | `uuid` | False | `None` |  | -> admin_users.id |  |
| `session_token` | `character varying` | False | `None` |  |  |  |
| `refresh_token` | `character varying` | True | `None` |  |  |  |
| `ip_address` | `inet` | True | `None` |  |  |  |
| `user_agent` | `text` | True | `None` |  |  |  |
| `device_fingerprint` | `character varying` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | True | `CURRENT_TIMESTAMP` |  |  |  |
| `last_activity` | `timestamp with time zone` | True | `CURRENT_TIMESTAMP` |  |  |  |
| `expires_at` | `timestamp with time zone` | False | `None` |  |  |  |
| `is_active` | `boolean` | True | `true` |  |  |  |
| `logout_reason` | `character varying` | True | `None` |  |  |  |
| `metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `admin_sessions_pkey` | id | True |
| `admin_sessions_refresh_token_key` | refresh_token | True |
| `admin_sessions_session_token_key` | session_token | True |
| `idx_admin_sessions_active` | is_active, last_activity | False |
| `idx_admin_sessions_expires` | expires_at | False |
| `idx_admin_sessions_ip` | ip_address | False |
| `idx_admin_sessions_token` | session_token | False |
| `idx_admin_sessions_user_id` | admin_user_id | False |

---

### `admin_user_permissions`
_Permissões diretas de usuários admin_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `admin_user_id` | `uuid` | False | `None` |  | -> admin_users.id |  |
| `permission_id` | `uuid` | False | `None` | ✅ | -> admin_permissions.id |  |
| `granted_at` | `timestamp with time zone` | True | `CURRENT_TIMESTAMP` |  |  |  |
| `granted_by` | `uuid` | True | `None` |  | -> admin_users.id |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `admin_user_permissions_pkey` | admin_user_id, permission_id | True |
| `idx_admin_user_permissions_user` | admin_user_id | False |

---

### `admin_users`
_Usuários administradores do sistema_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `email` | `character varying` | False | `None` |  |  |  |
| `password_hash` | `character varying` | False | `None` |  |  |  |
| `first_name` | `character varying` | False | `None` |  |  |  |
| `last_name` | `character varying` | False | `None` |  |  |  |
| `role` | `USER-DEFINED` | False | `'supervisor'::admin_role_type` |  |  |  |
| `department` | `character varying` | True | `None` |  |  |  |
| `phone_number` | `character varying` | True | `None` |  |  |  |
| `is_active` | `boolean` | True | `true` |  |  |  |
| `email_verified` | `boolean` | True | `false` |  |  |  |
| `two_factor_enabled` | `boolean` | True | `false` |  |  |  |
| `two_factor_secret` | `character varying` | True | `None` |  |  |  |
| `must_change_password` | `boolean` | True | `true` |  |  |  |
| `failed_login_attempts` | `integer` | True | `0` |  |  |  |
| `locked_until` | `timestamp with time zone` | True | `None` |  |  |  |
| `last_login_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `last_login_ip` | `inet` | True | `None` |  |  |  |
| `last_password_change` | `timestamp with time zone` | True | `CURRENT_TIMESTAMP` |  |  |  |
| `max_concurrent_sessions` | `integer` | True | `3` |  |  |  |
| `created_at` | `timestamp with time zone` | True | `CURRENT_TIMESTAMP` |  |  |  |
| `updated_at` | `timestamp with time zone` | True | `CURRENT_TIMESTAMP` |  |  |  |
| `created_by` | `uuid` | True | `None` |  | -> admin_users.id |  |
| `updated_by` | `uuid` | True | `None` |  | -> admin_users.id |  |
| `metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `admin_users_email_key` | email | True |
| `admin_users_pkey` | id | True |
| `idx_admin_users_active` | is_active | False |
| `idx_admin_users_email` | email | False |
| `idx_admin_users_last_login` | last_login_at | False |
| `idx_admin_users_locked` | locked_until | False |
| `idx_admin_users_role` | role | False |

---

## Audit & Logging
### `audit_log_entries`
_Entradas genéricas de log de auditoria_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `event_type` | `character varying` | False | `None` |  |  |  |
| `entity_type` | `character varying` | True | `None` |  |  |  |
| `entity_id` | `uuid` | True | `None` |  |  |  |
| `user_id` | `uuid` | True | `None` |  |  |  |
| `old_values` | `jsonb` | True | `None` |  |  |  |
| `new_values` | `jsonb` | True | `None` |  |  |  |
| `metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `ip_address` | `inet` | True | `None` |  |  |  |
| `user_agent` | `text` | True | `None` |  |  |  |
| `timestamp` | `timestamp with time zone` | True | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `audit_log_entries_pkey` | id | True |
| `idx_audit_log_entries_entity` | entity_type, entity_id | False |
| `idx_audit_log_entries_timestamp` | timestamp | False |
| `idx_audit_log_entries_user` | user_id, timestamp | False |

---

### `audit_logs`
_Security audit logs for authentication and authorization events_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `event_type` | `character varying` | False | `None` |  |  |  |
| `event_status` | `character varying` | False | `'success'::character varying` |  |  |  |
| `user_id` | `uuid` | True | `None` |  | -> users.id |  |
| `user_email` | `character varying` | True | `None` |  |  |  |
| `firebase_uid` | `character varying` | True | `None` |  |  |  |
| `ip_address` | `inet` | True | `None` |  |  |  |
| `user_agent` | `character varying` | True | `None` |  |  |  |
| `resource` | `character varying` | True | `None` |  |  |  |
| `action` | `character varying` | True | `None` |  |  |  |
| `event_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `message` | `character varying` | True | `None` |  |  |  |
| `error_details` | `character varying` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `session_id` | `character varying` | True | `None` |  |  |  |
| `session_token_hash` | `character varying` | True | `None` |  |  |  |
| `device_fingerprint` | `character varying` | True | `None` |  |  |  |
| `geolocation` | `jsonb` | True | `None` |  |  |  |
| `user_role` | `character varying` | True | `None` |  |  |  |
| `event_category` | `character varying` | True | `None` |  |  |  |
| `resource_type` | `character varying` | True | `None` |  |  |  |
| `resource_id` | `uuid` | True | `None` |  |  |  |
| `resource_identifiers` | `jsonb` | True | `None` |  |  |  |
| `operation` | `character varying` | True | `None` |  |  |  |
| `http_method` | `character varying` | True | `None` |  |  |  |
| `endpoint` | `character varying` | True | `None` |  |  |  |
| `changes_before` | `jsonb` | True | `None` |  |  |  |
| `changes_after` | `jsonb` | True | `None` |  |  |  |
| `changed_fields` | `ARRAY` | True | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `query_params` | `jsonb` | True | `None` |  |  |  |
| `request_body_hash` | `character varying` | True | `None` |  |  |  |
| `status` | `character varying` | True | `'SUCCESS'::character varying` |  |  |  |
| `http_status_code` | `integer` | True | `None` |  |  |  |
| `error_code` | `character varying` | True | `None` |  |  |  |
| `error_stack_trace` | `text` | True | `None` |  |  |  |
| `duration_ms` | `integer` | True | `None` |  |  |  |
| `checksum` | `character varying` | True | `None` |  |  |  |
| `previous_checksum` | `character varying` | True | `None` |  |  |  |
| `integrity_verified` | `boolean` | True | `true` |  |  |  |
| `reviewed` | `boolean` | True | `false` |  |  |  |
| `reviewed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `reviewed_by` | `uuid` | True | `None` |  |  |  |
| `review_notes` | `text` | True | `None` |  |  |  |
| `is_anomalous` | `boolean` | True | `false` |  |  |  |
| `anomaly_score` | `numeric` | True | `None` |  |  |  |
| `anomaly_reasons` | `ARRAY` | True | `None` |  |  |  |
| `alert_generated` | `boolean` | True | `false` |  |  |  |
| `alert_sent_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `alert_recipients` | `ARRAY` | True | `None` |  |  |  |
| `retention_period_years` | `integer` | True | `6` |  |  |  |
| `archive_eligible_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archived` | `boolean` | True | `false` |  |  |  |
| `archived_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archive_location` | `character varying` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `audit_logs_pkey` | id | True |
| `idx_audit_anomalous` | is_anomalous, created_at | False |
| `idx_audit_archive_eligible` | archive_eligible_at | False |
| `idx_audit_changes_after_gin` | changes_after | False |
| `idx_audit_changes_before_gin` | changes_before | False |
| `idx_audit_event_category_timestamp` | event_category, created_at | False |
| `idx_audit_event_type_timestamp` | event_type, created_at | False |
| `idx_audit_integrity` | integrity_verified, created_at | False |
| `idx_audit_ip_timestamp` | ip_address, created_at | False |
| `idx_audit_logs_created_at` | created_at | False |
| `idx_audit_logs_event_status` | event_status | False |
| `idx_audit_logs_event_type` | event_type | False |
| `idx_audit_logs_ip_address` | ip_address | False |
| `idx_audit_logs_resource_action` | resource, action | False |
| `idx_audit_logs_user_email` | user_email | False |
| `idx_audit_logs_user_id` | user_id | False |
| `idx_audit_metadata_gin` | event_metadata | False |
| `idx_audit_phi_access` | event_category, resource_type, created_at | False |
| `idx_audit_resource_type_id` | resource_type, resource_id | False |
| `idx_audit_session_id` | session_id, created_at | False |
| `idx_audit_status_timestamp` | status, created_at | False |
| `idx_audit_timestamp_desc` | created_at | False |
| `idx_audit_unreviewed` | reviewed, created_at | False |
| `idx_audit_user_email_timestamp` | user_email, created_at | False |
| `idx_audit_user_event_time` | user_id, event_type, created_at | False |
| `idx_audit_user_id_timestamp` | user_id, created_at | False |
| `idx_audit_user_resource` | user_id, resource_type, resource_id, created_at | False |

---

### `audit_logs_archive`

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `event_type` | `character varying` | False | `None` |  |  |  |
| `event_status` | `character varying` | False | `'success'::character varying` |  |  |  |
| `user_id` | `uuid` | True | `None` |  |  |  |
| `user_email` | `character varying` | True | `None` |  |  |  |
| `firebase_uid` | `character varying` | True | `None` |  |  |  |
| `ip_address` | `inet` | True | `None` |  |  |  |
| `user_agent` | `character varying` | True | `None` |  |  |  |
| `resource` | `character varying` | True | `None` |  |  |  |
| `action` | `character varying` | True | `None` |  |  |  |
| `event_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `message` | `character varying` | True | `None` |  |  |  |
| `error_details` | `character varying` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` | ✅ |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `session_id` | `character varying` | True | `None` |  |  |  |
| `session_token_hash` | `character varying` | True | `None` |  |  |  |
| `device_fingerprint` | `character varying` | True | `None` |  |  |  |
| `geolocation` | `jsonb` | True | `None` |  |  |  |
| `user_role` | `character varying` | True | `None` |  |  |  |
| `event_category` | `character varying` | True | `None` |  |  |  |
| `resource_type` | `character varying` | True | `None` |  |  |  |
| `resource_id` | `uuid` | True | `None` |  |  |  |
| `resource_identifiers` | `jsonb` | True | `None` |  |  |  |
| `operation` | `character varying` | True | `None` |  |  |  |
| `http_method` | `character varying` | True | `None` |  |  |  |
| `endpoint` | `character varying` | True | `None` |  |  |  |
| `changes_before` | `jsonb` | True | `None` |  |  |  |
| `changes_after` | `jsonb` | True | `None` |  |  |  |
| `changed_fields` | `ARRAY` | True | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `query_params` | `jsonb` | True | `None` |  |  |  |
| `request_body_hash` | `character varying` | True | `None` |  |  |  |
| `status` | `character varying` | True | `'SUCCESS'::character varying` |  |  |  |
| `http_status_code` | `integer` | True | `None` |  |  |  |
| `error_code` | `character varying` | True | `None` |  |  |  |
| `error_stack_trace` | `text` | True | `None` |  |  |  |
| `duration_ms` | `integer` | True | `None` |  |  |  |
| `checksum` | `character varying` | True | `None` |  |  |  |
| `previous_checksum` | `character varying` | True | `None` |  |  |  |
| `integrity_verified` | `boolean` | True | `true` |  |  |  |
| `reviewed` | `boolean` | True | `false` |  |  |  |
| `reviewed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `reviewed_by` | `uuid` | True | `None` |  |  |  |
| `review_notes` | `text` | True | `None` |  |  |  |
| `is_anomalous` | `boolean` | True | `false` |  |  |  |
| `anomaly_score` | `numeric` | True | `None` |  |  |  |
| `anomaly_reasons` | `ARRAY` | True | `None` |  |  |  |
| `alert_generated` | `boolean` | True | `false` |  |  |  |
| `alert_sent_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `alert_recipients` | `ARRAY` | True | `None` |  |  |  |
| `retention_period_years` | `integer` | True | `6` |  |  |  |
| `archive_eligible_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archived` | `boolean` | True | `false` |  |  |  |
| `archived_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archive_location` | `character varying` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `audit_logs_archive_pkey` | id, created_at | True |

---

### `audit_logs_archive_2025`

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `event_type` | `character varying` | False | `None` |  |  |  |
| `event_status` | `character varying` | False | `'success'::character varying` |  |  |  |
| `user_id` | `uuid` | True | `None` |  |  |  |
| `user_email` | `character varying` | True | `None` |  |  |  |
| `firebase_uid` | `character varying` | True | `None` |  |  |  |
| `ip_address` | `inet` | True | `None` |  |  |  |
| `user_agent` | `character varying` | True | `None` |  |  |  |
| `resource` | `character varying` | True | `None` |  |  |  |
| `action` | `character varying` | True | `None` |  |  |  |
| `event_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `message` | `character varying` | True | `None` |  |  |  |
| `error_details` | `character varying` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` | ✅ |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `session_id` | `character varying` | True | `None` |  |  |  |
| `session_token_hash` | `character varying` | True | `None` |  |  |  |
| `device_fingerprint` | `character varying` | True | `None` |  |  |  |
| `geolocation` | `jsonb` | True | `None` |  |  |  |
| `user_role` | `character varying` | True | `None` |  |  |  |
| `event_category` | `character varying` | True | `None` |  |  |  |
| `resource_type` | `character varying` | True | `None` |  |  |  |
| `resource_id` | `uuid` | True | `None` |  |  |  |
| `resource_identifiers` | `jsonb` | True | `None` |  |  |  |
| `operation` | `character varying` | True | `None` |  |  |  |
| `http_method` | `character varying` | True | `None` |  |  |  |
| `endpoint` | `character varying` | True | `None` |  |  |  |
| `changes_before` | `jsonb` | True | `None` |  |  |  |
| `changes_after` | `jsonb` | True | `None` |  |  |  |
| `changed_fields` | `ARRAY` | True | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `query_params` | `jsonb` | True | `None` |  |  |  |
| `request_body_hash` | `character varying` | True | `None` |  |  |  |
| `status` | `character varying` | True | `'SUCCESS'::character varying` |  |  |  |
| `http_status_code` | `integer` | True | `None` |  |  |  |
| `error_code` | `character varying` | True | `None` |  |  |  |
| `error_stack_trace` | `text` | True | `None` |  |  |  |
| `duration_ms` | `integer` | True | `None` |  |  |  |
| `checksum` | `character varying` | True | `None` |  |  |  |
| `previous_checksum` | `character varying` | True | `None` |  |  |  |
| `integrity_verified` | `boolean` | True | `true` |  |  |  |
| `reviewed` | `boolean` | True | `false` |  |  |  |
| `reviewed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `reviewed_by` | `uuid` | True | `None` |  |  |  |
| `review_notes` | `text` | True | `None` |  |  |  |
| `is_anomalous` | `boolean` | True | `false` |  |  |  |
| `anomaly_score` | `numeric` | True | `None` |  |  |  |
| `anomaly_reasons` | `ARRAY` | True | `None` |  |  |  |
| `alert_generated` | `boolean` | True | `false` |  |  |  |
| `alert_sent_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `alert_recipients` | `ARRAY` | True | `None` |  |  |  |
| `retention_period_years` | `integer` | True | `6` |  |  |  |
| `archive_eligible_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archived` | `boolean` | True | `false` |  |  |  |
| `archived_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archive_location` | `character varying` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `audit_logs_archive_2025_pkey` | id, created_at | True |

---

### `audit_logs_archive_2026`

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `event_type` | `character varying` | False | `None` |  |  |  |
| `event_status` | `character varying` | False | `'success'::character varying` |  |  |  |
| `user_id` | `uuid` | True | `None` |  |  |  |
| `user_email` | `character varying` | True | `None` |  |  |  |
| `firebase_uid` | `character varying` | True | `None` |  |  |  |
| `ip_address` | `inet` | True | `None` |  |  |  |
| `user_agent` | `character varying` | True | `None` |  |  |  |
| `resource` | `character varying` | True | `None` |  |  |  |
| `action` | `character varying` | True | `None` |  |  |  |
| `event_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `message` | `character varying` | True | `None` |  |  |  |
| `error_details` | `character varying` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` | ✅ |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `session_id` | `character varying` | True | `None` |  |  |  |
| `session_token_hash` | `character varying` | True | `None` |  |  |  |
| `device_fingerprint` | `character varying` | True | `None` |  |  |  |
| `geolocation` | `jsonb` | True | `None` |  |  |  |
| `user_role` | `character varying` | True | `None` |  |  |  |
| `event_category` | `character varying` | True | `None` |  |  |  |
| `resource_type` | `character varying` | True | `None` |  |  |  |
| `resource_id` | `uuid` | True | `None` |  |  |  |
| `resource_identifiers` | `jsonb` | True | `None` |  |  |  |
| `operation` | `character varying` | True | `None` |  |  |  |
| `http_method` | `character varying` | True | `None` |  |  |  |
| `endpoint` | `character varying` | True | `None` |  |  |  |
| `changes_before` | `jsonb` | True | `None` |  |  |  |
| `changes_after` | `jsonb` | True | `None` |  |  |  |
| `changed_fields` | `ARRAY` | True | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `query_params` | `jsonb` | True | `None` |  |  |  |
| `request_body_hash` | `character varying` | True | `None` |  |  |  |
| `status` | `character varying` | True | `'SUCCESS'::character varying` |  |  |  |
| `http_status_code` | `integer` | True | `None` |  |  |  |
| `error_code` | `character varying` | True | `None` |  |  |  |
| `error_stack_trace` | `text` | True | `None` |  |  |  |
| `duration_ms` | `integer` | True | `None` |  |  |  |
| `checksum` | `character varying` | True | `None` |  |  |  |
| `previous_checksum` | `character varying` | True | `None` |  |  |  |
| `integrity_verified` | `boolean` | True | `true` |  |  |  |
| `reviewed` | `boolean` | True | `false` |  |  |  |
| `reviewed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `reviewed_by` | `uuid` | True | `None` |  |  |  |
| `review_notes` | `text` | True | `None` |  |  |  |
| `is_anomalous` | `boolean` | True | `false` |  |  |  |
| `anomaly_score` | `numeric` | True | `None` |  |  |  |
| `anomaly_reasons` | `ARRAY` | True | `None` |  |  |  |
| `alert_generated` | `boolean` | True | `false` |  |  |  |
| `alert_sent_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `alert_recipients` | `ARRAY` | True | `None` |  |  |  |
| `retention_period_years` | `integer` | True | `6` |  |  |  |
| `archive_eligible_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archived` | `boolean` | True | `false` |  |  |  |
| `archived_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archive_location` | `character varying` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `audit_logs_archive_2026_pkey` | id, created_at | True |

---

### `audit_logs_archive_2027`

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `event_type` | `character varying` | False | `None` |  |  |  |
| `event_status` | `character varying` | False | `'success'::character varying` |  |  |  |
| `user_id` | `uuid` | True | `None` |  |  |  |
| `user_email` | `character varying` | True | `None` |  |  |  |
| `firebase_uid` | `character varying` | True | `None` |  |  |  |
| `ip_address` | `inet` | True | `None` |  |  |  |
| `user_agent` | `character varying` | True | `None` |  |  |  |
| `resource` | `character varying` | True | `None` |  |  |  |
| `action` | `character varying` | True | `None` |  |  |  |
| `event_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `message` | `character varying` | True | `None` |  |  |  |
| `error_details` | `character varying` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` | ✅ |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `session_id` | `character varying` | True | `None` |  |  |  |
| `session_token_hash` | `character varying` | True | `None` |  |  |  |
| `device_fingerprint` | `character varying` | True | `None` |  |  |  |
| `geolocation` | `jsonb` | True | `None` |  |  |  |
| `user_role` | `character varying` | True | `None` |  |  |  |
| `event_category` | `character varying` | True | `None` |  |  |  |
| `resource_type` | `character varying` | True | `None` |  |  |  |
| `resource_id` | `uuid` | True | `None` |  |  |  |
| `resource_identifiers` | `jsonb` | True | `None` |  |  |  |
| `operation` | `character varying` | True | `None` |  |  |  |
| `http_method` | `character varying` | True | `None` |  |  |  |
| `endpoint` | `character varying` | True | `None` |  |  |  |
| `changes_before` | `jsonb` | True | `None` |  |  |  |
| `changes_after` | `jsonb` | True | `None` |  |  |  |
| `changed_fields` | `ARRAY` | True | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `query_params` | `jsonb` | True | `None` |  |  |  |
| `request_body_hash` | `character varying` | True | `None` |  |  |  |
| `status` | `character varying` | True | `'SUCCESS'::character varying` |  |  |  |
| `http_status_code` | `integer` | True | `None` |  |  |  |
| `error_code` | `character varying` | True | `None` |  |  |  |
| `error_stack_trace` | `text` | True | `None` |  |  |  |
| `duration_ms` | `integer` | True | `None` |  |  |  |
| `checksum` | `character varying` | True | `None` |  |  |  |
| `previous_checksum` | `character varying` | True | `None` |  |  |  |
| `integrity_verified` | `boolean` | True | `true` |  |  |  |
| `reviewed` | `boolean` | True | `false` |  |  |  |
| `reviewed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `reviewed_by` | `uuid` | True | `None` |  |  |  |
| `review_notes` | `text` | True | `None` |  |  |  |
| `is_anomalous` | `boolean` | True | `false` |  |  |  |
| `anomaly_score` | `numeric` | True | `None` |  |  |  |
| `anomaly_reasons` | `ARRAY` | True | `None` |  |  |  |
| `alert_generated` | `boolean` | True | `false` |  |  |  |
| `alert_sent_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `alert_recipients` | `ARRAY` | True | `None` |  |  |  |
| `retention_period_years` | `integer` | True | `6` |  |  |  |
| `archive_eligible_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archived` | `boolean` | True | `false` |  |  |  |
| `archived_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archive_location` | `character varying` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `audit_logs_archive_2027_pkey` | id, created_at | True |

---

### `audit_logs_archive_2028`

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `event_type` | `character varying` | False | `None` |  |  |  |
| `event_status` | `character varying` | False | `'success'::character varying` |  |  |  |
| `user_id` | `uuid` | True | `None` |  |  |  |
| `user_email` | `character varying` | True | `None` |  |  |  |
| `firebase_uid` | `character varying` | True | `None` |  |  |  |
| `ip_address` | `inet` | True | `None` |  |  |  |
| `user_agent` | `character varying` | True | `None` |  |  |  |
| `resource` | `character varying` | True | `None` |  |  |  |
| `action` | `character varying` | True | `None` |  |  |  |
| `event_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `message` | `character varying` | True | `None` |  |  |  |
| `error_details` | `character varying` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` | ✅ |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `session_id` | `character varying` | True | `None` |  |  |  |
| `session_token_hash` | `character varying` | True | `None` |  |  |  |
| `device_fingerprint` | `character varying` | True | `None` |  |  |  |
| `geolocation` | `jsonb` | True | `None` |  |  |  |
| `user_role` | `character varying` | True | `None` |  |  |  |
| `event_category` | `character varying` | True | `None` |  |  |  |
| `resource_type` | `character varying` | True | `None` |  |  |  |
| `resource_id` | `uuid` | True | `None` |  |  |  |
| `resource_identifiers` | `jsonb` | True | `None` |  |  |  |
| `operation` | `character varying` | True | `None` |  |  |  |
| `http_method` | `character varying` | True | `None` |  |  |  |
| `endpoint` | `character varying` | True | `None` |  |  |  |
| `changes_before` | `jsonb` | True | `None` |  |  |  |
| `changes_after` | `jsonb` | True | `None` |  |  |  |
| `changed_fields` | `ARRAY` | True | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `query_params` | `jsonb` | True | `None` |  |  |  |
| `request_body_hash` | `character varying` | True | `None` |  |  |  |
| `status` | `character varying` | True | `'SUCCESS'::character varying` |  |  |  |
| `http_status_code` | `integer` | True | `None` |  |  |  |
| `error_code` | `character varying` | True | `None` |  |  |  |
| `error_stack_trace` | `text` | True | `None` |  |  |  |
| `duration_ms` | `integer` | True | `None` |  |  |  |
| `checksum` | `character varying` | True | `None` |  |  |  |
| `previous_checksum` | `character varying` | True | `None` |  |  |  |
| `integrity_verified` | `boolean` | True | `true` |  |  |  |
| `reviewed` | `boolean` | True | `false` |  |  |  |
| `reviewed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `reviewed_by` | `uuid` | True | `None` |  |  |  |
| `review_notes` | `text` | True | `None` |  |  |  |
| `is_anomalous` | `boolean` | True | `false` |  |  |  |
| `anomaly_score` | `numeric` | True | `None` |  |  |  |
| `anomaly_reasons` | `ARRAY` | True | `None` |  |  |  |
| `alert_generated` | `boolean` | True | `false` |  |  |  |
| `alert_sent_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `alert_recipients` | `ARRAY` | True | `None` |  |  |  |
| `retention_period_years` | `integer` | True | `6` |  |  |  |
| `archive_eligible_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archived` | `boolean` | True | `false` |  |  |  |
| `archived_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archive_location` | `character varying` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `audit_logs_archive_2028_pkey` | id, created_at | True |

---

### `audit_logs_archive_2029`

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `event_type` | `character varying` | False | `None` |  |  |  |
| `event_status` | `character varying` | False | `'success'::character varying` |  |  |  |
| `user_id` | `uuid` | True | `None` |  |  |  |
| `user_email` | `character varying` | True | `None` |  |  |  |
| `firebase_uid` | `character varying` | True | `None` |  |  |  |
| `ip_address` | `inet` | True | `None` |  |  |  |
| `user_agent` | `character varying` | True | `None` |  |  |  |
| `resource` | `character varying` | True | `None` |  |  |  |
| `action` | `character varying` | True | `None` |  |  |  |
| `event_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `message` | `character varying` | True | `None` |  |  |  |
| `error_details` | `character varying` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` | ✅ |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `session_id` | `character varying` | True | `None` |  |  |  |
| `session_token_hash` | `character varying` | True | `None` |  |  |  |
| `device_fingerprint` | `character varying` | True | `None` |  |  |  |
| `geolocation` | `jsonb` | True | `None` |  |  |  |
| `user_role` | `character varying` | True | `None` |  |  |  |
| `event_category` | `character varying` | True | `None` |  |  |  |
| `resource_type` | `character varying` | True | `None` |  |  |  |
| `resource_id` | `uuid` | True | `None` |  |  |  |
| `resource_identifiers` | `jsonb` | True | `None` |  |  |  |
| `operation` | `character varying` | True | `None` |  |  |  |
| `http_method` | `character varying` | True | `None` |  |  |  |
| `endpoint` | `character varying` | True | `None` |  |  |  |
| `changes_before` | `jsonb` | True | `None` |  |  |  |
| `changes_after` | `jsonb` | True | `None` |  |  |  |
| `changed_fields` | `ARRAY` | True | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `query_params` | `jsonb` | True | `None` |  |  |  |
| `request_body_hash` | `character varying` | True | `None` |  |  |  |
| `status` | `character varying` | True | `'SUCCESS'::character varying` |  |  |  |
| `http_status_code` | `integer` | True | `None` |  |  |  |
| `error_code` | `character varying` | True | `None` |  |  |  |
| `error_stack_trace` | `text` | True | `None` |  |  |  |
| `duration_ms` | `integer` | True | `None` |  |  |  |
| `checksum` | `character varying` | True | `None` |  |  |  |
| `previous_checksum` | `character varying` | True | `None` |  |  |  |
| `integrity_verified` | `boolean` | True | `true` |  |  |  |
| `reviewed` | `boolean` | True | `false` |  |  |  |
| `reviewed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `reviewed_by` | `uuid` | True | `None` |  |  |  |
| `review_notes` | `text` | True | `None` |  |  |  |
| `is_anomalous` | `boolean` | True | `false` |  |  |  |
| `anomaly_score` | `numeric` | True | `None` |  |  |  |
| `anomaly_reasons` | `ARRAY` | True | `None` |  |  |  |
| `alert_generated` | `boolean` | True | `false` |  |  |  |
| `alert_sent_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `alert_recipients` | `ARRAY` | True | `None` |  |  |  |
| `retention_period_years` | `integer` | True | `6` |  |  |  |
| `archive_eligible_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archived` | `boolean` | True | `false` |  |  |  |
| `archived_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archive_location` | `character varying` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `audit_logs_archive_2029_pkey` | id, created_at | True |

---

### `audit_logs_archive_2030`

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `event_type` | `character varying` | False | `None` |  |  |  |
| `event_status` | `character varying` | False | `'success'::character varying` |  |  |  |
| `user_id` | `uuid` | True | `None` |  |  |  |
| `user_email` | `character varying` | True | `None` |  |  |  |
| `firebase_uid` | `character varying` | True | `None` |  |  |  |
| `ip_address` | `inet` | True | `None` |  |  |  |
| `user_agent` | `character varying` | True | `None` |  |  |  |
| `resource` | `character varying` | True | `None` |  |  |  |
| `action` | `character varying` | True | `None` |  |  |  |
| `event_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `message` | `character varying` | True | `None` |  |  |  |
| `error_details` | `character varying` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` | ✅ |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `session_id` | `character varying` | True | `None` |  |  |  |
| `session_token_hash` | `character varying` | True | `None` |  |  |  |
| `device_fingerprint` | `character varying` | True | `None` |  |  |  |
| `geolocation` | `jsonb` | True | `None` |  |  |  |
| `user_role` | `character varying` | True | `None` |  |  |  |
| `event_category` | `character varying` | True | `None` |  |  |  |
| `resource_type` | `character varying` | True | `None` |  |  |  |
| `resource_id` | `uuid` | True | `None` |  |  |  |
| `resource_identifiers` | `jsonb` | True | `None` |  |  |  |
| `operation` | `character varying` | True | `None` |  |  |  |
| `http_method` | `character varying` | True | `None` |  |  |  |
| `endpoint` | `character varying` | True | `None` |  |  |  |
| `changes_before` | `jsonb` | True | `None` |  |  |  |
| `changes_after` | `jsonb` | True | `None` |  |  |  |
| `changed_fields` | `ARRAY` | True | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `query_params` | `jsonb` | True | `None` |  |  |  |
| `request_body_hash` | `character varying` | True | `None` |  |  |  |
| `status` | `character varying` | True | `'SUCCESS'::character varying` |  |  |  |
| `http_status_code` | `integer` | True | `None` |  |  |  |
| `error_code` | `character varying` | True | `None` |  |  |  |
| `error_stack_trace` | `text` | True | `None` |  |  |  |
| `duration_ms` | `integer` | True | `None` |  |  |  |
| `checksum` | `character varying` | True | `None` |  |  |  |
| `previous_checksum` | `character varying` | True | `None` |  |  |  |
| `integrity_verified` | `boolean` | True | `true` |  |  |  |
| `reviewed` | `boolean` | True | `false` |  |  |  |
| `reviewed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `reviewed_by` | `uuid` | True | `None` |  |  |  |
| `review_notes` | `text` | True | `None` |  |  |  |
| `is_anomalous` | `boolean` | True | `false` |  |  |  |
| `anomaly_score` | `numeric` | True | `None` |  |  |  |
| `anomaly_reasons` | `ARRAY` | True | `None` |  |  |  |
| `alert_generated` | `boolean` | True | `false` |  |  |  |
| `alert_sent_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `alert_recipients` | `ARRAY` | True | `None` |  |  |  |
| `retention_period_years` | `integer` | True | `6` |  |  |  |
| `archive_eligible_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archived` | `boolean` | True | `false` |  |  |  |
| `archived_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archive_location` | `character varying` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `audit_logs_archive_2030_pkey` | id, created_at | True |

---

### `audit_logs_archive_2031`

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `event_type` | `character varying` | False | `None` |  |  |  |
| `event_status` | `character varying` | False | `'success'::character varying` |  |  |  |
| `user_id` | `uuid` | True | `None` |  |  |  |
| `user_email` | `character varying` | True | `None` |  |  |  |
| `firebase_uid` | `character varying` | True | `None` |  |  |  |
| `ip_address` | `inet` | True | `None` |  |  |  |
| `user_agent` | `character varying` | True | `None` |  |  |  |
| `resource` | `character varying` | True | `None` |  |  |  |
| `action` | `character varying` | True | `None` |  |  |  |
| `event_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `message` | `character varying` | True | `None` |  |  |  |
| `error_details` | `character varying` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` | ✅ |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `session_id` | `character varying` | True | `None` |  |  |  |
| `session_token_hash` | `character varying` | True | `None` |  |  |  |
| `device_fingerprint` | `character varying` | True | `None` |  |  |  |
| `geolocation` | `jsonb` | True | `None` |  |  |  |
| `user_role` | `character varying` | True | `None` |  |  |  |
| `event_category` | `character varying` | True | `None` |  |  |  |
| `resource_type` | `character varying` | True | `None` |  |  |  |
| `resource_id` | `uuid` | True | `None` |  |  |  |
| `resource_identifiers` | `jsonb` | True | `None` |  |  |  |
| `operation` | `character varying` | True | `None` |  |  |  |
| `http_method` | `character varying` | True | `None` |  |  |  |
| `endpoint` | `character varying` | True | `None` |  |  |  |
| `changes_before` | `jsonb` | True | `None` |  |  |  |
| `changes_after` | `jsonb` | True | `None` |  |  |  |
| `changed_fields` | `ARRAY` | True | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `query_params` | `jsonb` | True | `None` |  |  |  |
| `request_body_hash` | `character varying` | True | `None` |  |  |  |
| `status` | `character varying` | True | `'SUCCESS'::character varying` |  |  |  |
| `http_status_code` | `integer` | True | `None` |  |  |  |
| `error_code` | `character varying` | True | `None` |  |  |  |
| `error_stack_trace` | `text` | True | `None` |  |  |  |
| `duration_ms` | `integer` | True | `None` |  |  |  |
| `checksum` | `character varying` | True | `None` |  |  |  |
| `previous_checksum` | `character varying` | True | `None` |  |  |  |
| `integrity_verified` | `boolean` | True | `true` |  |  |  |
| `reviewed` | `boolean` | True | `false` |  |  |  |
| `reviewed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `reviewed_by` | `uuid` | True | `None` |  |  |  |
| `review_notes` | `text` | True | `None` |  |  |  |
| `is_anomalous` | `boolean` | True | `false` |  |  |  |
| `anomaly_score` | `numeric` | True | `None` |  |  |  |
| `anomaly_reasons` | `ARRAY` | True | `None` |  |  |  |
| `alert_generated` | `boolean` | True | `false` |  |  |  |
| `alert_sent_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `alert_recipients` | `ARRAY` | True | `None` |  |  |  |
| `retention_period_years` | `integer` | True | `6` |  |  |  |
| `archive_eligible_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archived` | `boolean` | True | `false` |  |  |  |
| `archived_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `archive_location` | `character varying` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `audit_logs_archive_2031_pkey` | id, created_at | True |

---

### `audit_trail`
_Trilha de auditoria geral (retenção: 90 dias)_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `table_name` | `character varying` | False | `None` |  |  |  |
| `record_id` | `uuid` | False | `None` |  |  |  |
| `operation` | `character varying` | False | `None` |  |  |  |
| `old_data` | `jsonb` | True | `None` |  |  |  |
| `new_data` | `jsonb` | True | `None` |  |  |  |
| `changes` | `jsonb` | True | `None` |  |  |  |
| `actor_id` | `uuid` | True | `None` |  |  |  |
| `actor_type` | `character varying` | True | `None` |  |  |  |
| `actor_subject` | `character varying` | True | `None` |  |  |  |
| `ip_address` | `inet` | True | `None` |  |  |  |
| `user_agent` | `text` | True | `None` |  |  |  |
| `endpoint` | `character varying` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | True | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `audit_trail_pkey` | id | True |
| `idx_audit_trail_actor` | actor_id, created_at | False |
| `idx_audit_trail_created_at` | created_at | False |
| `idx_audit_trail_operation` | operation, created_at | False |
| `idx_audit_trail_table_record` | table_name, record_id | False |

---

### `error_logs`
_Error tracking table for monitoring and debugging critical system errors_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `error_type` | `character varying` | False | `None` |  |  | Type of error (DI_GENERATOR, ROLE_ENUM, SCHEMA_MISMATCH, etc.) |
| `error_message` | `text` | False | `None` |  |  | The error message or description |
| `stack_trace` | `text` | True | `None` |  |  | Full stack trace of the error (optional) |
| `context` | `jsonb` | False | `'{}'::jsonb` |  |  | Additional context data as JSON (request info, user data, etc.) |
| `count` | `integer` | False | `1` |  |  | Number of times this error has occurred (for deduplication) |
| `first_seen` | `timestamp with time zone` | False | `CURRENT_TIMESTAMP` |  |  | When this error was first encountered |
| `last_seen` | `timestamp with time zone` | False | `CURRENT_TIMESTAMP` |  |  | When this error was last encountered |
| `resolved` | `boolean` | False | `false` |  |  | Whether this error has been resolved |
| `severity` | `character varying` | False | `'ERROR'::character varying` |  |  | Error severity level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `created_at` | `timestamp with time zone` | False | `CURRENT_TIMESTAMP` |  |  |  |
| `updated_at` | `timestamp with time zone` | False | `CURRENT_TIMESTAMP` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `error_logs_pkey` | id | True |
| `idx_error_logs_context_gin` | context | False |
| `idx_error_logs_count` | count | False |
| `idx_error_logs_deduplication` | error_type | True |
| `idx_error_logs_error_type` | error_type | False |
| `idx_error_logs_first_seen` | first_seen | False |
| `idx_error_logs_last_seen` | last_seen | False |
| `idx_error_logs_resolved` | resolved | False |
| `idx_error_logs_severity` | severity | False |
| `idx_error_logs_severity_time` | severity, last_seen | False |
| `idx_error_logs_type_resolved` | error_type, resolved | False |
| `idx_error_logs_unresolved_recent` | resolved, last_seen | False |

---

### `security_audit_log`
_Security audit log for WhatsApp access monitoring and threat detection_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `event_type` | `character varying` | False | `None` |  |  |  |
| `phone_number` | `character varying` | False | `None` |  |  |  |
| `patient_id` | `uuid` | True | `None` |  | -> patients.id |  |
| `message_content` | `text` | True | `None` |  |  |  |
| `source_metadata` | `jsonb` | True | `None` |  |  |  |
| `risk_score` | `integer` | False | `0` |  |  |  |
| `ip_address` | `character varying` | True | `None` |  |  |  |
| `user_agent` | `character varying` | True | `None` |  |  |  |
| `session_id` | `character varying` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `CURRENT_TIMESTAMP` |  |  |  |
| `additional_data` | `jsonb` | True | `None` |  |  |  |
| `alert_sent` | `boolean` | False | `false` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_security_audit_additional_data_gin` | additional_data | False |
| `idx_security_audit_created_at` | created_at | False |
| `idx_security_audit_event_type` | event_type | False |
| `idx_security_audit_ip_address` | ip_address | False |
| `idx_security_audit_patient_id` | patient_id | False |
| `idx_security_audit_phone_event_time` | phone_number, event_type, created_at | False |
| `idx_security_audit_phone_number` | phone_number | False |
| `idx_security_audit_risk_score` | risk_score | False |
| `idx_security_audit_risk_time` | risk_score, created_at | False |
| `idx_security_audit_session_id` | session_id | False |
| `idx_security_audit_source_metadata_gin` | source_metadata | False |
| `security_audit_log_pkey` | id | True |

---

### `user_sync_log`
_Log de sincronização Firebase ↔ Supabase_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `firebase_uid` | `character varying` | False | `None` |  |  |  |
| `supabase_user_id` | `uuid` | True | `None` |  | -> users.id |  |
| `sync_action` | `character varying` | False | `None` |  |  |  |
| `sync_status` | `character varying` | False | `None` |  |  |  |
| `firebase_data` | `jsonb` | True | `None` |  |  |  |
| `supabase_data` | `jsonb` | True | `None` |  |  |  |
| `error_message` | `text` | True | `None` |  |  |  |
| `retry_count` | `integer` | True | `0` |  |  |  |
| `synced_at` | `timestamp with time zone` | True | `now()` |  |  |  |
| `created_at` | `timestamp with time zone` | True | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  | Auto-updated timestamp for record modifications (added 2025-10-06) |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_user_sync_log_firebase_uid` | firebase_uid | False |
| `idx_user_sync_log_status` | sync_status, synced_at | False |
| `idx_user_sync_log_supabase_user` | supabase_user_id | False |
| `idx_user_sync_log_updated_at` | updated_at | False |
| `user_sync_log_pkey` | id | True |

---

## Messaging & WhatsApp
### `contacts`
_Contatos gerais do sistema_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `name` | `character varying` | False | `None` |  |  |  |
| `email` | `character varying` | True | `None` |  |  |  |
| `phone` | `character varying` | True | `None` |  |  |  |
| `contact_type` | `character varying` | True | `None` |  |  |  |
| `related_patient_id` | `uuid` | True | `None` |  | -> patients.id |  |
| `related_user_id` | `uuid` | True | `None` |  | -> users.id |  |
| `notes` | `text` | True | `None` |  |  |  |
| `tags` | `ARRAY` | True | `None` |  |  |  |
| `contact_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `created_at` | `timestamp with time zone` | True | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | True | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `contacts_pkey` | id | True |
| `idx_contacts_email` | email | False |
| `idx_contacts_phone` | phone | False |
| `idx_contacts_type` | contact_type | False |

---

### `flow_messages`
_Templates de mensagens usadas nos fluxos_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `flow_template_version_id` | `uuid` | False | `None` |  | -> flow_template_versions.id |  |
| `step_number` | `integer` | False | `None` |  |  |  |
| `message_key` | `character varying` | False | `None` |  |  |  |
| `message_text` | `text` | False | `None` |  |  |  |
| `message_type` | `character varying` | True | `'text'::character varying` |  |  |  |
| `buttons` | `jsonb` | True | `None` |  |  |  |
| `list_items` | `jsonb` | True | `None` |  |  |  |
| `conditions` | `jsonb` | True | `None` |  |  |  |
| `delay_seconds` | `integer` | True | `0` |  |  |  |
| `created_at` | `timestamp with time zone` | True | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `flow_messages_pkey` | id | True |
| `idx_flow_messages_step` | flow_template_version_id, step_number | False |
| `idx_flow_messages_template` | flow_template_version_id | False |
| `idx_flow_messages_template_step` | flow_template_version_id, step_number | False |
| `idx_flow_messages_template_version_id` | flow_template_version_id | False |
| `unique_flow_message` | flow_template_version_id, step_number, message_key | True |

---

### `message_status_events`
_Rastreamento de mudanças de status de mensagens_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `message_id` | `uuid` | False | `None` |  | -> messages.id |  |
| `status` | `character varying` | False | `None` |  |  |  |
| `previous_status` | `character varying` | True | `None` |  |  |  |
| `whatsapp_id` | `character varying` | True | `None` |  |  |  |
| `whatsapp_timestamp` | `timestamp with time zone` | True | `None` |  |  |  |
| `error_code` | `character varying` | True | `None` |  |  |  |
| `error_message` | `text` | True | `None` |  |  |  |
| `retry_count` | `integer` | True | `0` |  |  |  |
| `metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `evolution_event_type` | `character varying` | True | `None` |  |  |  |
| `evolution_payload` | `jsonb` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_msg_status_error_time` | error_code, created_at | False |
| `idx_msg_status_msg_created` | message_id, created_at | False |
| `idx_msg_status_type_time` | status, created_at | False |
| `idx_msg_status_whatsapp` | whatsapp_id, status | False |
| `message_status_events_pkey` | id | True |

---

### `messages`
_Mensagens WhatsApp (enviadas e recebidas)_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `patient_id` | `uuid` | False | `None` |  | -> patients.id |  |
| `direction` | `USER-DEFINED` | False | `None` |  |  |  |
| `type` | `USER-DEFINED` | False | `'text'::message_type` |  |  |  |
| `content` | `text` | True | `None` |  |  |  |
| `message_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `whatsapp_id` | `character varying` | True | `None` |  |  |  |
| `status` | `USER-DEFINED` | False | `'pending'::message_status` |  |  |  |
| `scheduled_for` | `timestamp with time zone` | True | `None` |  |  |  |
| `sent_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `delivered_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `read_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `delivery_status` | `USER-DEFINED` | True | `None` |  |  |  |
| `retry_count` | `integer` | False | `0` |  |  |  |
| `last_retry_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `failure_reason` | `text` | True | `None` |  |  |  |
| `next_retry_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `idempotency_key` | `character varying` | False | `None` |  |  |  |
| `priority` | `USER-DEFINED` | False | `'normal'::message_priority` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_message_cursor_pagination` | created_at, id | False |
| `idx_messages_created_at` | created_at | False |
| `idx_messages_direction` | direction | False |
| `idx_messages_direction_created_desc` | direction, created_at | False |
| `idx_messages_direction_created_new` | direction, created_at | False |
| `idx_messages_direction_created_opt` | direction, created_at | False |
| `idx_messages_idempotency_key` | idempotency_key | False |
| `idx_messages_patient_created` | patient_id, created_at | False |
| `idx_messages_patient_created_desc` | patient_id, created_at | False |
| `idx_messages_patient_created_opt` | patient_id, created_at | False |
| `idx_messages_patient_direction_created_desc` | patient_id, direction, created_at | False |
| `idx_messages_patient_direction_created_opt` | patient_id, direction, created_at | False |
| `idx_messages_patient_id` | patient_id | False |
| `idx_messages_patient_id_created_new` | patient_id, created_at | False |
| `idx_messages_patient_idempotency` | patient_id, idempotency_key | True |
| `idx_messages_patient_status` | patient_id, status | False |
| `idx_messages_scheduled_for` | scheduled_for | False |
| `idx_messages_status` | status | False |
| `idx_messages_status_created_desc` | status, created_at | False |
| `idx_messages_whatsapp_id` | whatsapp_id | False |
| `messages_pkey` | id | True |

---

### `whatsapp_contacts`

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `text` | False | `None` |  |  |  |
| `instance_name` | `text` | False | `None` |  |  |  |
| `phone_number` | `text` | False | `None` |  |  |  |
| `formatted_number` | `text` | False | `None` |  |  |  |
| `name` | `text` | True | `None` |  |  |  |
| `profile_picture_url` | `text` | True | `None` |  |  |  |
| `is_whatsapp_user` | `boolean` | True | `true` |  |  |  |
| `last_seen` | `timestamp without time zone` | True | `None` |  |  |  |
| `created_at` | `timestamp without time zone` | True | `now()` |  |  |  |
| `updated_at` | `timestamp without time zone` | True | `now()` |  |  |  |
| `contact_data` | `json` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `ix_whatsapp_contacts_instance` | instance_name | False |
| `ix_whatsapp_contacts_phone` | phone_number | False |
| `whatsapp_contacts_pkey` | id | True |

---

### `whatsapp_delivery_failures`
_Dead Letter Queue (DLQ) para falhas de envio de mensagens WhatsApp._

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `patient_id` | `uuid` | False | `None` |  | -> patients.id |  |
| `phone_number` | `character varying` | False | `None` |  |  |  |
| `message_type` | `character varying` | False | `None` |  |  |  |
| `message_content` | `text` | True | `None` |  |  |  |
| `error_message` | `text` | False | `None` |  |  |  |
| `error_code` | `character varying` | True | `None` |  |  |  |
| `retry_count` | `integer` | False | `0` |  |  |  |
| `max_retries` | `integer` | False | `3` |  |  |  |
| `next_retry_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `last_retry_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `status` | `character varying` | False | `'pending'::character varying` |  |  | Status do item na fila: pending \| retrying \| failed \| resolved. |
| `resolved_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `dlq_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  | Additional failure information in JSONB format (renamed from metadata to avoid SQLAlchemy conflicts) |
| `reviewed_by` | `uuid` | True | `None` |  | -> users.id |  |
| `original_message_id` | `uuid` | True | `None` |  | -> messages.id |  |
| `created_at` | `timestamp with time zone` | False | `timezone('utc'::text, now())` |  |  |  |
| `updated_at` | `timestamp with time zone` | False | `timezone('utc'::text, now())` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_whatsapp_delivery_failures_created_at` | created_at | False |
| `idx_whatsapp_delivery_failures_patient` | patient_id | False |
| `idx_whatsapp_delivery_failures_status_nextretry` | status, next_retry_at | False |
| `whatsapp_delivery_failures_pkey` | id | True |

---

### `whatsapp_instances`

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `text` | False | `None` |  |  |  |
| `name` | `text` | False | `None` |  |  |  |
| `status` | `text` | True | `'disconnected'::text` |  |  |  |
| `qr_code` | `text` | True | `None` |  |  |  |
| `webhook_url` | `text` | True | `None` |  |  |  |
| `phone_number` | `text` | True | `None` |  |  |  |
| `profile_name` | `text` | True | `None` |  |  |  |
| `profile_picture_url` | `text` | True | `None` |  |  |  |
| `is_connected` | `boolean` | True | `false` |  |  |  |
| `created_at` | `timestamp without time zone` | True | `now()` |  |  |  |
| `updated_at` | `timestamp without time zone` | True | `now()` |  |  |  |
| `last_activity` | `timestamp without time zone` | True | `None` |  |  |  |
| `settings` | `json` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `ix_whatsapp_instances_name` | name | False |
| `whatsapp_instances_name_key` | name | True |
| `whatsapp_instances_pkey` | id | True |

---

### `whatsapp_messages`

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `text` | False | `None` |  |  |  |
| `instance_name` | `text` | False | `None` |  |  |  |
| `chat_id` | `text` | False | `None` |  |  |  |
| `sender_id` | `text` | False | `None` |  |  |  |
| `recipient_id` | `text` | False | `None` |  |  |  |
| `message_type` | `text` | False | `None` |  |  |  |
| `content` | `text` | True | `None` |  |  |  |
| `media_url` | `text` | True | `None` |  |  |  |
| `media_caption` | `text` | True | `None` |  |  |  |
| `status` | `text` | True | `'pending'::text` |  |  |  |
| `external_id` | `text` | True | `None` |  |  |  |
| `created_at` | `timestamp without time zone` | True | `now()` |  |  |  |
| `updated_at` | `timestamp without time zone` | True | `now()` |  |  |  |
| `sent_at` | `timestamp without time zone` | True | `None` |  |  |  |
| `delivered_at` | `timestamp without time zone` | True | `None` |  |  |  |
| `read_at` | `timestamp without time zone` | True | `None` |  |  |  |
| `failed_at` | `timestamp without time zone` | True | `None` |  |  |  |
| `retry_count` | `integer` | True | `0` |  |  |  |
| `error_message` | `text` | True | `None` |  |  |  |
| `message_data` | `json` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `ix_whatsapp_messages_chat` | chat_id | False |
| `ix_whatsapp_messages_external` | external_id | False |
| `ix_whatsapp_messages_instance` | instance_name | False |
| `whatsapp_messages_external_id_key` | external_id | True |
| `whatsapp_messages_pkey` | id | True |

---

## Patients & Medical
### `appointments`
_Agendamentos e consultas médicas_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `patient_id` | `uuid` | False | `None` |  | -> patients.id |  |
| `doctor_id` | `uuid` | False | `None` |  | -> users.id |  |
| `appointment_type` | `character varying` | False | `None` |  |  |  |
| `status` | `character varying` | True | `'scheduled'::character varying` |  |  |  |
| `scheduled_at` | `timestamp with time zone` | False | `None` |  |  |  |
| `duration_minutes` | `integer` | True | `60` |  |  |  |
| `completed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `cancelled_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `pre_appointment_notes` | `text` | True | `None` |  |  |  |
| `post_appointment_notes` | `text` | True | `None` |  |  |  |
| `appointment_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `created_at` | `timestamp with time zone` | True | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | True | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `appointments_pkey` | id | True |
| `idx_appointments_doctor` | doctor_id | False |
| `idx_appointments_patient` | patient_id | False |
| `idx_appointments_scheduled` | scheduled_at | False |
| `idx_appointments_status` | status, scheduled_at | False |

---

### `medical_reports`
_Relatórios médicos gerados para pacientes_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `patient_id` | `uuid` | False | `None` |  | -> patients.id |  |
| `generated_by` | `uuid` | False | `None` |  | -> users.id |  |
| `period_start` | `date` | False | `None` |  |  |  |
| `period_end` | `date` | False | `None` |  |  |  |
| `summary` | `text` | True | `None` |  |  |  |
| `insights` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `charts_data` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `alerts` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `report_type` | `character varying` | True | `None` |  |  |  |
| `report_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_medical_reports_generated_by` | generated_by | False |
| `idx_medical_reports_patient_id` | patient_id | False |
| `idx_medical_reports_patient_period` | patient_id, period_start, period_end | False |
| `idx_medical_reports_period` | period_start, period_end | False |
| `medical_reports_pkey` | id | True |

---

### `patient_flow_states`
_Estado atual de cada paciente em cada tipo de fluxo_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `patient_id` | `uuid` | False | `None` |  | -> patients.id |  |
| `flow_template_version_id` | `uuid` | False | `None` |  | -> flow_template_versions.id |  |
| `current_step` | `integer` | True | `0` |  |  |  |
| `step_data` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `status` | `character varying` | True | `'active'::character varying` |  |  |  |
| `started_at` | `timestamp with time zone` | True | `now()` |  |  |  |
| `last_interaction_at` | `timestamp with time zone` | True | `now()` |  |  |  |
| `completed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `next_scheduled_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `flow_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `created_at` | `timestamp with time zone` | True | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | True | `now()` |  |  |  |
| `version` | `integer` | False | `0` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_patient_flow_states_next_scheduled` | next_scheduled_at | False |
| `idx_patient_flow_states_patient` | patient_id | False |
| `idx_patient_flow_states_patient_completed` | patient_id, completed_at | False |
| `idx_patient_flow_states_patient_id` | patient_id | False |
| `idx_patient_flow_states_patient_template` | patient_id, flow_template_version_id | False |
| `idx_patient_flow_states_started_at` | started_at | False |
| `idx_patient_flow_states_status` | status, last_interaction_at | False |
| `idx_patient_flow_states_template` | flow_template_version_id | False |
| `idx_patient_flow_states_version` | id, version | False |
| `patient_flow_states_pkey` | id | True |
| `unique_patient_flow` | patient_id, flow_template_version_id | True |

---

### `patient_onboarding_saga`

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `patient_id` | `uuid` | True | `None` |  | -> patients.id |  |
| `doctor_id` | `uuid` | False | `None` |  | -> users.id |  |
| `status` | `USER-DEFINED` | False | `'STARTED'::saga_status` |  |  |  |
| `current_step` | `integer` | False | `0` |  |  |  |
| `retry_count` | `integer` | False | `0` |  |  |  |
| `max_retries` | `integer` | False | `3` |  |  |  |
| `patient_data` | `jsonb` | False | `None` |  |  |  |
| `execution_log` | `jsonb` | False | `'[]'::jsonb` |  |  |  |
| `error_message` | `text` | True | `None` |  |  |  |
| `error_type` | `character varying` | True | `None` |  |  |  |
| `next_retry_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `started_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `completed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `failed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `last_retry_at` | `timestamp with time zone` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_patient_onboarding_saga_doctor_id` | doctor_id | False |
| `idx_patient_onboarding_saga_last_retry` | last_retry_at | False |
| `idx_patient_onboarding_saga_patient_id` | patient_id | False |
| `idx_patient_onboarding_saga_retry` | status, next_retry_at | False |
| `idx_patient_onboarding_saga_status` | status | False |
| `patient_onboarding_saga_pkey` | id | True |

---

### `patients`
_Patient table with validated JSONB metadata (Migration 016)_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `doctor_id` | `uuid` | False | `None` |  | -> users.id |  |
| `phone` | `character varying` | False | `None` |  |  |  |
| `name` | `character varying` | False | `None` |  |  |  |
| `email` | `character varying` | True | `None` |  |  |  |
| `birth_date` | `date` | True | `None` |  |  |  |
| `treatment_type` | `character varying` | True | `None` |  |  |  |
| `treatment_start_date` | `date` | True | `None` |  |  |  |
| `treatment_phase` | `character varying` | True | `None` |  |  |  |
| `diagnosis` | `text` | True | `None` |  |  |  |
| `flow_state` | `USER-DEFINED` | False | `'onboarding'::flow_state` |  |  |  |
| `current_day` | `integer` | False | `0` |  |  |  |
| `cpf` | `character varying` | True | `None` |  |  |  |
| `doctor_notes` | `text` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `deleted_at` | `timestamp with time zone` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_patient_cpf_doctor` | cpf, doctor_id | False |
| `idx_patient_cursor_pagination` | created_at, id | False |
| `idx_patient_email_doctor` | email, doctor_id | False |
| `idx_patient_metadata_gin` | metadata | False |
| `idx_patient_phone_doctor` | phone, doctor_id | False |
| `idx_patients_active` | deleted_at | False |
| `idx_patients_cpf_unique` | cpf | True |
| `idx_patients_created_at` | created_at | False |
| `idx_patients_deleted` | deleted_at | False |
| `idx_patients_doctor_created` | doctor_id, created_at | False |
| `idx_patients_doctor_id` | doctor_id | False |
| `idx_patients_doctor_id_opt` | doctor_id | False |
| `idx_patients_flow_state` | flow_state | False |
| `idx_patients_metadata_gin` | metadata | False |
| `idx_patients_pagination` | created_at, id | False |
| `idx_patients_phone` | phone | False |
| `idx_patients_treatment_phase` | treatment_phase | False |
| `idx_patients_treatment_type` | treatment_type | False |
| `patients_pkey` | id | True |
| `uq_patient_cpf_doctor` | cpf, doctor_id | True |
| `uq_patient_email_doctor` | email, doctor_id | True |
| `uq_patient_phone_doctor` | phone, doctor_id | True |

---

## Quiz & Flow
### `flow_analytics`
_Analytics e métricas dos fluxos_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `flow_template_version_id` | `uuid` | True | `None` |  | -> flow_template_versions.id |  |
| `patient_id` | `uuid` | True | `None` |  | -> patients.id |  |
| `total_steps` | `integer` | True | `None` |  |  |  |
| `completed_steps` | `integer` | True | `None` |  |  |  |
| `success_rate` | `numeric` | True | `None` |  |  |  |
| `avg_response_time_seconds` | `integer` | True | `None` |  |  |  |
| `step_analytics` | `jsonb` | True | `None` |  |  |  |
| `interaction_patterns` | `jsonb` | True | `None` |  |  |  |
| `period_start` | `timestamp with time zone` | True | `None` |  |  |  |
| `period_end` | `timestamp with time zone` | True | `None` |  |  |  |
| `calculated_at` | `timestamp with time zone` | True | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `flow_analytics_pkey` | id | True |
| `idx_flow_analytics_patient` | patient_id | False |
| `idx_flow_analytics_patient_id` | patient_id | False |
| `idx_flow_analytics_period` | period_start, period_end | False |
| `idx_flow_analytics_template` | flow_template_version_id | False |
| `idx_flow_analytics_template_version_id` | flow_template_version_id | False |

---

### `flow_kinds`
_Tipos de fluxos conversacionais disponíveis_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `kind_key` | `character varying` | False | `None` |  |  |  |
| `display_name` | `character varying` | False | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `is_active` | `boolean` | True | `true` |  |  |  |
| `created_at` | `timestamp with time zone` | True | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | True | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `flow_kinds_kind_key_key` | kind_key | True |
| `flow_kinds_pkey` | id | True |
| `idx_flow_kinds_is_active` | is_active | False |
| `idx_flow_kinds_kind_key` | kind_key | False |

---

### `flow_states`
_Tabela legacy de estados de fluxo (substituída por patient_flow_states)_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `patient_id` | `uuid` | False | `None` |  | -> patients.id |  |
| `flow_type` | `character varying` | False | `None` |  |  |  |
| `current_step` | `integer` | False | `0` |  |  |  |
| `started_at` | `timestamp with time zone` | False | `None` |  |  |  |
| `completed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `state_data` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `flow_states_pkey` | id | True |
| `idx_flow_states_flow_type` | flow_type | False |
| `idx_flow_states_patient_id` | patient_id | False |

---

### `flow_template_categories`
_Categorização de templates de fluxos_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `category_key` | `character varying` | False | `None` |  |  |  |
| `display_name` | `character varying` | False | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `icon` | `character varying` | True | `None` |  |  |  |
| `sort_order` | `integer` | True | `0` |  |  |  |
| `is_active` | `boolean` | True | `true` |  |  |  |
| `created_at` | `timestamp with time zone` | True | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `flow_template_categories_category_key_key` | category_key | True |
| `flow_template_categories_pkey` | id | True |

---

### `flow_template_shares`
_Compartilhamento de templates entre médicos_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `flow_template_version_id` | `uuid` | False | `None` |  | -> flow_template_versions.id |  |
| `shared_by` | `uuid` | False | `None` |  | -> users.id |  |
| `shared_with` | `uuid` | True | `None` |  | -> users.id |  |
| `can_view` | `boolean` | True | `true` |  |  |  |
| `can_edit` | `boolean` | True | `false` |  |  |  |
| `can_reshare` | `boolean` | True | `false` |  |  |  |
| `share_notes` | `text` | True | `None` |  |  |  |
| `shared_at` | `timestamp with time zone` | True | `now()` |  |  |  |
| `expires_at` | `timestamp with time zone` | True | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `flow_template_shares_pkey` | id | True |
| `unique_share` | flow_template_version_id, shared_by, shared_with | True |

---

### `flow_template_stats`
_Estatísticas agregadas dos templates_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `flow_template_version_id` | `uuid` | False | `None` |  | -> flow_template_versions.id |  |
| `total_uses` | `integer` | True | `0` |  |  |  |
| `active_instances` | `integer` | True | `0` |  |  |  |
| `completed_instances` | `integer` | True | `0` |  |  |  |
| `avg_completion_rate` | `numeric` | True | `None` |  |  |  |
| `avg_duration_hours` | `numeric` | True | `None` |  |  |  |
| `avg_rating` | `numeric` | True | `None` |  |  |  |
| `total_ratings` | `integer` | True | `0` |  |  |  |
| `last_calculated_at` | `timestamp with time zone` | True | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `flow_template_stats_flow_template_version_id_key` | flow_template_version_id | True |
| `flow_template_stats_pkey` | id | True |

---

### `flow_template_versions`
_Versões de templates de fluxos conversacionais_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `flow_kind_id` | `uuid` | False | `None` |  | -> flow_kinds.id |  |
| `version_number` | `integer` | False | `None` |  |  |  |
| `template_name` | `character varying` | False | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `steps` | `jsonb` | False | `None` |  |  |  |
| `metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `is_active` | `boolean` | True | `false` |  |  |  |
| `is_draft` | `boolean` | True | `true` |  |  |  |
| `published_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `deprecated_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `created_by` | `uuid` | True | `None` |  | -> users.id |  |
| `created_at` | `timestamp with time zone` | True | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | True | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `flow_template_versions_pkey` | id | True |
| `idx_flow_template_versions_active` | flow_kind_id, is_active | False |
| `idx_flow_template_versions_flow_kind` | flow_kind_id | False |
| `idx_flow_template_versions_version` | flow_kind_id, version_number | False |
| `unique_flow_version` | flow_kind_id, version_number | True |

---

### `quiz_response_migration_log`

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `quiz_response_id` | `uuid` | False | `None` |  |  |  |
| `original_value` | `text` | True | `None` |  |  |  |
| `converted_value` | `jsonb` | True | `None` |  |  |  |
| `conversion_status` | `text` | False | `None` |  |  |  |
| `error_message` | `text` | True | `None` |  |  |  |
| `migrated_at` | `timestamp with time zone` | False | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_migration_log_errors` | quiz_response_id | False |
| `idx_migration_log_status` | conversion_status | False |
| `quiz_response_migration_log_pkey` | id | True |

---

### `quiz_responses`
_Respostas individuais de questionários_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `patient_id` | `uuid` | False | `None` |  | -> patients.id |  |
| `quiz_template_id` | `uuid` | False | `None` |  | -> quiz_templates.id |  |
| `quiz_session_id` | `uuid` | True | `None` |  | -> quiz_sessions.id |  |
| `question_id` | `character varying` | False | `None` |  |  |  |
| `question_text` | `text` | False | `None` |  |  |  |
| `response_type` | `character varying` | False | `None` |  |  |  |
| `response_value_text_backup` | `text` | False | `None` |  |  |  |
| `is_correct` | `boolean` | True | `None` |  |  |  |
| `points_earned` | `numeric` | True | `None` |  |  |  |
| `response_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `responded_at` | `timestamp with time zone` | False | `None` |  |  |  |
| `response_time_seconds` | `integer` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `other_text` | `text` | True | `None` |  |  |  |
| `response_value` | `jsonb` | True | `None` |  |  | JSONB column storing structured quiz responses.
        Formats:
        - Plain text: "response text" or {"text": "response text"}
        - Multiple choice: ["option1", "option2"] or {"selections": ["A", "B"]}
        - Scale: {"value": 7, "type": "scale"}
        - Boolean: {"text": "yes", "boolean": true}
        Migration completed: 2025-01-14 |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_quiz_response_analytics_covering_index` | quiz_template_id, question_id, response_value_text_backup, responded_at | False |
| `idx_quiz_response_array_value` | response_value | False |
| `idx_quiz_response_patient_template_index` | patient_id, quiz_template_id, responded_at | False |
| `idx_quiz_response_session_id` | quiz_session_id | False |
| `idx_quiz_response_value_gin` | response_value | False |
| `idx_quiz_responses_cursor_pagination` | created_at, id | False |
| `idx_quiz_responses_patient_created_new` | patient_id, created_at | False |
| `idx_quiz_responses_patient_id` | patient_id | False |
| `idx_quiz_responses_quiz_template_id` | quiz_template_id | False |
| `idx_quiz_responses_responded_at` | responded_at | False |
| `quiz_responses_pkey` | id | True |

---

### `quiz_sessions`
_Sessões de questionários respondidos por pacientes (Schema v2 - status-based)_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `patient_id` | `uuid` | False | `None` |  | -> patients.id |  |
| `quiz_template_id` | `uuid` | False | `None` |  | -> quiz_templates.id |  |
| `status` | `character varying` | False | `'started'::character varying` |  |  |  |
| `current_question` | `integer` | True | `0` |  |  |  |
| `total_questions` | `integer` | True | `None` |  |  |  |
| `answered_questions` | `integer` | True | `0` |  |  |  |
| `score` | `numeric` | True | `None` |  |  |  |
| `max_score` | `numeric` | True | `None` |  |  |  |
| `passed` | `boolean` | True | `None` |  |  |  |
| `started_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `completed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `time_spent_seconds` | `integer` | True | `None` |  |  |  |
| `session_metadata` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_quiz_session_cursor_pagination` | created_at, id | False |
| `idx_quiz_session_unique_active` | patient_id, quiz_template_id | True |
| `idx_quiz_sessions_completed_at_v2` | completed_at | False |
| `idx_quiz_sessions_created_at_v2` | created_at | False |
| `idx_quiz_sessions_patient_created` | patient_id, created_at | False |
| `idx_quiz_sessions_patient_id` | patient_id | False |
| `idx_quiz_sessions_patient_id_v2` | patient_id | False |
| `idx_quiz_sessions_patient_started_desc` | patient_id, started_at | False |
| `idx_quiz_sessions_patient_status` | patient_id, status | False |
| `idx_quiz_sessions_patient_status_v2` | patient_id, status | False |
| `idx_quiz_sessions_patient_template_v2` | patient_id, quiz_template_id, started_at | False |
| `idx_quiz_sessions_quiz_template_id_v2` | quiz_template_id | False |
| `idx_quiz_sessions_started_at` | started_at | False |
| `idx_quiz_sessions_status_v2` | status | False |
| `idx_quiz_sessions_template_status_v2` | quiz_template_id, status | False |
| `quiz_sessions_pkey` | id | True |

---

### `quiz_sessions_v2`
_Versão melhorada de sessões com suporte a versionamento_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `patient_id` | `uuid` | False | `None` |  | -> patients.id |  |
| `template_version_id` | `uuid` | False | `None` |  | -> quiz_template_versions_v2.id |  |
| `status` | `character varying` | True | `'started'::character varying` |  |  |  |
| `started_at` | `timestamp with time zone` | True | `now()` |  |  |  |
| `completed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `session_data` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `created_at` | `timestamp with time zone` | True | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_quiz_sessions_v2_patient` | patient_id | False |
| `idx_quiz_sessions_v2_template_version` | template_version_id | False |
| `quiz_sessions_v2_pkey` | id | True |

---

### `quiz_template_versions_v2`
_Sistema de versionamento aprimorado de questionários_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `template_id` | `uuid` | False | `None` |  | -> quiz_templates.id |  |
| `version_number` | `integer` | False | `None` |  |  |  |
| `questions` | `jsonb` | False | `None` |  |  |  |
| `scoring_rules` | `jsonb` | True | `None` |  |  |  |
| `is_active` | `boolean` | True | `false` |  |  |  |
| `is_draft` | `boolean` | True | `true` |  |  |  |
| `published_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `created_by` | `uuid` | True | `None` |  | -> users.id |  |
| `change_notes` | `text` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | True | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_quiz_template_versions_v2_active` | template_id, is_active | False |
| `idx_quiz_template_versions_v2_template` | template_id | False |
| `quiz_template_versions_v2_pkey` | id | True |
| `unique_template_version` | template_id, version_number | True |

---

### `quiz_templates`
_Templates de questionários para pacientes_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `name` | `character varying` | False | `None` |  |  |  |
| `version` | `character varying` | False | `None` |  |  |  |
| `description` | `text` | True | `None` |  |  |  |
| `questions` | `jsonb` | False | `None` |  |  |  |
| `is_active` | `boolean` | False | `true` |  |  |  |
| `category` | `character varying` | True | `None` |  |  |  |
| `tags` | `ARRAY` | True | `None` |  |  |  |
| `passing_score` | `integer` | True | `None` |  |  |  |
| `time_limit_minutes` | `integer` | True | `None` |  |  |  |
| `randomize_questions` | `boolean` | True | `false` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_quiz_templates_category` | category | False |
| `idx_quiz_templates_is_active` | is_active | False |
| `quiz_templates_pkey` | id | True |

---

## System & Meta
### `alembic_version`
_Controle de versão de migrações Alembic (gerenciado automaticamente)_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `version_num` | `character varying` | False | `None` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `alembic_version_pkc` | version_num | True |

---

### `alerts`
_Alertas e notificações do sistema_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `patient_id` | `uuid` | False | `None` |  | -> patients.id |  |
| `type` | `character varying` | False | `None` |  |  |  |
| `severity` | `USER-DEFINED` | False | `None` |  |  |  |
| `message` | `text` | False | `None` |  |  |  |
| `data` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `acknowledged` | `boolean` | False | `false` |  |  |  |
| `acknowledged_by` | `uuid` | True | `None` |  | -> users.id |  |
| `acknowledged_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `alerts_pkey` | id | True |
| `idx_alerts_acknowledged` | acknowledged | False |
| `idx_alerts_acknowledged_by` | acknowledged_by | False |
| `idx_alerts_patient_acknowledged` | patient_id, acknowledged | False |
| `idx_alerts_patient_created` | patient_id, created_at | False |
| `idx_alerts_patient_id` | patient_id | False |
| `idx_alerts_severity` | severity | False |
| `idx_alerts_type` | type | False |

---

### `notifications`
_System notifications for users with support for patient-related alerts_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `user_id` | `uuid` | False | `None` |  | -> users.id |  |
| `related_patient_id` | `uuid` | True | `None` |  | -> patients.id |  |
| `notification_type` | `character varying` | False | `None` |  |  | Type: info, warning, error, success, alert, reminder |
| `priority` | `character varying` | False | `'medium'::character varying` |  |  | Priority: low, medium, high, urgent |
| `title` | `character varying` | False | `None` |  |  |  |
| `message` | `text` | False | `None` |  |  |  |
| `action_url` | `character varying` | True | `None` |  |  |  |
| `action_label` | `character varying` | True | `None` |  |  |  |
| `notification_metadata` | `jsonb` | True | `None` |  |  | Additional metadata in JSON format |
| `is_read` | `boolean` | False | `false` |  |  |  |
| `read_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `is_archived` | `boolean` | False | `false` |  |  |  |
| `archived_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `expires_at` | `timestamp with time zone` | True | `None` |  |  | Optional expiration timestamp for temporary notifications |
| `created_at` | `timestamp with time zone` | False | `CURRENT_TIMESTAMP` |  |  |  |
| `updated_at` | `timestamp with time zone` | False | `CURRENT_TIMESTAMP` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_notifications_expires_at` | expires_at | False |
| `idx_notifications_is_archived` | is_archived | False |
| `idx_notifications_is_read` | is_read | False |
| `idx_notifications_priority` | priority | False |
| `idx_notifications_related_patient_id` | related_patient_id | False |
| `idx_notifications_type` | notification_type | False |
| `idx_notifications_user_id` | user_id | False |
| `idx_notifications_user_unread` | user_id, is_read, is_archived | False |
| `notifications_pkey` | id | True |

---

### `user_profiles`
_Perfis estendidos de usuários profissionais_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `user_id` | `uuid` | False | `None` |  | -> users.id |  |
| `bio` | `text` | True | `None` |  |  |  |
| `avatar_url` | `character varying` | True | `None` |  |  |  |
| `phone` | `character varying` | True | `None` |  |  |  |
| `specialty` | `character varying` | True | `None` |  |  |  |
| `license_number` | `character varying` | True | `None` |  |  |  |
| `years_of_experience` | `integer` | True | `None` |  |  |  |
| `preferences` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `notification_settings` | `jsonb` | True | `'{}'::jsonb` |  |  |  |
| `created_at` | `timestamp with time zone` | True | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | True | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_user_profiles_user_id` | user_id | False |
| `user_profiles_pkey` | id | True |
| `user_profiles_user_id_key` | user_id | True |

---

### `users`
_Profissionais de saúde (médicos e administradores) - Supports local and Firebase authentication_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `email` | `character varying` | False | `None` |  |  |  |
| `hashed_password` | `character varying` | True | `None` |  |  | Password hash - NULL for Firebase-only users |
| `full_name` | `character varying` | True | `None` |  |  |  |
| `role` | `USER-DEFINED` | False | `'doctor'::user_role` |  |  |  |
| `is_active` | `boolean` | False | `true` |  |  |  |
| `firebase_uid` | `character varying` | True | `None` |  |  | Firebase user UID from Firebase Authentication |
| `auth_provider` | `USER-DEFINED` | False | `'local'::auth_provider` |  |  | Authentication provider: local (password) or firebase |
| `firebase_last_sign_in` | `timestamp with time zone` | True | `None` |  |  |  |
| `firebase_created_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `firebase_email_verified` | `boolean` | False | `false` |  |  |  |
| `firebase_display_name` | `character varying` | True | `None` |  |  |  |
| `firebase_photo_url` | `character varying` | True | `None` |  |  |  |
| `firebase_custom_claims` | `jsonb` | False | `'{}'::jsonb` |  |  | Firebase custom claims including role (admin/doctor) and permissions |
| `last_firebase_sync` | `timestamp with time zone` | True | `None` |  |  | Timestamp of last sync with Firebase Authentication |
| `created_at` | `timestamp with time zone` | False | `now()` |  |  |  |
| `updated_at` | `timestamp with time zone` | False | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_users_auth_provider` | auth_provider | False |
| `idx_users_email` | email | False |
| `idx_users_firebase_uid` | firebase_uid | False |
| `idx_users_firebase_uid_active_new` | firebase_uid | False |
| `idx_users_is_active` | is_active | False |
| `idx_users_role` | role | False |
| `users_email_key` | email | True |
| `users_firebase_uid_key` | firebase_uid | True |
| `users_pkey` | id | True |

---

### `webhook_events`
_Armazenamento e replay de webhooks da Evolution API_

#### Columns
| Name | Type | Nullable | Default | PK | FK | Description |
|------|------|----------|---------|----|----|-------------|
| `id` | `uuid` | False | `gen_random_uuid()` |  |  |  |
| `event_type` | `character varying` | False | `None` |  |  |  |
| `source` | `character varying` | False | `'evolution_api'::character varying` |  |  |  |
| `payload` | `jsonb` | False | `None` |  |  |  |
| `processed` | `boolean` | False | `false` |  |  |  |
| `processed_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `retry_count` | `integer` | True | `0` |  |  |  |
| `max_retries` | `integer` | True | `3` |  |  |  |
| `next_retry_at` | `timestamp with time zone` | True | `None` |  |  |  |
| `error_message` | `text` | True | `None` |  |  |  |
| `error_stack_trace` | `text` | True | `None` |  |  |  |
| `related_message_id` | `uuid` | True | `None` |  |  |  |
| `related_patient_id` | `uuid` | True | `None` |  |  |  |
| `event_hash` | `character varying` | False | `None` |  |  |  |
| `is_duplicate` | `boolean` | True | `false` |  |  |  |
| `original_event_id` | `uuid` | True | `None` |  |  |  |
| `created_at` | `timestamp with time zone` | False | `now()` |  |  |  |

#### Indexes
| Name | Columns | Unique |
|------|---------|--------|
| `idx_webhook_events_cursor_pagination` | created_at, id | False |
| `idx_webhook_pending` | processed, retry_count, created_at | False |
| `idx_webhook_related_msg` | related_message_id, event_type | False |
| `idx_webhook_related_patient` | related_patient_id, event_type | False |
| `idx_webhook_retry_schedule` | processed, next_retry_at | False |
| `idx_webhook_source_time` | source, created_at | False |
| `idx_webhook_type_processed` | event_type, processed, created_at | False |
| `webhook_events_event_hash_key` | event_hash | True |
| `webhook_events_pkey` | id | True |

---
