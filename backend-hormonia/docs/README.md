# Documentação Backend - Clínica Oncológica

**Última Atualização**: 2025-11-12

## 📋 Navegação Rápida

### 🚀 Para Começar
- [Quick Start - Instalação e Configuração](guides/quickstart/)
- [Troubleshooting - Resolução de Problemas](guides/troubleshooting/)
- [Guia de Migrações](guides/migration/)

### 📚 API & Integrações
- [API REST - Endpoints e Guias](api/rest/)
- [API Pública de Quiz](api/public/)
- [Webhooks - Configuração e Segurança](api/webhooks/)

### 🏛️ Arquitetura & Design
- [Design do Sistema](architecture/system-design/)
- [Banco de Dados](database/) - ⚠️ Documentação atualizada e completa
- [Padrões de Design](architecture/patterns/)

### ⚙️ Operações & Produção
- [Deployment e Configuração](operations/deployment/)
- [Monitoramento e Métricas](operations/monitoring/)
- [Segurança](operations/security/)
- [Performance e Otimização](operations/performance/)
- [Manutenção](operations/maintenance/)

### 📖 Referências Técnicas
- [Implementações Específicas](reference/)
- [Configurações do Sistema](reference/)

### 📦 Arquivo Histórico
- [Relatórios de Migrações V2](archive/v2-migrations/)
- [Relatórios de Fases/Sprints](archive/phase-reports/)
- [Bug Fixes Documentados](archive/bug-fixes/)
- [Relatórios de Performance](archive/performance-reports/)

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

## 📝 Sobre esta Documentação

Esta documentação foi reestruturada em 2025-11-12 para melhor organização e navegabilidade:

- **Documentação Ativa**: Organizada por propósito em `guides/`, `api/`, `architecture/`, `operations/` e `reference/`
- **Documentação Histórica**: Migrada para `archive/` com subcategorias por tipo
- **Banco de Dados**: Mantida em `database/` - já estava atualizada e bem organizada
- **Navegação**: Cada pasta principal contém README próprio para facilitar a navegação

### Convenções

- **Guias Práticos**: Documentos how-to em `guides/`
- **Referências Técnicas**: Especificações em `reference/`
- **Arquivo**: Relatórios históricos e completados em `archive/`
- **Língua**: PT-BR (padrão do projeto)

---

**Stack:** Python 3.13+ | FastAPI | PostgreSQL | Redis | Celery | Supabase + Firebase
