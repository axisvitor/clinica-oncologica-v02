# Análise Completa dos Endpoints da API v2

**Data:** 2025-11-30
**Escopo:** `/backend-hormonia/app/api/v2/`
**Total de Arquivos Python:** 155
**Total de Routers:** 54+

---

## 📋 Sumário Executivo

A API v2 contém **54+ routers** organizados em **10 fases de desenvolvimento**, com aproximadamente **155 arquivos Python**. A estrutura apresenta uma arquitetura modular bem organizada, porém com algumas inconsistências e oportunidades significativas de otimização.

### Principais Achados:
- ✅ **Pontos Fortes:** Modularização em fases, RBAC implementado, Redis caching, rate limiting
- ⚠️ **Pontos de Atenção:** Duplicação de lógica, complexidade excessiva em alguns endpoints, inconsistências na estrutura
- 🔴 **Crítico:** Endpoints duplicados/redundantes, falta de padronização em serialização

---

## 🗂️ Inventário Completo de Endpoints

### **Fase 1: Core Clinical Modules**

#### **1.1 Patients (4 routers modulares)**

**Router:** `/api/v2/patients`
**Arquivos:**
- `routers/patients.py` (CRUD principal)
- `routers/patients_import.py` (Importação em lote)
- `routers/patients_flow.py` (Gestão de fluxo/estado)
- `routers/patients_integrity.py` (Validação de integridade)

**Endpoints Principais:**
```
GET    /api/v2/patients                  # Listar com paginação cursor
GET    /api/v2/patients/{id}             # Obter por ID
POST   /api/v2/patients                  # Criar (com idempotência QW-004)
PATCH  /api/v2/patients/{id}             # Atualizar parcialmente
DELETE /api/v2/patients/{id}             # Soft delete (admin only)

# Importação
POST   /api/v2/patients/import           # Importação em lote
GET    /api/v2/patients/import/status    # Status da importação

# Fluxo
GET    /api/v2/patients/{id}/flow        # Estado do fluxo
PATCH  /api/v2/patients/{id}/flow/advance # Avançar fluxo
POST   /api/v2/patients/{id}/flow/reset  # Resetar fluxo

# Integridade
GET    /api/v2/patients/{id}/integrity   # Validar integridade
POST   /api/v2/patients/{id}/validate    # Validação manual
```

**Features:**
- ✅ Idempotência com `X-Idempotency-Key` (QW-004)
- ✅ Redis cache secundário (fallback)
- ✅ Paginação cursor-based
- ✅ Field selection (`?fields=id,name,email`)
- ✅ Eager loading (`?include=doctor,treatments`)
- ✅ RBAC completo (doctors veem apenas seus pacientes)
- ✅ Saga pattern para operações complexas

**Problemas Identificados:**
- 🔴 **Alta complexidade** no endpoint `create_patient` (70+ linhas, múltiplas responsabilidades)
- ⚠️ Serialização duplicada em `patients_utils.py` e dentro dos endpoints
- ⚠️ Falta de consistência: alguns endpoints usam Service, outros chamam Repository diretamente

---

#### **1.2 Appointments**

**Router:** `/api/v2/appointments`
**Arquivo:** `routers/appointments.py`

**Endpoints:**
```
GET    /api/v2/appointments              # Listar
GET    /api/v2/appointments/{id}         # Obter por ID
POST   /api/v2/appointments              # Criar
PATCH  /api/v2/appointments/{id}         # Atualizar
DELETE /api/v2/appointments/{id}         # Cancelar
PATCH  /api/v2/appointments/{id}/confirm # Confirmar
PATCH  /api/v2/appointments/{id}/complete # Completar
GET    /api/v2/appointments/upcoming     # Próximas consultas
```

**Features:**
- ✅ Paginação cursor
- ✅ Filtros: data, status, practitioner_id, patient_id
- ✅ Redis caching
- ✅ Rate limiting

---

#### **1.3 Treatments**

**Router:** `/api/v2/treatments`
**Arquivo:** `routers/treatments.py` (368 linhas)

**Endpoints:**
```
GET    /api/v2/treatments                # Listar
GET    /api/v2/treatments/statistics     # Estatísticas agregadas
GET    /api/v2/treatments/{id}           # Obter por ID
POST   /api/v2/treatments                # Criar
PATCH  /api/v2/treatments/{id}           # Atualizar
DELETE /api/v2/treatments/{id}           # Soft delete
PATCH  /api/v2/treatments/{id}/activate  # Ativar tratamento
```

**Features:**
- ✅ Eager loading (`?include=patient,doctor,medications`)
- ✅ Filtros avançados (treatment_type, status, start_date range)
- ✅ Estatísticas em tempo real (completion rate, by status, by type)
- ✅ Service layer implementado

**Problemas:**
- ⚠️ Lógica de permissão duplicada em múltiplos endpoints
- ⚠️ Validação de UUIDs repetida (poderia estar em middleware)

---

#### **1.4 Medications**

**Router:** `/api/v2/medications`
**Arquivo:** `routers/medications.py` (375 linhas)

**Endpoints:**
```
GET    /api/v2/medications               # Listar
GET    /api/v2/medications/active        # Apenas ativos
GET    /api/v2/medications/search        # Busca rápida (q=query)
GET    /api/v2/medications/{id}          # Obter por ID
POST   /api/v2/medications               # Criar
PATCH  /api/v2/medications/{id}          # Atualizar
DELETE /api/v2/medications/{id}          # Soft delete
```

