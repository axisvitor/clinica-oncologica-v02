# Schema Reference

> Gerado em 09/11/2025 20:08 Hora oficial do Brasil – sem dados sensíveis


## Schema `public`


### Tabela `public.admin_audit_log`

- Tamanho: tabela 8.0 KB | índices 56.0 KB | total 64.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| admin_user_id | uuid | YES |  |
| session_id | uuid | YES |  |
| event_type | character varying | NO |  |
| event_category | character varying | NO |  |
| action | character varying | NO |  |
| resource_type | character varying | YES |  |
| resource_id | character varying | YES |  |
| ip_address | inet | YES |  |
| user_agent | text | YES |  |
| endpoint | character varying | YES |  |
| http_method | USER-DEFINED | YES |  |
| details | jsonb | YES | '{}'::jsonb |
| changes | jsonb | YES |  |
| success | boolean | YES | true |
| error_message | text | YES |  |
| timestamp | timestamp with time zone | YES | CURRENT_TIMESTAMP |
| duration_ms | integer | YES |  |
| severity | USER-DEFINED | YES | 'low'::severity_type |

#### Chave Primária
- id

#### Chaves Estrangeiras
- admin_user_id → public.admin_users.id
- session_id → public.admin_sessions.id

#### Índices
- admin_audit_log_pkey: `CREATE UNIQUE INDEX admin_audit_log_pkey ON public.admin_audit_log USING btree (id)`
- idx_admin_audit_event_type: `CREATE INDEX idx_admin_audit_event_type ON public.admin_audit_log USING btree (event_type)`
- idx_admin_audit_ip: `CREATE INDEX idx_admin_audit_ip ON public.admin_audit_log USING btree (ip_address)`
- idx_admin_audit_resource: `CREATE INDEX idx_admin_audit_resource ON public.admin_audit_log USING btree (resource_type, resource_id)`
- idx_admin_audit_severity: `CREATE INDEX idx_admin_audit_severity ON public.admin_audit_log USING btree (severity)`
- idx_admin_audit_timestamp: `CREATE INDEX idx_admin_audit_timestamp ON public.admin_audit_log USING btree ("timestamp")`
- idx_admin_audit_user_id: `CREATE INDEX idx_admin_audit_user_id ON public.admin_audit_log USING btree (admin_user_id)`

#### Triggers
- (sem triggers)

### Tabela `public.admin_ip_blacklist`

- Tamanho: tabela 8.0 KB | índices 24.0 KB | total 32.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| ip_address | inet | NO |  |
| reason | character varying | NO |  |
| blocked_at | timestamp with time zone | YES | CURRENT_TIMESTAMP |
| blocked_by | uuid | YES |  |
| expires_at | timestamp with time zone | YES |  |
| is_permanent | boolean | YES | false |
| incident_id | uuid | YES |  |
| threat_level | USER-DEFINED | YES | 'medium'::severity_type |
| block_count | integer | YES | 1 |
| details | jsonb | YES | '{}'::jsonb |
| notes | text | YES |  |

#### Chave Primária
- id

#### Chaves Estrangeiras
- blocked_by → public.admin_users.id

#### Índices
- admin_ip_blacklist_ip_address_key: `CREATE UNIQUE INDEX admin_ip_blacklist_ip_address_key ON public.admin_ip_blacklist USING btree (ip_address)`
- admin_ip_blacklist_pkey: `CREATE UNIQUE INDEX admin_ip_blacklist_pkey ON public.admin_ip_blacklist USING btree (id)`
- idx_ip_blacklist_active: `CREATE INDEX idx_ip_blacklist_active ON public.admin_ip_blacklist USING btree (ip_address, expires_at)`

#### Triggers
- (sem triggers)

### Tabela `public.admin_ip_whitelist`

- Tamanho: tabela 8.0 KB | índices 32.0 KB | total 40.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| ip_address | inet | YES |  |
| ip_range | cidr | YES |  |
| description | text | YES |  |
| added_by | uuid | YES |  |
| added_at | timestamp with time zone | YES | CURRENT_TIMESTAMP |
| is_active | boolean | YES | true |
| expires_at | timestamp with time zone | YES |  |
| last_used_at | timestamp with time zone | YES |  |
| usage_count | integer | YES | 0 |

#### Chave Primária
- id

#### Chaves Estrangeiras
- added_by → public.admin_users.id

#### Índices
- admin_ip_whitelist_pkey: `CREATE UNIQUE INDEX admin_ip_whitelist_pkey ON public.admin_ip_whitelist USING btree (id)`
- idx_ip_whitelist_active: `CREATE INDEX idx_ip_whitelist_active ON public.admin_ip_whitelist USING btree (is_active, ip_address)`
- idx_ip_whitelist_range: `CREATE INDEX idx_ip_whitelist_range ON public.admin_ip_whitelist USING gist (ip_range)`
- unique_ip_or_range: `CREATE UNIQUE INDEX unique_ip_or_range ON public.admin_ip_whitelist USING btree (ip_address, ip_range)`

#### Triggers
- (sem triggers)

### Tabela `public.admin_permissions`

- Tamanho: tabela 8.0 KB | índices 24.0 KB | total 32.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| name | character varying | NO |  |
| description | text | YES |  |
| category | character varying | NO |  |
| created_at | timestamp with time zone | YES | CURRENT_TIMESTAMP |

#### Chave Primária
- id

#### Chaves Estrangeiras
- (sem FKs)

#### Índices
- admin_permissions_name_key: `CREATE UNIQUE INDEX admin_permissions_name_key ON public.admin_permissions USING btree (name)`
- admin_permissions_pkey: `CREATE UNIQUE INDEX admin_permissions_pkey ON public.admin_permissions USING btree (id)`
- idx_admin_permissions_category: `CREATE INDEX idx_admin_permissions_category ON public.admin_permissions USING btree (category)`

#### Triggers
- (sem triggers)

### Tabela `public.admin_role_permissions`

- Tamanho: tabela 0.0 B | índices 16.0 KB | total 16.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| role_id | uuid | NO |  |
| permission_id | uuid | NO |  |
| created_at | timestamp with time zone | YES | CURRENT_TIMESTAMP |

#### Chave Primária
- role_id, permission_id

#### Chaves Estrangeiras
- role_id → public.admin_roles.id
- permission_id → public.admin_permissions.id

#### Índices
- admin_role_permissions_pkey: `CREATE UNIQUE INDEX admin_role_permissions_pkey ON public.admin_role_permissions USING btree (role_id, permission_id)`
- idx_admin_role_permissions_role: `CREATE INDEX idx_admin_role_permissions_role ON public.admin_role_permissions USING btree (role_id)`

#### Triggers
- (sem triggers)

### Tabela `public.admin_roles`

- Tamanho: tabela 8.0 KB | índices 16.0 KB | total 24.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| name | character varying | NO |  |
| description | text | YES |  |
| is_system_role | boolean | YES | false |
| created_at | timestamp with time zone | YES | CURRENT_TIMESTAMP |
| updated_at | timestamp with time zone | YES | CURRENT_TIMESTAMP |

#### Chave Primária
- id

#### Chaves Estrangeiras
- (sem FKs)

#### Índices
- admin_roles_name_key: `CREATE UNIQUE INDEX admin_roles_name_key ON public.admin_roles USING btree (name)`
- admin_roles_pkey: `CREATE UNIQUE INDEX admin_roles_pkey ON public.admin_roles USING btree (id)`

#### Triggers
- update_admin_roles_updated_at (BEFORE UPDATE)

### Tabela `public.admin_security_events`

- Tamanho: tabela 8.0 KB | índices 48.0 KB | total 56.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| event_type | character varying | NO |  |
| severity | USER-DEFINED | NO | 'medium'::severity_type |
| ip_address | inet | YES |  |
| user_agent | text | YES |  |
| admin_user_id | uuid | YES |  |
| session_id | uuid | YES |  |
| description | text | YES |  |
| details | jsonb | YES | '{}'::jsonb |
| endpoint | character varying | YES |  |
| detected_at | timestamp with time zone | YES | CURRENT_TIMESTAMP |
| resolved_at | timestamp with time zone | YES |  |
| resolution_notes | text | YES |  |
| auto_resolved | boolean | YES | false |
| risk_score | integer | YES | 0 |
| threat_level | USER-DEFINED | YES | 'low'::severity_type |

#### Chave Primária
- id

#### Chaves Estrangeiras
- admin_user_id → public.admin_users.id
- session_id → public.admin_sessions.id

#### Índices
- admin_security_events_pkey: `CREATE UNIQUE INDEX admin_security_events_pkey ON public.admin_security_events USING btree (id)`
- idx_security_events_ip: `CREATE INDEX idx_security_events_ip ON public.admin_security_events USING btree (ip_address)`
- idx_security_events_resolved: `CREATE INDEX idx_security_events_resolved ON public.admin_security_events USING btree (resolved_at) WHERE (resolved_at IS NOT NULL)`
- idx_security_events_severity: `CREATE INDEX idx_security_events_severity ON public.admin_security_events USING btree (severity)`
- idx_security_events_timestamp: `CREATE INDEX idx_security_events_timestamp ON public.admin_security_events USING btree (detected_at)`
- idx_security_events_user_id: `CREATE INDEX idx_security_events_user_id ON public.admin_security_events USING btree (admin_user_id)`

#### Triggers
- (sem triggers)

