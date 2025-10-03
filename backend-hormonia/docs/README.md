# Documentação Backend - Clínica Oncológica

**Última Atualização**: 2025-10-02

## 📋 Índice Geral

### 🔐 Segurança
- [Guia de Autenticação](security/AUTHENTICATION_GUIDE.md)
- [RLS via API - Guia de Testes](security/rls/TESTES_RLS_API_GUIA.md)
- [Segurança Firebase](security/FIREBASE_SECURITY.md)
- [Setup de Ambiente Firebase](security/FIREBASE_ENV_SETUP.md)
- [Implementação de Sincronização Firebase](security/FIREBASE_SYNC_IMPLEMENTATION.md)

### 🗄️ Banco de Dados
- [Documentação Completa do Banco](db/BANCO_DE_DADOS_COMPLETO.md)
- [Schema Master SQL](../SCHEMA_MASTER_COMPLETO.sql) (v2.1)
- [Relatórios](db/reports/)

### 🚀 API
- [Documentação da API](api/API.md)
- [Índice da API Pública de Quiz](QUIZ_PUBLIC_API_INDEX.md)
- [Referência Rápida de Migrations](MIGRATION_QUICK_REFERENCE.md)

### 📦 Deployment
- [Guia de Deployment](deployment/DEPLOYMENT.md)
- [Variáveis de Ambiente](deployment/ENVIRONMENT_VARIABLES.md)
- [Guia de Migrations](deployment/MIGRATIONS_GUIDE.md)
- [Upgrade Python 3.13](PYTHON_313_UPGRADE.md)

### 🔴 Redis
- [Guia de Uso do Redis](redis/REDIS_USAGE_GUIDE.md)
- [Status Final do Redis](redis/REDIS_FINAL_STATUS.md)
- [Guia de Remoção Legacy](redis/REDIS_LEGACY_REMOVAL_GUIDE.md)
- [Sumário de Migração](redis/REDIS_MIGRATION_SUMMARY.md)

### 📊 Monitoramento
- [Monitoramento de Performance de Queries](monitoring/QUERY_PERFORMANCE_MONITORING.md)
- [Grafana Dashboard](../config/monitoring/grafana/README.md)

### 🧪 Testes
- [Métricas de Testes E2E do Quiz](testing/QUIZ_E2E_TESTING_METRICS.md)
- [Guia de Testes RLS via API](security/rls/TESTES_RLS_API_GUIA.md)

### 📋 Relatórios Arquivados
- [Relatórios de Incidentes](incidents/_archive/)

## 📁 Estrutura de Backend

```
backend-hormonia/
├── app/
│   ├── api/v1/              # REST endpoints
│   │   ├── auth.py          # Authentication
│   │   ├── patients.py      # Patient management
│   │   ├── messages.py      # WhatsApp messaging
│   │   ├── flows.py         # Conversation flows
│   │   ├── quiz.py          # Quiz system
│   │   └── reports.py       # Reports & analytics
│   ├── core/                # Core modules
│   │   ├── application_factory.py
│   │   ├── middleware_setup.py
│   │   ├── session_manager.py
│   │   └── redis_manager.py
│   ├── models/              # SQLAlchemy models
│   ├── schemas/             # Pydantic schemas
│   └── services/            # Business logic
├── alembic/                 # Database migrations
├── tests/                   # Pytest tests
├── scripts/                 # Utility scripts
└── docs/                    # Esta documentação
```

## 🚀 Quick Start

```bash
# Install
cd backend-hormonia
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your credentials

# Run
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Test
pytest
```

## 🔐 Segurança

### Row Level Security (RLS)
- 7 roles: admin, doctor, patient, service_provider, system, viewer, external_integration
- Políticas por tabela no PostgreSQL
- Audit trail completo
- Validação runtime via middleware

### Authentication
- JWT com access token (30min) + refresh token (7 dias)
- Token blacklist no Redis
- Auto-refresh 5min antes de expirar
- Integração Firebase + Supabase

### Rate Limiting
- 100 req/min por IP
- 5 login attempts / 15 min
- Configurável por endpoint

## ⚡ Performance

### Redis Cache
- Dual-client (sync/async)
- API response caching
- Session storage
- Rate limiting storage

### Optimizations
- Connection pooling (DB + Redis)
- Middleware stack otimizado
- Thread-safe session manager
- 84.8% redução de chamadas Gemini via cache

## 📊 Database

### Models (SQLAlchemy)
- User, Patient, Message, Flow, QuizSession, Report, Alert, AuditLog

### Migrations (Alembic)
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Run migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## 🧪 Testing

```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific tests
pytest tests/test_auth.py
pytest tests/test_core/  # Modular architecture tests

# Verbose
pytest -v
```

**Coverage Target:** 95%+

## 📚 Navegação

- [← Voltar para Raiz](../../README.md)
- [Frontend →](../../frontend-hormonia/docs/README.md)
- [Quiz Interface →](../../quiz-mensal-interface/docs/README.md)

## 📄 API Documentation

Acesse a documentação interativa:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Convenções

- **Canônicos**: Documentos de referência atuais e mantidos
- **Arquivados**: Relatórios históricos em `incidents/_archive/`
- **Língua**: PT-BR (padrão do projeto)

---

**Stack:** Python 3.13+ | FastAPI | PostgreSQL | Redis | Celery | Supabase + Firebase