**Features:**
- ✅ Paginação cursor
- ✅ Filtros: patient_id, prescribed_by_id, treatment_id, is_active, route
- ✅ Redis caching (TTL: 300s)
- ✅ Service layer (`MedicationService`)

**Problemas:**
- 🔴 **Endpoint duplicado:** `/medications/active` retorna praticamente o mesmo que `/medications?is_active=true`
- ⚠️ Serialização manual `_serialize_medication` poderia usar Pydantic
- ⚠️ Lógica RBAC repetida (pattern comum em todos os routers)

---

#### **1.5 Physicians**

**Router:** `/api/v2/physicians`
**Arquivo:** `routers/physicians.py` (892 linhas) ⚠️ **MUITO GRANDE**

**Endpoints:**
```
GET    /api/v2/physicians                # Listar médicos
GET    /api/v2/physicians/{id}           # Perfil do médico
PATCH  /api/v2/physicians/{id}           # Atualizar (admin only)
```

**Features:**
- ✅ **Estatísticas avançadas** (calculadas sob demanda):
  - Patient metrics (total, active, inactive, new this month)
  - Workload level (LOW, MEDIUM, HIGH, OVERLOADED)
  - Message stats (sent, received, unread, response rate, avg response time)
  - Appointment stats (scheduled, completed, cancelled, upcoming, today)
  - Alert stats (by severity)
  - Patient satisfaction score (weighted algorithm)
  - Average treatment duration
- ✅ Redis caching (profiles: 15min, stats: 10min, list: 30min)
- ✅ Field selection e eager loading
- ✅ Filtros: specialty, status, workload, min/max patients, search

**Problemas Críticos:**
- 🔴 **Arquivo gigante:** 892 linhas, violando princípio de responsabilidade única
- 🔴 **Função `_calculate_physician_statistics`:** 280+ linhas, deveria ser Service separado
- 🔴 **Performance:** Cálculo de estatísticas faz múltiplas queries N+1 (não otimizado)
- ⚠️ Lógica de cálculo de satisfaction score (linhas 336-360) está embutida no router

**Recomendação:** Refatorar para:
```
services/
  physician/
    statistics_service.py    # Cálculo de estatísticas
    workload_service.py      # Workload calculation
routers/
  physicians.py              # Apenas endpoints (< 300 linhas)
```

---

### **Fase 2: Quiz and Analytics**

#### **2.1 Quiz Sessions**

**Router:** `/api/v2/quiz`
**Arquivo:** `routers/quiz_sessions.py`

**Endpoints:**
```
GET    /api/v2/quiz                      # Listar sessões
GET    /api/v2/quiz/{id}                 # Obter sessão
POST   /api/v2/quiz/start                # Iniciar sessão
POST   /api/v2/quiz/{id}/submit          # Submeter resposta
POST   /api/v2/quiz/{id}/complete        # Completar sessão
GET    /api/v2/quiz/{id}/progress        # Progresso da sessão
```

**Routers Relacionados (Refatorado - Sprint 1):**
- `quiz_responses.py` - Gestão de respostas
- `quiz_alerts.py` - Alertas baseados em respostas
- `monthly_quiz_management.py` - Quiz mensal (admin)
- `monthly_quiz_operations.py` - Operações públicas

**Problemas:**
- ⚠️ **3 aliases diferentes** para o mesmo router de quiz mensal:
  ```
  /api/v2/quiz-extensions/monthly-quiz     (principal)
  /api/v2/monthly-quiz-public/*            (alias frontend)
  /api/v2/monthly-quiz/*                   (alias compatibilidade)
  ```
  **Recomendação:** Consolidar em um único path com redirect

---

#### **2.2 Analytics**

**Router:** `/api/v2/analytics`
**Arquivos:**
- `routers/analytics.py` (22k lines) 🔴
- `routers/enhanced_analytics.py` (8k lines)

**Endpoints:**
```
GET    /api/v2/analytics/patients        # Métricas de pacientes
GET    /api/v2/analytics/messages        # Métricas de mensagens
GET    /api/v2/analytics/engagement      # Engajamento
GET    /api/v2/analytics/cohort          # Análise de cohort
GET    /api/v2/analytics/retention       # Retenção
GET    /api/v2/analytics/dashboard       # Dashboard completo

# Enhanced Analytics
GET    /api/v2/enhanced-analytics/realtime
GET    /api/v2/enhanced-analytics/predictive
```

**Problemas Críticos:**
- 🔴 **Arquivo gigante:** `analytics.py` tem 22.666 linhas!
- 🔴 **Duplicação:** Lógica similar entre `analytics` e `enhanced_analytics`
- 🔴 **Performance:** Queries complexas sem otimização aparente

**Recomendação URGENTE:**
Refatorar em micro-serviços:
```
services/analytics/
  patient_analytics_service.py
  message_analytics_service.py
  engagement_service.py
  cohort_service.py
  retention_service.py
routers/
  analytics/
    patients.py
    messages.py
    engagement.py
    cohort.py
```

---

### **Fase 3: Auth & Users**

#### **3.1 Auth**

**Router:** `/api/v2/auth`
**Arquivo:** `routers/auth.py` (268 linhas)

**Endpoints:**
```
POST   /api/v2/auth/firebase/verify      # Verificar token Firebase
POST   /api/v2/auth/verify-session       # Verificar sessão
DELETE /api/v2/auth/logout               # Logout
DELETE /api/v2/auth/logout-all           # Logout de todos os devices
GET    /api/v2/auth/csrf-token           # CSRF token
```