### Tabela `public.admin_sessions`

- Tamanho: tabela 8.0 KB | índices 64.0 KB | total 72.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| admin_user_id | uuid | NO |  |
| session_token | character varying | NO |  |
| refresh_token | character varying | YES |  |
| ip_address | inet | YES |  |
| user_agent | text | YES |  |
| device_fingerprint | character varying | YES |  |
| created_at | timestamp with time zone | YES | CURRENT_TIMESTAMP |
| last_activity | timestamp with time zone | YES | CURRENT_TIMESTAMP |
| expires_at | timestamp with time zone | NO |  |
| is_active | boolean | YES | true |
| logout_reason | character varying | YES |  |
| metadata | jsonb | YES | '{}'::jsonb |

#### Chave Primária
- id

#### Chaves Estrangeiras
- admin_user_id → public.admin_users.id

#### Índices
- admin_sessions_pkey: `CREATE UNIQUE INDEX admin_sessions_pkey ON public.admin_sessions USING btree (id)`
- admin_sessions_refresh_token_key: `CREATE UNIQUE INDEX admin_sessions_refresh_token_key ON public.admin_sessions USING btree (refresh_token)`
- admin_sessions_session_token_key: `CREATE UNIQUE INDEX admin_sessions_session_token_key ON public.admin_sessions USING btree (session_token)`
- idx_admin_sessions_active: `CREATE INDEX idx_admin_sessions_active ON public.admin_sessions USING btree (is_active, last_activity)`
- idx_admin_sessions_expires: `CREATE INDEX idx_admin_sessions_expires ON public.admin_sessions USING btree (expires_at)`
- idx_admin_sessions_ip: `CREATE INDEX idx_admin_sessions_ip ON public.admin_sessions USING btree (ip_address)`
- idx_admin_sessions_token: `CREATE INDEX idx_admin_sessions_token ON public.admin_sessions USING btree (session_token)`
- idx_admin_sessions_user_id: `CREATE INDEX idx_admin_sessions_user_id ON public.admin_sessions USING btree (admin_user_id)`

#### Triggers
- (sem triggers)

### Tabela `public.admin_user_permissions`

- Tamanho: tabela 0.0 B | índices 16.0 KB | total 16.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| admin_user_id | uuid | NO |  |
| permission_id | uuid | NO |  |
| granted_at | timestamp with time zone | YES | CURRENT_TIMESTAMP |
| granted_by | uuid | YES |  |

#### Chave Primária
- admin_user_id, permission_id

#### Chaves Estrangeiras
- admin_user_id → public.admin_users.id
- permission_id → public.admin_permissions.id
- granted_by → public.admin_users.id

#### Índices
- admin_user_permissions_pkey: `CREATE UNIQUE INDEX admin_user_permissions_pkey ON public.admin_user_permissions USING btree (admin_user_id, permission_id)`
- idx_admin_user_permissions_user: `CREATE INDEX idx_admin_user_permissions_user ON public.admin_user_permissions USING btree (admin_user_id)`

#### Triggers
- (sem triggers)

### Tabela `public.admin_users`

- Tamanho: tabela 8.0 KB | índices 56.0 KB | total 64.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| email | character varying | NO |  |
| password_hash | character varying | NO |  |
| first_name | character varying | NO |  |
| last_name | character varying | NO |  |
| role | USER-DEFINED | NO | 'supervisor'::admin_role_type |
| department | character varying | YES |  |
| phone_number | character varying | YES |  |
| is_active | boolean | YES | true |
| email_verified | boolean | YES | false |
| two_factor_enabled | boolean | YES | false |
| two_factor_secret | character varying | YES |  |
| must_change_password | boolean | YES | true |
| failed_login_attempts | integer | YES | 0 |
| locked_until | timestamp with time zone | YES |  |
| last_login_at | timestamp with time zone | YES |  |
| last_login_ip | inet | YES |  |
| last_password_change | timestamp with time zone | YES | CURRENT_TIMESTAMP |
| max_concurrent_sessions | integer | YES | 3 |
| created_at | timestamp with time zone | YES | CURRENT_TIMESTAMP |
| updated_at | timestamp with time zone | YES | CURRENT_TIMESTAMP |
| created_by | uuid | YES |  |
| updated_by | uuid | YES |  |
| metadata | jsonb | YES | '{}'::jsonb |

#### Chave Primária
- id

#### Chaves Estrangeiras
- created_by → public.admin_users.id
- updated_by → public.admin_users.id

#### Índices
- admin_users_email_key: `CREATE UNIQUE INDEX admin_users_email_key ON public.admin_users USING btree (email)`
- admin_users_pkey: `CREATE UNIQUE INDEX admin_users_pkey ON public.admin_users USING btree (id)`
- idx_admin_users_active: `CREATE INDEX idx_admin_users_active ON public.admin_users USING btree (is_active)`
- idx_admin_users_email: `CREATE INDEX idx_admin_users_email ON public.admin_users USING btree (email)`
- idx_admin_users_last_login: `CREATE INDEX idx_admin_users_last_login ON public.admin_users USING btree (last_login_at)`
- idx_admin_users_locked: `CREATE INDEX idx_admin_users_locked ON public.admin_users USING btree (locked_until) WHERE (locked_until IS NOT NULL)`
- idx_admin_users_role: `CREATE INDEX idx_admin_users_role ON public.admin_users USING btree (role)`

#### Triggers
- update_admin_users_updated_at (BEFORE UPDATE)

### Tabela `public.alembic_version`

- Tamanho: tabela 40.0 KB | índices 16.0 KB | total 56.0 KB
- Linhas (aprox): 1

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| version_num | character varying | NO |  |

#### Chave Primária
- version_num

#### Chaves Estrangeiras
- (sem FKs)

#### Índices
- alembic_version_pkc: `CREATE UNIQUE INDEX alembic_version_pkc ON public.alembic_version USING btree (version_num)`

#### Triggers
- (sem triggers)

### Tabela `public.alerts`

- Tamanho: tabela 8.0 KB | índices 40.0 KB | total 48.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| patient_id | uuid | NO |  |
| type | character varying | NO |  |
| severity | USER-DEFINED | NO |  |
| message | text | NO |  |
| data | jsonb | YES | '{}'::jsonb |
| acknowledged | boolean | NO | false |
| acknowledged_by | uuid | YES |  |
| acknowledged_at | timestamp with time zone | YES |  |
| created_at | timestamp with time zone | NO | now() |
| updated_at | timestamp with time zone | NO | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- acknowledged_by → public.users.id
- patient_id → public.patients.id

#### Índices
- alerts_pkey: `CREATE UNIQUE INDEX alerts_pkey ON public.alerts USING btree (id)`
- idx_alerts_acknowledged: `CREATE INDEX idx_alerts_acknowledged ON public.alerts USING btree (acknowledged)`
- idx_alerts_patient_id: `CREATE INDEX idx_alerts_patient_id ON public.alerts USING btree (patient_id)`
- idx_alerts_severity: `CREATE INDEX idx_alerts_severity ON public.alerts USING btree (severity)`
- idx_alerts_type: `CREATE INDEX idx_alerts_type ON public.alerts USING btree (type)`

#### Triggers
- update_alerts_updated_at (BEFORE UPDATE)

### Tabela `public.appointments`

- Tamanho: tabela 8.0 KB | índices 40.0 KB | total 48.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| patient_id | uuid | NO |  |
| doctor_id | uuid | NO |  |
| appointment_type | character varying | NO |  |
| status | character varying | YES | 'scheduled'::character varying |
| scheduled_at | timestamp with time zone | NO |  |
| duration_minutes | integer | YES | 60 |
| completed_at | timestamp with time zone | YES |  |
| cancelled_at | timestamp with time zone | YES |  |
| pre_appointment_notes | text | YES |  |
| post_appointment_notes | text | YES |  |
| appointment_metadata | jsonb | YES | '{}'::jsonb |
| created_at | timestamp with time zone | YES | now() |
| updated_at | timestamp with time zone | YES | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- doctor_id → public.users.id
- patient_id → public.patients.id

#### Índices
- appointments_pkey: `CREATE UNIQUE INDEX appointments_pkey ON public.appointments USING btree (id)`
- idx_appointments_doctor: `CREATE INDEX idx_appointments_doctor ON public.appointments USING btree (doctor_id)`
- idx_appointments_patient: `CREATE INDEX idx_appointments_patient ON public.appointments USING btree (patient_id)`
- idx_appointments_scheduled: `CREATE INDEX idx_appointments_scheduled ON public.appointments USING btree (scheduled_at)`
- idx_appointments_status: `CREATE INDEX idx_appointments_status ON public.appointments USING btree (status, scheduled_at)`

#### Triggers
- (sem triggers)

### Tabela `public.audit_log_entries`

- Tamanho: tabela 8.0 KB | índices 32.0 KB | total 40.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| event_type | character varying | NO |  |
| entity_type | character varying | YES |  |
| entity_id | uuid | YES |  |
| user_id | uuid | YES |  |
| old_values | jsonb | YES |  |
| new_values | jsonb | YES |  |
| metadata | jsonb | YES | '{}'::jsonb |
| ip_address | inet | YES |  |
| user_agent | text | YES |  |
| timestamp | timestamp with time zone | YES | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- (sem FKs)

