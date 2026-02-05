# Arquitetura do Sistema - Clinica Oncologica Hormonia

**Versao:** 2.0.0
**Data:** 2025-12-26
**Status:** Producao

---

## Sumario Executivo

O Sistema Hormonia e uma plataforma integrada de gestao de pacientes oncologicos que combina:

- **Backend API** em FastAPI com arquitetura modular e seguranca enterprise
- **Frontend SPA** em React 19 com TypeScript e React Query
- **Integracao WhatsApp** para comunicacao automatizada com pacientes
- **Sistema de Flows** para acompanhamento de tratamentos
- **Quiz Mensal** para monitoramento de bem-estar

---

## 1. Diagrama de Arquitetura

```
+------------------------------------------------------------------+
|                         CLIENTES                                  |
+------------------------------------------------------------------+
|  +-------------------+  +-------------------+  +----------------+ |
|  |   Admin Panel     |  |   Quiz Interface  |  |   WhatsApp     | |
|  |   (React SPA)     |  |   (Next.js 14)    |  |   (Mobile)     | |
+------------------------------------------------------------------+
            |                      |                     |
            v                      v                     v
+------------------------------------------------------------------+
|                      CAMADA DE APLICACAO                          |
+------------------------------------------------------------------+
|  +-------------------------------------------------------------+  |
|  |                    FastAPI Application                       |  |
|  |  +------------------+  +------------------+  +-------------+ |  |
|  |  |   Middlewares    |  |    API Routers   |  |  Background | |  |
|  |  |  CORS, CSRF,     |  |  /api/v2/*       |  |   Tasks     | |  |
|  |  |  Rate Limit      |  |  Auth, Patients  |  |   (Celery)  | |  |
|  |  +------------------+  +------------------+  +-------------+ |  |
|  +-------------------------------------------------------------+  |
+------------------------------------------------------------------+
            |                      |                     |
            v                      v                     v
+------------------------------------------------------------------+
|                      CAMADA DE DADOS                              |
+------------------------------------------------------------------+
|  +-------------------+  +-------------------+  +----------------+ |
|  |   PostgreSQL      |  |      Redis        |  |    Firebase    | |
|  |   (77 tabelas)    |  |   (Cache/Queue)   |  |   (Auth)       | |
+------------------------------------------------------------------+
```

---

## 2. Componentes Principais

### 2.1 Backend (`/backend-hormonia`)

```
backend-hormonia/
├── app/
│   ├── main.py                    # Entry point FastAPI
│   ├── api/v2/routers/           # 60+ endpoints
│   ├── core/                      # Configuracoes centrais
│   ├── models/                    # 77 SQLAlchemy Models
│   ├── services/                  # Business Logic
│   ├── repositories/              # Data Access Layer
│   ├── orchestration/             # Saga Pattern
│   ├── domain/                    # DDD Logic
│   └── middleware/                # CSRF, Rate Limit
├── alembic/                       # 37 Migrations
└── tests/                         # 5,423 test functions
```

### 2.2 Frontend (`/frontend-hormonia`)

```
frontend-hormonia/
├── src/
│   ├── lib/api-client/           # HTTP client (CSRF handling)
│   ├── components/               # UI Components (Radix UI)
│   ├── features/                 # Feature modules
│   ├── pages/                    # Route pages
│   └── hooks/                    # Custom hooks
└── vite.config.ts                # Build config
```

---

## 3. Padroes Arquiteturais

### 3.1 Saga Pattern (Transacoes Distribuidas)

```
┌─────────┐   ┌─────────────┐   ┌─────────┐   ┌─────────┐
│ Request │──>│    Saga     │──>│ Patient │──>│  Flow   │
│  POST   │   │Orchestrator │   │  Create │   │  Init   │
└────┬────┘   └──────┬──────┘   └────┬────┘   └────┬────┘
     │               │               │              │
     │   1. Lock     │               │              │
     │──────────────>│               │              │
     │               │   2. Create   │              │
     │               │──────────────>│              │
     │               │   Patient OK  │              │
     │               │<──────────────│              │
     │               │               │   3. Init    │
     │               │──────────────────────────────>│
     │               │               │   Flow OK    │
     │               │<──────────────────────────────│
     │   4. Commit   │                              │
     │<──────────────│                              │
```

**Implementacao:** `/app/orchestration/saga_orchestrator.py`

- Distributed Lock (Redis) para prevenir duplicatas
- Unit of Work com single commit
- Compensacao automatica em caso de falha
- Idempotencia via chave unica

### 3.2 Repository Pattern

```python
class PatientRepository(BaseRepository[Patient]):
    def get_by_phone_hash(self, phone_hash: str) -> Optional[Patient]:
        return self.db.query(Patient).filter(
            Patient.phone_hash == phone_hash,
            Patient.deleted_at.is_(None)
        ).first()
```

### 3.3 State Machine (Flows)

```python
class FlowState(Enum):
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

VALID_TRANSITIONS = {
    FlowState.ONBOARDING: [FlowState.ACTIVE, FlowState.CANCELLED],
    FlowState.ACTIVE: [FlowState.PAUSED, FlowState.COMPLETED],
    FlowState.PAUSED: [FlowState.ACTIVE, FlowState.CANCELLED],
}
```

---

## 4. Seguranca (8 Camadas)

| Camada | Componente | Implementacao |
|--------|------------|---------------|
| 1 | Transporte | HTTPS/TLS, HSTS |
| 2 | CORS | Origin whitelist |
| 3 | Security Headers | X-Frame-Options, CSP |
| 4 | Rate Limiting | Redis sliding window |
| 5 | CSRF | Double Submit Cookie |
| 6 | Autenticacao | Firebase + Redis Sessions |
| 7 | Autorizacao | RBAC |
| 8 | Input Validation | Pydantic schemas |

---

## 5. Performance e Caching

### Cache em 3 Camadas

| Layer | Key Pattern | TTL | Latencia |
|-------|-------------|-----|----------|
| 1 | token:{hash} | 1h | 5ms |
| 2 | user:{uid} | 15min | 5ms |
| 3 | session:{id} | 5d | 2-5ms |

**Performance:**
- Cache hit: ~2-5ms (90x mais rapido)
- Cold authentication: ~250-350ms

---

## 6. Integracoes Externas

| Servico | Proposito | SDK |
|---------|-----------|-----|
| Firebase | Autenticacao | firebase-admin |
| Redis | Cache/Sessions/Locks | redis-py |
| Evolution API | WhatsApp | REST |
| Google Gemini | AI/Humanizacao | google-generativeai |
| PostgreSQL | Dados | SQLAlchemy |

---

## 7. Endpoints da API

### Autenticacao

| Metodo | Endpoint | Rate Limit |
|--------|----------|------------|
| GET | `/api/v2/auth/csrf-token` | 60/min |
| POST | `/api/v2/auth/firebase/verify` | 10/min |
| GET | `/api/v2/auth/verify-session` | 100/min |
| DELETE | `/api/v2/auth/logout` | 20/min |

### Pacientes

| Metodo | Endpoint | Proposito |
|--------|----------|-----------|
| GET | `/api/v2/patients` | Listar |
| POST | `/api/v2/patients` | Criar (Saga) |
| GET | `/api/v2/patients/{id}` | Obter |
| PATCH | `/api/v2/patients/{id}` | Atualizar |
| DELETE | `/api/v2/patients/{id}` | Soft delete |

---

**Documento gerado por:** System Architecture Agent
**Data:** 2025-12-26