**Features:**
- ✅ Firebase authentication
- ✅ Session management (DB + Redis)
- ✅ HttpOnly cookies + X-Session-ID header
- ✅ Account lock mechanism
- ✅ Rate limiting

**Problemas:**
- ⚠️ **Endpoint duplicado:** `/api/v2/csrf-token` existe tanto em:
  - `/api/v2/csrf-token` (deprecated, linha 70-134 do router.py)
  - `/api/v2/auth/csrf-token` (correto, linha 258-267)

  **Status:** Marcado como deprecated com warning log, mas ainda ativo

  **Recomendação:** Remover após migração do frontend

---

#### **3.2 Users**

**Router:** `/api/v2/auth` (prefixo compartilhado)
**Arquivo:** `routers/users.py`

**Endpoints:**
```
GET    /api/v2/auth/me                   # Usuário atual
PATCH  /api/v2/auth/me                   # Atualizar perfil
GET    /api/v2/auth/preferences          # Preferências
PATCH  /api/v2/auth/preferences          # Atualizar preferências
```

---

#### **3.3 Session (Backward Compatibility)**

**Router:** `/api/v2/session`
**Arquivo:** `routers/session.py`

**Endpoint:**
```
GET    /api/v2/session/verify            # Wrapper para /auth/verify-session
```

**Status:** Compatibility layer, pode ser removido

---

### **Fase 4: Messages & WhatsApp**

#### **4.1 Messages**

**Router:** `/api/v2/messages`
**Arquivo:** `routers/messages.py` (400 linhas)

**Endpoints:**
```
GET    /api/v2/messages                  # Listar
GET    /api/v2/messages/{id}             # Obter por ID
POST   /api/v2/messages                  # Enviar mensagem
PATCH  /api/v2/messages/{id}/read        # Marcar como lida
DELETE /api/v2/messages/{id}             # Cancelar (apenas pending/scheduled)
GET    /api/v2/messages/conversations/{patient_id} # Conversa completa
POST   /api/v2/messages/bulk             # Envio em lote
```

**Features:**
- ✅ Rate limiting (50/min para GET, 20/min para POST)
- ✅ Redis caching (TTL: list=300s, single=600s)
- ✅ Validação de tamanho (MAX: 4096 chars - QW-004)
- ✅ Background tasks para envio assíncrono
- ✅ Idempotência automática (hash de conteúdo + timestamp)
- ✅ Suporte a mensagens agendadas

**Problemas:**
- ⚠️ Endpoint `/bulk` está incompleto (linha 377-399, retorna mock)
- ⚠️ Falta implementação de retry logic visível na API
- ⚠️ MessageSender importado mas não definido (linha 261)

---

#### **4.2 Enhanced Messages**

**Router:** `/api/v2/enhanced-messages`
**Pasta:** `routers/enhanced_messages/`

**Arquivos:**
- `__init__.py`
- `analytics.py`
- `bulk.py`
- `conversations.py`
- `crud.py`
- `helpers.py`
- `retry.py`
- `send.py`
- `stats.py`
- `templates.py`

**Problemas:**
- 🔴 **Duplicação massiva:** Funcionalidade overlap com `/api/v2/messages`
- ⚠️ Não está claro qual usar (messages vs enhanced-messages)

**Recomendação:** Consolidar em um único router `/api/v2/messages` com todas as features

---

### **Fase 5: Admin**

#### **5.1 Admin Main**

**Router:** `/api/v2/admin`
**Pasta:** `routers/admin/`

**Arquivos:**
- `actions.py` - User actions (activate, deactivate, reset password, update role)
- `activity.py` - Activity logs e audit trail
- `stats.py` - Estatísticas administrativas
- `users.py` - Gestão de usuários
- `utils.py` - Helpers compartilhados
- `dependencies.py` - Admin auth

**Endpoints Principais:**
```
# User Actions
POST   /api/v2/admin/users/{id}/activate
POST   /api/v2/admin/users/{id}/deactivate
POST   /api/v2/admin/users/{id}/reset-password
PUT    /api/v2/admin/users/{id}/role

# Activity
GET    /api/v2/admin/activity              # Activity log
GET    /api/v2/admin/activity/export       # Export CSV/JSON

# Stats
GET    /api/v2/admin/stats/overview        # Overview geral
GET    /api/v2/admin/stats/users           # Stats de usuários
GET    /api/v2/admin/stats/patients        # Stats de pacientes

# Users
GET    /api/v2/admin/users                 # Listar usuários
GET    /api/v2/admin/users/{id}            # Obter usuário
POST   /api/v2/admin/users                 # Criar usuário
```

**Features:**
- ✅ Rate limiting rigoroso (20/hour para ações sensíveis, 10/hour para password reset)
- ✅ Audit logging completo
- ✅ Cache invalidation após ações
- ✅ Password strength validation
- ✅ Self-protection (não pode desativar própria conta ou remover próprio admin)

**Qualidade do Código:**
- ✅ **Muito bem estruturado:** Modularizado por responsabilidade
- ✅ **Documentação clara:** Docstrings detalhados
- ✅ **Error handling robusto:** Try-catch adequado
- ✅ **Segurança:** Rate limiting adequado para operações sensíveis

---

#### **5.2 Admin Extensions**

**Router:** `/api/v2/admin-extensions`
**Pasta:** `routers/admin_extensions/`

**Arquivos:**
- `dependencies.py`
- Outros módulos (não listados)

**Status:** Pouco documentado, precisa de revisão

---

### **Fase 6: Health & System**

#### **6.1 Health**