#### Índices
- audit_log_entries_pkey: `CREATE UNIQUE INDEX audit_log_entries_pkey ON public.audit_log_entries USING btree (id)`
- idx_audit_log_entries_entity: `CREATE INDEX idx_audit_log_entries_entity ON public.audit_log_entries USING btree (entity_type, entity_id)`
- idx_audit_log_entries_timestamp: `CREATE INDEX idx_audit_log_entries_timestamp ON public.audit_log_entries USING btree ("timestamp")`
- idx_audit_log_entries_user: `CREATE INDEX idx_audit_log_entries_user ON public.audit_log_entries USING btree (user_id, "timestamp" DESC)`

#### Triggers
- (sem triggers)

### Tabela `public.audit_logs`

- Tamanho: tabela 64.0 KB | índices 144.0 KB | total 208.0 KB
- Linhas (aprox): 102

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| event_type | character varying | NO |  |
| event_status | character varying | NO | 'success'::character varying |
| user_id | uuid | YES |  |
| user_email | character varying | YES |  |
| firebase_uid | character varying | YES |  |
| ip_address | inet | YES |  |
| user_agent | character varying | YES |  |
| resource | character varying | YES |  |
| action | character varying | YES |  |
| event_metadata | jsonb | YES | '{}'::jsonb |
| message | character varying | YES |  |
| error_details | character varying | YES |  |
| created_at | timestamp with time zone | NO | now() |
| updated_at | timestamp with time zone | NO | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- user_id → public.users.id

#### Índices
- audit_logs_pkey: `CREATE UNIQUE INDEX audit_logs_pkey ON public.audit_logs USING btree (id)`
- idx_audit_logs_created_at: `CREATE INDEX idx_audit_logs_created_at ON public.audit_logs USING btree (created_at)`
- idx_audit_logs_event_status: `CREATE INDEX idx_audit_logs_event_status ON public.audit_logs USING btree (event_status)`
- idx_audit_logs_event_type: `CREATE INDEX idx_audit_logs_event_type ON public.audit_logs USING btree (event_type)`
- idx_audit_logs_ip_address: `CREATE INDEX idx_audit_logs_ip_address ON public.audit_logs USING btree (ip_address)`
- idx_audit_logs_resource_action: `CREATE INDEX idx_audit_logs_resource_action ON public.audit_logs USING btree (resource, action)`
- idx_audit_logs_user_email: `CREATE INDEX idx_audit_logs_user_email ON public.audit_logs USING btree (user_email)`
- idx_audit_logs_user_id: `CREATE INDEX idx_audit_logs_user_id ON public.audit_logs USING btree (user_id)`
- idx_audit_user_event_time: `CREATE INDEX idx_audit_user_event_time ON public.audit_logs USING btree (user_id, event_type, created_at)`

#### Triggers
- update_audit_logs_updated_at (BEFORE UPDATE)

### Tabela `public.audit_trail`

- Tamanho: tabela 8.0 KB | índices 40.0 KB | total 48.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| table_name | character varying | NO |  |
| record_id | uuid | NO |  |
| operation | character varying | NO |  |
| old_data | jsonb | YES |  |
| new_data | jsonb | YES |  |
| changes | jsonb | YES |  |
| actor_id | uuid | YES |  |
| actor_type | character varying | YES |  |
| actor_subject | character varying | YES |  |
| ip_address | inet | YES |  |
| user_agent | text | YES |  |
| endpoint | character varying | YES |  |
| created_at | timestamp with time zone | YES | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- (sem FKs)

#### Índices
- audit_trail_pkey: `CREATE UNIQUE INDEX audit_trail_pkey ON public.audit_trail USING btree (id)`
- idx_audit_trail_actor: `CREATE INDEX idx_audit_trail_actor ON public.audit_trail USING btree (actor_id, created_at DESC)`
- idx_audit_trail_created_at: `CREATE INDEX idx_audit_trail_created_at ON public.audit_trail USING btree (created_at)`
- idx_audit_trail_operation: `CREATE INDEX idx_audit_trail_operation ON public.audit_trail USING btree (operation, created_at DESC)`
- idx_audit_trail_table_record: `CREATE INDEX idx_audit_trail_table_record ON public.audit_trail USING btree (table_name, record_id)`

#### Triggers
- (sem triggers)

### Tabela `public.contacts`

- Tamanho: tabela 8.0 KB | índices 32.0 KB | total 40.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| name | character varying | NO |  |
| email | character varying | YES |  |
| phone | character varying | YES |  |
| contact_type | character varying | YES |  |
| related_patient_id | uuid | YES |  |
| related_user_id | uuid | YES |  |
| notes | text | YES |  |
| tags | ARRAY | YES |  |
| contact_metadata | jsonb | YES | '{}'::jsonb |
| created_at | timestamp with time zone | YES | now() |
| updated_at | timestamp with time zone | YES | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- related_user_id → public.users.id
- related_patient_id → public.patients.id

#### Índices
- contacts_pkey: `CREATE UNIQUE INDEX contacts_pkey ON public.contacts USING btree (id)`
- idx_contacts_email: `CREATE INDEX idx_contacts_email ON public.contacts USING btree (email)`
- idx_contacts_phone: `CREATE INDEX idx_contacts_phone ON public.contacts USING btree (phone)`
- idx_contacts_type: `CREATE INDEX idx_contacts_type ON public.contacts USING btree (contact_type)`

#### Triggers
- (sem triggers)

### Tabela `public.error_logs`

- Tamanho: tabela 48.0 KB | índices 208.0 KB | total 256.0 KB
- Linhas (aprox): 5

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| error_type | character varying | NO |  |
| error_message | text | NO |  |
| stack_trace | text | YES |  |
| context | jsonb | NO | '{}'::jsonb |
| count | integer | NO | 1 |
| first_seen | timestamp with time zone | NO | CURRENT_TIMESTAMP |
| last_seen | timestamp with time zone | NO | CURRENT_TIMESTAMP |
| resolved | boolean | NO | false |
| severity | character varying | NO | 'ERROR'::character varying |
| created_at | timestamp with time zone | NO | CURRENT_TIMESTAMP |
| updated_at | timestamp with time zone | NO | CURRENT_TIMESTAMP |

#### Chave Primária
- id

#### Chaves Estrangeiras
- (sem FKs)

#### Índices
- error_logs_pkey: `CREATE UNIQUE INDEX error_logs_pkey ON public.error_logs USING btree (id)`
- idx_error_logs_context_gin: `CREATE INDEX idx_error_logs_context_gin ON public.error_logs USING gin (context)`
- idx_error_logs_count: `CREATE INDEX idx_error_logs_count ON public.error_logs USING btree (count)`
- idx_error_logs_deduplication: `CREATE UNIQUE INDEX idx_error_logs_deduplication ON public.error_logs USING btree (error_type, md5(error_message))`
- idx_error_logs_error_type: `CREATE INDEX idx_error_logs_error_type ON public.error_logs USING btree (error_type)`
- idx_error_logs_first_seen: `CREATE INDEX idx_error_logs_first_seen ON public.error_logs USING btree (first_seen)`
- idx_error_logs_last_seen: `CREATE INDEX idx_error_logs_last_seen ON public.error_logs USING btree (last_seen)`
- idx_error_logs_resolved: `CREATE INDEX idx_error_logs_resolved ON public.error_logs USING btree (resolved)`
- idx_error_logs_severity: `CREATE INDEX idx_error_logs_severity ON public.error_logs USING btree (severity)`
- idx_error_logs_severity_time: `CREATE INDEX idx_error_logs_severity_time ON public.error_logs USING btree (severity, last_seen)`
- idx_error_logs_type_resolved: `CREATE INDEX idx_error_logs_type_resolved ON public.error_logs USING btree (error_type, resolved)`
- idx_error_logs_unresolved_recent: `CREATE INDEX idx_error_logs_unresolved_recent ON public.error_logs USING btree (resolved, last_seen)`

#### Triggers
- (sem triggers)

### Tabela `public.flow_analytics`

- Tamanho: tabela 8.0 KB | índices 32.0 KB | total 40.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| flow_template_version_id | uuid | YES |  |
| patient_id | uuid | YES |  |
| total_steps | integer | YES |  |
| completed_steps | integer | YES |  |
| success_rate | numeric | YES |  |
| avg_response_time_seconds | integer | YES |  |
| step_analytics | jsonb | YES |  |
| interaction_patterns | jsonb | YES |  |
| period_start | timestamp with time zone | YES |  |
| period_end | timestamp with time zone | YES |  |
| calculated_at | timestamp with time zone | YES | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- flow_template_version_id → public.flow_template_versions.id
- patient_id → public.patients.id

#### Índices
- flow_analytics_pkey: `CREATE UNIQUE INDEX flow_analytics_pkey ON public.flow_analytics USING btree (id)`
- idx_flow_analytics_patient: `CREATE INDEX idx_flow_analytics_patient ON public.flow_analytics USING btree (patient_id)`
- idx_flow_analytics_period: `CREATE INDEX idx_flow_analytics_period ON public.flow_analytics USING btree (period_start, period_end)`
- idx_flow_analytics_template: `CREATE INDEX idx_flow_analytics_template ON public.flow_analytics USING btree (flow_template_version_id)`

#### Triggers
- (sem triggers)

### Tabela `public.flow_kinds`

