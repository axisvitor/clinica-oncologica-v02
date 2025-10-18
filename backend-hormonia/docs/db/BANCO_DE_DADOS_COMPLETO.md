# 📊 Documentação Completa do Banco de Dados - Clínica Oncológica Hormonia

**Data de Extração:** 2025-10-15
**Banco de Dados:** postgres
**Versão PostgreSQL:** PostgreSQL 17.4 on aarch64-unknown-linux-gnu
**Usuário:** neoplasias
**Schema:** public
**Servidor:** 172.31.47.65:5432

> 🤖 **Documentação gerada automaticamente** a partir do script `extract_database_complete.py`

---

## 📑 Índice

1. [Resumo Executivo](#resumo-executivo)
2. [Extensões PostgreSQL](#extensões-postgresql)
3. [Enums](#enums)
4. [Tabelas](#tabelas)
5. [Views](#views)
6. [Materialized Views](#materialized-views)
7. [Funções](#funções)
8. [Sequences](#sequences)

---

## 📊 Resumo Executivo

| Métrica | Valor |
|---------|-------|
| **Total de Tabelas** | 47 |
| **Total de Índices** | 244 |
| **Total de Constraints** | 342 |
| **Políticas RLS** | 0 |
| **Funções** | 259 |
| **Triggers** | 14 |
| **Views** | 2 |
| **Materialized Views** | 5 |
| **Enums** | 12 |
| **Extensões** | 6 |
| **Sequences** | 0 |

### 📈 Top 10 Tabelas com Mais Registros

| # | Tabela | Registros |
|---|--------|-----------|
| 1 | public.audit_logs | 44 |
| 2 | public.flow_template_versions | 7 |
| 3 | public.flow_kinds | 4 |
| 4 | public.error_logs | 3 |
| 5 | public.alembic_version | 1 |
| 6 | public.patients | 1 |
| 7 | public.quiz_templates | 1 |
| 8 | public.users | 1 |
| 9 | public.whatsapp_instances | 1 |

### 💾 Top 10 Tabelas Maiores

| # | Tabela | Tamanho |
|---|--------|---------|
| 1 | public.messages | 272 kB |
| 2 | public.error_logs | 224 kB |
| 3 | public.patients | 200 kB |
| 4 | public.audit_logs | 192 kB |
| 5 | public.flow_template_versions | 192 kB |
| 6 | public.quiz_sessions | 184 kB |
| 7 | public.users | 160 kB |
| 8 | public.security_audit_log | 120 kB |
| 9 | public.patient_flow_states | 104 kB |
| 10 | public.flow_kinds | 80 kB |

---

## 🔌 Extensões PostgreSQL

| Extensão | Versão | Schema | Relocatable |
|----------|--------|--------|-------------|
| btree_gist | 1.7 | public | ✓ |
| pg_stat_statements | 1.11 | public | ✓ |
| pg_trgm | 1.6 | public | ✓ |
| pgcrypto | 1.3 | public | ✓ |
| plpgsql | 1.0 | pg_catalog | ✗ |
| uuid-ossp | 1.1 | public | ✓ |

---

## 🏷️ Enums

### admin_role_type

**Valores:**

- `super_admin`
- `admin`
- `manager`
- `supervisor`

### alert_severity

**Valores:**

- `low`
- `medium`
- `high`
- `critical`

### auth_provider

**Valores:**

- `local`
- `firebase`
- `google`
- `apple`

### deliverystatus

**Valores:**

- `scheduled`
- `queued`
- `sending`
- `sent`
- `delivered`
- `read`
- `failed`
- `cancelled`

### flow_state

**Valores:**

- `onboarding`
- `active`
- `paused`
- `completed`
- `inactive`
- `cancelled`

### http_method_type

**Valores:**

- `GET`
- `POST`
- `PUT`
- `PATCH`
- `DELETE`
- `OPTIONS`
- `HEAD`

### message_direction

**Valores:**

- `inbound`
- `outbound`

### message_status

**Valores:**

- `pending`
- `sent`
- `delivered`
- `read`
- `failed`
- `scheduled`
- `sending`

### message_type

**Valores:**

- `text`
- `button`
- `list`
- `media`
- `location`
- `quiz_intro`
- `quiz_question`
- `quiz_encouragement`
- `quiz_completion`
- `monthly_quiz_link`
- `monthly_quiz_reminder`
- `monthly_quiz_expired`
- `monthly_quiz_completed`

### messagestatus

**Valores:**

- `pending`
- `scheduled`
- `sending`
- `sent`
- `failed`
- `delivered`
- `read`

### severity_type

**Valores:**

- `low`
- `medium`
- `high`
- `critical`

### user_role

**Valores:**

- `doctor`
- `admin`

---

## 📋 Tabelas

Total de tabelas: **47**

## Grupo: ADMIN (10 tabelas)

### admin_audit_log

**Descrição:** Log de auditoria de ações administrativas

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 64 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| admin_user_id | uuid | ✓ | - | - |
| session_id | uuid | ✓ | - | - |
| event_type | character varying(100) | ✗ | - | - |
| event_category | character varying(50) | ✗ | - | - |
| action | character varying(255) | ✗ | - | - |
| resource_type | character varying(100) | ✓ | - | - |
| resource_id | character varying(255) | ✓ | - | - |
| ip_address | inet | ✓ | - | - |
| user_agent | text | ✓ | - | - |
| endpoint | character varying(500) | ✓ | - | - |
| http_method | USER-DEFINED | ✓ | - | - |
| details | jsonb | ✓ | '{}'::jsonb | - |
| changes | jsonb | ✓ | - | - |
| success | boolean | ✓ | true | - |
| error_message | text | ✓ | - | - |
| timestamp | timestamp with time zone | ✓ | CURRENT_TIMESTAMP | - |
| duration_ms | integer(32) | ✓ | - | - |
| severity | USER-DEFINED | ✓ | 'low'::severity_type | - |

#### Índices

- **admin_audit_log_pkey**
  ```sql
  CREATE UNIQUE INDEX admin_audit_log_pkey ON public.admin_audit_log USING btree (id)
  ```
- **idx_admin_audit_event_type**
  ```sql
  CREATE INDEX idx_admin_audit_event_type ON public.admin_audit_log USING btree (event_type)
  ```
- **idx_admin_audit_ip**
  ```sql
  CREATE INDEX idx_admin_audit_ip ON public.admin_audit_log USING btree (ip_address)
  ```
- **idx_admin_audit_resource**
  ```sql
  CREATE INDEX idx_admin_audit_resource ON public.admin_audit_log USING btree (resource_type, resource_id)
  ```
- **idx_admin_audit_severity**
  ```sql
  CREATE INDEX idx_admin_audit_severity ON public.admin_audit_log USING btree (severity)
  ```
- **idx_admin_audit_timestamp**
  ```sql
  CREATE INDEX idx_admin_audit_timestamp ON public.admin_audit_log USING btree ("timestamp")
  ```
- **idx_admin_audit_user_id**
  ```sql
  CREATE INDEX idx_admin_audit_user_id ON public.admin_audit_log USING btree (admin_user_id)
  ```

#### Constraints

- **2200_20230_1_not_null** (CHECK)
- **2200_20230_4_not_null** (CHECK)
- **2200_20230_5_not_null** (CHECK)
- **2200_20230_6_not_null** (CHECK)
- **admin_audit_log_admin_user_id_fkey** (FK): admin_user_id → admin_users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **admin_audit_log_pkey** (PK): id
- **admin_audit_log_session_id_fkey** (FK): session_id → admin_sessions.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION

---

### admin_ip_blacklist

**Descrição:** IPs bloqueados para acesso admin

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 32 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| ip_address | inet | ✗ | - | - |
| reason | character varying(255) | ✗ | - | - |
| blocked_at | timestamp with time zone | ✓ | CURRENT_TIMESTAMP | - |
| blocked_by | uuid | ✓ | - | - |
| expires_at | timestamp with time zone | ✓ | - | - |
| is_permanent | boolean | ✓ | false | - |
| incident_id | uuid | ✓ | - | - |
| threat_level | USER-DEFINED | ✓ | 'medium'::severity_type | - |
| block_count | integer(32) | ✓ | 1 | - |
| details | jsonb | ✓ | '{}'::jsonb | - |
| notes | text | ✓ | - | - |

#### Índices

- **admin_ip_blacklist_ip_address_key**
  ```sql
  CREATE UNIQUE INDEX admin_ip_blacklist_ip_address_key ON public.admin_ip_blacklist USING btree (ip_address)
  ```
- **admin_ip_blacklist_pkey**
  ```sql
  CREATE UNIQUE INDEX admin_ip_blacklist_pkey ON public.admin_ip_blacklist USING btree (id)
  ```
- **idx_ip_blacklist_active**
  ```sql
  CREATE INDEX idx_ip_blacklist_active ON public.admin_ip_blacklist USING btree (ip_address, expires_at)
  ```

#### Constraints

- **2200_20309_1_not_null** (CHECK)
- **2200_20309_2_not_null** (CHECK)
- **2200_20309_3_not_null** (CHECK)
- **admin_ip_blacklist_blocked_by_fkey** (FK): blocked_by → admin_users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **admin_ip_blacklist_ip_address_key** (UNIQUE): ip_address
- **admin_ip_blacklist_pkey** (PK): id

---

### admin_ip_whitelist

**Descrição:** IPs permitidos para acesso admin

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 40 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| ip_address | inet | ✓ | - | - |
| ip_range | cidr | ✓ | - | - |
| description | text | ✓ | - | - |
| added_by | uuid | ✓ | - | - |
| added_at | timestamp with time zone | ✓ | CURRENT_TIMESTAMP | - |
| is_active | boolean | ✓ | true | - |
| expires_at | timestamp with time zone | ✓ | - | - |
| last_used_at | timestamp with time zone | ✓ | - | - |
| usage_count | integer(32) | ✓ | 0 | - |

#### Índices

- **admin_ip_whitelist_pkey**
  ```sql
  CREATE UNIQUE INDEX admin_ip_whitelist_pkey ON public.admin_ip_whitelist USING btree (id)
  ```
- **idx_ip_whitelist_active**
  ```sql
  CREATE INDEX idx_ip_whitelist_active ON public.admin_ip_whitelist USING btree (is_active, ip_address)
  ```
- **idx_ip_whitelist_range**
  ```sql
  CREATE INDEX idx_ip_whitelist_range ON public.admin_ip_whitelist USING gist (ip_range)
  ```
- **unique_ip_or_range**
  ```sql
  CREATE UNIQUE INDEX unique_ip_or_range ON public.admin_ip_whitelist USING btree (ip_address, ip_range)
  ```

#### Constraints

- **2200_20288_1_not_null** (CHECK)
- **admin_ip_whitelist_added_by_fkey** (FK): added_by → admin_users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **admin_ip_whitelist_pkey** (PK): id
- **ip_or_range_required** (CHECK)
- **ip_or_range_required** (CHECK)
- **unique_ip_or_range** (UNIQUE): ip_address, ip_address, ip_range, ip_range
- **unique_ip_or_range** (UNIQUE): ip_address, ip_address, ip_range, ip_range
- **unique_ip_or_range** (UNIQUE): ip_address, ip_address, ip_range, ip_range
- **unique_ip_or_range** (UNIQUE): ip_address, ip_address, ip_range, ip_range

---

### admin_permissions

**Descrição:** Permissões disponíveis no sistema

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 32 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| name | character varying(100) | ✗ | - | - |
| description | text | ✓ | - | - |
| category | character varying(50) | ✗ | - | - |
| created_at | timestamp with time zone | ✓ | CURRENT_TIMESTAMP | - |

#### Índices

- **admin_permissions_name_key**
  ```sql
  CREATE UNIQUE INDEX admin_permissions_name_key ON public.admin_permissions USING btree (name)
  ```
- **admin_permissions_pkey**
  ```sql
  CREATE UNIQUE INDEX admin_permissions_pkey ON public.admin_permissions USING btree (id)
  ```
- **idx_admin_permissions_category**
  ```sql
  CREATE INDEX idx_admin_permissions_category ON public.admin_permissions USING btree (category)
  ```

#### Constraints

- **2200_20137_1_not_null** (CHECK)
- **2200_20137_2_not_null** (CHECK)
- **2200_20137_4_not_null** (CHECK)
- **admin_permissions_name_key** (UNIQUE): name
- **admin_permissions_pkey** (PK): id
- **valid_permission_name** (CHECK)

---

### admin_role_permissions

**Descrição:** Permissões associadas a roles

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 16 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| role_id | uuid | ✗ | - | - |
| permission_id | uuid | ✗ | - | - |
| created_at | timestamp with time zone | ✓ | CURRENT_TIMESTAMP | - |

#### Índices

- **admin_role_permissions_pkey**
  ```sql
  CREATE UNIQUE INDEX admin_role_permissions_pkey ON public.admin_role_permissions USING btree (role_id, permission_id)
  ```
- **idx_admin_role_permissions_role**
  ```sql
  CREATE INDEX idx_admin_role_permissions_role ON public.admin_role_permissions USING btree (role_id)
  ```

#### Constraints

- **2200_20186_1_not_null** (CHECK)
- **2200_20186_2_not_null** (CHECK)
- **admin_role_permissions_permission_id_fkey** (FK): permission_id → admin_permissions.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **admin_role_permissions_pkey** (PK): role_id, role_id, permission_id, permission_id
- **admin_role_permissions_pkey** (PK): role_id, role_id, permission_id, permission_id
- **admin_role_permissions_pkey** (PK): role_id, role_id, permission_id, permission_id
- **admin_role_permissions_pkey** (PK): role_id, role_id, permission_id, permission_id
- **admin_role_permissions_role_id_fkey** (FK): role_id → admin_roles.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION

---

### admin_roles

**Descrição:** Roles do sistema admin

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 24 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| name | character varying(50) | ✗ | - | - |
| description | text | ✓ | - | - |
| is_system_role | boolean | ✓ | false | - |
| created_at | timestamp with time zone | ✓ | CURRENT_TIMESTAMP | - |
| updated_at | timestamp with time zone | ✓ | CURRENT_TIMESTAMP | - |

#### Índices

- **admin_roles_name_key**
  ```sql
  CREATE UNIQUE INDEX admin_roles_name_key ON public.admin_roles USING btree (name)
  ```
- **admin_roles_pkey**
  ```sql
  CREATE UNIQUE INDEX admin_roles_pkey ON public.admin_roles USING btree (id)
  ```

#### Constraints

- **2200_20150_1_not_null** (CHECK)
- **2200_20150_2_not_null** (CHECK)
- **admin_roles_name_key** (UNIQUE): name
- **admin_roles_pkey** (PK): id
- **valid_role_name** (CHECK)

#### Triggers

- **update_admin_roles_updated_at**
  - Timing: BEFORE
  - Event: UPDATE
  - Statement: `EXECUTE FUNCTION update_updated_at_column()...`

---

### admin_security_events

**Descrição:** Eventos de segurança detectados no sistema admin

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 56 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| event_type | character varying(100) | ✗ | - | - |
| severity | USER-DEFINED | ✗ | 'medium'::severity_type | - |
| ip_address | inet | ✓ | - | - |
| user_agent | text | ✓ | - | - |
| admin_user_id | uuid | ✓ | - | - |
| session_id | uuid | ✓ | - | - |
| description | text | ✓ | - | - |
| details | jsonb | ✓ | '{}'::jsonb | - |
| endpoint | character varying(500) | ✓ | - | - |
| detected_at | timestamp with time zone | ✓ | CURRENT_TIMESTAMP | - |
| resolved_at | timestamp with time zone | ✓ | - | - |
| resolution_notes | text | ✓ | - | - |
| auto_resolved | boolean | ✓ | false | - |
| risk_score | integer(32) | ✓ | 0 | - |
| threat_level | USER-DEFINED | ✓ | 'low'::severity_type | - |

#### Índices

- **admin_security_events_pkey**
  ```sql
  CREATE UNIQUE INDEX admin_security_events_pkey ON public.admin_security_events USING btree (id)
  ```
- **idx_security_events_ip**
  ```sql
  CREATE INDEX idx_security_events_ip ON public.admin_security_events USING btree (ip_address)
  ```
- **idx_security_events_resolved**
  ```sql
  CREATE INDEX idx_security_events_resolved ON public.admin_security_events USING btree (resolved_at) WHERE (resolved_at IS NOT NULL)
  ```
- **idx_security_events_severity**
  ```sql
  CREATE INDEX idx_security_events_severity ON public.admin_security_events USING btree (severity)
  ```
- **idx_security_events_timestamp**
  ```sql
  CREATE INDEX idx_security_events_timestamp ON public.admin_security_events USING btree (detected_at)
  ```
- **idx_security_events_user_id**
  ```sql
  CREATE INDEX idx_security_events_user_id ON public.admin_security_events USING btree (admin_user_id)
  ```

#### Constraints

- **2200_20258_1_not_null** (CHECK)
- **2200_20258_2_not_null** (CHECK)
- **2200_20258_3_not_null** (CHECK)
- **admin_security_events_admin_user_id_fkey** (FK): admin_user_id → admin_users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **admin_security_events_pkey** (PK): id
- **admin_security_events_session_id_fkey** (FK): session_id → admin_sessions.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **valid_risk_score** (CHECK)

---

### admin_sessions

**Descrição:** Sessões ativas de administradores

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 72 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| admin_user_id | uuid | ✗ | - | - |
| session_token | character varying(255) | ✗ | - | - |
| refresh_token | character varying(255) | ✓ | - | - |
| ip_address | inet | ✓ | - | - |
| user_agent | text | ✓ | - | - |
| device_fingerprint | character varying(255) | ✓ | - | - |
| created_at | timestamp with time zone | ✓ | CURRENT_TIMESTAMP | - |
| last_activity | timestamp with time zone | ✓ | CURRENT_TIMESTAMP | - |
| expires_at | timestamp with time zone | ✗ | - | - |
| is_active | boolean | ✓ | true | - |
| logout_reason | character varying(100) | ✓ | - | - |
| metadata | jsonb | ✓ | '{}'::jsonb | - |

#### Índices

- **admin_sessions_pkey**
  ```sql
  CREATE UNIQUE INDEX admin_sessions_pkey ON public.admin_sessions USING btree (id)
  ```
- **admin_sessions_refresh_token_key**
  ```sql
  CREATE UNIQUE INDEX admin_sessions_refresh_token_key ON public.admin_sessions USING btree (refresh_token)
  ```
- **admin_sessions_session_token_key**
  ```sql
  CREATE UNIQUE INDEX admin_sessions_session_token_key ON public.admin_sessions USING btree (session_token)
  ```
- **idx_admin_sessions_active**
  ```sql
  CREATE INDEX idx_admin_sessions_active ON public.admin_sessions USING btree (is_active, last_activity)
  ```
- **idx_admin_sessions_expires**
  ```sql
  CREATE INDEX idx_admin_sessions_expires ON public.admin_sessions USING btree (expires_at)
  ```
- **idx_admin_sessions_ip**
  ```sql
  CREATE INDEX idx_admin_sessions_ip ON public.admin_sessions USING btree (ip_address)
  ```
- **idx_admin_sessions_token**
  ```sql
  CREATE INDEX idx_admin_sessions_token ON public.admin_sessions USING btree (session_token)
  ```
- **idx_admin_sessions_user_id**
  ```sql
  CREATE INDEX idx_admin_sessions_user_id ON public.admin_sessions USING btree (admin_user_id)
  ```

#### Constraints

- **2200_20203_10_not_null** (CHECK)
- **2200_20203_1_not_null** (CHECK)
- **2200_20203_2_not_null** (CHECK)
- **2200_20203_3_not_null** (CHECK)
- **admin_sessions_admin_user_id_fkey** (FK): admin_user_id → admin_users.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **admin_sessions_pkey** (PK): id
- **admin_sessions_refresh_token_key** (UNIQUE): refresh_token
- **admin_sessions_session_token_key** (UNIQUE): session_token
- **valid_session_duration** (CHECK)
- **valid_session_duration** (CHECK)

---

### admin_user_permissions

**Descrição:** Permissões diretas de usuários admin

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 16 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| admin_user_id | uuid | ✗ | - | - |
| permission_id | uuid | ✗ | - | - |
| granted_at | timestamp with time zone | ✓ | CURRENT_TIMESTAMP | - |
| granted_by | uuid | ✓ | - | - |

#### Índices

- **admin_user_permissions_pkey**
  ```sql
  CREATE UNIQUE INDEX admin_user_permissions_pkey ON public.admin_user_permissions USING btree (admin_user_id, permission_id)
  ```
- **idx_admin_user_permissions_user**
  ```sql
  CREATE INDEX idx_admin_user_permissions_user ON public.admin_user_permissions USING btree (admin_user_id)
  ```

#### Constraints

- **2200_20164_1_not_null** (CHECK)
- **2200_20164_2_not_null** (CHECK)
- **admin_user_permissions_admin_user_id_fkey** (FK): admin_user_id → admin_users.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **admin_user_permissions_granted_by_fkey** (FK): granted_by → admin_users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **admin_user_permissions_permission_id_fkey** (FK): permission_id → admin_permissions.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **admin_user_permissions_pkey** (PK): admin_user_id, admin_user_id, permission_id, permission_id
- **admin_user_permissions_pkey** (PK): admin_user_id, admin_user_id, permission_id, permission_id
- **admin_user_permissions_pkey** (PK): admin_user_id, admin_user_id, permission_id, permission_id
- **admin_user_permissions_pkey** (PK): admin_user_id, admin_user_id, permission_id, permission_id

---

### admin_users

**Descrição:** Usuários administradores do sistema

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 64 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| email | character varying(255) | ✗ | - | - |
| password_hash | character varying(255) | ✗ | - | - |
| first_name | character varying(100) | ✗ | - | - |
| last_name | character varying(100) | ✗ | - | - |
| role | USER-DEFINED | ✗ | 'supervisor'::admin_role_type | - |
| department | character varying(100) | ✓ | - | - |
| phone_number | character varying(20) | ✓ | - | - |
| is_active | boolean | ✓ | true | - |
| email_verified | boolean | ✓ | false | - |
| two_factor_enabled | boolean | ✓ | false | - |
| two_factor_secret | character varying(255) | ✓ | - | - |
| must_change_password | boolean | ✓ | true | - |
| failed_login_attempts | integer(32) | ✓ | 0 | - |
| locked_until | timestamp with time zone | ✓ | - | - |
| last_login_at | timestamp with time zone | ✓ | - | - |
| last_login_ip | inet | ✓ | - | - |
| last_password_change | timestamp with time zone | ✓ | CURRENT_TIMESTAMP | - |
| max_concurrent_sessions | integer(32) | ✓ | 3 | - |
| created_at | timestamp with time zone | ✓ | CURRENT_TIMESTAMP | - |
| updated_at | timestamp with time zone | ✓ | CURRENT_TIMESTAMP | - |
| created_by | uuid | ✓ | - | - |
| updated_by | uuid | ✓ | - | - |
| metadata | jsonb | ✓ | '{}'::jsonb | - |

#### Índices

- **admin_users_email_key**
  ```sql
  CREATE UNIQUE INDEX admin_users_email_key ON public.admin_users USING btree (email)
  ```
- **admin_users_pkey**
  ```sql
  CREATE UNIQUE INDEX admin_users_pkey ON public.admin_users USING btree (id)
  ```
- **idx_admin_users_active**
  ```sql
  CREATE INDEX idx_admin_users_active ON public.admin_users USING btree (is_active)
  ```
- **idx_admin_users_email**
  ```sql
  CREATE INDEX idx_admin_users_email ON public.admin_users USING btree (email)
  ```
- **idx_admin_users_last_login**
  ```sql
  CREATE INDEX idx_admin_users_last_login ON public.admin_users USING btree (last_login_at)
  ```
- **idx_admin_users_locked**
  ```sql
  CREATE INDEX idx_admin_users_locked ON public.admin_users USING btree (locked_until) WHERE (locked_until IS NOT NULL)
  ```
- **idx_admin_users_role**
  ```sql
  CREATE INDEX idx_admin_users_role ON public.admin_users USING btree (role)
  ```

#### Constraints

- **2200_20098_1_not_null** (CHECK)
- **2200_20098_2_not_null** (CHECK)
- **2200_20098_3_not_null** (CHECK)
- **2200_20098_4_not_null** (CHECK)
- **2200_20098_5_not_null** (CHECK)
- **2200_20098_6_not_null** (CHECK)
- **admin_users_created_by_fkey** (FK): created_by → admin_users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **admin_users_email_key** (UNIQUE): email
- **admin_users_pkey** (PK): id
- **admin_users_updated_by_fkey** (FK): updated_by → admin_users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **positive_max_sessions** (CHECK)
- **valid_email_admin** (CHECK)
- **valid_failed_attempts** (CHECK)

#### Triggers

- **update_admin_users_updated_at**
  - Timing: BEFORE
  - Event: UPDATE
  - Statement: `EXECUTE FUNCTION update_updated_at_column()...`

---

## Grupo: ALEMBIC (1 tabelas)

### alembic_version

**Descrição:** Controle de versão de migrações Alembic (gerenciado automaticamente)

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 56 kB
- **Registros:** 1

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| version_num | character varying(32) | ✗ | - | - |

#### Índices

- **alembic_version_pkc**
  ```sql
  CREATE UNIQUE INDEX alembic_version_pkc ON public.alembic_version USING btree (version_num)
  ```

#### Constraints

- **2200_20397_1_not_null** (CHECK)
- **alembic_version_pkc** (PK): version_num

---

## Grupo: AUDIT (3 tabelas)

### audit_log_entries

**Descrição:** Entradas genéricas de log de auditoria

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 40 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| event_type | character varying(100) | ✗ | - | - |
| entity_type | character varying(100) | ✓ | - | - |
| entity_id | uuid | ✓ | - | - |
| user_id | uuid | ✓ | - | - |
| old_values | jsonb | ✓ | - | - |
| new_values | jsonb | ✓ | - | - |
| metadata | jsonb | ✓ | '{}'::jsonb | - |
| ip_address | inet | ✓ | - | - |
| user_agent | text | ✓ | - | - |
| timestamp | timestamp with time zone | ✓ | now() | - |

#### Índices

- **audit_log_entries_pkey**
  ```sql
  CREATE UNIQUE INDEX audit_log_entries_pkey ON public.audit_log_entries USING btree (id)
  ```
- **idx_audit_log_entries_entity**
  ```sql
  CREATE INDEX idx_audit_log_entries_entity ON public.audit_log_entries USING btree (entity_type, entity_id)
  ```
- **idx_audit_log_entries_timestamp**
  ```sql
  CREATE INDEX idx_audit_log_entries_timestamp ON public.audit_log_entries USING btree ("timestamp")
  ```
- **idx_audit_log_entries_user**
  ```sql
  CREATE INDEX idx_audit_log_entries_user ON public.audit_log_entries USING btree (user_id, "timestamp" DESC)
  ```

#### Constraints

- **2200_20384_1_not_null** (CHECK)
- **2200_20384_2_not_null** (CHECK)
- **audit_log_entries_pkey** (PK): id

---

### audit_logs

**Descrição:** Security audit logs for authentication and authorization events

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 192 kB
- **Registros:** 44

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| event_type | character varying(50) | ✗ | - | - |
| event_status | character varying(20) | ✗ | 'success'::character varying | - |
| user_id | uuid | ✓ | - | - |
| user_email | character varying(255) | ✓ | - | - |
| firebase_uid | character varying(255) | ✓ | - | - |
| ip_address | inet | ✓ | - | - |
| user_agent | character varying(500) | ✓ | - | - |
| resource | character varying(255) | ✓ | - | - |
| action | character varying(100) | ✓ | - | - |
| event_metadata | jsonb | ✓ | '{}'::jsonb | - |
| message | character varying(500) | ✓ | - | - |
| error_details | character varying(1000) | ✓ | - | - |
| created_at | timestamp with time zone | ✗ | now() | - |
| updated_at | timestamp with time zone | ✗ | now() | - |

#### Índices

- **audit_logs_pkey**
  ```sql
  CREATE UNIQUE INDEX audit_logs_pkey ON public.audit_logs USING btree (id)
  ```
- **idx_audit_logs_created_at**
  ```sql
  CREATE INDEX idx_audit_logs_created_at ON public.audit_logs USING btree (created_at)
  ```
- **idx_audit_logs_event_status**
  ```sql
  CREATE INDEX idx_audit_logs_event_status ON public.audit_logs USING btree (event_status)
  ```
- **idx_audit_logs_event_type**
  ```sql
  CREATE INDEX idx_audit_logs_event_type ON public.audit_logs USING btree (event_type)
  ```
- **idx_audit_logs_ip_address**
  ```sql
  CREATE INDEX idx_audit_logs_ip_address ON public.audit_logs USING btree (ip_address)
  ```
- **idx_audit_logs_resource_action**
  ```sql
  CREATE INDEX idx_audit_logs_resource_action ON public.audit_logs USING btree (resource, action)
  ```
- **idx_audit_logs_user_email**
  ```sql
  CREATE INDEX idx_audit_logs_user_email ON public.audit_logs USING btree (user_email)
  ```
- **idx_audit_logs_user_id**
  ```sql
  CREATE INDEX idx_audit_logs_user_id ON public.audit_logs USING btree (user_id)
  ```
- **idx_audit_user_event_time**
  ```sql
  CREATE INDEX idx_audit_user_event_time ON public.audit_logs USING btree (user_id, event_type, created_at)
  ```

#### Constraints

- **2200_22539_14_not_null** (CHECK)
- **2200_22539_15_not_null** (CHECK)
- **2200_22539_1_not_null** (CHECK)
- **2200_22539_2_not_null** (CHECK)
- **2200_22539_3_not_null** (CHECK)
- **audit_logs_pkey** (PK): id
- **fk_audit_logs_user** (FK): user_id → users.id
  - ON DELETE: SET NULL
  - ON UPDATE: NO ACTION

#### Triggers

- **update_audit_logs_updated_at**
  - Timing: BEFORE
  - Event: UPDATE
  - Statement: `EXECUTE FUNCTION update_updated_at_column()...`

---

### audit_trail

**Descrição:** Trilha de auditoria geral (retenção: 90 dias)

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 48 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| table_name | character varying(255) | ✗ | - | - |
| record_id | uuid | ✗ | - | - |
| operation | character varying(50) | ✗ | - | - |
| old_data | jsonb | ✓ | - | - |
| new_data | jsonb | ✓ | - | - |
| changes | jsonb | ✓ | - | - |
| actor_id | uuid | ✓ | - | - |
| actor_type | character varying(50) | ✓ | - | - |
| actor_subject | character varying(255) | ✓ | - | - |
| ip_address | inet | ✓ | - | - |
| user_agent | text | ✓ | - | - |
| endpoint | character varying(500) | ✓ | - | - |
| created_at | timestamp with time zone | ✓ | now() | - |

#### Índices

- **audit_trail_pkey**
  ```sql
  CREATE UNIQUE INDEX audit_trail_pkey ON public.audit_trail USING btree (id)
  ```
- **idx_audit_trail_actor**
  ```sql
  CREATE INDEX idx_audit_trail_actor ON public.audit_trail USING btree (actor_id, created_at DESC)
  ```
- **idx_audit_trail_created_at**
  ```sql
  CREATE INDEX idx_audit_trail_created_at ON public.audit_trail USING btree (created_at)
  ```
- **idx_audit_trail_operation**
  ```sql
  CREATE INDEX idx_audit_trail_operation ON public.audit_trail USING btree (operation, created_at DESC)
  ```
- **idx_audit_trail_table_record**
  ```sql
  CREATE INDEX idx_audit_trail_table_record ON public.audit_trail USING btree (table_name, record_id)
  ```

#### Constraints

- **2200_20371_1_not_null** (CHECK)
- **2200_20371_2_not_null** (CHECK)
- **2200_20371_3_not_null** (CHECK)
- **2200_20371_4_not_null** (CHECK)
- **audit_trail_pkey** (PK): id

---

## Grupo: ERROR (1 tabelas)

### error_logs

**Descrição:** Error tracking table for monitoring and debugging critical system errors

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 224 kB
- **Registros:** 3

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| error_type | character varying(100) | ✗ | - | Type of error (DI_GENERATOR, ROLE_ENUM, SCHEMA_MISMATCH, etc.) |
| error_message | text | ✗ | - | The error message or description |
| stack_trace | text | ✓ | - | Full stack trace of the error (optional) |
| context | jsonb | ✗ | '{}'::jsonb | Additional context data as JSON (request info, user data, etc.) |
| count | integer(32) | ✗ | 1 | Number of times this error has occurred (for deduplication) |
| first_seen | timestamp with time zone | ✗ | CURRENT_TIMESTAMP | When this error was first encountered |
| last_seen | timestamp with time zone | ✗ | CURRENT_TIMESTAMP | When this error was last encountered |
| resolved | boolean | ✗ | false | Whether this error has been resolved |
| severity | character varying(20) | ✗ | 'ERROR'::character varying | Error severity level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| created_at | timestamp with time zone | ✗ | CURRENT_TIMESTAMP | - |
| updated_at | timestamp with time zone | ✗ | CURRENT_TIMESTAMP | - |

#### Índices

- **error_logs_pkey**
  ```sql
  CREATE UNIQUE INDEX error_logs_pkey ON public.error_logs USING btree (id)
  ```
- **idx_error_logs_context_gin**
  ```sql
  CREATE INDEX idx_error_logs_context_gin ON public.error_logs USING gin (context)
  ```
- **idx_error_logs_count**
  ```sql
  CREATE INDEX idx_error_logs_count ON public.error_logs USING btree (count)
  ```
- **idx_error_logs_deduplication**
  ```sql
  CREATE UNIQUE INDEX idx_error_logs_deduplication ON public.error_logs USING btree (error_type, md5(error_message))
  ```
- **idx_error_logs_error_type**
  ```sql
  CREATE INDEX idx_error_logs_error_type ON public.error_logs USING btree (error_type)
  ```
- **idx_error_logs_first_seen**
  ```sql
  CREATE INDEX idx_error_logs_first_seen ON public.error_logs USING btree (first_seen)
  ```
- **idx_error_logs_last_seen**
  ```sql
  CREATE INDEX idx_error_logs_last_seen ON public.error_logs USING btree (last_seen)
  ```
- **idx_error_logs_resolved**
  ```sql
  CREATE INDEX idx_error_logs_resolved ON public.error_logs USING btree (resolved)
  ```
- **idx_error_logs_severity**
  ```sql
  CREATE INDEX idx_error_logs_severity ON public.error_logs USING btree (severity)
  ```
- **idx_error_logs_severity_time**
  ```sql
  CREATE INDEX idx_error_logs_severity_time ON public.error_logs USING btree (severity, last_seen)
  ```
- **idx_error_logs_type_resolved**
  ```sql
  CREATE INDEX idx_error_logs_type_resolved ON public.error_logs USING btree (error_type, resolved)
  ```
- **idx_error_logs_unresolved_recent**
  ```sql
  CREATE INDEX idx_error_logs_unresolved_recent ON public.error_logs USING btree (resolved, last_seen)
  ```

#### Constraints

- **2200_22565_10_not_null** (CHECK)
- **2200_22565_11_not_null** (CHECK)
- **2200_22565_12_not_null** (CHECK)
- **2200_22565_1_not_null** (CHECK)
- **2200_22565_2_not_null** (CHECK)
- **2200_22565_3_not_null** (CHECK)
- **2200_22565_5_not_null** (CHECK)
- **2200_22565_6_not_null** (CHECK)
- **2200_22565_7_not_null** (CHECK)
- **2200_22565_8_not_null** (CHECK)
- **2200_22565_9_not_null** (CHECK)
- **error_logs_pkey** (PK): id

---

## Grupo: FLOW (8 tabelas)

### flow_analytics

**Descrição:** Analytics e métricas dos fluxos

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 40 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| flow_template_version_id | uuid | ✓ | - | - |
| patient_id | uuid | ✓ | - | - |
| total_steps | integer(32) | ✓ | - | - |
| completed_steps | integer(32) | ✓ | - | - |
| success_rate | numeric(5,2) | ✓ | - | - |
| avg_response_time_seconds | integer(32) | ✓ | - | - |
| step_analytics | jsonb | ✓ | - | - |
| interaction_patterns | jsonb | ✓ | - | - |
| period_start | timestamp with time zone | ✓ | - | - |
| period_end | timestamp with time zone | ✓ | - | - |
| calculated_at | timestamp with time zone | ✓ | now() | - |

#### Índices

- **flow_analytics_pkey**
  ```sql
  CREATE UNIQUE INDEX flow_analytics_pkey ON public.flow_analytics USING btree (id)
  ```
- **idx_flow_analytics_patient**
  ```sql
  CREATE INDEX idx_flow_analytics_patient ON public.flow_analytics USING btree (patient_id)
  ```
- **idx_flow_analytics_period**
  ```sql
  CREATE INDEX idx_flow_analytics_period ON public.flow_analytics USING btree (period_start, period_end)
  ```
- **idx_flow_analytics_template**
  ```sql
  CREATE INDEX idx_flow_analytics_template ON public.flow_analytics USING btree (flow_template_version_id)
  ```

#### Constraints

- **2200_19776_1_not_null** (CHECK)
- **flow_analytics_flow_template_version_id_fkey** (FK): flow_template_version_id → flow_template_versions.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **flow_analytics_patient_id_fkey** (FK): patient_id → patients.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **flow_analytics_pkey** (PK): id

---

### flow_kinds

**Descrição:** Tipos de fluxos conversacionais disponíveis

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 80 kB
- **Registros:** 4

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| kind_key | character varying(50) | ✗ | - | - |
| display_name | character varying(255) | ✗ | - | - |
| description | text | ✓ | - | - |
| is_active | boolean | ✓ | true | - |
| created_at | timestamp with time zone | ✓ | now() | - |
| updated_at | timestamp with time zone | ✓ | now() | - |

#### Índices

- **flow_kinds_kind_key_key**
  ```sql
  CREATE UNIQUE INDEX flow_kinds_kind_key_key ON public.flow_kinds USING btree (kind_key)
  ```
- **flow_kinds_pkey**
  ```sql
  CREATE UNIQUE INDEX flow_kinds_pkey ON public.flow_kinds USING btree (id)
  ```
- **idx_flow_kinds_is_active**
  ```sql
  CREATE INDEX idx_flow_kinds_is_active ON public.flow_kinds USING btree (is_active)
  ```
- **idx_flow_kinds_kind_key**
  ```sql
  CREATE INDEX idx_flow_kinds_kind_key ON public.flow_kinds USING btree (kind_key)
  ```

#### Constraints

- **2200_19681_1_not_null** (CHECK)
- **2200_19681_2_not_null** (CHECK)
- **2200_19681_3_not_null** (CHECK)
- **flow_kinds_kind_key_key** (UNIQUE): kind_key
- **flow_kinds_pkey** (PK): id

---

### flow_messages

**Descrição:** Templates de mensagens usadas nos fluxos

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 40 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| flow_template_version_id | uuid | ✗ | - | - |
| step_number | integer(32) | ✗ | - | - |
| message_key | character varying(100) | ✗ | - | - |
| message_text | text | ✗ | - | - |
| message_type | character varying(50) | ✓ | 'text'::character varying | - |
| buttons | jsonb | ✓ | - | - |
| list_items | jsonb | ✓ | - | - |
| conditions | jsonb | ✓ | - | - |
| delay_seconds | integer(32) | ✓ | 0 | - |
| created_at | timestamp with time zone | ✓ | now() | - |

#### Índices

- **flow_messages_pkey**
  ```sql
  CREATE UNIQUE INDEX flow_messages_pkey ON public.flow_messages USING btree (id)
  ```
- **idx_flow_messages_step**
  ```sql
  CREATE INDEX idx_flow_messages_step ON public.flow_messages USING btree (flow_template_version_id, step_number)
  ```
- **idx_flow_messages_template**
  ```sql
  CREATE INDEX idx_flow_messages_template ON public.flow_messages USING btree (flow_template_version_id)
  ```
- **unique_flow_message**
  ```sql
  CREATE UNIQUE INDEX unique_flow_message ON public.flow_messages USING btree (flow_template_version_id, step_number, message_key)
  ```

#### Constraints

- **2200_19756_1_not_null** (CHECK)
- **2200_19756_2_not_null** (CHECK)
- **2200_19756_3_not_null** (CHECK)
- **2200_19756_4_not_null** (CHECK)
- **2200_19756_5_not_null** (CHECK)
- **flow_messages_flow_template_version_id_fkey** (FK): flow_template_version_id → flow_template_versions.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **flow_messages_pkey** (PK): id
- **unique_flow_message** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, step_number, step_number, step_number, message_key, message_key, message_key
- **unique_flow_message** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, step_number, step_number, step_number, message_key, message_key, message_key
- **unique_flow_message** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, step_number, step_number, step_number, message_key, message_key, message_key
- **unique_flow_message** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, step_number, step_number, step_number, message_key, message_key, message_key
- **unique_flow_message** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, step_number, step_number, step_number, message_key, message_key, message_key
- **unique_flow_message** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, step_number, step_number, step_number, message_key, message_key, message_key
- **unique_flow_message** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, step_number, step_number, step_number, message_key, message_key, message_key
- **unique_flow_message** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, step_number, step_number, step_number, message_key, message_key, message_key
- **unique_flow_message** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, step_number, step_number, step_number, message_key, message_key, message_key

---

### flow_states

**Descrição:** Tabela legacy de estados de fluxo (substituída por patient_flow_states)

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 32 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| patient_id | uuid | ✗ | - | - |
| flow_type | character varying(50) | ✗ | - | - |
| current_step | integer(32) | ✗ | 0 | - |
| started_at | timestamp with time zone | ✗ | - | - |
| completed_at | timestamp with time zone | ✓ | - | - |
| state_data | jsonb | ✓ | '{}'::jsonb | - |
| created_at | timestamp with time zone | ✗ | now() | - |
| updated_at | timestamp with time zone | ✗ | now() | - |

#### Índices

- **flow_states_pkey**
  ```sql
  CREATE UNIQUE INDEX flow_states_pkey ON public.flow_states USING btree (id)
  ```
- **idx_flow_states_flow_type**
  ```sql
  CREATE INDEX idx_flow_states_flow_type ON public.flow_states USING btree (flow_type)
  ```
- **idx_flow_states_patient_id**
  ```sql
  CREATE INDEX idx_flow_states_patient_id ON public.flow_states USING btree (patient_id)
  ```

#### Constraints

- **2200_19858_1_not_null** (CHECK)
- **2200_19858_2_not_null** (CHECK)
- **2200_19858_3_not_null** (CHECK)
- **2200_19858_4_not_null** (CHECK)
- **2200_19858_5_not_null** (CHECK)
- **2200_19858_8_not_null** (CHECK)
- **2200_19858_9_not_null** (CHECK)
- **flow_states_patient_id_fkey** (FK): patient_id → patients.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **flow_states_pkey** (PK): id

#### Triggers

- **update_flow_states_updated_at**
  - Timing: BEFORE
  - Event: UPDATE
  - Statement: `EXECUTE FUNCTION update_updated_at_column()...`

---

### flow_template_categories

**Descrição:** Categorização de templates de fluxos

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 24 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| category_key | character varying(50) | ✗ | - | - |
| display_name | character varying(255) | ✗ | - | - |
| description | text | ✓ | - | - |
| icon | character varying(100) | ✓ | - | - |
| sort_order | integer(32) | ✓ | 0 | - |
| is_active | boolean | ✓ | true | - |
| created_at | timestamp with time zone | ✓ | now() | - |

#### Índices

- **flow_template_categories_category_key_key**
  ```sql
  CREATE UNIQUE INDEX flow_template_categories_category_key_key ON public.flow_template_categories USING btree (category_key)
  ```
- **flow_template_categories_pkey**
  ```sql
  CREATE UNIQUE INDEX flow_template_categories_pkey ON public.flow_template_categories USING btree (id)
  ```

#### Constraints

- **2200_19845_1_not_null** (CHECK)
- **2200_19845_2_not_null** (CHECK)
- **2200_19845_3_not_null** (CHECK)
- **flow_template_categories_category_key_key** (UNIQUE): category_key
- **flow_template_categories_pkey** (PK): id

---

### flow_template_shares

**Descrição:** Compartilhamento de templates entre médicos

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 24 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| flow_template_version_id | uuid | ✗ | - | - |
| shared_by | uuid | ✗ | - | - |
| shared_with | uuid | ✓ | - | - |
| can_view | boolean | ✓ | true | - |
| can_edit | boolean | ✓ | false | - |
| can_reshare | boolean | ✓ | false | - |
| share_notes | text | ✓ | - | - |
| shared_at | timestamp with time zone | ✓ | now() | - |
| expires_at | timestamp with time zone | ✓ | - | - |

#### Índices

- **flow_template_shares_pkey**
  ```sql
  CREATE UNIQUE INDEX flow_template_shares_pkey ON public.flow_template_shares USING btree (id)
  ```
- **unique_share**
  ```sql
  CREATE UNIQUE INDEX unique_share ON public.flow_template_shares USING btree (flow_template_version_id, shared_by, shared_with)
  ```

#### Constraints

- **2200_19816_1_not_null** (CHECK)
- **2200_19816_2_not_null** (CHECK)
- **2200_19816_3_not_null** (CHECK)
- **flow_template_shares_flow_template_version_id_fkey** (FK): flow_template_version_id → flow_template_versions.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **flow_template_shares_pkey** (PK): id
- **flow_template_shares_shared_by_fkey** (FK): shared_by → users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **flow_template_shares_shared_with_fkey** (FK): shared_with → users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **unique_share** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, shared_by, shared_by, shared_by, shared_with, shared_with, shared_with
- **unique_share** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, shared_by, shared_by, shared_by, shared_with, shared_with, shared_with
- **unique_share** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, shared_by, shared_by, shared_by, shared_with, shared_with, shared_with
- **unique_share** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, shared_by, shared_by, shared_by, shared_with, shared_with, shared_with
- **unique_share** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, shared_by, shared_by, shared_by, shared_with, shared_with, shared_with
- **unique_share** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, shared_by, shared_by, shared_by, shared_with, shared_with, shared_with
- **unique_share** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, shared_by, shared_by, shared_by, shared_with, shared_with, shared_with
- **unique_share** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, shared_by, shared_by, shared_by, shared_with, shared_with, shared_with
- **unique_share** (UNIQUE): flow_template_version_id, flow_template_version_id, flow_template_version_id, shared_by, shared_by, shared_by, shared_with, shared_with, shared_with

---

### flow_template_stats

**Descrição:** Estatísticas agregadas dos templates

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 16 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| flow_template_version_id | uuid | ✗ | - | - |
| total_uses | integer(32) | ✓ | 0 | - |
| active_instances | integer(32) | ✓ | 0 | - |
| completed_instances | integer(32) | ✓ | 0 | - |
| avg_completion_rate | numeric(5,2) | ✓ | - | - |
| avg_duration_hours | numeric(10,2) | ✓ | - | - |
| avg_rating | numeric(3,2) | ✓ | - | - |
| total_ratings | integer(32) | ✓ | 0 | - |
| last_calculated_at | timestamp with time zone | ✓ | now() | - |

#### Índices

- **flow_template_stats_flow_template_version_id_key**
  ```sql
  CREATE UNIQUE INDEX flow_template_stats_flow_template_version_id_key ON public.flow_template_stats USING btree (flow_template_version_id)
  ```
- **flow_template_stats_pkey**
  ```sql
  CREATE UNIQUE INDEX flow_template_stats_pkey ON public.flow_template_stats USING btree (id)
  ```

#### Constraints

- **2200_19798_1_not_null** (CHECK)
- **2200_19798_2_not_null** (CHECK)
- **flow_template_stats_flow_template_version_id_fkey** (FK): flow_template_version_id → flow_template_versions.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **flow_template_stats_flow_template_version_id_key** (UNIQUE): flow_template_version_id
- **flow_template_stats_pkey** (PK): id

---

### flow_template_versions

**Descrição:** Versões de templates de fluxos conversacionais

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 192 kB
- **Registros:** 7

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| flow_kind_id | uuid | ✗ | - | - |
| version_number | integer(32) | ✗ | - | - |
| template_name | character varying(255) | ✗ | - | - |
| description | text | ✓ | - | - |
| steps | jsonb | ✗ | - | - |
| metadata | jsonb | ✓ | '{}'::jsonb | - |
| is_active | boolean | ✓ | false | - |
| is_draft | boolean | ✓ | true | - |
| published_at | timestamp with time zone | ✓ | - | - |
| deprecated_at | timestamp with time zone | ✓ | - | - |
| created_by | uuid | ✓ | - | - |
| created_at | timestamp with time zone | ✓ | now() | - |
| updated_at | timestamp with time zone | ✓ | now() | - |

#### Índices

- **flow_template_versions_pkey**
  ```sql
  CREATE UNIQUE INDEX flow_template_versions_pkey ON public.flow_template_versions USING btree (id)
  ```
- **idx_flow_template_versions_active**
  ```sql
  CREATE INDEX idx_flow_template_versions_active ON public.flow_template_versions USING btree (flow_kind_id, is_active) WHERE (is_active = true)
  ```
- **idx_flow_template_versions_flow_kind**
  ```sql
  CREATE INDEX idx_flow_template_versions_flow_kind ON public.flow_template_versions USING btree (flow_kind_id)
  ```
- **idx_flow_template_versions_version**
  ```sql
  CREATE INDEX idx_flow_template_versions_version ON public.flow_template_versions USING btree (flow_kind_id, version_number DESC)
  ```
- **unique_flow_version**
  ```sql
  CREATE UNIQUE INDEX unique_flow_version ON public.flow_template_versions USING btree (flow_kind_id, version_number)
  ```

#### Constraints

- **2200_19696_1_not_null** (CHECK)
- **2200_19696_2_not_null** (CHECK)
- **2200_19696_3_not_null** (CHECK)
- **2200_19696_4_not_null** (CHECK)
- **2200_19696_6_not_null** (CHECK)
- **flow_template_versions_created_by_fkey** (FK): created_by → users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **flow_template_versions_flow_kind_id_fkey** (FK): flow_kind_id → flow_kinds.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **flow_template_versions_pkey** (PK): id
- **unique_flow_version** (UNIQUE): flow_kind_id, flow_kind_id, version_number, version_number
- **unique_flow_version** (UNIQUE): flow_kind_id, flow_kind_id, version_number, version_number
- **unique_flow_version** (UNIQUE): flow_kind_id, flow_kind_id, version_number, version_number
- **unique_flow_version** (UNIQUE): flow_kind_id, flow_kind_id, version_number, version_number

---

## Grupo: MEDICAL (1 tabelas)

### medical_reports

**Descrição:** Relatórios médicos gerados para pacientes

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 40 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| patient_id | uuid | ✗ | - | - |
| generated_by | uuid | ✗ | - | - |
| period_start | date | ✗ | - | - |
| period_end | date | ✗ | - | - |
| summary | text | ✓ | - | - |
| insights | jsonb | ✓ | '{}'::jsonb | - |
| charts_data | jsonb | ✓ | '{}'::jsonb | - |
| alerts | jsonb | ✓ | '{}'::jsonb | - |
| report_type | character varying(50) | ✓ | - | - |
| report_metadata | jsonb | ✓ | '{}'::jsonb | - |
| created_at | timestamp with time zone | ✗ | now() | - |
| updated_at | timestamp with time zone | ✗ | now() | - |

#### Índices

- **idx_medical_reports_generated_by**
  ```sql
  CREATE INDEX idx_medical_reports_generated_by ON public.medical_reports USING btree (generated_by)
  ```
- **idx_medical_reports_patient_id**
  ```sql
  CREATE INDEX idx_medical_reports_patient_id ON public.medical_reports USING btree (patient_id)
  ```
- **idx_medical_reports_period**
  ```sql
  CREATE INDEX idx_medical_reports_period ON public.medical_reports USING btree (period_start, period_end)
  ```
- **medical_reports_pkey**
  ```sql
  CREATE UNIQUE INDEX medical_reports_pkey ON public.medical_reports USING btree (id)
  ```

#### Constraints

- **2200_20071_12_not_null** (CHECK)
- **2200_20071_13_not_null** (CHECK)
- **2200_20071_1_not_null** (CHECK)
- **2200_20071_2_not_null** (CHECK)
- **2200_20071_3_not_null** (CHECK)
- **2200_20071_4_not_null** (CHECK)
- **2200_20071_5_not_null** (CHECK)
- **medical_reports_generated_by_fkey** (FK): generated_by → users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **medical_reports_patient_id_fkey** (FK): patient_id → patients.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **medical_reports_pkey** (PK): id

#### Triggers

- **update_medical_reports_updated_at**
  - Timing: BEFORE
  - Event: UPDATE
  - Statement: `EXECUTE FUNCTION update_updated_at_column()...`

---

## Grupo: MESSAGE (1 tabelas)

### message_status_events

**Descrição:** Rastreamento de mudanças de status de mensagens

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 48 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| message_id | uuid | ✗ | - | - |
| status | character varying(50) | ✗ | - | - |
| previous_status | character varying(50) | ✓ | - | - |
| whatsapp_id | character varying(255) | ✓ | - | - |
| whatsapp_timestamp | timestamp with time zone | ✓ | - | - |
| error_code | character varying(50) | ✓ | - | - |
| error_message | text | ✓ | - | - |
| retry_count | integer(32) | ✓ | 0 | - |
| metadata | jsonb | ✓ | '{}'::jsonb | - |
| evolution_event_type | character varying(100) | ✓ | - | - |
| evolution_payload | jsonb | ✓ | - | - |
| created_at | timestamp with time zone | ✗ | now() | - |

#### Índices

- **idx_msg_status_error_time**
  ```sql
  CREATE INDEX idx_msg_status_error_time ON public.message_status_events USING btree (error_code, created_at) WHERE (error_code IS NOT NULL)
  ```
- **idx_msg_status_msg_created**
  ```sql
  CREATE INDEX idx_msg_status_msg_created ON public.message_status_events USING btree (message_id, created_at)
  ```
- **idx_msg_status_type_time**
  ```sql
  CREATE INDEX idx_msg_status_type_time ON public.message_status_events USING btree (status, created_at)
  ```
- **idx_msg_status_whatsapp**
  ```sql
  CREATE INDEX idx_msg_status_whatsapp ON public.message_status_events USING btree (whatsapp_id, status)
  ```
- **message_status_events_pkey**
  ```sql
  CREATE UNIQUE INDEX message_status_events_pkey ON public.message_status_events USING btree (id)
  ```

#### Constraints

- **2200_19613_13_not_null** (CHECK)
- **2200_19613_1_not_null** (CHECK)
- **2200_19613_2_not_null** (CHECK)
- **2200_19613_3_not_null** (CHECK)
- **message_status_events_message_id_fkey** (FK): message_id → messages.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **message_status_events_pkey** (PK): id

---

## Grupo: OTHER (6 tabelas)

### alerts

**Descrição:** Alertas e notificações do sistema

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 48 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| patient_id | uuid | ✗ | - | - |
| type | character varying(100) | ✗ | - | - |
| severity | USER-DEFINED | ✗ | - | - |
| message | text | ✗ | - | - |
| data | jsonb | ✓ | '{}'::jsonb | - |
| acknowledged | boolean | ✗ | false | - |
| acknowledged_by | uuid | ✓ | - | - |
| acknowledged_at | timestamp with time zone | ✓ | - | - |
| created_at | timestamp with time zone | ✗ | now() | - |
| updated_at | timestamp with time zone | ✗ | now() | - |

#### Índices

- **alerts_pkey**
  ```sql
  CREATE UNIQUE INDEX alerts_pkey ON public.alerts USING btree (id)
  ```
- **idx_alerts_acknowledged**
  ```sql
  CREATE INDEX idx_alerts_acknowledged ON public.alerts USING btree (acknowledged)
  ```
- **idx_alerts_patient_id**
  ```sql
  CREATE INDEX idx_alerts_patient_id ON public.alerts USING btree (patient_id)
  ```
- **idx_alerts_severity**
  ```sql
  CREATE INDEX idx_alerts_severity ON public.alerts USING btree (severity)
  ```
- **idx_alerts_type**
  ```sql
  CREATE INDEX idx_alerts_type ON public.alerts USING btree (type)
  ```

#### Constraints

- **2200_19655_10_not_null** (CHECK)
- **2200_19655_11_not_null** (CHECK)
- **2200_19655_1_not_null** (CHECK)
- **2200_19655_2_not_null** (CHECK)
- **2200_19655_3_not_null** (CHECK)
- **2200_19655_4_not_null** (CHECK)
- **2200_19655_5_not_null** (CHECK)
- **2200_19655_7_not_null** (CHECK)
- **alerts_acknowledged_by_fkey** (FK): acknowledged_by → users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **alerts_patient_id_fkey** (FK): patient_id → patients.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **alerts_pkey** (PK): id

#### Triggers

- **update_alerts_updated_at**
  - Timing: BEFORE
  - Event: UPDATE
  - Statement: `EXECUTE FUNCTION update_updated_at_column()...`

---

### appointments

**Descrição:** Agendamentos e consultas médicas

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 48 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| patient_id | uuid | ✗ | - | - |
| doctor_id | uuid | ✗ | - | - |
| appointment_type | character varying(100) | ✗ | - | - |
| status | character varying(50) | ✓ | 'scheduled'::character varying | - |
| scheduled_at | timestamp with time zone | ✗ | - | - |
| duration_minutes | integer(32) | ✓ | 60 | - |
| completed_at | timestamp with time zone | ✓ | - | - |
| cancelled_at | timestamp with time zone | ✓ | - | - |
| pre_appointment_notes | text | ✓ | - | - |
| post_appointment_notes | text | ✓ | - | - |
| appointment_metadata | jsonb | ✓ | '{}'::jsonb | - |
| created_at | timestamp with time zone | ✓ | now() | - |
| updated_at | timestamp with time zone | ✓ | now() | - |

#### Índices

- **appointments_pkey**
  ```sql
  CREATE UNIQUE INDEX appointments_pkey ON public.appointments USING btree (id)
  ```
- **idx_appointments_doctor**
  ```sql
  CREATE INDEX idx_appointments_doctor ON public.appointments USING btree (doctor_id)
  ```
- **idx_appointments_patient**
  ```sql
  CREATE INDEX idx_appointments_patient ON public.appointments USING btree (patient_id)
  ```
- **idx_appointments_scheduled**
  ```sql
  CREATE INDEX idx_appointments_scheduled ON public.appointments USING btree (scheduled_at)
  ```
- **idx_appointments_status**
  ```sql
  CREATE INDEX idx_appointments_status ON public.appointments USING btree (status, scheduled_at)
  ```

#### Constraints

- **2200_20426_1_not_null** (CHECK)
- **2200_20426_2_not_null** (CHECK)
- **2200_20426_3_not_null** (CHECK)
- **2200_20426_4_not_null** (CHECK)
- **2200_20426_6_not_null** (CHECK)
- **appointments_doctor_id_fkey** (FK): doctor_id → users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **appointments_patient_id_fkey** (FK): patient_id → patients.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **appointments_pkey** (PK): id

---

### contacts

**Descrição:** Contatos gerais do sistema

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 40 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| name | character varying(255) | ✗ | - | - |
| email | character varying(255) | ✓ | - | - |
| phone | character varying(20) | ✓ | - | - |
| contact_type | character varying(50) | ✓ | - | - |
| related_patient_id | uuid | ✓ | - | - |
| related_user_id | uuid | ✓ | - | - |
| notes | text | ✓ | - | - |
| tags | ARRAY | ✓ | - | - |
| contact_metadata | jsonb | ✓ | '{}'::jsonb | - |
| created_at | timestamp with time zone | ✓ | now() | - |
| updated_at | timestamp with time zone | ✓ | now() | - |

#### Índices

- **contacts_pkey**
  ```sql
  CREATE UNIQUE INDEX contacts_pkey ON public.contacts USING btree (id)
  ```
- **idx_contacts_email**
  ```sql
  CREATE INDEX idx_contacts_email ON public.contacts USING btree (email)
  ```
- **idx_contacts_phone**
  ```sql
  CREATE INDEX idx_contacts_phone ON public.contacts USING btree (phone)
  ```
- **idx_contacts_type**
  ```sql
  CREATE INDEX idx_contacts_type ON public.contacts USING btree (contact_type)
  ```

#### Constraints

- **2200_20402_1_not_null** (CHECK)
- **2200_20402_2_not_null** (CHECK)
- **contacts_pkey** (PK): id
- **contacts_related_patient_id_fkey** (FK): related_patient_id → patients.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **contacts_related_user_id_fkey** (FK): related_user_id → users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION

---

### messages

**Descrição:** Mensagens WhatsApp (enviadas e recebidas)

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 272 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| patient_id | uuid | ✗ | - | - |
| direction | USER-DEFINED | ✗ | - | - |
| type | USER-DEFINED | ✗ | 'text'::message_type | - |
| content | text | ✓ | - | - |
| message_metadata | jsonb | ✓ | '{}'::jsonb | - |
| whatsapp_id | character varying(255) | ✓ | - | - |
| status | USER-DEFINED | ✗ | 'pending'::message_status | - |
| scheduled_for | timestamp with time zone | ✓ | - | - |
| sent_at | timestamp with time zone | ✓ | - | - |
| delivered_at | timestamp with time zone | ✓ | - | - |
| read_at | timestamp with time zone | ✓ | - | - |
| created_at | timestamp with time zone | ✗ | now() | - |
| updated_at | timestamp with time zone | ✗ | now() | - |
| delivery_status | USER-DEFINED | ✓ | - | - |
| retry_count | integer(32) | ✗ | 0 | - |
| last_retry_at | timestamp with time zone | ✓ | - | - |
| failure_reason | text | ✓ | - | - |
| next_retry_at | timestamp with time zone | ✓ | - | - |

#### Índices

- **idx_messages_created_at**
  ```sql
  CREATE INDEX idx_messages_created_at ON public.messages USING btree (created_at DESC)
  ```
- **idx_messages_direction**
  ```sql
  CREATE INDEX idx_messages_direction ON public.messages USING btree (direction)
  ```
- **idx_messages_direction_created_desc**
  ```sql
  CREATE INDEX idx_messages_direction_created_desc ON public.messages USING btree (direction, created_at DESC)
  ```
- **idx_messages_direction_created_new**
  ```sql
  CREATE INDEX idx_messages_direction_created_new ON public.messages USING btree (direction, created_at DESC)
  ```
- **idx_messages_direction_created_opt**
  ```sql
  CREATE INDEX idx_messages_direction_created_opt ON public.messages USING btree (direction, created_at DESC)
  ```
- **idx_messages_patient_created_desc**
  ```sql
  CREATE INDEX idx_messages_patient_created_desc ON public.messages USING btree (patient_id, created_at DESC)
  ```
- **idx_messages_patient_created_opt**
  ```sql
  CREATE INDEX idx_messages_patient_created_opt ON public.messages USING btree (patient_id, created_at DESC)
  ```
- **idx_messages_patient_direction_created_desc**
  ```sql
  CREATE INDEX idx_messages_patient_direction_created_desc ON public.messages USING btree (patient_id, direction, created_at DESC)
  ```
- **idx_messages_patient_direction_created_opt**
  ```sql
  CREATE INDEX idx_messages_patient_direction_created_opt ON public.messages USING btree (patient_id, direction, created_at DESC)
  ```
- **idx_messages_patient_id**
  ```sql
  CREATE INDEX idx_messages_patient_id ON public.messages USING btree (patient_id)
  ```
- **idx_messages_patient_id_created_new**
  ```sql
  CREATE INDEX idx_messages_patient_id_created_new ON public.messages USING btree (patient_id, created_at DESC)
  ```
- **idx_messages_scheduled_for**
  ```sql
  CREATE INDEX idx_messages_scheduled_for ON public.messages USING btree (scheduled_for)
  ```
- **idx_messages_status**
  ```sql
  CREATE INDEX idx_messages_status ON public.messages USING btree (status)
  ```
- **idx_messages_status_created_desc**
  ```sql
  CREATE INDEX idx_messages_status_created_desc ON public.messages USING btree (status, created_at DESC)
  ```
- **idx_messages_whatsapp_id**
  ```sql
  CREATE INDEX idx_messages_whatsapp_id ON public.messages USING btree (whatsapp_id)
  ```
- **messages_pkey**
  ```sql
  CREATE UNIQUE INDEX messages_pkey ON public.messages USING btree (id)
  ```

#### Constraints

- **2200_19589_13_not_null** (CHECK)
- **2200_19589_14_not_null** (CHECK)
- **2200_19589_16_not_null** (CHECK)
- **2200_19589_1_not_null** (CHECK)
- **2200_19589_2_not_null** (CHECK)
- **2200_19589_3_not_null** (CHECK)
- **2200_19589_4_not_null** (CHECK)
- **2200_19589_8_not_null** (CHECK)
- **messages_patient_id_fkey** (FK): patient_id → patients.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **messages_pkey** (PK): id

#### Triggers

- **update_messages_updated_at**
  - Timing: BEFORE
  - Event: UPDATE
  - Statement: `EXECUTE FUNCTION update_updated_at_column()...`

---

### patients

**Descrição:** Pacientes em tratamento oncológico

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 200 kB
- **Registros:** 1

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| doctor_id | uuid | ✗ | - | - |
| phone | character varying(20) | ✗ | - | - |
| name | character varying(255) | ✗ | - | - |
| email | character varying(255) | ✓ | - | - |
| birth_date | date | ✓ | - | - |
| treatment_type | character varying(100) | ✓ | - | - |
| treatment_start_date | date | ✓ | - | - |
| treatment_phase | character varying(50) | ✓ | - | - |
| diagnosis | text | ✓ | - | - |
| flow_state | USER-DEFINED | ✗ | 'onboarding'::flow_state | - |
| current_day | integer(32) | ✗ | 0 | - |
| cpf | character varying(14) | ✓ | - | - |
| doctor_notes | text | ✓ | - | - |
| patient_metadata | jsonb | ✓ | '{}'::jsonb | - |
| created_at | timestamp with time zone | ✗ | now() | - |
| updated_at | timestamp with time zone | ✗ | now() | - |
| metadata | jsonb | ✓ | '{}'::jsonb | - |

#### Índices

- **idx_patients_cpf_unique**
  ```sql
  CREATE UNIQUE INDEX idx_patients_cpf_unique ON public.patients USING btree (cpf) WHERE (cpf IS NOT NULL)
  ```
- **idx_patients_created_at**
  ```sql
  CREATE INDEX idx_patients_created_at ON public.patients USING btree (created_at DESC)
  ```
- **idx_patients_doctor_id**
  ```sql
  CREATE INDEX idx_patients_doctor_id ON public.patients USING btree (doctor_id)
  ```
- **idx_patients_doctor_id_opt**
  ```sql
  CREATE INDEX idx_patients_doctor_id_opt ON public.patients USING btree (doctor_id)
  ```
- **idx_patients_flow_state**
  ```sql
  CREATE INDEX idx_patients_flow_state ON public.patients USING btree (flow_state)
  ```
- **idx_patients_pagination**
  ```sql
  CREATE INDEX idx_patients_pagination ON public.patients USING btree (created_at DESC, id)
  ```
- **idx_patients_phone**
  ```sql
  CREATE INDEX idx_patients_phone ON public.patients USING btree (phone)
  ```
- **idx_patients_treatment_phase**
  ```sql
  CREATE INDEX idx_patients_treatment_phase ON public.patients USING btree (treatment_phase) WHERE (treatment_phase IS NOT NULL)
  ```
- **idx_patients_treatment_type**
  ```sql
  CREATE INDEX idx_patients_treatment_type ON public.patients USING btree (treatment_type)
  ```
- **patients_cpf_key**
  ```sql
  CREATE UNIQUE INDEX patients_cpf_key ON public.patients USING btree (cpf)
  ```
- **patients_phone_key**
  ```sql
  CREATE UNIQUE INDEX patients_phone_key ON public.patients USING btree (phone)
  ```
- **patients_pkey**
  ```sql
  CREATE UNIQUE INDEX patients_pkey ON public.patients USING btree (id)
  ```

#### Constraints

- **2200_19560_11_not_null** (CHECK)
- **2200_19560_12_not_null** (CHECK)
- **2200_19560_16_not_null** (CHECK)
- **2200_19560_17_not_null** (CHECK)
- **2200_19560_1_not_null** (CHECK)
- **2200_19560_2_not_null** (CHECK)
- **2200_19560_3_not_null** (CHECK)
- **2200_19560_4_not_null** (CHECK)
- **patients_cpf_key** (UNIQUE): cpf
- **patients_doctor_id_fkey** (FK): doctor_id → users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **patients_phone_key** (UNIQUE): phone
- **patients_pkey** (PK): id
- **valid_phone** (CHECK)

#### Triggers

- **update_patients_updated_at**
  - Timing: BEFORE
  - Event: UPDATE
  - Statement: `EXECUTE FUNCTION update_updated_at_column()...`

---

### users

**Descrição:** Profissionais de saúde (médicos e administradores) - Supports local and Firebase authentication

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 160 kB
- **Registros:** 1

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| email | character varying(255) | ✗ | - | - |
| hashed_password | character varying(255) | ✓ | - | Password hash - NULL for Firebase-only users |
| full_name | character varying(255) | ✓ | - | - |
| role | USER-DEFINED | ✗ | 'doctor'::user_role | - |
| is_active | boolean | ✗ | true | - |
| firebase_uid | character varying(255) | ✓ | - | Firebase user UID from Firebase Authentication |
| auth_provider | USER-DEFINED | ✗ | 'local'::auth_provider | Authentication provider: local (password) or firebase |
| firebase_last_sign_in | timestamp with time zone | ✓ | - | - |
| firebase_created_at | timestamp with time zone | ✓ | - | - |
| firebase_email_verified | boolean | ✗ | false | - |
| firebase_display_name | character varying(255) | ✓ | - | - |
| firebase_photo_url | character varying(500) | ✓ | - | - |
| firebase_custom_claims | jsonb | ✗ | '{}'::jsonb | Firebase custom claims including role (admin/doctor) and permissions |
| last_firebase_sync | timestamp with time zone | ✓ | - | Timestamp of last sync with Firebase Authentication |
| created_at | timestamp with time zone | ✗ | now() | - |
| updated_at | timestamp with time zone | ✗ | now() | - |

#### Índices

- **idx_users_auth_provider**
  ```sql
  CREATE INDEX idx_users_auth_provider ON public.users USING btree (auth_provider)
  ```
- **idx_users_email**
  ```sql
  CREATE INDEX idx_users_email ON public.users USING btree (email)
  ```
- **idx_users_firebase_uid**
  ```sql
  CREATE INDEX idx_users_firebase_uid ON public.users USING btree (firebase_uid) WHERE (firebase_uid IS NOT NULL)
  ```
- **idx_users_firebase_uid_active_new**
  ```sql
  CREATE INDEX idx_users_firebase_uid_active_new ON public.users USING btree (firebase_uid) WHERE (is_active = true)
  ```
- **idx_users_is_active**
  ```sql
  CREATE INDEX idx_users_is_active ON public.users USING btree (is_active)
  ```
- **idx_users_role**
  ```sql
  CREATE INDEX idx_users_role ON public.users USING btree (role)
  ```
- **users_email_key**
  ```sql
  CREATE UNIQUE INDEX users_email_key ON public.users USING btree (email)
  ```
- **users_firebase_uid_key**
  ```sql
  CREATE UNIQUE INDEX users_firebase_uid_key ON public.users USING btree (firebase_uid)
  ```
- **users_pkey**
  ```sql
  CREATE UNIQUE INDEX users_pkey ON public.users USING btree (id)
  ```

#### Constraints

- **2200_19535_11_not_null** (CHECK)
- **2200_19535_14_not_null** (CHECK)
- **2200_19535_16_not_null** (CHECK)
- **2200_19535_17_not_null** (CHECK)
- **2200_19535_1_not_null** (CHECK)
- **2200_19535_2_not_null** (CHECK)
- **2200_19535_5_not_null** (CHECK)
- **2200_19535_6_not_null** (CHECK)
- **2200_19535_8_not_null** (CHECK)
- **users_email_key** (UNIQUE): email
- **users_firebase_uid_key** (UNIQUE): firebase_uid
- **users_pkey** (PK): id
- **valid_email** (CHECK)

#### Triggers

- **update_users_updated_at**
  - Timing: BEFORE
  - Event: UPDATE
  - Statement: `EXECUTE FUNCTION update_updated_at_column()...`

---

## Grupo: PATIENT (1 tabelas)

### patient_flow_states

**Descrição:** Estado atual de cada paciente em cada tipo de fluxo

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 104 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| patient_id | uuid | ✗ | - | - |
| flow_template_version_id | uuid | ✗ | - | - |
| current_step | integer(32) | ✓ | 0 | - |
| step_data | jsonb | ✓ | '{}'::jsonb | - |
| status | character varying(50) | ✓ | 'active'::character varying | - |
| started_at | timestamp with time zone | ✓ | now() | - |
| last_interaction_at | timestamp with time zone | ✓ | now() | - |
| completed_at | timestamp with time zone | ✓ | - | - |
| next_scheduled_at | timestamp with time zone | ✓ | - | - |
| flow_metadata | jsonb | ✓ | '{}'::jsonb | - |
| created_at | timestamp with time zone | ✓ | now() | - |
| updated_at | timestamp with time zone | ✓ | now() | - |

#### Índices

- **idx_patient_flow_states_next_scheduled**
  ```sql
  CREATE INDEX idx_patient_flow_states_next_scheduled ON public.patient_flow_states USING btree (next_scheduled_at) WHERE (((status)::text = 'active'::text) AND (next_scheduled_at IS NOT NULL))
  ```
- **idx_patient_flow_states_patient**
  ```sql
  CREATE INDEX idx_patient_flow_states_patient ON public.patient_flow_states USING btree (patient_id)
  ```
- **idx_patient_flow_states_status**
  ```sql
  CREATE INDEX idx_patient_flow_states_status ON public.patient_flow_states USING btree (status, last_interaction_at)
  ```
- **idx_patient_flow_states_template**
  ```sql
  CREATE INDEX idx_patient_flow_states_template ON public.patient_flow_states USING btree (flow_template_version_id)
  ```
- **patient_flow_states_pkey**
  ```sql
  CREATE UNIQUE INDEX patient_flow_states_pkey ON public.patient_flow_states USING btree (id)
  ```
- **unique_patient_flow**
  ```sql
  CREATE UNIQUE INDEX unique_patient_flow ON public.patient_flow_states USING btree (patient_id, flow_template_version_id)
  ```

#### Constraints

- **2200_19724_1_not_null** (CHECK)
- **2200_19724_2_not_null** (CHECK)
- **2200_19724_3_not_null** (CHECK)
- **patient_flow_states_flow_template_version_id_fkey** (FK): flow_template_version_id → flow_template_versions.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **patient_flow_states_patient_id_fkey** (FK): patient_id → patients.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **patient_flow_states_pkey** (PK): id
- **unique_patient_flow** (UNIQUE): patient_id, patient_id, flow_template_version_id, flow_template_version_id
- **unique_patient_flow** (UNIQUE): patient_id, patient_id, flow_template_version_id, flow_template_version_id
- **unique_patient_flow** (UNIQUE): patient_id, patient_id, flow_template_version_id, flow_template_version_id
- **unique_patient_flow** (UNIQUE): patient_id, patient_id, flow_template_version_id, flow_template_version_id

---

## Grupo: PG (2 tabelas)

### pg_stat_statements

- **Schema:** public
- **Tipo:** VIEW
- **Tamanho:** 0 bytes
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| userid | oid | ✓ | - | - |
| dbid | oid | ✓ | - | - |
| toplevel | boolean | ✓ | - | - |
| queryid | bigint(64) | ✓ | - | - |
| query | text | ✓ | - | - |
| plans | bigint(64) | ✓ | - | - |
| total_plan_time | double precision(53) | ✓ | - | - |
| min_plan_time | double precision(53) | ✓ | - | - |
| max_plan_time | double precision(53) | ✓ | - | - |
| mean_plan_time | double precision(53) | ✓ | - | - |
| stddev_plan_time | double precision(53) | ✓ | - | - |
| calls | bigint(64) | ✓ | - | - |
| total_exec_time | double precision(53) | ✓ | - | - |
| min_exec_time | double precision(53) | ✓ | - | - |
| max_exec_time | double precision(53) | ✓ | - | - |
| mean_exec_time | double precision(53) | ✓ | - | - |
| stddev_exec_time | double precision(53) | ✓ | - | - |
| rows | bigint(64) | ✓ | - | - |
| shared_blks_hit | bigint(64) | ✓ | - | - |
| shared_blks_read | bigint(64) | ✓ | - | - |
| shared_blks_dirtied | bigint(64) | ✓ | - | - |
| shared_blks_written | bigint(64) | ✓ | - | - |
| local_blks_hit | bigint(64) | ✓ | - | - |
| local_blks_read | bigint(64) | ✓ | - | - |
| local_blks_dirtied | bigint(64) | ✓ | - | - |
| local_blks_written | bigint(64) | ✓ | - | - |
| temp_blks_read | bigint(64) | ✓ | - | - |
| temp_blks_written | bigint(64) | ✓ | - | - |
| shared_blk_read_time | double precision(53) | ✓ | - | - |
| shared_blk_write_time | double precision(53) | ✓ | - | - |
| local_blk_read_time | double precision(53) | ✓ | - | - |
| local_blk_write_time | double precision(53) | ✓ | - | - |
| temp_blk_read_time | double precision(53) | ✓ | - | - |
| temp_blk_write_time | double precision(53) | ✓ | - | - |
| wal_records | bigint(64) | ✓ | - | - |
| wal_fpi | bigint(64) | ✓ | - | - |
| wal_bytes | numeric | ✓ | - | - |
| jit_functions | bigint(64) | ✓ | - | - |
| jit_generation_time | double precision(53) | ✓ | - | - |
| jit_inlining_count | bigint(64) | ✓ | - | - |
| jit_inlining_time | double precision(53) | ✓ | - | - |
| jit_optimization_count | bigint(64) | ✓ | - | - |
| jit_optimization_time | double precision(53) | ✓ | - | - |
| jit_emission_count | bigint(64) | ✓ | - | - |
| jit_emission_time | double precision(53) | ✓ | - | - |
| jit_deform_count | bigint(64) | ✓ | - | - |
| jit_deform_time | double precision(53) | ✓ | - | - |
| stats_since | timestamp with time zone | ✓ | - | - |
| minmax_stats_since | timestamp with time zone | ✓ | - | - |

---

### pg_stat_statements_info

- **Schema:** public
- **Tipo:** VIEW
- **Tamanho:** 0 bytes
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| dealloc | bigint(64) | ✓ | - | - |
| stats_reset | timestamp with time zone | ✓ | - | - |

---

## Grupo: QUIZ (5 tabelas)

### quiz_responses

**Descrição:** Respostas individuais de questionários

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 72 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| patient_id | uuid | ✗ | - | - |
| quiz_template_id | uuid | ✗ | - | - |
| quiz_session_id | uuid | ✓ | - | - |
| question_id | character varying(100) | ✗ | - | - |
| question_text | text | ✗ | - | - |
| response_type | character varying(50) | ✗ | - | - |
| response_value | text | ✗ | - | - |
| is_correct | boolean | ✓ | - | - |
| points_earned | numeric(5,2) | ✓ | - | - |
| response_metadata | jsonb | ✓ | '{}'::jsonb | - |
| responded_at | timestamp with time zone | ✗ | - | - |
| response_time_seconds | integer(32) | ✓ | - | - |
| created_at | timestamp with time zone | ✗ | now() | - |
| updated_at | timestamp with time zone | ✗ | now() | - |
| other_text | text | ✓ | - | - |

#### Índices

- **idx_quiz_response_analytics_covering_index**
  ```sql
  CREATE INDEX idx_quiz_response_analytics_covering_index ON public.quiz_responses USING btree (quiz_template_id, question_id, response_value, responded_at)
  ```
- **idx_quiz_response_patient_template_index**
  ```sql
  CREATE INDEX idx_quiz_response_patient_template_index ON public.quiz_responses USING btree (patient_id, quiz_template_id, responded_at DESC)
  ```
- **idx_quiz_response_session_id**
  ```sql
  CREATE INDEX idx_quiz_response_session_id ON public.quiz_responses USING btree (quiz_session_id)
  ```
- **idx_quiz_responses_patient_created_new**
  ```sql
  CREATE INDEX idx_quiz_responses_patient_created_new ON public.quiz_responses USING btree (patient_id, created_at DESC)
  ```
- **idx_quiz_responses_patient_id**
  ```sql
  CREATE INDEX idx_quiz_responses_patient_id ON public.quiz_responses USING btree (patient_id)
  ```
- **idx_quiz_responses_quiz_template_id**
  ```sql
  CREATE INDEX idx_quiz_responses_quiz_template_id ON public.quiz_responses USING btree (quiz_template_id)
  ```
- **idx_quiz_responses_responded_at**
  ```sql
  CREATE INDEX idx_quiz_responses_responded_at ON public.quiz_responses USING btree (responded_at)
  ```
- **quiz_responses_pkey**
  ```sql
  CREATE UNIQUE INDEX quiz_responses_pkey ON public.quiz_responses USING btree (id)
  ```

#### Constraints

- **2200_19975_12_not_null** (CHECK)
- **2200_19975_14_not_null** (CHECK)
- **2200_19975_15_not_null** (CHECK)
- **2200_19975_1_not_null** (CHECK)
- **2200_19975_2_not_null** (CHECK)
- **2200_19975_3_not_null** (CHECK)
- **2200_19975_5_not_null** (CHECK)
- **2200_19975_6_not_null** (CHECK)
- **2200_19975_7_not_null** (CHECK)
- **2200_19975_8_not_null** (CHECK)
- **quiz_responses_patient_id_fkey** (FK): patient_id → patients.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **quiz_responses_pkey** (PK): id
- **quiz_responses_quiz_template_id_fkey** (FK): quiz_template_id → quiz_templates.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **quiz_responses_session_id_fkey** (FK): quiz_session_id → quiz_sessions.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION

#### Triggers

- **update_quiz_responses_updated_at**
  - Timing: BEFORE
  - Event: UPDATE
  - Statement: `EXECUTE FUNCTION update_updated_at_column()...`

---

### quiz_sessions

**Descrição:** Sessões de questionários respondidos por pacientes (Schema v2 - status-based)

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 184 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| patient_id | uuid | ✗ | - | - |
| quiz_template_id | uuid | ✗ | - | - |
| status | character varying(50) | ✗ | 'started'::character varying | - |
| current_question | integer(32) | ✓ | 0 | - |
| total_questions | integer(32) | ✓ | - | - |
| answered_questions | integer(32) | ✓ | 0 | - |
| score | numeric(5,2) | ✓ | - | - |
| max_score | numeric(5,2) | ✓ | - | - |
| passed | boolean | ✓ | - | - |
| started_at | timestamp with time zone | ✗ | now() | - |
| completed_at | timestamp with time zone | ✓ | - | - |
| time_spent_seconds | integer(32) | ✓ | - | - |
| session_metadata | jsonb | ✓ | '{}'::jsonb | - |
| created_at | timestamp with time zone | ✗ | now() | - |
| updated_at | timestamp with time zone | ✗ | now() | - |

#### Índices

- **idx_quiz_session_unique_active**
  ```sql
  CREATE UNIQUE INDEX idx_quiz_session_unique_active ON public.quiz_sessions USING btree (patient_id, quiz_template_id) WHERE ((status)::text = 'started'::text)
  ```
- **idx_quiz_sessions_completed_at_v2**
  ```sql
  CREATE INDEX idx_quiz_sessions_completed_at_v2 ON public.quiz_sessions USING btree (completed_at DESC) WHERE (completed_at IS NOT NULL)
  ```
- **idx_quiz_sessions_created_at_v2**
  ```sql
  CREATE INDEX idx_quiz_sessions_created_at_v2 ON public.quiz_sessions USING btree (created_at DESC)
  ```
- **idx_quiz_sessions_patient_id_v2**
  ```sql
  CREATE INDEX idx_quiz_sessions_patient_id_v2 ON public.quiz_sessions USING btree (patient_id)
  ```
- **idx_quiz_sessions_patient_started_desc**
  ```sql
  CREATE INDEX idx_quiz_sessions_patient_started_desc ON public.quiz_sessions USING btree (patient_id, started_at DESC) WHERE (session_metadata IS NOT NULL)
  ```
- **idx_quiz_sessions_patient_status_v2**
  ```sql
  CREATE INDEX idx_quiz_sessions_patient_status_v2 ON public.quiz_sessions USING btree (patient_id, status)
  ```
- **idx_quiz_sessions_patient_template_v2**
  ```sql
  CREATE INDEX idx_quiz_sessions_patient_template_v2 ON public.quiz_sessions USING btree (patient_id, quiz_template_id, started_at DESC)
  ```
- **idx_quiz_sessions_quiz_template_id_v2**
  ```sql
  CREATE INDEX idx_quiz_sessions_quiz_template_id_v2 ON public.quiz_sessions USING btree (quiz_template_id)
  ```
- **idx_quiz_sessions_status_v2**
  ```sql
  CREATE INDEX idx_quiz_sessions_status_v2 ON public.quiz_sessions USING btree (status)
  ```
- **idx_quiz_sessions_template_status_v2**
  ```sql
  CREATE INDEX idx_quiz_sessions_template_status_v2 ON public.quiz_sessions USING btree (quiz_template_id, status)
  ```
- **quiz_sessions_pkey**
  ```sql
  CREATE UNIQUE INDEX quiz_sessions_pkey ON public.quiz_sessions USING btree (id)
  ```

#### Constraints

- **2200_19916_11_not_null** (CHECK)
- **2200_19916_15_not_null** (CHECK)
- **2200_19916_16_not_null** (CHECK)
- **2200_19916_1_not_null** (CHECK)
- **2200_19916_2_not_null** (CHECK)
- **2200_19916_3_not_null** (CHECK)
- **2200_19916_4_not_null** (CHECK)
- **quiz_sessions_patient_id_fkey** (FK): patient_id → patients.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **quiz_sessions_pkey** (PK): id
- **quiz_sessions_quiz_template_id_fkey** (FK): quiz_template_id → quiz_templates.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **quiz_sessions_status_check** (CHECK)

#### Triggers

- **update_quiz_sessions_updated_at**
  - Timing: BEFORE
  - Event: UPDATE
  - Statement: `EXECUTE FUNCTION update_updated_at_column()...`

---

### quiz_sessions_v2

**Descrição:** Versão melhorada de sessões com suporte a versionamento

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 32 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| patient_id | uuid | ✗ | - | - |
| template_version_id | uuid | ✗ | - | - |
| status | character varying(50) | ✓ | 'started'::character varying | - |
| started_at | timestamp with time zone | ✓ | now() | - |
| completed_at | timestamp with time zone | ✓ | - | - |
| session_data | jsonb | ✓ | '{}'::jsonb | - |
| created_at | timestamp with time zone | ✓ | now() | - |

#### Índices

- **idx_quiz_sessions_v2_patient**
  ```sql
  CREATE INDEX idx_quiz_sessions_v2_patient ON public.quiz_sessions_v2 USING btree (patient_id)
  ```
- **idx_quiz_sessions_v2_template_version**
  ```sql
  CREATE INDEX idx_quiz_sessions_v2_template_version ON public.quiz_sessions_v2 USING btree (template_version_id)
  ```
- **quiz_sessions_v2_pkey**
  ```sql
  CREATE UNIQUE INDEX quiz_sessions_v2_pkey ON public.quiz_sessions_v2 USING btree (id)
  ```

#### Constraints

- **2200_19951_1_not_null** (CHECK)
- **2200_19951_2_not_null** (CHECK)
- **2200_19951_3_not_null** (CHECK)
- **quiz_sessions_v2_patient_id_fkey** (FK): patient_id → patients.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **quiz_sessions_v2_pkey** (PK): id
- **quiz_sessions_v2_template_version_id_fkey** (FK): template_version_id → quiz_template_versions_v2.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION

---

### quiz_template_versions_v2

**Descrição:** Sistema de versionamento aprimorado de questionários

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 40 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| template_id | uuid | ✗ | - | - |
| version_number | integer(32) | ✗ | - | - |
| questions | jsonb | ✗ | - | - |
| scoring_rules | jsonb | ✓ | - | - |
| is_active | boolean | ✓ | false | - |
| is_draft | boolean | ✓ | true | - |
| published_at | timestamp with time zone | ✓ | - | - |
| created_by | uuid | ✓ | - | - |
| change_notes | text | ✓ | - | - |
| created_at | timestamp with time zone | ✓ | now() | - |

#### Índices

- **idx_quiz_template_versions_v2_active**
  ```sql
  CREATE INDEX idx_quiz_template_versions_v2_active ON public.quiz_template_versions_v2 USING btree (template_id, is_active) WHERE (is_active = true)
  ```
- **idx_quiz_template_versions_v2_template**
  ```sql
  CREATE INDEX idx_quiz_template_versions_v2_template ON public.quiz_template_versions_v2 USING btree (template_id)
  ```
- **quiz_template_versions_v2_pkey**
  ```sql
  CREATE UNIQUE INDEX quiz_template_versions_v2_pkey ON public.quiz_template_versions_v2 USING btree (id)
  ```
- **unique_template_version**
  ```sql
  CREATE UNIQUE INDEX unique_template_version ON public.quiz_template_versions_v2 USING btree (template_id, version_number)
  ```

#### Constraints

- **2200_19891_1_not_null** (CHECK)
- **2200_19891_2_not_null** (CHECK)
- **2200_19891_3_not_null** (CHECK)
- **2200_19891_4_not_null** (CHECK)
- **quiz_template_versions_v2_created_by_fkey** (FK): created_by → users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **quiz_template_versions_v2_pkey** (PK): id
- **quiz_template_versions_v2_template_id_fkey** (FK): template_id → quiz_templates.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **unique_template_version** (UNIQUE): template_id, template_id, version_number, version_number
- **unique_template_version** (UNIQUE): template_id, template_id, version_number, version_number
- **unique_template_version** (UNIQUE): template_id, template_id, version_number, version_number
- **unique_template_version** (UNIQUE): template_id, template_id, version_number, version_number

---

### quiz_templates

**Descrição:** Templates de questionários para pacientes

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 80 kB
- **Registros:** 1

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| name | character varying(255) | ✗ | - | - |
| version | character varying(50) | ✗ | - | - |
| description | text | ✓ | - | - |
| questions | jsonb | ✗ | - | - |
| is_active | boolean | ✗ | true | - |
| category | character varying(100) | ✓ | - | - |
| tags | ARRAY | ✓ | - | - |
| passing_score | integer(32) | ✓ | - | - |
| time_limit_minutes | integer(32) | ✓ | - | - |
| randomize_questions | boolean | ✓ | false | - |
| created_at | timestamp with time zone | ✗ | now() | - |
| updated_at | timestamp with time zone | ✗ | now() | - |

#### Índices

- **idx_quiz_templates_category**
  ```sql
  CREATE INDEX idx_quiz_templates_category ON public.quiz_templates USING btree (category)
  ```
- **idx_quiz_templates_is_active**
  ```sql
  CREATE INDEX idx_quiz_templates_is_active ON public.quiz_templates USING btree (is_active)
  ```
- **quiz_templates_pkey**
  ```sql
  CREATE UNIQUE INDEX quiz_templates_pkey ON public.quiz_templates USING btree (id)
  ```

#### Constraints

- **2200_19877_12_not_null** (CHECK)
- **2200_19877_13_not_null** (CHECK)
- **2200_19877_1_not_null** (CHECK)
- **2200_19877_2_not_null** (CHECK)
- **2200_19877_3_not_null** (CHECK)
- **2200_19877_5_not_null** (CHECK)
- **2200_19877_6_not_null** (CHECK)
- **quiz_templates_pkey** (PK): id

#### Triggers

- **update_quiz_templates_updated_at**
  - Timing: BEFORE
  - Event: UPDATE
  - Statement: `EXECUTE FUNCTION update_updated_at_column()...`

---

## Grupo: SECURITY (1 tabelas)

### security_audit_log

**Descrição:** Security audit log for WhatsApp access monitoring and threat detection

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 120 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| event_type | character varying(100) | ✗ | - | - |
| phone_number | character varying(20) | ✗ | - | - |
| patient_id | uuid | ✓ | - | - |
| message_content | text | ✓ | - | - |
| source_metadata | jsonb | ✓ | - | - |
| risk_score | integer(32) | ✗ | 0 | - |
| ip_address | character varying(45) | ✓ | - | - |
| user_agent | character varying(500) | ✓ | - | - |
| session_id | character varying(32) | ✓ | - | - |
| created_at | timestamp with time zone | ✗ | CURRENT_TIMESTAMP | - |
| additional_data | jsonb | ✓ | - | - |
| alert_sent | boolean | ✗ | false | - |

#### Índices

- **idx_security_audit_additional_data_gin**
  ```sql
  CREATE INDEX idx_security_audit_additional_data_gin ON public.security_audit_log USING gin (additional_data)
  ```
- **idx_security_audit_created_at**
  ```sql
  CREATE INDEX idx_security_audit_created_at ON public.security_audit_log USING btree (created_at)
  ```
- **idx_security_audit_event_type**
  ```sql
  CREATE INDEX idx_security_audit_event_type ON public.security_audit_log USING btree (event_type)
  ```
- **idx_security_audit_ip_address**
  ```sql
  CREATE INDEX idx_security_audit_ip_address ON public.security_audit_log USING btree (ip_address)
  ```
- **idx_security_audit_patient_id**
  ```sql
  CREATE INDEX idx_security_audit_patient_id ON public.security_audit_log USING btree (patient_id)
  ```
- **idx_security_audit_phone_event_time**
  ```sql
  CREATE INDEX idx_security_audit_phone_event_time ON public.security_audit_log USING btree (phone_number, event_type, created_at)
  ```
- **idx_security_audit_phone_number**
  ```sql
  CREATE INDEX idx_security_audit_phone_number ON public.security_audit_log USING btree (phone_number)
  ```
- **idx_security_audit_risk_score**
  ```sql
  CREATE INDEX idx_security_audit_risk_score ON public.security_audit_log USING btree (risk_score)
  ```
- **idx_security_audit_risk_time**
  ```sql
  CREATE INDEX idx_security_audit_risk_time ON public.security_audit_log USING btree (risk_score, created_at)
  ```
- **idx_security_audit_session_id**
  ```sql
  CREATE INDEX idx_security_audit_session_id ON public.security_audit_log USING btree (session_id)
  ```
- **idx_security_audit_source_metadata_gin**
  ```sql
  CREATE INDEX idx_security_audit_source_metadata_gin ON public.security_audit_log USING gin (source_metadata)
  ```
- **security_audit_log_pkey**
  ```sql
  CREATE UNIQUE INDEX security_audit_log_pkey ON public.security_audit_log USING btree (id)
  ```

#### Constraints

- **2200_22501_11_not_null** (CHECK)
- **2200_22501_13_not_null** (CHECK)
- **2200_22501_1_not_null** (CHECK)
- **2200_22501_2_not_null** (CHECK)
- **2200_22501_3_not_null** (CHECK)
- **2200_22501_7_not_null** (CHECK)
- **fk_security_audit_patient** (FK): patient_id → patients.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **security_audit_log_pkey** (PK): id

---

## Grupo: USER (2 tabelas)

### user_profiles

**Descrição:** Perfis estendidos de usuários profissionais

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 32 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| user_id | uuid | ✗ | - | - |
| bio | text | ✓ | - | - |
| avatar_url | character varying(500) | ✓ | - | - |
| phone | character varying(20) | ✓ | - | - |
| specialty | character varying(255) | ✓ | - | - |
| license_number | character varying(100) | ✓ | - | - |
| years_of_experience | integer(32) | ✓ | - | - |
| preferences | jsonb | ✓ | '{}'::jsonb | - |
| notification_settings | jsonb | ✓ | '{}'::jsonb | - |
| created_at | timestamp with time zone | ✓ | now() | - |
| updated_at | timestamp with time zone | ✓ | now() | - |

#### Índices

- **idx_user_profiles_user_id**
  ```sql
  CREATE INDEX idx_user_profiles_user_id ON public.user_profiles USING btree (user_id)
  ```
- **user_profiles_pkey**
  ```sql
  CREATE UNIQUE INDEX user_profiles_pkey ON public.user_profiles USING btree (id)
  ```
- **user_profiles_user_id_key**
  ```sql
  CREATE UNIQUE INDEX user_profiles_user_id_key ON public.user_profiles USING btree (user_id)
  ```

#### Constraints

- **2200_20330_1_not_null** (CHECK)
- **2200_20330_2_not_null** (CHECK)
- **user_profiles_pkey** (PK): id
- **user_profiles_user_id_fkey** (FK): user_id → users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION
- **user_profiles_user_id_key** (UNIQUE): user_id

---

### user_sync_log

**Descrição:** Log de sincronização Firebase ↔ Supabase

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 48 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| firebase_uid | character varying(255) | ✗ | - | - |
| supabase_user_id | uuid | ✓ | - | - |
| sync_action | character varying(50) | ✗ | - | - |
| sync_status | character varying(50) | ✗ | - | - |
| firebase_data | jsonb | ✓ | - | - |
| supabase_data | jsonb | ✓ | - | - |
| error_message | text | ✓ | - | - |
| retry_count | integer(32) | ✓ | 0 | - |
| synced_at | timestamp with time zone | ✓ | now() | - |
| created_at | timestamp with time zone | ✓ | now() | - |
| updated_at | timestamp with time zone | ✗ | now() | Auto-updated timestamp for record modifications (added 2025-10-06) |

#### Índices

- **idx_user_sync_log_firebase_uid**
  ```sql
  CREATE INDEX idx_user_sync_log_firebase_uid ON public.user_sync_log USING btree (firebase_uid)
  ```
- **idx_user_sync_log_status**
  ```sql
  CREATE INDEX idx_user_sync_log_status ON public.user_sync_log USING btree (sync_status, synced_at)
  ```
- **idx_user_sync_log_supabase_user**
  ```sql
  CREATE INDEX idx_user_sync_log_supabase_user ON public.user_sync_log USING btree (supabase_user_id)
  ```
- **idx_user_sync_log_updated_at**
  ```sql
  CREATE INDEX idx_user_sync_log_updated_at ON public.user_sync_log USING btree (updated_at)
  ```
- **user_sync_log_pkey**
  ```sql
  CREATE UNIQUE INDEX user_sync_log_pkey ON public.user_sync_log USING btree (id)
  ```

#### Constraints

- **2200_20350_12_not_null** (CHECK)
- **2200_20350_1_not_null** (CHECK)
- **2200_20350_2_not_null** (CHECK)
- **2200_20350_4_not_null** (CHECK)
- **2200_20350_5_not_null** (CHECK)
- **user_sync_log_pkey** (PK): id
- **user_sync_log_supabase_user_id_fkey** (FK): supabase_user_id → users.id
  - ON DELETE: NO ACTION
  - ON UPDATE: NO ACTION

#### Triggers

- **trigger_user_sync_log_updated_at**
  - Timing: BEFORE
  - Event: UPDATE
  - Statement: `EXECUTE FUNCTION update_user_sync_log_updated_at()...`

---

## Grupo: WEBHOOK (1 tabelas)

### webhook_events

**Descrição:** Armazenamento e replay de webhooks da Evolution API

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 72 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| event_type | character varying(100) | ✗ | - | - |
| source | character varying(100) | ✗ | 'evolution_api'::character varying | - |
| payload | jsonb | ✗ | - | - |
| processed | boolean | ✗ | false | - |
| processed_at | timestamp with time zone | ✓ | - | - |
| retry_count | integer(32) | ✓ | 0 | - |
| max_retries | integer(32) | ✓ | 3 | - |
| next_retry_at | timestamp with time zone | ✓ | - | - |
| error_message | text | ✓ | - | - |
| error_stack_trace | text | ✓ | - | - |
| related_message_id | uuid | ✓ | - | - |
| related_patient_id | uuid | ✓ | - | - |
| event_hash | character varying(64) | ✗ | - | - |
| is_duplicate | boolean | ✓ | false | - |
| original_event_id | uuid | ✓ | - | - |
| created_at | timestamp with time zone | ✗ | now() | - |

#### Índices

- **idx_webhook_pending**
  ```sql
  CREATE INDEX idx_webhook_pending ON public.webhook_events USING btree (processed, retry_count, created_at) WHERE (NOT processed)
  ```
- **idx_webhook_related_msg**
  ```sql
  CREATE INDEX idx_webhook_related_msg ON public.webhook_events USING btree (related_message_id, event_type)
  ```
- **idx_webhook_related_patient**
  ```sql
  CREATE INDEX idx_webhook_related_patient ON public.webhook_events USING btree (related_patient_id, event_type)
  ```
- **idx_webhook_retry_schedule**
  ```sql
  CREATE INDEX idx_webhook_retry_schedule ON public.webhook_events USING btree (processed, next_retry_at) WHERE ((NOT processed) AND (retry_count < max_retries))
  ```
- **idx_webhook_source_time**
  ```sql
  CREATE INDEX idx_webhook_source_time ON public.webhook_events USING btree (source, created_at)
  ```
- **idx_webhook_type_processed**
  ```sql
  CREATE INDEX idx_webhook_type_processed ON public.webhook_events USING btree (event_type, processed, created_at)
  ```
- **webhook_events_event_hash_key**
  ```sql
  CREATE UNIQUE INDEX webhook_events_event_hash_key ON public.webhook_events USING btree (event_hash)
  ```
- **webhook_events_pkey**
  ```sql
  CREATE UNIQUE INDEX webhook_events_pkey ON public.webhook_events USING btree (id)
  ```

#### Constraints

- **2200_19633_14_not_null** (CHECK)
- **2200_19633_17_not_null** (CHECK)
- **2200_19633_1_not_null** (CHECK)
- **2200_19633_2_not_null** (CHECK)
- **2200_19633_3_not_null** (CHECK)
- **2200_19633_4_not_null** (CHECK)
- **2200_19633_5_not_null** (CHECK)
- **webhook_events_event_hash_key** (UNIQUE): event_hash
- **webhook_events_pkey** (PK): id

---

## Grupo: WHATSAPP (4 tabelas)

### whatsapp_contacts

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 32 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | text | ✗ | - | - |
| instance_name | text | ✗ | - | - |
| phone_number | text | ✗ | - | - |
| formatted_number | text | ✗ | - | - |
| name | text | ✓ | - | - |
| profile_picture_url | text | ✓ | - | - |
| is_whatsapp_user | boolean | ✓ | true | - |
| last_seen | timestamp without time zone | ✓ | - | - |
| created_at | timestamp without time zone | ✓ | now() | - |
| updated_at | timestamp without time zone | ✓ | now() | - |
| contact_data | json | ✓ | - | - |

#### Índices

- **ix_whatsapp_contacts_instance**
  ```sql
  CREATE INDEX ix_whatsapp_contacts_instance ON public.whatsapp_contacts USING btree (instance_name)
  ```
- **ix_whatsapp_contacts_phone**
  ```sql
  CREATE INDEX ix_whatsapp_contacts_phone ON public.whatsapp_contacts USING btree (phone_number)
  ```
- **whatsapp_contacts_pkey**
  ```sql
  CREATE UNIQUE INDEX whatsapp_contacts_pkey ON public.whatsapp_contacts USING btree (id)
  ```

#### Constraints

- **2200_22711_1_not_null** (CHECK)
- **2200_22711_2_not_null** (CHECK)
- **2200_22711_3_not_null** (CHECK)
- **2200_22711_4_not_null** (CHECK)
- **whatsapp_contacts_pkey** (PK): id

---

### whatsapp_delivery_failures

**Descrição:** Dead Letter Queue (DLQ) para falhas de envio de mensagens WhatsApp.

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 40 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | uuid | ✗ | gen_random_uuid() | - |
| patient_id | uuid | ✗ | - | - |
| phone_number | character varying(20) | ✗ | - | - |
| message_type | character varying(50) | ✗ | - | - |
| message_content | text | ✓ | - | - |
| error_message | text | ✗ | - | - |
| error_code | character varying(50) | ✓ | - | - |
| retry_count | integer(32) | ✗ | 0 | - |
| max_retries | integer(32) | ✗ | 3 | - |
| next_retry_at | timestamp with time zone | ✓ | - | - |
| last_retry_at | timestamp with time zone | ✓ | - | - |
| status | character varying(20) | ✗ | 'pending'::character varying | Status do item na fila: pending | retrying | failed | resolved. |
| resolved_at | timestamp with time zone | ✓ | - | - |
| dlq_metadata | jsonb | ✓ | '{}'::jsonb | Additional failure information in JSONB format (renamed from metadata to avoid SQLAlchemy conflicts) |
| reviewed_by | uuid | ✓ | - | - |
| original_message_id | uuid | ✓ | - | - |
| created_at | timestamp with time zone | ✗ | timezone('utc'::text, now()) | - |
| updated_at | timestamp with time zone | ✗ | timezone('utc'::text, now()) | - |

#### Índices

- **idx_whatsapp_delivery_failures_created_at**
  ```sql
  CREATE INDEX idx_whatsapp_delivery_failures_created_at ON public.whatsapp_delivery_failures USING btree (created_at DESC)
  ```
- **idx_whatsapp_delivery_failures_patient**
  ```sql
  CREATE INDEX idx_whatsapp_delivery_failures_patient ON public.whatsapp_delivery_failures USING btree (patient_id)
  ```
- **idx_whatsapp_delivery_failures_status_nextretry**
  ```sql
  CREATE INDEX idx_whatsapp_delivery_failures_status_nextretry ON public.whatsapp_delivery_failures USING btree (status, next_retry_at)
  ```
- **whatsapp_delivery_failures_pkey**
  ```sql
  CREATE UNIQUE INDEX whatsapp_delivery_failures_pkey ON public.whatsapp_delivery_failures USING btree (id)
  ```

#### Constraints

- **2200_22747_12_not_null** (CHECK)
- **2200_22747_17_not_null** (CHECK)
- **2200_22747_18_not_null** (CHECK)
- **2200_22747_1_not_null** (CHECK)
- **2200_22747_2_not_null** (CHECK)
- **2200_22747_3_not_null** (CHECK)
- **2200_22747_4_not_null** (CHECK)
- **2200_22747_6_not_null** (CHECK)
- **2200_22747_8_not_null** (CHECK)
- **2200_22747_9_not_null** (CHECK)
- **whatsapp_delivery_failures_original_message_id_fkey** (FK): original_message_id → messages.id
  - ON DELETE: SET NULL
  - ON UPDATE: NO ACTION
- **whatsapp_delivery_failures_patient_id_fkey** (FK): patient_id → patients.id
  - ON DELETE: CASCADE
  - ON UPDATE: NO ACTION
- **whatsapp_delivery_failures_pkey** (PK): id
- **whatsapp_delivery_failures_reviewed_by_fkey** (FK): reviewed_by → users.id
  - ON DELETE: SET NULL
  - ON UPDATE: NO ACTION
- **whatsapp_delivery_failures_status_check** (CHECK)

#### Triggers

- **trg_whatsapp_delivery_failures_updated_at**
  - Timing: BEFORE
  - Event: UPDATE
  - Statement: `EXECUTE FUNCTION update_updated_at_column()...`

---

### whatsapp_instances

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 64 kB
- **Registros:** 1

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | text | ✗ | - | - |
| name | text | ✗ | - | - |
| status | text | ✓ | 'disconnected'::text | - |
| qr_code | text | ✓ | - | - |
| webhook_url | text | ✓ | - | - |
| phone_number | text | ✓ | - | - |
| profile_name | text | ✓ | - | - |
| profile_picture_url | text | ✓ | - | - |
| is_connected | boolean | ✓ | false | - |
| created_at | timestamp without time zone | ✓ | now() | - |
| updated_at | timestamp without time zone | ✓ | now() | - |
| last_activity | timestamp without time zone | ✓ | - | - |
| settings | json | ✓ | - | - |

#### Índices

- **ix_whatsapp_instances_name**
  ```sql
  CREATE INDEX ix_whatsapp_instances_name ON public.whatsapp_instances USING btree (name)
  ```
- **whatsapp_instances_name_key**
  ```sql
  CREATE UNIQUE INDEX whatsapp_instances_name_key ON public.whatsapp_instances USING btree (name)
  ```
- **whatsapp_instances_pkey**
  ```sql
  CREATE UNIQUE INDEX whatsapp_instances_pkey ON public.whatsapp_instances USING btree (id)
  ```

#### Constraints

- **2200_22723_1_not_null** (CHECK)
- **2200_22723_2_not_null** (CHECK)
- **whatsapp_instances_name_key** (UNIQUE): name
- **whatsapp_instances_pkey** (PK): id

---

### whatsapp_messages

- **Schema:** public
- **Tipo:** BASE TABLE
- **Tamanho:** 48 kB
- **Registros:** 0

#### Colunas

| Coluna | Tipo | Nullable | Default | Comentário |
|--------|------|----------|---------|------------|
| id | text | ✗ | - | - |
| instance_name | text | ✗ | - | - |
| chat_id | text | ✗ | - | - |
| sender_id | text | ✗ | - | - |
| recipient_id | text | ✗ | - | - |
| message_type | text | ✗ | - | - |
| content | text | ✓ | - | - |
| media_url | text | ✓ | - | - |
| media_caption | text | ✓ | - | - |
| status | text | ✓ | 'pending'::text | - |
| external_id | text | ✓ | - | - |
| created_at | timestamp without time zone | ✓ | now() | - |
| updated_at | timestamp without time zone | ✓ | now() | - |
| sent_at | timestamp without time zone | ✓ | - | - |
| delivered_at | timestamp without time zone | ✓ | - | - |
| read_at | timestamp without time zone | ✓ | - | - |
| failed_at | timestamp without time zone | ✓ | - | - |
| retry_count | integer(32) | ✓ | 0 | - |
| error_message | text | ✓ | - | - |
| message_data | json | ✓ | - | - |

#### Índices

- **ix_whatsapp_messages_chat**
  ```sql
  CREATE INDEX ix_whatsapp_messages_chat ON public.whatsapp_messages USING btree (chat_id)
  ```
- **ix_whatsapp_messages_external**
  ```sql
  CREATE INDEX ix_whatsapp_messages_external ON public.whatsapp_messages USING btree (external_id)
  ```
- **ix_whatsapp_messages_instance**
  ```sql
  CREATE INDEX ix_whatsapp_messages_instance ON public.whatsapp_messages USING btree (instance_name)
  ```
- **whatsapp_messages_external_id_key**
  ```sql
  CREATE UNIQUE INDEX whatsapp_messages_external_id_key ON public.whatsapp_messages USING btree (external_id)
  ```
- **whatsapp_messages_pkey**
  ```sql
  CREATE UNIQUE INDEX whatsapp_messages_pkey ON public.whatsapp_messages USING btree (id)
  ```

#### Constraints

- **2200_22695_1_not_null** (CHECK)
- **2200_22695_2_not_null** (CHECK)
- **2200_22695_3_not_null** (CHECK)
- **2200_22695_4_not_null** (CHECK)
- **2200_22695_5_not_null** (CHECK)
- **2200_22695_6_not_null** (CHECK)
- **whatsapp_messages_external_id_key** (UNIQUE): external_id
- **whatsapp_messages_pkey** (PK): id

---

## 👁️ Views

Total de views: **2**

### pg_stat_statements

- **Schema:** public
- **Updatable:** ✗
- **Insertable:** ✗

---

### pg_stat_statements_info

- **Schema:** public
- **Updatable:** ✗
- **Insertable:** ✗

---

## 📊 Materialized Views

Total de materialized views: **5**

### quiz_daily_activity_summary

- **Schema:** public
- **Populated:** ✓

**Definição:**
```sql
 SELECT date(started_at) AS activity_date,
    count(DISTINCT patient_id) AS unique_patients,
    count(id) AS total_sessions_started,
    count(id) FILTER (WHERE ((status)::text = 'completed'::text)) AS sessions_completed,
    count(id) FILTER (WHERE ((status)::text = 'cancelled'::text)) AS sessions_cancelled,
    count(DISTINCT quiz_template_id) AS unique_templates_used,
    avg(score) FILTER (WHERE ((status)::text = 'completed'::text)) AS avg_score,
    avg(time_spent_seconds) FILTER (WHERE (...
```

---

### quiz_patient_engagement_stats

- **Schema:** public
- **Populated:** ✓

**Definição:**
```sql
 SELECT p.id AS patient_id,
    p.name AS patient_name,
    count(qs.id) AS total_sessions,
    count(qs.id) FILTER (WHERE ((qs.status)::text = 'completed'::text)) AS completed_sessions,
    count(qs.id) FILTER (WHERE ((qs.status)::text = 'started'::text)) AS active_sessions,
    avg(qs.score) FILTER (WHERE ((qs.status)::text = 'completed'::text)) AS avg_score,
    avg(qs.time_spent_seconds) FILTER (WHERE ((qs.status)::text = 'completed'::text)) AS avg_completion_time_seconds,
    max(qs.started...
```

---

### quiz_patient_latest_responses

- **Schema:** public
- **Populated:** ✓

**Definição:**
```sql
 SELECT DISTINCT ON (patient_id, quiz_template_id, question_id) patient_id,
    quiz_template_id,
    question_id,
    response_value,
    responded_at
   FROM quiz_responses
  ORDER BY patient_id, quiz_template_id, question_id, responded_at DESC;
```

---

### quiz_template_performance_metrics

- **Schema:** public
- **Populated:** ✓

**Definição:**
```sql
 SELECT qt.id AS template_id,
    qt.name AS template_name,
    qt.category,
    count(qs.id) FILTER (WHERE (((qs.status)::text = 'completed'::text) AND (qs.started_at >= (now() - '30 days'::interval)))) AS completions_last_30d,
    count(qs.id) FILTER (WHERE (((qs.status)::text = 'completed'::text) AND (qs.started_at >= (now() - '7 days'::interval)))) AS completions_last_7d,
    avg(qs.score) FILTER (WHERE (((qs.status)::text = 'completed'::text) AND (qs.started_at >= (now() - '30 days'::interv...
```

---

### quiz_template_usage_stats

- **Schema:** public
- **Populated:** ✓

**Definição:**
```sql
 SELECT qt.id AS template_id,
    qt.name AS template_name,
    qt.version AS template_version,
    count(qs.id) FILTER (WHERE ((qs.status)::text = 'completed'::text)) AS completed_sessions,
    count(qs.id) FILTER (WHERE ((qs.status)::text = 'started'::text)) AS active_sessions,
    count(qs.id) FILTER (WHERE ((qs.status)::text = 'cancelled'::text)) AS cancelled_sessions,
    avg(qs.score) FILTER (WHERE ((qs.status)::text = 'completed'::text)) AS avg_score,
    max(qs.score) FILTER (WHERE ((qs....
```

---

## ⚙️ Funções

Total de funções: **259**

### Schema: public (259 funções)

- **armor**(bytea, text[], text[]) → text
- **cash_dist**(money, money) → money
- **cleanup_all_audit_tables**() → TABLE(table_name text, deleted_count integer, space_before text, space_after text)
- **cleanup_old_audit_log_entries**() → TABLE(deleted_count integer, space_before text, space_after text)
- **cleanup_old_audit_trail**() → TABLE(deleted_count integer, space_before text, space_after text)
- **crypt**(text, text) → text
- **date_dist**(date, date) → integer
- **dearmor**(text) → bytea
- **decrypt**(bytea, bytea, text) → bytea
- **decrypt_iv**(bytea, bytea, bytea, text) → bytea
- **digest**(bytea, text) → bytea
- **encrypt**(bytea, bytea, text) → bytea
- **encrypt_iv**(bytea, bytea, bytea, text) → bytea
- **float4_dist**(real, real) → real
- **float8_dist**(double precision, double precision) → double precision
- **gbt_bit_compress**(internal) → internal
- **gbt_bit_consistent**(internal, bit, smallint, oid, internal) → boolean
- **gbt_bit_penalty**(internal, internal, internal) → internal
- **gbt_bit_picksplit**(internal, internal) → internal
- **gbt_bit_same**(gbtreekey_var, gbtreekey_var, internal) → internal
- ... e mais 239 funções