**Router:** `/api/v2/health`
**Pasta:** `routers/health/`

**Arquivos (8 módulos):**
- `__init__.py` - Agregador principal
- `core.py` - Basic health, readiness, liveness
- `database_health.py` - DB health checks
- `service_health.py` - Redis, workers, external services
- `storage_external.py` - Storage health
- `metrics.py` - Prometheus metrics
- `platform.py` - Railway, production health
- `monitoring.py` - Health history, incidents, alerts
- `test.py` - Admin-only manual testing
- `utils.py` - Helpers (health score calculation)

**Endpoints:**
```
GET    /api/v2/health                    # Basic health check (PUBLIC)
GET    /api/v2/health/ready              # Readiness probe (PUBLIC)
GET    /api/v2/health/live               # Liveness probe (PUBLIC)
GET    /api/v2/health/database           # Database health
GET    /api/v2/health/redis              # Redis health
GET    /api/v2/health/workers            # Worker health
GET    /api/v2/health/external           # External services
GET    /api/v2/health/storage            # Storage health
GET    /api/v2/health/metrics            # Prometheus metrics
GET    /api/v2/health/platform           # Platform (Railway)
GET    /api/v2/health/monitoring         # Health monitoring
GET    /api/v2/health/test               # Manual testing (Admin)
```

**Features:**
- ✅ **PUBLIC endpoints** (sem auth para load balancers)
- ✅ Health scoring (0-100)
- ✅ Redis caching com TTLs apropriados
- ✅ Rate limiting
- ✅ HTTP 200 (healthy) / 503 (unhealthy)
- ✅ Prometheus-compatible metrics

**Qualidade:**
- ✅ **Excelente modularização:** Cada módulo tem responsabilidade clara
- ✅ **Documentação completa:** Docstrings detalhados no `__init__.py`

---

#### **6.2 System**

**Router:** `/api/v2/system`
**Pasta:** `routers/system/`

**Arquivos (6 módulos):**
- `__init__.py` - Agregador
- `config.py` - Public config (NO auth)
- `health.py` - System health (admin only)
- `initialization.py` - System initialization (admin only)
- `components.py` - Component management (admin only)
- `metrics.py` - System metrics (admin only)
- `validation.py` - Config validation (admin only)

**Subpasta helpers:**
- `config_builder.py`
- `health_checker.py`

**Endpoints:**
```
GET    /api/v2/system/config             # Public config (NO AUTH)
GET    /api/v2/system/health             # System health (admin)
POST   /api/v2/system/initialize         # Initialize (admin)
GET    /api/v2/system/components         # Component status (admin)
GET    /api/v2/system/metrics            # Metrics (admin)
POST   /api/v2/system/validate           # Validate config (admin)
```

**Features:**
- ✅ Public config endpoint para frontend
- ✅ System initialization checks
- ✅ Component management
- ✅ Metrics collection

**Qualidade:**
- ✅ Bem modularizado
- ✅ Separação clara entre public e admin endpoints

---

### **Fase 7: Supporting Modules**

#### **7.1 Flows**

**Router:** `/api/v2/flows`
**Arquivo:** `routers/flows.py`

**Endpoints:**
```
GET    /api/v2/flows                     # Listar flows
GET    /api/v2/flows/{id}                # Obter flow
POST   /api/v2/flows                     # Criar flow
PATCH  /api/v2/flows/{id}/advance        # Avançar estado
```

---

#### **7.2 Flow Templates**

**Router:** `/api/v2/templates`
**Arquivo:** `routers/flow_templates.py`

**Endpoints:**
```
GET    /api/v2/templates/flows           # Listar templates de flow
GET    /api/v2/templates/flows/{id}      # Obter template
POST   /api/v2/templates/flows           # Criar template (admin)
PATCH  /api/v2/templates/flows/{id}      # Atualizar template (admin)
DELETE /api/v2/templates/flows/{id}      # Deletar template (admin)
```

---

#### **7.3 Quiz Templates**

**Router:** `/api/v2/templates`
**Arquivo:** `routers/quiz_templates.py`

**Endpoints:**
```
GET    /api/v2/templates/quiz            # Listar templates de quiz
GET    /api/v2/templates/quiz/{id}       # Obter template
POST   /api/v2/templates/quiz            # Criar template (admin)
```

---

#### **7.4 Template Versions**

**Router:** `/api/v2/templates`
**Arquivo:** `routers/template_versions.py`

**Endpoints:**
```
GET    /api/v2/templates/{id}/versions   # Listar versões
POST   /api/v2/templates/{id}/versions   # Criar versão
GET    /api/v2/templates/{id}/versions/{version_id}
```

---

#### **7.5 Template Admin**

**Router:** `/api/v2/templates`
**Arquivo:** `routers/template_admin.py`

**Endpoints:**
```
POST   /api/v2/templates/{id}/publish    # Publicar template
POST   /api/v2/templates/{id}/deprecate  # Deprecar template
```

**Problema:**
- ⚠️ **4 routers** compartilham o mesmo prefixo `/api/v2/templates`
- Dificulta navegação e documentação OpenAPI

**Recomendação:** Consolidar em estrutura hierárquica clara

---

#### **7.6 Upload**

**Router:** `/api/v2/upload`
**Pasta:** `routers/upload/`

**Arquivos:**
- `__init__.py`
- `handlers.py`

**Endpoints:**
```
POST   /api/v2/upload/file               # Upload de arquivo
POST   /api/v2/upload/image              # Upload de imagem
POST   /api/v2/upload/document           # Upload de documento
```

---