- Tamanho: tabela 16.0 KB | índices 64.0 KB | total 80.0 KB
- Linhas (aprox): 8

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| kind_key | character varying | NO |  |
| display_name | character varying | NO |  |
| description | text | YES |  |
| is_active | boolean | YES | true |
| created_at | timestamp with time zone | YES | now() |
| updated_at | timestamp with time zone | YES | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- (sem FKs)

#### Índices
- flow_kinds_kind_key_key: `CREATE UNIQUE INDEX flow_kinds_kind_key_key ON public.flow_kinds USING btree (kind_key)`
- flow_kinds_pkey: `CREATE UNIQUE INDEX flow_kinds_pkey ON public.flow_kinds USING btree (id)`
- idx_flow_kinds_is_active: `CREATE INDEX idx_flow_kinds_is_active ON public.flow_kinds USING btree (is_active)`
- idx_flow_kinds_kind_key: `CREATE INDEX idx_flow_kinds_kind_key ON public.flow_kinds USING btree (kind_key)`

#### Triggers
- (sem triggers)

### Tabela `public.flow_messages`

- Tamanho: tabela 8.0 KB | índices 32.0 KB | total 40.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| flow_template_version_id | uuid | NO |  |
| step_number | integer | NO |  |
| message_key | character varying | NO |  |
| message_text | text | NO |  |
| message_type | character varying | YES | 'text'::character varying |
| buttons | jsonb | YES |  |
| list_items | jsonb | YES |  |
| conditions | jsonb | YES |  |
| delay_seconds | integer | YES | 0 |
| created_at | timestamp with time zone | YES | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- flow_template_version_id → public.flow_template_versions.id

#### Índices
- flow_messages_pkey: `CREATE UNIQUE INDEX flow_messages_pkey ON public.flow_messages USING btree (id)`
- idx_flow_messages_step: `CREATE INDEX idx_flow_messages_step ON public.flow_messages USING btree (flow_template_version_id, step_number)`
- idx_flow_messages_template: `CREATE INDEX idx_flow_messages_template ON public.flow_messages USING btree (flow_template_version_id)`
- unique_flow_message: `CREATE UNIQUE INDEX unique_flow_message ON public.flow_messages USING btree (flow_template_version_id, step_number, message_key)`

#### Triggers
- (sem triggers)

### Tabela `public.flow_states`

- Tamanho: tabela 8.0 KB | índices 24.0 KB | total 32.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| patient_id | uuid | NO |  |
| flow_type | character varying | NO |  |
| current_step | integer | NO | 0 |
| started_at | timestamp with time zone | NO |  |
| completed_at | timestamp with time zone | YES |  |
| state_data | jsonb | YES | '{}'::jsonb |
| created_at | timestamp with time zone | NO | now() |
| updated_at | timestamp with time zone | NO | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- patient_id → public.patients.id

#### Índices
- flow_states_pkey: `CREATE UNIQUE INDEX flow_states_pkey ON public.flow_states USING btree (id)`
- idx_flow_states_flow_type: `CREATE INDEX idx_flow_states_flow_type ON public.flow_states USING btree (flow_type)`
- idx_flow_states_patient_id: `CREATE INDEX idx_flow_states_patient_id ON public.flow_states USING btree (patient_id)`

#### Triggers
- update_flow_states_updated_at (BEFORE UPDATE)

### Tabela `public.flow_template_categories`

- Tamanho: tabela 8.0 KB | índices 16.0 KB | total 24.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| category_key | character varying | NO |  |
| display_name | character varying | NO |  |
| description | text | YES |  |
| icon | character varying | YES |  |
| sort_order | integer | YES | 0 |
| is_active | boolean | YES | true |
| created_at | timestamp with time zone | YES | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- (sem FKs)

#### Índices
- flow_template_categories_category_key_key: `CREATE UNIQUE INDEX flow_template_categories_category_key_key ON public.flow_template_categories USING btree (category_key)`
- flow_template_categories_pkey: `CREATE UNIQUE INDEX flow_template_categories_pkey ON public.flow_template_categories USING btree (id)`

#### Triggers
- (sem triggers)

### Tabela `public.flow_template_shares`

- Tamanho: tabela 8.0 KB | índices 16.0 KB | total 24.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| flow_template_version_id | uuid | NO |  |
| shared_by | uuid | NO |  |
| shared_with | uuid | YES |  |
| can_view | boolean | YES | true |
| can_edit | boolean | YES | false |
| can_reshare | boolean | YES | false |
| share_notes | text | YES |  |
| shared_at | timestamp with time zone | YES | now() |
| expires_at | timestamp with time zone | YES |  |

#### Chave Primária
- id

#### Chaves Estrangeiras
- flow_template_version_id → public.flow_template_versions.id
- shared_by → public.users.id
- shared_with → public.users.id

#### Índices
- flow_template_shares_pkey: `CREATE UNIQUE INDEX flow_template_shares_pkey ON public.flow_template_shares USING btree (id)`
- unique_share: `CREATE UNIQUE INDEX unique_share ON public.flow_template_shares USING btree (flow_template_version_id, shared_by, shared_with)`

#### Triggers
- (sem triggers)

### Tabela `public.flow_template_stats`

- Tamanho: tabela 0.0 B | índices 16.0 KB | total 16.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| flow_template_version_id | uuid | NO |  |
| total_uses | integer | YES | 0 |
| active_instances | integer | YES | 0 |
| completed_instances | integer | YES | 0 |
| avg_completion_rate | numeric | YES |  |
| avg_duration_hours | numeric | YES |  |
| avg_rating | numeric | YES |  |
| total_ratings | integer | YES | 0 |
| last_calculated_at | timestamp with time zone | YES | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- flow_template_version_id → public.flow_template_versions.id

#### Índices
- flow_template_stats_flow_template_version_id_key: `CREATE UNIQUE INDEX flow_template_stats_flow_template_version_id_key ON public.flow_template_stats USING btree (flow_template_version_id)`
- flow_template_stats_pkey: `CREATE UNIQUE INDEX flow_template_stats_pkey ON public.flow_template_stats USING btree (id)`

#### Triggers
- (sem triggers)

### Tabela `public.flow_template_versions`

- Tamanho: tabela 176.0 KB | índices 80.0 KB | total 256.0 KB
- Linhas (aprox): 3

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| flow_kind_id | uuid | NO |  |
| version_number | integer | NO |  |
| template_name | character varying | NO |  |
| description | text | YES |  |
| steps | jsonb | NO |  |
| metadata | jsonb | YES | '{}'::jsonb |
| is_active | boolean | YES | false |
| is_draft | boolean | YES | true |
| published_at | timestamp with time zone | YES |  |
| deprecated_at | timestamp with time zone | YES |  |
| created_by | uuid | YES |  |
| created_at | timestamp with time zone | YES | now() |
| updated_at | timestamp with time zone | YES | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- flow_kind_id → public.flow_kinds.id
- created_by → public.users.id

#### Índices
- flow_template_versions_pkey: `CREATE UNIQUE INDEX flow_template_versions_pkey ON public.flow_template_versions USING btree (id)`
- idx_flow_template_versions_active: `CREATE INDEX idx_flow_template_versions_active ON public.flow_template_versions USING btree (flow_kind_id, is_active) WHERE (is_active = true)`
- idx_flow_template_versions_flow_kind: `CREATE INDEX idx_flow_template_versions_flow_kind ON public.flow_template_versions USING btree (flow_kind_id)`
- idx_flow_template_versions_version: `CREATE INDEX idx_flow_template_versions_version ON public.flow_template_versions USING btree (flow_kind_id, version_number DESC)`
- unique_flow_version: `CREATE UNIQUE INDEX unique_flow_version ON public.flow_template_versions USING btree (flow_kind_id, version_number)`

#### Triggers
- (sem triggers)

### Tabela `public.medical_reports`

- Tamanho: tabela 8.0 KB | índices 32.0 KB | total 40.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| patient_id | uuid | NO |  |
| generated_by | uuid | NO |  |
| period_start | date | NO |  |
| period_end | date | NO |  |
| summary | text | YES |  |
| insights | jsonb | YES | '{}'::jsonb |
| charts_data | jsonb | YES | '{}'::jsonb |
| alerts | jsonb | YES | '{}'::jsonb |
| report_type | character varying | YES |  |
| report_metadata | jsonb | YES | '{}'::jsonb |
| created_at | timestamp with time zone | NO | now() |
| updated_at | timestamp with time zone | NO | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- generated_by → public.users.id
- patient_id → public.patients.id

#### Índices
- idx_medical_reports_generated_by: `CREATE INDEX idx_medical_reports_generated_by ON public.medical_reports USING btree (generated_by)`
- idx_medical_reports_patient_id: `CREATE INDEX idx_medical_reports_patient_id ON public.medical_reports USING btree (patient_id)`
- idx_medical_reports_period: `CREATE INDEX idx_medical_reports_period ON public.medical_reports USING btree (period_start, period_end)`
- medical_reports_pkey: `CREATE UNIQUE INDEX medical_reports_pkey ON public.medical_reports USING btree (id)`

#### Triggers
- update_medical_reports_updated_at (BEFORE UPDATE)

### Tabela `public.message_status_events`

