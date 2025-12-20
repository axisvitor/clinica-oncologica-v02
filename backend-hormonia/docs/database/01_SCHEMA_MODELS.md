# 1. Database Schema & Models

> **Scope:** Schema definitions, SQLAlchemy mappings, Relationships, and Data Structure.
> **Source:** Consolidated from `SCHEMA_DOCUMENTATION.md`, `TABLES_REFERENCE.md`, `models_analysis_report.md`.

---

## 1. Overview

- **Database:** PostgreSQL 14+ on Amazon RDS (sa-east-1)
- **Total Tables:** 77 (Core + Partições de Auditoria)
- **ORM:** SQLAlchemy 2.0+ (Async)
- **Migration Head:** `ac193e8656c1` (Sessions Table)

### Flows & Quiz Domain (V2 Standardized)

#### `flow_kinds`
Definição dos tipos de fluxos (Ex: Onboarding, Manutenção).
- **PK:** `id` (UUID)
- **Key:** `kind_key` (String 100) - Identificador único (ex: `initial_15_days`).
- **Display:** `display_name` (String 255).
- **Status:** `is_active` (Boolean).

#### `flow_template_versions`
Versões de conteúdo para cada fluxo.
- **FK:** `flow_kind_id` (UUID) -> `flow_kinds.id`.
- **Version:** `version_number` (Integer) - Controle numérico sequencial.
- **Content:** `steps` (JSONB) - Estrutura centralizada contendo mensagens e lógica de quiz por dia.
- **Lifecycle:** `is_active` (Boolean) - Determina se é a versão oficial. Apenas uma versão por Kind deve estar ativa.
- **Audit:** `created_by`, `published_at`, `template_name`.

*Nota: As colunas `is_current` e `status` foram removidas em favor do controle unificado via `is_active` e `version_number`.*

---

## 2. SQLAlchemy Model Analysis

**Coverage:** 76.4% (42 models for 55 base tables).
**Status:** Todos os modelos core estão mapeados.

### Model Configuration Highlights
- **Relationships:** 78 chaves estrangeiras (FKs) garantindo integridade referencial.
- **Validation:** JSONB schema validation implementado em serviços.
- **Enums:** 17 tipos customizados PostgreSQL.
- **Encryption:** Campos LGPD (`cpf_encrypted`, etc.) protegidos por AES-256-GCM.

---

## 3. Key Table References

### Core Tables

#### `patients`
Entidade central.
- **PK:** `id` (UUID)
- **LGPD:** `cpf_encrypted`, `email_encrypted`, `phone_encrypted` (AES-256)
- **Search:** `*_hash` colunas indexadas para busca cega.
- **Flow:** `flow_state` (Enum), `current_day` (Int).
- **Meta:** `metadata` (JSONB), `deleted_at` (Soft Delete).

#### `users`
Autenticação e Segurança.
- **Security:** Colunas para bloqueio de conta e tentativas falhas (Migration 032).
- **RBAC:** `role` (Enum), `permissions` (JSONB).

---

## 5. Recent Schema Changes (Dec 2025)

| Change | Description | Migration |
|--------|-------------|-----------|
| **Sessions Table** | Persistência de sessões de usuário | `ac193e8656c1` |
| **Account Lockout** | Colunas de segurança para usuários | 032 |
| **Performance** | Otimização massiva de índices (479 total) | 031 |
| **LGPD Complete** | Encrypt Email/Phone. Plaintext removido. | 028, 030 |

---

*For full column details, refer to `reference/complete_schema.json`.*