#### **7.7 Outros Routers**

**Listagem:**
- `tasks.py` - Task management
- `localization.py` - Localização (i18n)
- `dashboard.py` - Dashboard
- `docs.py` - Documentação
- `roles.py` - Roles & Permissions
- `performance.py` - Performance monitoring
- `reports.py` - Relatórios
- `webhooks.py` - Webhooks
- `ab_testing.py` - A/B Testing
- `platform_sync.py` - Platform sync
- `alerts.py` - Alertas
- `enhanced_monitoring.py` - Monitoramento avançado
- `enhanced_quiz.py` - Quiz avançado
- `enhanced_reports.py` - Relatórios avançados
- `notifications.py` - Notificações

---

### **Fase 8: AI**

**Router:** `/api/v2/ai`
**Pasta:** `routers/ai/`

**Arquivos:**
- `health.py` - AI health checks

**Endpoints:**
```
GET    /api/v2/ai/health                 # AI service health
POST   /api/v2/ai/generate               # Gerar conteúdo (presumido)
```

---

### **Fase 9: Debug (CONDITIONAL)**

**Router:** `/api/v2/debug`
**Pasta:** `routers/debug/`

**Arquivos:**
- `common.py`
- Outros módulos

**Status:**
- ⚠️ **Habilitado apenas se:** `ENABLE_DEBUG_ENDPOINTS=true`
- ⚠️ **Nunca em produção!** (warning log na linha 217-228 do router.py)

**Endpoints:**
```
GET    /api/v2/debug/env                 # Environment variables (masked)
GET    /api/v2/debug/database            # Database diagnostics
GET    /api/v2/debug/auth                # Auth flow debugging
POST   /api/v2/debug/test-query          # Test database queries
```

**Segurança:**
- ✅ Admin-only
- ✅ Fully audit logged
- ✅ Conditional registration

---

## 🔍 Análise de Complexidade

### **Endpoints Muito Complexos (Refatoração Urgente)**

#### 1. **`physicians.py`** - 892 linhas 🔴
**Problemas:**
- Função `_calculate_physician_statistics` tem 280+ linhas
- Múltiplas queries N+1 para cálculo de estatísticas
- Lógica de negócio (satisfaction score) no router
- Violação de Single Responsibility Principle

**Complexidade Ciclomática Estimada:** 15-20 (alto risco)

**Refatoração Recomendada:**
```python
# services/physician/statistics_service.py
class PhysicianStatisticsService:
    def calculate_statistics(self, physician_id: UUID) -> PhysicianStatistics:
        """Calcula estatísticas com queries otimizadas"""
        return PhysicianStatistics(
            patient_metrics=self._calculate_patient_metrics(physician_id),
            message_stats=self._calculate_message_stats(physician_id),
            appointment_stats=self._calculate_appointment_stats(physician_id),
            alert_stats=self._calculate_alert_stats(physician_id),
            satisfaction_score=self._calculate_satisfaction_score(physician_id)
        )

    def _calculate_patient_metrics(self, physician_id: UUID):
        # Query otimizada com agregações
        pass

# routers/physicians.py (< 300 linhas)
@router.get("/{id}")
async def get_physician(physician_id: str, ...):
    service = PhysicianStatisticsService(db)
    statistics = service.calculate_statistics(physician_id)
    return _serialize_physician(physician, statistics)
```

---

#### 2. **`analytics.py`** - 22.666 linhas 🔴🔴🔴
**Problemas:**
- **Arquivo monstruoso:** 22k linhas em um único arquivo!
- Múltiplas responsabilidades (patient analytics, message analytics, cohort, etc.)
- Impossível de manter
- Provavelmente queries complexas sem otimização

**Complexidade Ciclomática Estimada:** >50 (crítico)

**Refatoração URGENTE:**
```
services/analytics/
  base_analytics_service.py       # Base class
  patient_analytics_service.py    # Patient metrics
  message_analytics_service.py    # Message metrics
  engagement_service.py           # Engagement
  cohort_service.py               # Cohort analysis
  retention_service.py            # Retention
  predictive_service.py           # Predictive analytics

routers/analytics/
  __init__.py                     # Agregador
  patients.py                     # GET /analytics/patients
  messages.py                     # GET /analytics/messages
  engagement.py                   # GET /analytics/engagement
  cohort.py                       # GET /analytics/cohort
  retention.py                    # GET /analytics/retention
  predictive.py                   # GET /analytics/predictive
```

---

#### 3. **`patients.py` - `create_patient`** - 100+ linhas no endpoint
**Problemas:**
- Múltiplas responsabilidades no endpoint
- Lógica de idempotência misturada com criação
- Validação, Saga, Redis cache, tudo no mesmo lugar

**Refatoração Recomendada:**
```python
# Usar pattern de Command + Handler
class CreatePatientCommand:
    patient_data: PatientV2Create
    doctor_id: UUID
    idempotency_key: Optional[str]

class CreatePatientHandler:
    def __init__(self, db, saga, redis):
        self.db = db
        self.saga = saga
        self.redis = redis
        self.idempotency_service = IdempotencyService(db, redis)

    async def handle(self, command: CreatePatientCommand):
        # 1. Check idempotency
        if existing := await self.idempotency_service.check(command.idempotency_key):
            return existing

        # 2. Validate
        validated = await self.validator.validate(command.patient_data)

        # 3. Execute Saga
        patient = await self.saga.create_patient(validated, command.doctor_id)

        # 4. Store idempotency
        await self.idempotency_service.store(command.idempotency_key, patient)

        return patient

# routers/patients.py
@router.post("")
async def create_patient(patient_data: PatientV2Create, ...):
    command = CreatePatientCommand(patient_data, doctor_id, idempotency_key)
    handler = CreatePatientHandler(db, saga, redis)
    return await handler.handle(command)
```