- Tamanho: tabela 8.0 KB | índices 40.0 KB | total 48.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| message_id | uuid | NO |  |
| status | character varying | NO |  |
| previous_status | character varying | YES |  |
| whatsapp_id | character varying | YES |  |
| whatsapp_timestamp | timestamp with time zone | YES |  |
| error_code | character varying | YES |  |
| error_message | text | YES |  |
| retry_count | integer | YES | 0 |
| metadata | jsonb | YES | '{}'::jsonb |
| evolution_event_type | character varying | YES |  |
| evolution_payload | jsonb | YES |  |
| created_at | timestamp with time zone | NO | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- message_id → public.messages.id

#### Índices
- idx_msg_status_error_time: `CREATE INDEX idx_msg_status_error_time ON public.message_status_events USING btree (error_code, created_at) WHERE (error_code IS NOT NULL)`
- idx_msg_status_msg_created: `CREATE INDEX idx_msg_status_msg_created ON public.message_status_events USING btree (message_id, created_at)`
- idx_msg_status_type_time: `CREATE INDEX idx_msg_status_type_time ON public.message_status_events USING btree (status, created_at)`
- idx_msg_status_whatsapp: `CREATE INDEX idx_msg_status_whatsapp ON public.message_status_events USING btree (whatsapp_id, status)`
- message_status_events_pkey: `CREATE UNIQUE INDEX message_status_events_pkey ON public.message_status_events USING btree (id)`

#### Triggers
- (sem triggers)

### Tabela `public.messages`

- Tamanho: tabela 32.0 KB | índices 288.0 KB | total 320.0 KB
- Linhas (aprox): 1

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| patient_id | uuid | NO |  |
| direction | USER-DEFINED | NO |  |
| type | USER-DEFINED | NO | 'text'::message_type |
| content | text | YES |  |
| message_metadata | jsonb | YES | '{}'::jsonb |
| whatsapp_id | character varying | YES |  |
| status | USER-DEFINED | NO | 'pending'::message_status |
| scheduled_for | timestamp with time zone | YES |  |
| sent_at | timestamp with time zone | YES |  |
| delivered_at | timestamp with time zone | YES |  |
| read_at | timestamp with time zone | YES |  |
| created_at | timestamp with time zone | NO | now() |
| updated_at | timestamp with time zone | NO | now() |
| delivery_status | USER-DEFINED | YES |  |
| retry_count | integer | NO | 0 |
| last_retry_at | timestamp with time zone | YES |  |
| failure_reason | text | YES |  |
| next_retry_at | timestamp with time zone | YES |  |
| idempotency_key | character varying | NO |  |

#### Chave Primária
- id

#### Chaves Estrangeiras
- patient_id → public.patients.id

#### Índices
- idx_messages_created_at: `CREATE INDEX idx_messages_created_at ON public.messages USING btree (created_at DESC)`
- idx_messages_direction: `CREATE INDEX idx_messages_direction ON public.messages USING btree (direction)`
- idx_messages_direction_created_desc: `CREATE INDEX idx_messages_direction_created_desc ON public.messages USING btree (direction, created_at DESC)`
- idx_messages_direction_created_new: `CREATE INDEX idx_messages_direction_created_new ON public.messages USING btree (direction, created_at DESC)`
- idx_messages_direction_created_opt: `CREATE INDEX idx_messages_direction_created_opt ON public.messages USING btree (direction, created_at DESC)`
- idx_messages_idempotency_key: `CREATE INDEX idx_messages_idempotency_key ON public.messages USING btree (idempotency_key)`
- idx_messages_patient_created_desc: `CREATE INDEX idx_messages_patient_created_desc ON public.messages USING btree (patient_id, created_at DESC)`
- idx_messages_patient_created_opt: `CREATE INDEX idx_messages_patient_created_opt ON public.messages USING btree (patient_id, created_at DESC)`
- idx_messages_patient_direction_created_desc: `CREATE INDEX idx_messages_patient_direction_created_desc ON public.messages USING btree (patient_id, direction, created_at DESC)`
- idx_messages_patient_direction_created_opt: `CREATE INDEX idx_messages_patient_direction_created_opt ON public.messages USING btree (patient_id, direction, created_at DESC)`
- idx_messages_patient_id: `CREATE INDEX idx_messages_patient_id ON public.messages USING btree (patient_id)`
- idx_messages_patient_id_created_new: `CREATE INDEX idx_messages_patient_id_created_new ON public.messages USING btree (patient_id, created_at DESC)`
- idx_messages_patient_idempotency: `CREATE UNIQUE INDEX idx_messages_patient_idempotency ON public.messages USING btree (patient_id, idempotency_key) WHERE (idempotency_key IS NOT NULL)`
- idx_messages_scheduled_for: `CREATE INDEX idx_messages_scheduled_for ON public.messages USING btree (scheduled_for)`
- idx_messages_status: `CREATE INDEX idx_messages_status ON public.messages USING btree (status)`
- idx_messages_status_created_desc: `CREATE INDEX idx_messages_status_created_desc ON public.messages USING btree (status, created_at DESC)`
- idx_messages_whatsapp_id: `CREATE INDEX idx_messages_whatsapp_id ON public.messages USING btree (whatsapp_id)`
- messages_pkey: `CREATE UNIQUE INDEX messages_pkey ON public.messages USING btree (id)`

#### Triggers
- update_messages_updated_at (BEFORE UPDATE)

### Tabela `public.patient_flow_states`

- Tamanho: tabela 16.0 KB | índices 88.0 KB | total 104.0 KB
- Linhas (aprox): 1

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| patient_id | uuid | NO |  |
| flow_template_version_id | uuid | NO |  |
| current_step | integer | YES | 0 |
| step_data | jsonb | YES | '{}'::jsonb |
| status | character varying | YES | 'active'::character varying |
| started_at | timestamp with time zone | YES | now() |
| last_interaction_at | timestamp with time zone | YES | now() |
| completed_at | timestamp with time zone | YES |  |
| next_scheduled_at | timestamp with time zone | YES |  |
| flow_metadata | jsonb | YES | '{}'::jsonb |
| created_at | timestamp with time zone | YES | now() |
| updated_at | timestamp with time zone | YES | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- flow_template_version_id → public.flow_template_versions.id
- patient_id → public.patients.id

#### Índices
- idx_patient_flow_states_next_scheduled: `CREATE INDEX idx_patient_flow_states_next_scheduled ON public.patient_flow_states USING btree (next_scheduled_at) WHERE (((status)::text = 'active'::text) AND (next_scheduled_at IS NOT NULL))`
- idx_patient_flow_states_patient: `CREATE INDEX idx_patient_flow_states_patient ON public.patient_flow_states USING btree (patient_id)`
- idx_patient_flow_states_status: `CREATE INDEX idx_patient_flow_states_status ON public.patient_flow_states USING btree (status, last_interaction_at)`
- idx_patient_flow_states_template: `CREATE INDEX idx_patient_flow_states_template ON public.patient_flow_states USING btree (flow_template_version_id)`
- patient_flow_states_pkey: `CREATE UNIQUE INDEX patient_flow_states_pkey ON public.patient_flow_states USING btree (id)`
- unique_patient_flow: `CREATE UNIQUE INDEX unique_patient_flow ON public.patient_flow_states USING btree (patient_id, flow_template_version_id)`

#### Triggers
- (sem triggers)

### Tabela `public.patient_onboarding_saga`

- Tamanho: tabela 16.0 KB | índices 72.0 KB | total 88.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| patient_id | uuid | YES |  |
| doctor_id | uuid | NO |  |
| status | USER-DEFINED | NO | 'STARTED'::saga_status |
| current_step | integer | NO | 0 |
| retry_count | integer | NO | 0 |
| max_retries | integer | NO | 3 |
| patient_data | jsonb | NO |  |
| execution_log | jsonb | NO | '[]'::jsonb |
| error_message | text | YES |  |
| error_type | character varying | YES |  |
| next_retry_at | timestamp with time zone | YES |  |
| started_at | timestamp with time zone | NO | now() |
| completed_at | timestamp with time zone | YES |  |
| failed_at | timestamp with time zone | YES |  |
| created_at | timestamp with time zone | NO | now() |
| updated_at | timestamp with time zone | NO | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- patient_id → public.patients.id
- doctor_id → public.users.id

#### Índices
- idx_patient_onboarding_saga_doctor_id: `CREATE INDEX idx_patient_onboarding_saga_doctor_id ON public.patient_onboarding_saga USING btree (doctor_id)`
- idx_patient_onboarding_saga_patient_id: `CREATE INDEX idx_patient_onboarding_saga_patient_id ON public.patient_onboarding_saga USING btree (patient_id)`
- idx_patient_onboarding_saga_retry: `CREATE INDEX idx_patient_onboarding_saga_retry ON public.patient_onboarding_saga USING btree (status, next_retry_at) WHERE (status = 'RETRY_SCHEDULED'::saga_status)`
- idx_patient_onboarding_saga_status: `CREATE INDEX idx_patient_onboarding_saga_status ON public.patient_onboarding_saga USING btree (status)`
- patient_onboarding_saga_pkey: `CREATE UNIQUE INDEX patient_onboarding_saga_pkey ON public.patient_onboarding_saga USING btree (id)`

#### Triggers
- (sem triggers)

### Tabela `public.patients`

