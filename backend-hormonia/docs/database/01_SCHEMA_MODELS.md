# 1. Database Schema & Models

> **Scope:** Schema definitions, SQLAlchemy mappings, Relationships, and Data Structure.
> **Source:** Consolidated from `SCHEMA_DOCUMENTATION.md`, `TABLES_REFERENCE.md`, `models_analysis_report.md`.

---

## 1. Overview

- **Database:** PostgreSQL 14+ on Amazon RDS (sa-east-1)
- **Total Tables:** 77 (Core + Partições de Auditoria)
- **Total Indexes:** 479+
- **ORM:** SQLAlchemy 2.0+ (Async)
- **Migration Head:** `034_add_performance_indexes`

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
| **Performance Indexes** | Índices CONCURRENTLY para patients, quiz, messages, appointments | `034` |
| **User Sync Log Fix** | Schema Firebase sync com novos campos | `033` |
| **Sessions Table** | Persistência de sessões de usuário | `ac193e8656c1` |
| **Account Lockout** | Colunas de segurança para usuários | `032` |
| **Performance** | Otimização massiva de índices (479 total) | `031` |
| **LGPD Complete** | Encrypt Email/Phone. Plaintext removido. | `028`, `030` |

---

## 6. Centralized Enums (app/models/enums.py)

Enums compartilhados foram consolidados para evitar duplicação:

```python
# FlowState - Estados do fluxo do paciente
class FlowState(enum.Enum):
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

# SagaStatus - Status de transações distribuídas
class SagaStatus(enum.Enum):
    STARTED = "STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    COMPENSATING = "COMPENSATING"
    COMPENSATED = "COMPENSATED"
```

*Importado em:* `patient.py`, `flow.py`, `patient_onboarding_saga.py`

---

## 7. Additional Key Tables

### `patient_onboarding_saga`
Gerenciamento de transações distribuídas para onboarding.
- **PK:** `id` (UUID)
- **FK:** `patient_id` → `patients.id` (CASCADE)
- **Status:** `status` (SagaStatus enum)
- **Tracking:** `current_step`, `steps_completed` (JSONB), `error_message`
- **Indexes:** `patient_id`, `status`, `created_at`
- **Utility:** Saga pattern, orphan detection, compensation handling

### Webhook Tables
- **`webhook_endpoints`**: Configuração de webhooks (URL, secret, retry)
- **`webhook_deliveries`**: Tentativas de entrega com status e response_time
- **`webhook_logs`**: Audit trail de mudanças administrativas
- **`webhook_idempotency`**: Prevenção de processamento duplicado

### A/B Testing Tables (6 tables)
- **`ab_experiments`**: Configurações com compliance HIPAA
- **`ab_variant_assignments`**: Atribuições anônimas de variantes
- **`ab_experiment_metrics`**: Métricas de eventos
- **`ab_experiment_results`**: Análise estatística (p-value, Cohen's d)
- **`ab_experiment_audit`**: Audit trail HIPAA/GDPR
- **`ab_experiment_monitoring`**: Monitoramento em tempo real

---

*For full column details, refer to `reference/complete_schema.json`.*