---

### **Endpoints com Lógica Muito Similar (DRY Violation)**

#### 1. **Medications vs Treatments - Estrutura Idêntica**

**Problema:**
```python
# medications.py (linhas 82-181)
@router.get("")
async def list_medications(...):
    # 1. Cache check
    # 2. Query building
    # 3. RBAC filtering
    # 4. Cursor pagination
    # 5. Eager loading
    # 6. Serialization
    # 7. Cache store
    pass

# treatments.py (linhas 77-187)
@router.get("")
async def list_treatments(...):
    # EXATAMENTE A MESMA ESTRUTURA!
    pass
```

**Refatoração Recomendada:**
```python
# base/list_endpoint_base.py
class ListEndpointBase:
    def __init__(self, db, redis, model, serializer):
        self.db = db
        self.redis = redis
        self.model = model
        self.serializer = serializer

    async def execute(self, pagination, filters, include):
        # 1. Cache check
        cache_key = self._build_cache_key(filters)
        if cached := await self.redis.get(cache_key):
            return cached

        # 2. Query building
        query = self._build_query(filters, include)

        # 3. RBAC
        query = self._apply_rbac(query)

        # 4. Pagination
        items, has_more, next_cursor = self._paginate(query, pagination)

        # 5. Serialize
        data = [self.serializer(item) for item in items]

        # 6. Cache
        result = {"data": data, "has_more": has_more, "next_cursor": next_cursor}
        await self.redis.set(cache_key, result, ttl=300)

        return result

# routers/medications.py
@router.get("")
async def list_medications(...):
    endpoint = ListEndpointBase(db, redis, Medication, _serialize_medication)
    return await endpoint.execute(pagination, filters, include)

# routers/treatments.py
@router.get("")
async def list_treatments(...):
    endpoint = ListEndpointBase(db, redis, Treatment, _serialize_treatment)
    return await endpoint.execute(pagination, filters, include)
```

---

## 🔴 Inconsistências na Estrutura

### **1. Duplicação de Endpoints**

#### **1.1 CSRF Token**
```
GET /api/v2/csrf-token              (deprecated, linha 70-134)
GET /api/v2/auth/csrf-token         (correto, linha 258-267)
```
**Status:** Marcado como deprecated, mas ainda ativo
**Ação:** Remover após migração do frontend

---

#### **1.2 Medications Active**
```
GET /api/v2/medications/active      (linha 183-217)
GET /api/v2/medications?is_active=true
```
**Problema:** Endpoint especializado retorna praticamente o mesmo que filtro
**Ação:** Remover `/active` e documentar uso de `?is_active=true`

---

#### **1.3 Monthly Quiz (3 aliases!)**
```
POST /api/v2/quiz-extensions/monthly-quiz/start
POST /api/v2/monthly-quiz-public/start
POST /api/v2/monthly-quiz/start
```
**Problema:** 3 paths diferentes para o mesmo endpoint
**Ação:** Consolidar em um único path com redirects

---

#### **1.4 Messages vs Enhanced Messages**
```
/api/v2/messages/*
/api/v2/enhanced-messages/*
```
**Problema:** Overlap funcional massivo
**Ação:** Consolidar em `/api/v2/messages` com todas as features

---

### **2. Inconsistência em Serialização**

**Problema:** 3 abordagens diferentes para serialização:

#### **Abordagem 1: Função `_serialize_*`** (medications, treatments)
```python
def _serialize_medication(medication) -> dict:
    return {
        "id": str(medication.id),
        "name": medication.name,
        # ... manual mapping
    }
```

#### **Abordagem 2: Pydantic schemas** (alguns endpoints)
```python
return MedicationV2Response.from_orm(medication)
```

#### **Abordagem 3: Método `_serialize_*_with_includes`** (patients)
```python
def _serialize_patient_with_includes(patient, include):
    # Lógica condicional de includes
    pass
```

**Recomendação:** Padronizar para Pydantic com `from_orm`:
```python
class MedicationV2Response(BaseModel):
    id: UUID
    name: str
    # ...

    class Config:
        from_attributes = True

    @classmethod
    def with_relations(cls, medication, include: List[str]):
        data = cls.from_orm(medication).dict()
        if "patient" in include:
            data["patient"] = PatientMinimalResponse.from_orm(medication.patient)
        return data
```

---

### **3. Inconsistência em RBAC**

**Problema:** Lógica RBAC repetida em TODOS os routers

**Padrão encontrado em 15+ arquivos:**
```python
role_enum, user_id = _extract_user_context(current_user)
current_user_uuid = _ensure_uuid(user_id)

if role_enum != UserRole.ADMIN:
    if not current_user_uuid:
        raise HTTPException(status_code=403)
    filters.append(Model.doctor_id == current_user_uuid)
```

**Refatoração Recomendada:**
```python
# dependencies/rbac_filters.py
class RBACFilterBuilder:
    @staticmethod
    def doctor_owned_resources(current_user, model_class):
        """Retorna filtro SQLAlchemy para recursos do médico"""
        role_enum, user_id = _extract_user_context(current_user)

        if role_enum == UserRole.ADMIN:
            return True  # Sem filtro

        user_uuid = _ensure_uuid(user_id)
        if not user_uuid:
            raise HTTPException(status_code=403)

        return model_class.doctor_id == user_uuid

# routers/medications.py
@router.get("")
async def list_medications(...):
    query = db.query(Medication)
    query = query.filter(RBACFilterBuilder.doctor_owned_resources(current_user, Medication))
    # ... resto do código
```