- Tamanho: tabela 48.0 KB | índices 240.0 KB | total 288.0 KB
- Linhas (aprox): 1

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| doctor_id | uuid | NO |  |
| phone | character varying | NO |  |
| name | character varying | NO |  |
| email | character varying | YES |  |
| birth_date | date | YES |  |
| treatment_type | character varying | YES |  |
| treatment_start_date | date | YES |  |
| treatment_phase | character varying | YES |  |
| diagnosis | text | YES |  |
| flow_state | USER-DEFINED | NO | 'onboarding'::flow_state |
| current_day | integer | NO | 0 |
| cpf | character varying | YES |  |
| doctor_notes | text | YES |  |
| created_at | timestamp with time zone | NO | now() |
| updated_at | timestamp with time zone | NO | now() |
| metadata | jsonb | YES | '{}'::jsonb |
| deleted_at | timestamp with time zone | YES |  |

#### Chave Primária
- id

#### Chaves Estrangeiras
- doctor_id → public.users.id

#### Índices
- idx_patients_active: `CREATE INDEX idx_patients_active ON public.patients USING btree (deleted_at)`
- idx_patients_cpf_unique: `CREATE UNIQUE INDEX idx_patients_cpf_unique ON public.patients USING btree (cpf) WHERE (cpf IS NOT NULL)`
- idx_patients_created_at: `CREATE INDEX idx_patients_created_at ON public.patients USING btree (created_at DESC)`
- idx_patients_deleted: `CREATE INDEX idx_patients_deleted ON public.patients USING btree (deleted_at) WHERE (deleted_at IS NOT NULL)`
- idx_patients_doctor_id: `CREATE INDEX idx_patients_doctor_id ON public.patients USING btree (doctor_id)`
- idx_patients_doctor_id_opt: `CREATE INDEX idx_patients_doctor_id_opt ON public.patients USING btree (doctor_id)`
- idx_patients_flow_state: `CREATE INDEX idx_patients_flow_state ON public.patients USING btree (flow_state)`
- idx_patients_metadata_gin: `CREATE INDEX idx_patients_metadata_gin ON public.patients USING gin (metadata)`
- idx_patients_pagination: `CREATE INDEX idx_patients_pagination ON public.patients USING btree (created_at DESC, id)`
- idx_patients_phone: `CREATE INDEX idx_patients_phone ON public.patients USING btree (phone)`
- idx_patients_treatment_phase: `CREATE INDEX idx_patients_treatment_phase ON public.patients USING btree (treatment_phase) WHERE (treatment_phase IS NOT NULL)`
- idx_patients_treatment_type: `CREATE INDEX idx_patients_treatment_type ON public.patients USING btree (treatment_type)`
- patients_cpf_key: `CREATE UNIQUE INDEX patients_cpf_key ON public.patients USING btree (cpf)`
- patients_phone_key: `CREATE UNIQUE INDEX patients_phone_key ON public.patients USING btree (phone)`
- patients_pkey: `CREATE UNIQUE INDEX patients_pkey ON public.patients USING btree (id)`

#### Triggers
- update_patients_updated_at (BEFORE UPDATE)

### Tabela `public.quiz_responses`

- Tamanho: tabela 16.0 KB | índices 128.0 KB | total 144.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| patient_id | uuid | NO |  |
| quiz_template_id | uuid | NO |  |
| quiz_session_id | uuid | YES |  |
| question_id | character varying | NO |  |
| question_text | text | NO |  |
| response_type | character varying | NO |  |
| response_value | text | NO |  |
| is_correct | boolean | YES |  |
| points_earned | numeric | YES |  |
| response_metadata | jsonb | YES | '{}'::jsonb |
| responded_at | timestamp with time zone | NO |  |
| response_time_seconds | integer | YES |  |
| created_at | timestamp with time zone | NO | now() |
| updated_at | timestamp with time zone | NO | now() |
| other_text | text | YES |  |

#### Chave Primária
- id

#### Chaves Estrangeiras
- quiz_template_id → public.quiz_templates.id
- quiz_session_id → public.quiz_sessions.id
- patient_id → public.patients.id

#### Índices
- idx_quiz_response_analytics_covering_index: `CREATE INDEX idx_quiz_response_analytics_covering_index ON public.quiz_responses USING btree (quiz_template_id, question_id, response_value, responded_at)`
- idx_quiz_response_patient_template_index: `CREATE INDEX idx_quiz_response_patient_template_index ON public.quiz_responses USING btree (patient_id, quiz_template_id, responded_at DESC)`
- idx_quiz_response_session_id: `CREATE INDEX idx_quiz_response_session_id ON public.quiz_responses USING btree (quiz_session_id)`
- idx_quiz_responses_patient_created_new: `CREATE INDEX idx_quiz_responses_patient_created_new ON public.quiz_responses USING btree (patient_id, created_at DESC)`
- idx_quiz_responses_patient_id: `CREATE INDEX idx_quiz_responses_patient_id ON public.quiz_responses USING btree (patient_id)`
- idx_quiz_responses_quiz_template_id: `CREATE INDEX idx_quiz_responses_quiz_template_id ON public.quiz_responses USING btree (quiz_template_id)`
- idx_quiz_responses_responded_at: `CREATE INDEX idx_quiz_responses_responded_at ON public.quiz_responses USING btree (responded_at)`
- quiz_responses_pkey: `CREATE UNIQUE INDEX quiz_responses_pkey ON public.quiz_responses USING btree (id)`

#### Triggers
- update_quiz_responses_updated_at (BEFORE UPDATE)

### Tabela `public.quiz_sessions`

- Tamanho: tabela 16.0 KB | índices 176.0 KB | total 192.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| patient_id | uuid | NO |  |
| quiz_template_id | uuid | NO |  |
| status | character varying | NO | 'started'::character varying |
| current_question | integer | YES | 0 |
| total_questions | integer | YES |  |
| answered_questions | integer | YES | 0 |
| score | numeric | YES |  |
| max_score | numeric | YES |  |
| passed | boolean | YES |  |
| started_at | timestamp with time zone | NO | now() |
| completed_at | timestamp with time zone | YES |  |
| time_spent_seconds | integer | YES |  |
| session_metadata | jsonb | YES | '{}'::jsonb |
| created_at | timestamp with time zone | NO | now() |
| updated_at | timestamp with time zone | NO | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- quiz_template_id → public.quiz_templates.id
- patient_id → public.patients.id

#### Índices
- idx_quiz_session_unique_active: `CREATE UNIQUE INDEX idx_quiz_session_unique_active ON public.quiz_sessions USING btree (patient_id, quiz_template_id) WHERE ((status)::text = 'started'::text)`
- idx_quiz_sessions_completed_at_v2: `CREATE INDEX idx_quiz_sessions_completed_at_v2 ON public.quiz_sessions USING btree (completed_at DESC) WHERE (completed_at IS NOT NULL)`
- idx_quiz_sessions_created_at_v2: `CREATE INDEX idx_quiz_sessions_created_at_v2 ON public.quiz_sessions USING btree (created_at DESC)`
- idx_quiz_sessions_patient_id_v2: `CREATE INDEX idx_quiz_sessions_patient_id_v2 ON public.quiz_sessions USING btree (patient_id)`
- idx_quiz_sessions_patient_started_desc: `CREATE INDEX idx_quiz_sessions_patient_started_desc ON public.quiz_sessions USING btree (patient_id, started_at DESC) WHERE (session_metadata IS NOT NULL)`
- idx_quiz_sessions_patient_status_v2: `CREATE INDEX idx_quiz_sessions_patient_status_v2 ON public.quiz_sessions USING btree (patient_id, status)`
- idx_quiz_sessions_patient_template_v2: `CREATE INDEX idx_quiz_sessions_patient_template_v2 ON public.quiz_sessions USING btree (patient_id, quiz_template_id, started_at DESC)`
- idx_quiz_sessions_quiz_template_id_v2: `CREATE INDEX idx_quiz_sessions_quiz_template_id_v2 ON public.quiz_sessions USING btree (quiz_template_id)`
- idx_quiz_sessions_status_v2: `CREATE INDEX idx_quiz_sessions_status_v2 ON public.quiz_sessions USING btree (status)`
- idx_quiz_sessions_template_status_v2: `CREATE INDEX idx_quiz_sessions_template_status_v2 ON public.quiz_sessions USING btree (quiz_template_id, status)`
- quiz_sessions_pkey: `CREATE UNIQUE INDEX quiz_sessions_pkey ON public.quiz_sessions USING btree (id)`

#### Triggers
- update_quiz_sessions_updated_at (BEFORE UPDATE)

### Tabela `public.quiz_sessions_v2`

- Tamanho: tabela 8.0 KB | índices 24.0 KB | total 32.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| patient_id | uuid | NO |  |
| template_version_id | uuid | NO |  |
| status | character varying | YES | 'started'::character varying |
| started_at | timestamp with time zone | YES | now() |
| completed_at | timestamp with time zone | YES |  |
| session_data | jsonb | YES | '{}'::jsonb |
| created_at | timestamp with time zone | YES | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- template_version_id → public.quiz_template_versions_v2.id
- patient_id → public.patients.id

#### Índices
- idx_quiz_sessions_v2_patient: `CREATE INDEX idx_quiz_sessions_v2_patient ON public.quiz_sessions_v2 USING btree (patient_id)`
- idx_quiz_sessions_v2_template_version: `CREATE INDEX idx_quiz_sessions_v2_template_version ON public.quiz_sessions_v2 USING btree (template_version_id)`
- quiz_sessions_v2_pkey: `CREATE UNIQUE INDEX quiz_sessions_v2_pkey ON public.quiz_sessions_v2 USING btree (id)`