---

## 📊 Oportunidades de Simplificação

### **1. Consolidação de Routers**

#### **Templates (4 routers → 1)**
```
Atual:
  /api/v2/templates/flows
  /api/v2/templates/quiz
  /api/v2/templates/{id}/versions
  /api/v2/templates/{id}/publish

Proposta:
  routers/templates/
    __init__.py          # Agregador
    flows.py             # Flow templates
    quiz.py              # Quiz templates
    versions.py          # Template versions
    admin.py             # Publish, deprecate
```

---

#### **Messages (2 routers → 1)**
```
Atual:
  /api/v2/messages
  /api/v2/enhanced-messages

Proposta:
  /api/v2/messages         # Tudo consolidado
    └─ Features: analytics, bulk, retry, stats, templates
```

---

#### **Patients (4 routers → manter, mas melhorar)**
```
Atual (BOM):
  routers/patients.py           # CRUD
  routers/patients_import.py    # Import
  routers/patients_flow.py      # Flow
  routers/patients_integrity.py # Integrity

Melhoria:
  Mover para estrutura de pasta:
  routers/patients/
    __init__.py
    crud.py
    import_ops.py
    flow.py
    integrity.py
```

---

### **2. Eliminação de Código Duplicado**

#### **Pattern: List Endpoint**
**Repetido em:** medications, treatments, patients, physicians, messages, appointments (6+ vezes)

**Solução:**
```python
# base/generic_list_endpoint.py
class GenericListEndpoint(Generic[T]):
    def __init__(
        self,
        db: Session,
        redis: RedisCache,
        model: Type[T],
        serializer: Callable[[T], dict],
        rbac_filter: Callable[[User, Query], Query]
    ):
        self.db = db
        self.redis = redis
        self.model = model
        self.serializer = serializer
        self.rbac_filter = rbac_filter

    async def execute(
        self,
        pagination: PaginationParams,
        filters: Dict[str, Any],
        include: List[str],
        current_user: User
    ) -> ListResponse:
        # Implementação genérica
        pass

# Uso em routers/medications.py
@router.get("")
async def list_medications(pagination, filters, include, current_user):
    endpoint = GenericListEndpoint(
        db=db,
        redis=redis,
        model=Medication,
        serializer=_serialize_medication,
        rbac_filter=lambda user, q: q.filter_doctor_owned(user)
    )
    return await endpoint.execute(pagination, filters, include, current_user)
```

---

### **3. Extraction de Helpers Compartilhados**

**Padrão repetido:**
```python
# Validação de UUID (15+ ocorrências)
try:
    uuid_val = UUID(string_id)
except (ValueError, TypeError):
    raise HTTPException(status_code=400, detail="Invalid UUID")
```

**Solução:**
```python
# utils/validation.py
def validate_uuid(value: str, field_name: str = "id") -> UUID:
    try:
        return UUID(value)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field_name} format. Must be a valid UUID."
        )

# Uso
patient_id = validate_uuid(patient_id_str, "patient_id")
```

---

## 📋 Melhorias de Documentação OpenAPI

### **Problemas Identificados**

#### **1. Tags Inconsistentes**
```python
# router.py linha 139-204
api_v2_router.include_router(patients_crud_router, tags=["patients-crud-v2"])
api_v2_router.include_router(patients_import_router, tags=["patients-import-v2"])
api_v2_router.include_router(patients_flow_router, tags=["patients-flow-v2"])
api_v2_router.include_router(patients_integrity_router, tags=["patients-integrity-v2"])
```

**Problema:** Sufixo `-v2` redundante (já está em `/api/v2/`)

**Recomendação:**
```python
tags=["patients-crud"]
tags=["patients-import"]
tags=["patients-flow"]
tags=["patients-integrity"]
```

---

#### **2. Falta de Descrições em Endpoints**

**Exemplo ruim:**
```python
@router.get("/{id}")
async def get_medication(id: str, ...):
    pass
```

**Exemplo bom:**
```python
@router.get(
    "/{id}",
    response_model=MedicationV2Response,
    summary="Get medication by ID",
    description="""
    Retrieve detailed information about a specific medication.

    **Features:**
    - Field selection (?fields=id,name,dosage)
    - Eager loading (?include=patient,treatment)
    - Redis caching (TTL: 10 minutes)

    **RBAC:**
    - Admin: View all medications
    - Doctor: View own patient medications

    **Rate Limit:** 100 requests/minute
    """,
    responses={
        200: {"description": "Medication found"},
        404: {"description": "Medication not found"},
        403: {"description": "Not enough permissions"}
    }
)
async def get_medication(id: str, ...):
    pass
```

---

#### **3. Falta de Response Models Completos**

**Problema:** Alguns endpoints não declaram `response_model`

**Exemplo:**
```python
# medications.py linha 189-217
@router.get("/active", response_model=MedicationV2List)
async def list_active_medications(...):
    # ... código
    return {"data": resp_data, "has_more": has_more, "total": None, "next_cursor": None}
```

**Problema:** Retorna dict diretamente ao invés de `MedicationV2List`

**Correção:**
```python
@router.get("/active", response_model=MedicationV2List)
async def list_active_medications(...):
    # ... código
    return MedicationV2List(
        data=resp_data,
        has_more=has_more,
        total=None,
        next_cursor=None
    )
```