#### Triggers
- (sem triggers)

### Tabela `public.quiz_template_versions_v2`

- Tamanho: tabela 8.0 KB | índices 32.0 KB | total 40.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| template_id | uuid | NO |  |
| version_number | integer | NO |  |
| questions | jsonb | NO |  |
| scoring_rules | jsonb | YES |  |
| is_active | boolean | YES | false |
| is_draft | boolean | YES | true |
| published_at | timestamp with time zone | YES |  |
| created_by | uuid | YES |  |
| change_notes | text | YES |  |
| created_at | timestamp with time zone | YES | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- template_id → public.quiz_templates.id
- created_by → public.users.id

#### Índices
- idx_quiz_template_versions_v2_active: `CREATE INDEX idx_quiz_template_versions_v2_active ON public.quiz_template_versions_v2 USING btree (template_id, is_active) WHERE (is_active = true)`
- idx_quiz_template_versions_v2_template: `CREATE INDEX idx_quiz_template_versions_v2_template ON public.quiz_template_versions_v2 USING btree (template_id)`
- quiz_template_versions_v2_pkey: `CREATE UNIQUE INDEX quiz_template_versions_v2_pkey ON public.quiz_template_versions_v2 USING btree (id)`
- unique_template_version: `CREATE UNIQUE INDEX unique_template_version ON public.quiz_template_versions_v2 USING btree (template_id, version_number)`

#### Triggers
- (sem triggers)

### Tabela `public.quiz_templates`

- Tamanho: tabela 32.0 KB | índices 48.0 KB | total 80.0 KB
- Linhas (aprox): 2

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| name | character varying | NO |  |
| version | character varying | NO |  |
| description | text | YES |  |
| questions | jsonb | NO |  |
| is_active | boolean | NO | true |
| category | character varying | YES |  |
| tags | ARRAY | YES |  |
| passing_score | integer | YES |  |
| time_limit_minutes | integer | YES |  |
| randomize_questions | boolean | YES | false |
| created_at | timestamp with time zone | NO | now() |
| updated_at | timestamp with time zone | NO | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- (sem FKs)

#### Índices
- idx_quiz_templates_category: `CREATE INDEX idx_quiz_templates_category ON public.quiz_templates USING btree (category)`
- idx_quiz_templates_is_active: `CREATE INDEX idx_quiz_templates_is_active ON public.quiz_templates USING btree (is_active)`
- quiz_templates_pkey: `CREATE UNIQUE INDEX quiz_templates_pkey ON public.quiz_templates USING btree (id)`

#### Triggers
- update_quiz_templates_updated_at (BEFORE UPDATE)

### Tabela `public.security_audit_log`

- Tamanho: tabela 8.0 KB | índices 112.0 KB | total 120.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| event_type | character varying | NO |  |
| phone_number | character varying | NO |  |
| patient_id | uuid | YES |  |
| message_content | text | YES |  |
| source_metadata | jsonb | YES |  |
| risk_score | integer | NO | 0 |
| ip_address | character varying | YES |  |
| user_agent | character varying | YES |  |
| session_id | character varying | YES |  |
| created_at | timestamp with time zone | NO | CURRENT_TIMESTAMP |
| additional_data | jsonb | YES |  |
| alert_sent | boolean | NO | false |

#### Chave Primária
- id

#### Chaves Estrangeiras
- patient_id → public.patients.id

#### Índices
- idx_security_audit_additional_data_gin: `CREATE INDEX idx_security_audit_additional_data_gin ON public.security_audit_log USING gin (additional_data)`
- idx_security_audit_created_at: `CREATE INDEX idx_security_audit_created_at ON public.security_audit_log USING btree (created_at)`
- idx_security_audit_event_type: `CREATE INDEX idx_security_audit_event_type ON public.security_audit_log USING btree (event_type)`
- idx_security_audit_ip_address: `CREATE INDEX idx_security_audit_ip_address ON public.security_audit_log USING btree (ip_address)`
- idx_security_audit_patient_id: `CREATE INDEX idx_security_audit_patient_id ON public.security_audit_log USING btree (patient_id)`
- idx_security_audit_phone_event_time: `CREATE INDEX idx_security_audit_phone_event_time ON public.security_audit_log USING btree (phone_number, event_type, created_at)`
- idx_security_audit_phone_number: `CREATE INDEX idx_security_audit_phone_number ON public.security_audit_log USING btree (phone_number)`
- idx_security_audit_risk_score: `CREATE INDEX idx_security_audit_risk_score ON public.security_audit_log USING btree (risk_score)`
- idx_security_audit_risk_time: `CREATE INDEX idx_security_audit_risk_time ON public.security_audit_log USING btree (risk_score, created_at)`
- idx_security_audit_session_id: `CREATE INDEX idx_security_audit_session_id ON public.security_audit_log USING btree (session_id)`
- idx_security_audit_source_metadata_gin: `CREATE INDEX idx_security_audit_source_metadata_gin ON public.security_audit_log USING gin (source_metadata)`
- security_audit_log_pkey: `CREATE UNIQUE INDEX security_audit_log_pkey ON public.security_audit_log USING btree (id)`

#### Triggers
- (sem triggers)

### Tabela `public.user_profiles`

- Tamanho: tabela 8.0 KB | índices 24.0 KB | total 32.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| user_id | uuid | NO |  |
| bio | text | YES |  |
| avatar_url | character varying | YES |  |
| phone | character varying | YES |  |
| specialty | character varying | YES |  |
| license_number | character varying | YES |  |
| years_of_experience | integer | YES |  |
| preferences | jsonb | YES | '{}'::jsonb |
| notification_settings | jsonb | YES | '{}'::jsonb |
| created_at | timestamp with time zone | YES | now() |
| updated_at | timestamp with time zone | YES | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- user_id → public.users.id

#### Índices
- idx_user_profiles_user_id: `CREATE INDEX idx_user_profiles_user_id ON public.user_profiles USING btree (user_id)`
- user_profiles_pkey: `CREATE UNIQUE INDEX user_profiles_pkey ON public.user_profiles USING btree (id)`
- user_profiles_user_id_key: `CREATE UNIQUE INDEX user_profiles_user_id_key ON public.user_profiles USING btree (user_id)`

#### Triggers
- (sem triggers)

### Tabela `public.user_sync_log`

- Tamanho: tabela 8.0 KB | índices 40.0 KB | total 48.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| firebase_uid | character varying | NO |  |
| supabase_user_id | uuid | YES |  |
| sync_action | character varying | NO |  |
| sync_status | character varying | NO |  |
| firebase_data | jsonb | YES |  |
| supabase_data | jsonb | YES |  |
| error_message | text | YES |  |
| retry_count | integer | YES | 0 |
| synced_at | timestamp with time zone | YES | now() |
| created_at | timestamp with time zone | YES | now() |
| updated_at | timestamp with time zone | NO | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- supabase_user_id → public.users.id

#### Índices
- idx_user_sync_log_firebase_uid: `CREATE INDEX idx_user_sync_log_firebase_uid ON public.user_sync_log USING btree (firebase_uid)`
- idx_user_sync_log_status: `CREATE INDEX idx_user_sync_log_status ON public.user_sync_log USING btree (sync_status, synced_at)`
- idx_user_sync_log_supabase_user: `CREATE INDEX idx_user_sync_log_supabase_user ON public.user_sync_log USING btree (supabase_user_id)`
- idx_user_sync_log_updated_at: `CREATE INDEX idx_user_sync_log_updated_at ON public.user_sync_log USING btree (updated_at)`
- user_sync_log_pkey: `CREATE UNIQUE INDEX user_sync_log_pkey ON public.user_sync_log USING btree (id)`

#### Triggers
- trigger_user_sync_log_updated_at (BEFORE UPDATE)

### Tabela `public.users`

- Tamanho: tabela 16.0 KB | índices 144.0 KB | total 160.0 KB
- Linhas (aprox): 2

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| email | character varying | NO |  |
| hashed_password | character varying | YES |  |
| full_name | character varying | YES |  |
| role | USER-DEFINED | NO | 'doctor'::user_role |
| is_active | boolean | NO | true |
| firebase_uid | character varying | YES |  |
| auth_provider | USER-DEFINED | NO | 'local'::auth_provider |
| firebase_last_sign_in | timestamp with time zone | YES |  |
| firebase_created_at | timestamp with time zone | YES |  |
| firebase_email_verified | boolean | NO | false |
| firebase_display_name | character varying | YES |  |
| firebase_photo_url | character varying | YES |  |
| firebase_custom_claims | jsonb | NO | '{}'::jsonb |
| last_firebase_sync | timestamp with time zone | YES |  |
| created_at | timestamp with time zone | NO | now() |
| updated_at | timestamp with time zone | NO | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- (sem FKs)

#### Índices
- idx_users_auth_provider: `CREATE INDEX idx_users_auth_provider ON public.users USING btree (auth_provider)`
- idx_users_email: `CREATE INDEX idx_users_email ON public.users USING btree (email)`
- idx_users_firebase_uid: `CREATE INDEX idx_users_firebase_uid ON public.users USING btree (firebase_uid) WHERE (firebase_uid IS NOT NULL)`
- idx_users_firebase_uid_active_new: `CREATE INDEX idx_users_firebase_uid_active_new ON public.users USING btree (firebase_uid) WHERE (is_active = true)`
- idx_users_is_active: `CREATE INDEX idx_users_is_active ON public.users USING btree (is_active)`
- idx_users_role: `CREATE INDEX idx_users_role ON public.users USING btree (role)`
- users_email_key: `CREATE UNIQUE INDEX users_email_key ON public.users USING btree (email)`
- users_firebase_uid_key: `CREATE UNIQUE INDEX users_firebase_uid_key ON public.users USING btree (firebase_uid)`
- users_pkey: `CREATE UNIQUE INDEX users_pkey ON public.users USING btree (id)`

#### Triggers
- update_users_updated_at (BEFORE UPDATE)

### Tabela `public.webhook_events`

- Tamanho: tabela 8.0 KB | índices 64.0 KB | total 72.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| event_type | character varying | NO |  |
| source | character varying | NO | 'evolution_api'::character varying |
| payload | jsonb | NO |  |
| processed | boolean | NO | false |
| processed_at | timestamp with time zone | YES |  |
| retry_count | integer | YES | 0 |
| max_retries | integer | YES | 3 |
| next_retry_at | timestamp with time zone | YES |  |
| error_message | text | YES |  |
| error_stack_trace | text | YES |  |
| related_message_id | uuid | YES |  |
| related_patient_id | uuid | YES |  |
| event_hash | character varying | NO |  |
| is_duplicate | boolean | YES | false |
| original_event_id | uuid | YES |  |
| created_at | timestamp with time zone | NO | now() |

#### Chave Primária
- id

#### Chaves Estrangeiras
- (sem FKs)

#### Índices
- idx_webhook_pending: `CREATE INDEX idx_webhook_pending ON public.webhook_events USING btree (processed, retry_count, created_at) WHERE (NOT processed)`
- idx_webhook_related_msg: `CREATE INDEX idx_webhook_related_msg ON public.webhook_events USING btree (related_message_id, event_type)`
- idx_webhook_related_patient: `CREATE INDEX idx_webhook_related_patient ON public.webhook_events USING btree (related_patient_id, event_type)`
- idx_webhook_retry_schedule: `CREATE INDEX idx_webhook_retry_schedule ON public.webhook_events USING btree (processed, next_retry_at) WHERE ((NOT processed) AND (retry_count < max_retries))`
- idx_webhook_source_time: `CREATE INDEX idx_webhook_source_time ON public.webhook_events USING btree (source, created_at)`
- idx_webhook_type_processed: `CREATE INDEX idx_webhook_type_processed ON public.webhook_events USING btree (event_type, processed, created_at)`
- webhook_events_event_hash_key: `CREATE UNIQUE INDEX webhook_events_event_hash_key ON public.webhook_events USING btree (event_hash)`
- webhook_events_pkey: `CREATE UNIQUE INDEX webhook_events_pkey ON public.webhook_events USING btree (id)`

#### Triggers
- (sem triggers)

### Tabela `public.whatsapp_contacts`

- Tamanho: tabela 8.0 KB | índices 24.0 KB | total 32.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | text | NO |  |
| instance_name | text | NO |  |
| phone_number | text | NO |  |
| formatted_number | text | NO |  |
| name | text | YES |  |
| profile_picture_url | text | YES |  |
| is_whatsapp_user | boolean | YES | true |
| last_seen | timestamp without time zone | YES |  |
| created_at | timestamp without time zone | YES | now() |
| updated_at | timestamp without time zone | YES | now() |
| contact_data | json | YES |  |

#### Chave Primária
- id

#### Chaves Estrangeiras
- (sem FKs)

#### Índices
- ix_whatsapp_contacts_instance: `CREATE INDEX ix_whatsapp_contacts_instance ON public.whatsapp_contacts USING btree (instance_name)`
- ix_whatsapp_contacts_phone: `CREATE INDEX ix_whatsapp_contacts_phone ON public.whatsapp_contacts USING btree (phone_number)`
- whatsapp_contacts_pkey: `CREATE UNIQUE INDEX whatsapp_contacts_pkey ON public.whatsapp_contacts USING btree (id)`

#### Triggers
- (sem triggers)

### Tabela `public.whatsapp_delivery_failures`

- Tamanho: tabela 8.0 KB | índices 32.0 KB | total 40.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | uuid | NO | gen_random_uuid() |
| patient_id | uuid | NO |  |
| phone_number | character varying | NO |  |
| message_type | character varying | NO |  |
| message_content | text | YES |  |
| error_message | text | NO |  |
| error_code | character varying | YES |  |
| retry_count | integer | NO | 0 |
| max_retries | integer | NO | 3 |
| next_retry_at | timestamp with time zone | YES |  |
| last_retry_at | timestamp with time zone | YES |  |
| status | character varying | NO | 'pending'::character varying |
| resolved_at | timestamp with time zone | YES |  |
| dlq_metadata | jsonb | YES | '{}'::jsonb |
| reviewed_by | uuid | YES |  |
| original_message_id | uuid | YES |  |
| created_at | timestamp with time zone | NO | timezone('utc'::text, now()) |
| updated_at | timestamp with time zone | NO | timezone('utc'::text, now()) |

#### Chave Primária
- id

#### Chaves Estrangeiras
- reviewed_by → public.users.id
- original_message_id → public.messages.id
- patient_id → public.patients.id

#### Índices
- idx_whatsapp_delivery_failures_created_at: `CREATE INDEX idx_whatsapp_delivery_failures_created_at ON public.whatsapp_delivery_failures USING btree (created_at DESC)`
- idx_whatsapp_delivery_failures_patient: `CREATE INDEX idx_whatsapp_delivery_failures_patient ON public.whatsapp_delivery_failures USING btree (patient_id)`
- idx_whatsapp_delivery_failures_status_nextretry: `CREATE INDEX idx_whatsapp_delivery_failures_status_nextretry ON public.whatsapp_delivery_failures USING btree (status, next_retry_at)`
- whatsapp_delivery_failures_pkey: `CREATE UNIQUE INDEX whatsapp_delivery_failures_pkey ON public.whatsapp_delivery_failures USING btree (id)`

#### Triggers
- trg_whatsapp_delivery_failures_updated_at (BEFORE UPDATE)

### Tabela `public.whatsapp_instances`

- Tamanho: tabela 16.0 KB | índices 48.0 KB | total 64.0 KB
- Linhas (aprox): 1

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | text | NO |  |
| name | text | NO |  |
| status | text | YES | 'disconnected'::text |
| qr_code | text | YES |  |
| webhook_url | text | YES |  |
| phone_number | text | YES |  |
| profile_name | text | YES |  |
| profile_picture_url | text | YES |  |
| is_connected | boolean | YES | false |
| created_at | timestamp without time zone | YES | now() |
| updated_at | timestamp without time zone | YES | now() |
| last_activity | timestamp without time zone | YES |  |
| settings | json | YES |  |

#### Chave Primária
- id

#### Chaves Estrangeiras
- (sem FKs)

#### Índices
- ix_whatsapp_instances_name: `CREATE INDEX ix_whatsapp_instances_name ON public.whatsapp_instances USING btree (name)`
- whatsapp_instances_name_key: `CREATE UNIQUE INDEX whatsapp_instances_name_key ON public.whatsapp_instances USING btree (name)`
- whatsapp_instances_pkey: `CREATE UNIQUE INDEX whatsapp_instances_pkey ON public.whatsapp_instances USING btree (id)`

#### Triggers
- (sem triggers)

### Tabela `public.whatsapp_messages`

- Tamanho: tabela 8.0 KB | índices 40.0 KB | total 48.0 KB
- Linhas (aprox): 0

#### Colunas
| Coluna | Tipo | Nulo | Default |
|--------|------|------|---------|
| id | text | NO |  |
| instance_name | text | NO |  |
| chat_id | text | NO |  |
| sender_id | text | NO |  |
| recipient_id | text | NO |  |
| message_type | text | NO |  |
| content | text | YES |  |
| media_url | text | YES |  |
| media_caption | text | YES |  |
| status | text | YES | 'pending'::text |
| external_id | text | YES |  |
| created_at | timestamp without time zone | YES | now() |
| updated_at | timestamp without time zone | YES | now() |
| sent_at | timestamp without time zone | YES |  |
| delivered_at | timestamp without time zone | YES |  |
| read_at | timestamp without time zone | YES |  |
| failed_at | timestamp without time zone | YES |  |
| retry_count | integer | YES | 0 |
| error_message | text | YES |  |
| message_data | json | YES |  |

#### Chave Primária
- id

#### Chaves Estrangeiras
- (sem FKs)

#### Índices
- ix_whatsapp_messages_chat: `CREATE INDEX ix_whatsapp_messages_chat ON public.whatsapp_messages USING btree (chat_id)`
- ix_whatsapp_messages_external: `CREATE INDEX ix_whatsapp_messages_external ON public.whatsapp_messages USING btree (external_id)`
- ix_whatsapp_messages_instance: `CREATE INDEX ix_whatsapp_messages_instance ON public.whatsapp_messages USING btree (instance_name)`
- whatsapp_messages_external_id_key: `CREATE UNIQUE INDEX whatsapp_messages_external_id_key ON public.whatsapp_messages USING btree (external_id)`
- whatsapp_messages_pkey: `CREATE UNIQUE INDEX whatsapp_messages_pkey ON public.whatsapp_messages USING btree (id)`

#### Triggers
- (sem triggers)