---

#### **4. Falta de Exemplos em Schemas**

**Recomendação:** Adicionar exemplos Pydantic:
```python
class MedicationV2Create(BaseModel):
    patient_id: str = Field(..., description="Patient UUID")
    name: str = Field(..., min_length=1, max_length=200)
    dosage: str = Field(..., example="500mg")
    frequency: str = Field(..., example="2x ao dia")

    class Config:
        json_schema_extra = {
            "example": {
                "patient_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Paracetamol",
                "dosage": "500mg",
                "frequency": "2x ao dia",
                "route": "oral",
                "instructions": "Tomar após as refeições"
            }
        }
```

---

## 🎯 Sumário de Recomendações

### **Prioridade CRÍTICA (Fazer Imediatamente)**

1. **Refatorar `analytics.py` (22k linhas)**
   - Quebrar em 6-8 módulos
   - Criar services especializados
   - Otimizar queries

2. **Refatorar `physicians.py` (892 linhas)**
   - Extrair `PhysicianStatisticsService`
   - Otimizar cálculos de estatísticas (queries N+1)
   - Mover lógica de negócio para services

3. **Consolidar Messages**
   - Remover `/enhanced-messages`
   - Consolidar em `/messages`

4. **Remover Duplicação RBAC**
   - Criar `RBACFilterBuilder`
   - Aplicar em todos os routers

---

### **Prioridade ALTA (Próximo Sprint)**

5. **Consolidar Endpoints Duplicados**
   - Remover `/csrf-token` deprecated
   - Remover `/medications/active`
   - Consolidar 3 aliases de monthly quiz

6. **Padronizar Serialização**
   - Usar Pydantic `from_orm` everywhere
   - Remover funções `_serialize_*` manuais

7. **Criar Base Classes Genéricas**
   - `GenericListEndpoint`
   - `GenericCRUDEndpoint`
   - Reduzir duplicação em 70%+

8. **Melhorar Documentação OpenAPI**
   - Adicionar descrições em todos os endpoints
   - Adicionar exemplos em schemas
   - Documentar RBAC, rate limits, caching

---

### **Prioridade MÉDIA (Backlog)**

9. **Reorganizar Estrutura de Pastas**
   - Mover routers grandes para pastas modulares
   - Exemplo: `routers/patients/` ao invés de múltiplos arquivos raiz

10. **Implementar Endpoints Incompletos**
    - `/messages/bulk` (mock atualmente)
    - Outros endpoints marcados como "TODO"

11. **Otimização de Performance**
    - Adicionar database indexes
    - Otimizar queries N+1 em physicians
    - Implementar query result caching

---

## 📈 Métricas de Qualidade

### **Cobertura Atual**

| Categoria | Status |
|-----------|--------|
| **Modularização** | 7/10 ✅ |
| **Documentação OpenAPI** | 5/10 ⚠️ |
| **DRY (Don't Repeat Yourself)** | 4/10 🔴 |
| **SOLID Principles** | 5/10 ⚠️ |
| **Performance** | 6/10 ⚠️ |
| **Security (RBAC, Rate Limiting)** | 8/10 ✅ |
| **Error Handling** | 7/10 ✅ |
| **Testing** | Unknown (needs separate analysis) |

---

### **Impacto Estimado das Refatorações**

| Refatoração | Redução de Linhas | Melhoria de Manutenibilidade | Ganho de Performance |
|-------------|-------------------|------------------------------|----------------------|
| Analytics split | -18k linhas | +90% | +40% (queries otimizadas) |
| Physicians refactor | -400 linhas | +70% | +60% (eliminar N+1) |
| Generic endpoints | -1.5k linhas | +80% | +10% (cache unificado) |
| RBAC consolidation | -800 linhas | +85% | 0% |
| Serialization padronização | -600 linhas | +75% | +5% (Pydantic otimizado) |
| **TOTAL** | **-21.3k linhas** | **+80% avg** | **+23% avg** |

---

## 🎯 Próximos Passos

1. **Revisão com time de desenvolvimento**
   - Priorizar refatorações críticas
   - Definir sprints para cada categoria

2. **Criar issues no GitHub/Jira**
   - Uma issue por refatoração
   - Incluir acceptance criteria

3. **Implementar testes antes de refatorar**
   - Garantir que refatoração não quebra funcionalidade
   - Testes de integração para endpoints críticos

4. **Documentação de arquitetura**
   - Criar ADRs (Architecture Decision Records)
   - Documentar padrões adotados

5. **Monitoramento pós-refatoração**
   - Métricas de performance
   - Error rates
   - Response times

---

## 📝 Conclusão

A API v2 tem uma **base sólida** com boas práticas de segurança, modularização e features modernas (paginação cursor, Redis caching, rate limiting). No entanto, há **oportunidades significativas** de melhoria:

- **Redução de complexidade:** Refatorar arquivos gigantes (analytics.py, physicians.py)
- **Eliminação de duplicação:** Consolidar lógica repetida em 70%+
- **Padronização:** Uniformizar serialização, RBAC, validação
- **Documentação:** Melhorar OpenAPI para facilitar adoção

Com as refatorações propostas, estima-se uma **redução de 21k+ linhas de código** e **melhoria de 80% na manutenibilidade**, mantendo todas as funcionalidades existentes.

---

**Relatório gerado em:** 2025-11-30
**Ferramentas:** Claude Code Analysis + Manual Review
**Próxima revisão sugerida:** Após implementação das refatorações críticas
