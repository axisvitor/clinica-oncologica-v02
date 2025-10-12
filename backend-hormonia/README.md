# Sistema Hormonia Backend

**AI-Powered Patient Communication Platform for Hormone Therapy**
*Version: 1.0.0 | Python 3.13+ | FastAPI Framework*

---

## 🚀 Quick Start

### One-Command Setup

```bash
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# or
source venv/bin/activate  # Linux/Mac

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 4. Start development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Alternative Setup Methods

```bash
# Bash helper
chmod +x scripts/backend_init.sh && ./scripts/backend_init.sh check

# Python helper
python scripts/backend_init.py --verbose
```

### Health Checks

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/redis/health
curl http://localhost:8000/api/v1/enhanced/monitoring/dashboard
```

---

## 📋 System Overview

Sistema Hormonia is a comprehensive AI-powered platform for oncology patient care, featuring automated communication flows, intelligent assessments, and comprehensive analytics.

### Key Features

- **🤖 AI-Powered Communication**: Personalized patient interactions using Google Gemini
- **📊 Interactive Assessments**: YAML-configured quiz system with real-time validation
- **🔄 Conversation Flows**: Multi-phase automated patient engagement workflows
- **⚡ High Performance**: Redis-based caching with 84.8% performance improvements
- **🔐 Enterprise Security**: HIPAA-compliant with comprehensive audit trails
- **📱 Real-time Updates**: WebSocket-based live notifications
- **📈 Advanced Analytics**: Patient engagement tracking and clinical insights

### Modular Architecture

The system features a completely refactored modular architecture with clean separation of responsibilities, improved performance, and greater maintainability.

## 🛠️ Technology Stack

- **Framework**: FastAPI 0.104+
- **Language**: Python 3.13+
- **Database**: PostgreSQL (via Supabase)
- **Cache**: Redis (dual client architecture)
- **Authentication**: JWT with refresh tokens
- **Async Processing**: Celery with Redis broker
- **WhatsApp Integration**: Evolution API
- **AI**: Google Gemini with intelligent caching
- **Documentation**: Auto-generated Swagger/OpenAPI
- **Testing**: Pytest with comprehensive coverage
- **Containerization**: Docker + Docker Compose
- **Architecture**: Modular with Factory Pattern

## 🏗️ Architecture Overview

### Project Structure

```
Backend/
├── app/                         # Main application code
│   ├── api/                    # API endpoints
│   │   └── v1/                # API v1 routes (auth, patients, quiz, flows, etc.)
│   ├── core/                   # Core modular architecture
│   │   ├── application_factory.py    # Application factory
│   │   ├── middleware_setup.py       # Middleware configuration
│   │   ├── lifespan.py              # Application lifecycle
│   │   └── session_manager.py        # Thread-safe sessions
│   ├── models/                # SQLAlchemy models
│   ├── schemas/               # Pydantic schemas
│   ├── services/              # Business logic
│   └── main.py               # Entry point (25 lines)
├── docs/                      # Consolidated documentation
│   ├── api/                   # API documentation
│   │   └── API.md                  # Complete API reference
│   ├── deployment/            # Deployment guides
│   │   └── DEPLOYMENT.md           # Unified deployment guide
│   └── systems/               # System documentation
│       ├── FLOW_SYSTEM.md          # AI conversation flows
│       ├── QUIZ_SYSTEM.md          # Medical assessments
│       └── REDIS_GUIDE.md          # Redis implementation
├── alembic/                   # Database migrations
├── tests/                     # Automated tests
├── scripts/                   # Utility scripts
└── requirements.txt           # Python dependencies
```

### Core Architecture Components

1. **Application Factory**: FastAPI app creation and configuration
2. **Middleware Setup**: Optimized middleware configuration
3. **Lifespan Manager**: Application startup/shutdown lifecycle
4. **Session Manager**: Thread-safe database sessions with contextvars
5. **Redis Manager**: Dual sync/async Redis clients with connection pooling

### Architecture Benefits

- **✅ Separation of Concerns**: Each component has a specific function
- **✅ Thread Safety**: Safe session management in multi-worker environments
- **✅ Performance**: Middleware and connection optimizations
- **✅ Testability**: Isolated and testable components
- **✅ Maintainability**: Organized and easy-to-maintain code
- **✅ Backward Compatibility**: Compatible with existing code

## ⚙️ Installation & Configuration

### Prerequisites

- Python 3.13+
- PostgreSQL (or Supabase)
- Redis
- Docker and Docker Compose (optional)

### Environment Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/axisvitor/clinica-oncologica-v02.git
   cd clinica-oncologica-v02/backend-hormonia
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate     # Windows
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env file with your configurations
   ```

### Key Environment Variables

```env
# Application
DEBUG=true
ENVIRONMENT=development
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Supabase
SUPABASE_URL=your-supabase-url
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/hormonia

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=

# Evolution API (WhatsApp)
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_INSTANCE_NAME=hormonia
EVOLUTION_API_KEY=your-evolution-api-key

# AI Services
LANGCHAIN_API_KEY=your-langchain-key
GOOGLE_API_KEY=your-google-key

# Logging Configuration (Enhanced for Critical Bug Fixes)
LOG_LEVEL=INFO
MAX_LOGS_PER_SECOND=100
ENABLE_REQUEST_LOGGING=true
LOG_STACK_TRACES=true
LOG_DEDUPLICATION_WINDOW=300

# Error Tracking Configuration (Critical Bug Fixes)
ENABLE_ERROR_TRACKING=true
MAX_ERROR_LOGS=1000
ERROR_DEDUPLICATION_WINDOW=3600
ERROR_TRACKING_RATE_LIMIT=10
CRITICAL_ERROR_NOTIFICATION=true
```

### 🔧 Enhanced Configuration (Critical Bug Fixes)

The system now includes enhanced logging and error tracking configuration to prevent and monitor critical issues:

#### Logging Configuration
- **`LOG_LEVEL`**: Controls logging verbosity (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **`MAX_LOGS_PER_SECOND`**: Rate limiting to prevent log flooding (Railway limit: 500/sec)
- **`ENABLE_REQUEST_LOGGING`**: Toggle request logging (uses DEBUG level for routine operations)
- **`LOG_STACK_TRACES`**: Enable/disable stack trace logging for errors
- **`LOG_DEDUPLICATION_WINDOW`**: Time window for preventing duplicate log messages

#### Error Tracking Configuration
- **`ENABLE_ERROR_TRACKING`**: Centralized error tracking and database logging
- **`MAX_ERROR_LOGS`**: Maximum error logs stored (prevents unbounded growth)
- **`ERROR_DEDUPLICATION_WINDOW`**: Groups similar errors with count tracking
- **`ERROR_TRACKING_RATE_LIMIT`**: Prevents error log flooding
- **`CRITICAL_ERROR_NOTIFICATION`**: Alerts for critical errors (DI, role enum, schema issues)

#### Deployment Validation
Run validation scripts before deployment:
```bash
# Full validation
python scripts/deployment_validation.py --base-url http://your-api-url

# Quick health check
python scripts/validate_deployment_health.py

# Critical fixes validation
python scripts/validate_critical_fixes.py
```

For complete configuration documentation, see [docs/DEPLOYMENT_CONFIGURATION.md](docs/DEPLOYMENT_CONFIGURATION.md).

---

## 💻 Development Setup

### Modular Architecture Development

```bash
# 1. Clone and setup
git clone https://github.com/axisvitor/clinica-oncologica-v02.git
cd clinica-oncologica-v02/backend-hormonia
python -m venv venv
source venv/bin/activate  # Linux/Mac or venv\Scripts\activate on Windows
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your configurations

# 3. Initialize modular architecture
python -c "from app.core.application_factory import create_application; print('✅ Modular architecture OK')"

# 4. Run migrations
alembic upgrade head

# 5. Start application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Using Makefile (Recommended)

```bash
# View all available commands
make help

# Setup development environment
make setup

# Start development server (uses modular architecture)
make dev

# Run tests (includes modular architecture tests)
make test

# Run tests with coverage
make test-cov

# Start Docker services (Redis, Celery)
make docker-up

# Stop Docker services
make docker-down

# Run migrations
make migrate

# Create new migration
make migration name="migration description"

# Populate test data
make populate-test-data
```

### Verificação da Arquitetura Modular

```bash
# Verificar componentes da nova arquitetura
python -c "
from app.core.application_factory import create_application
from app.core.session_manager import get_session_manager, get_session_health_info
from app.core.redis_manager import get_redis_manager

app = create_application()
print('✅ Application Factory: OK')
print('✅ Session Manager: OK')
print('✅ Redis Manager: OK')
print('📊 Arquitetura modular funcionando perfeitamente!')
"

# Verificar health checks
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/redis/health
```

### População de Dados de Teste

Para desenvolvimento e demonstração, você pode popular o banco com dados de teste realistas:

```bash
# Testar conexão com o banco
python scripts/test_db_connection.py

# Popular com dados de teste (mantém dados existentes)
python scripts/populate_test_data.py

# Popular limpando dados existentes primeiro
python scripts/populate_test_data.py --clean

# Ou usando o wrapper Windows
scripts\run_populate_test_data.bat
scripts\run_populate_test_data.bat clean
```

**Dados criados:**
- 3 usuários médicos com credenciais de teste
- 10 pacientes com dados brasileiros realistas
- 20 mensagens WhatsApp simuladas
- 5 sessões de questionários completas
- 3 alertas de diferentes severidades

**Credenciais de teste:**
- `dr.silva@clinicaoncologica.com.br` / `senha123`
- `dra.santos@clinicaoncologica.com.br` / `senha123` 
- `admin@clinicaoncologica.com.br` / `[REMOVED-WEAK-PASSWORD]`

Veja mais detalhes em [`scripts/README.md`](scripts/README.md).

### Comandos Manuais

```bash
# 🎯 Iniciar servidor com nova arquitetura modular
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ✅ Executar testes (inclui testes de arquitetura)
pytest
pytest tests/test_core/  # Testes específicos da arquitetura modular

# 📊 Executar migrações
alembic upgrade head

# 🔧 Criar migração
alembic revision --autogenerate -m "descrição"

# ⚡ Iniciar Celery worker
celery -A app.celery_app worker --loglevel=info

# 📅 Iniciar Celery beat
celery -A app.celery_app beat --loglevel=info

# 🌸 Monitoramento Celery (Flower)
celery -A app.celery_app flower --port=5555

# 🔍 Testar componentes individuais
python -c "from app.core.session_manager import SessionManager; print(SessionManager().__doc__)"
python -c "from app.core.redis_manager import get_redis_manager; print('Redis Manager OK')"
```

### Usando Docker

```bash
# Iniciar todos os serviços
docker-compose up -d

# Ver logs
docker-compose logs -f

# Parar serviços
docker-compose down

# Rebuild e restart
docker-compose up --build -d
```

## 🔌 API Endpoints

The API offers 100+ endpoints organized across multiple modules:

### Authentication
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh token
- `POST /api/v1/auth/logout` - User logout

### Patients
- `GET /api/v1/patients` - List patients
- `POST /api/v1/patients` - Create patient
- `GET /api/v1/patients/{id}` - Get patient details
- `PUT /api/v1/patients/{id}` - Update patient
- `DELETE /api/v1/patients/{id}` - Delete patient

### Messages
- `GET /api/v1/messages` - List messages
- `POST /api/v1/messages/send` - Send message
- `GET /api/v1/messages/threads` - Conversation threads

### Conversation Flows
- `GET /api/v1/flows` - List flows
- `POST /api/v1/flows` - Create flow
- `PUT /api/v1/flows/{id}` - Update flow

### Assessments
- `GET /api/v1/quiz/templates` - Quiz templates
- `POST /api/v1/quiz/responses` - Submit response
- `GET /api/v1/quiz/analytics` - Response analytics

### Reports
- `GET /api/v1/reports` - List reports
- `POST /api/v1/reports/generate` - Generate report
- `GET /api/v1/reports/{id}/download` - Download PDF

### Analytics
- `GET /api/v1/analytics/dashboard` - Dashboard data
- `GET /api/v1/analytics/insights` - AI insights

**For complete API documentation, see:** [docs/api/API.md](docs/api/API.md)

---

## 📚 API Documentation

Interactive API documentation is available at:

- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`
- **Complete Reference**: [docs/api/API.md](docs/api/API.md)

## 🧪 Testing

### Running Tests with Modular Architecture

```bash
# 🧪 All tests (includes modular architecture tests)
pytest

# 📊 Tests with coverage
pytest --cov=app --cov-report=html

# 🔧 Specific modular architecture tests
pytest tests/test_core/

# 🎯 Specific component tests
pytest tests/test_core/test_application_factory.py
pytest tests/test_core/test_session_manager.py
pytest tests/test_core/test_redis_manager.py

# 📋 Legacy tests (still working)
pytest tests/test_patients.py
pytest tests/test_auth.py

# 🔍 Verbose tests
pytest -v

# 🚀 Architecture integration tests
pytest tests/test_integration/test_modular_architecture.py
```

### Estrutura de Testes Atualizada

```
tests/
├── conftest.py                    # Configurações e fixtures
├── test_core/                     # 🆕 Testes da arquitetura modular
│   ├── test_application_factory.py    # Testes do factory
│   ├── test_middleware_setup.py       # Testes de middleware
│   ├── test_router_registry.py        # Testes de routers
│   ├── test_lifespan.py              # Testes de ciclo de vida
│   ├── test_session_manager.py        # Testes de sessões
│   └── test_redis_manager.py          # Testes Redis
├── test_integration/              # 🆕 Testes de integração
│   └── test_modular_architecture.py   # Integração end-to-end
├── test_auth.py                   # Testes de autenticação
├── test_patients.py               # Testes de pacientes
├── test_messages.py               # Testes de mensagens
├── test_flows.py                  # Testes de fluxos
├── test_quiz.py                   # Testes de questionários
└── test_reports.py                # Testes de relatórios
```

### Testes de Performance da Arquitetura

```bash
# 🚀 Benchmark da nova arquitetura vs legacy
pytest tests/test_performance/test_architecture_benchmark.py

# 📈 Testes de carga com middleware otimizado
pytest tests/test_performance/test_middleware_performance.py

# 🔄 Testes de concorrência com session manager
pytest tests/test_performance/test_session_concurrency.py
```

## Monitoramento e Observabilidade

### Logs com Nova Arquitetura

Os logs são configurados com diferentes níveis e estrutura aprimorada:

- **DEBUG**: Informações detalhadas para desenvolvimento (inclui session manager, Redis)
- **INFO**: Informações gerais de operação (startup de componentes modulares)
- **WARNING**: Avisos que não impedem a operação
- **ERROR**: Erros que impedem operações específicas
- **CRITICAL**: Erros críticos que podem parar o sistema

### Health Checks Avançados

```bash
# 🩺 Health check básico da aplicação
curl http://localhost:8000/health

# 🔧 Health check detalhado do Redis
curl http://localhost:8000/api/v1/redis/health

# 📊 Status da arquitetura modular
python -c "
from app.core.session_manager import get_session_health_info
print('Session Health:', get_session_health_info())
"
```

### Métricas da Nova Arquitetura

- **🌸 Celery Flower**: `http://localhost:5555` - Monitoramento de tarefas
- **❤️ Application Health**: `GET /health` - Status da aplicação
- **⚡ Redis Health**: `GET /api/v1/redis/health` - Status Redis detalhado
- **📈 Metrics**: `GET /metrics` - Métricas Prometheus (se configurado)
- **🔄 Session Manager**: Métricas de sessões ativas e performance
- **🚀 Middleware Performance**: Tempo de execução de cada middleware

## Deployment com Nova Arquitetura

### Variáveis de Produção Otimizadas

```env
# 🎯 Core settings para arquitetura modular
DEBUG=false
ENVIRONMENT=production
ALLOWED_HOSTS=your-domain.com
CORS_ORIGINS=https://your-frontend-domain.com

# ⚡ Otimizações de performance
USE_MODULAR_ARCHITECTURE=true
MIDDLEWARE_OPTIMIZATION=true
SESSION_MANAGER_REDIS_CACHE=true

# 🔧 Configurações Redis dual-client
REDIS_URL=redis://your-redis-server:6379
REDIS_MAX_CONNECTIONS=20
REDIS_HEALTH_CHECK_INTERVAL=30
```

### Docker em Produção

```bash
# 🚀 Build da imagem com nova arquitetura
docker build -t hormonia-backend .

# 🎯 Run em produção com otimizações
docker run -d \
  --name hormonia-backend \
  -p 8000:8000 \
  --env-file .env.production \
  --restart unless-stopped \
  -e USE_MODULAR_ARCHITECTURE=true \
  hormonia-backend

# 📊 Verificar saúde da aplicação
docker exec hormonia-backend curl -s http://localhost:8000/health
docker exec hormonia-backend curl -s http://localhost:8000/api/v1/redis/health
```

### Deployment Checklist

```bash
# ✅ Pré-deployment
- [ ] Executar testes da arquitetura modular
- [ ] Verificar configurações de middleware
- [ ] Testar Redis dual-client em staging
- [ ] Verificar session manager performance
- [ ] Validar health checks

# ✅ Post-deployment
- [ ] Verificar logs de inicialização dos componentes
- [ ] Monitorar performance do middleware stack
- [ ] Validar funcionamento do session manager
- [ ] Verificar conexões Redis síncronas/assíncronas
- [ ] Confirmar health endpoints responsivos
```

## Contribuição

1. **Fork** o projeto
2. **Crie** uma branch para sua feature (`git checkout -b feature/nova-feature`)
3. **Commit** suas mudanças (`git commit -am 'Adiciona nova feature'`)
4. **Push** para a branch (`git push origin feature/nova-feature`)
5. **Abra** um Pull Request

### Padrões de Código

```bash
# Formatação
make format

# Linting
make lint

# Verificação completa
make format && make lint && make test
```

## 🚀 Deployment

### Production Deployment

For production deployment, consult our specialized guides:

- **📚 [Complete Deployment Guide](docs/deployment/DEPLOYMENT.md)** - Comprehensive backend deployment guide
- **🔧 [Railway Deployment](docs/deployment/RAILWAY_DEPLOYMENT.md)** - Railway platform deployment
- **🐳 [Docker Deployment](docs/deployment/DEPLOYMENT.md#docker-deployment)** - Docker containerization

### Key Deployment Topics

**Session Management:**
- Thread-safe session management with contextvars
- Request-scoped database sessions
- Automatic cleanup and transaction safety

**Redis Architecture:**
- Async and sync Redis clients
- SSL support for Redis Cloud
- Connection pooling and retry logic
- Health monitoring and metrics

**Environment Configuration:**
- Production-ready environment variables
- Security hardening settings
- Performance optimizations
- Monitoring configuration

**Scaling Strategy:**
- Horizontal and vertical scaling strategies
- Load balancer configuration
- Database optimization
- Resource requirements by load

---

## 📚 Additional Documentation

### System Guides
- **🤖 [AI Flow System](docs/systems/FLOW_SYSTEM.md)** - AI-powered conversation flows
- **📋 [Quiz System](docs/systems/QUIZ_SYSTEM.md)** - Medical assessment platform
- **⚡ [Redis Implementation](docs/systems/REDIS_GUIDE.md)** - Caching and session storage

### Deployment & Operations
- **🚀 [Deployment Guide](docs/deployment/DEPLOYMENT.md)** - Complete deployment guide
- **📊 [API Reference](docs/api/API.md)** - Complete API documentation
- **🔒 [Security Configuration](docs/deployment/DEPLOYMENT.md#security-hardening)** - Security best practices
- **⚡ [Performance Optimization](docs/deployment/DEPLOYMENT.md#production-optimizations)** - Performance tuning

### Quick Links
- **API Documentation**: `http://localhost:8000/docs`
- **Health Checks**: `http://localhost:8000/health`
- **Redis Status**: `http://localhost:8000/api/v1/redis/health`
- **Enhanced Monitoring**: `http://localhost:8000/api/v1/enhanced/monitoring/dashboard`

## 📞 Support

For support and questions:

- **📖 Documentation**: Check API documentation at `/docs`
- **🏗️ System Guides**: See `docs/systems/` for detailed system documentation
- **🐛 Issues**: Open an issue in the repository
- **📝 Logs**: Check application logs for debugging
- **🩺 Health Checks**: Use health endpoints for diagnostics

### Troubleshooting

```bash
# 🔍 Check components
python -c "
from app.core.application_factory import create_application
from app.core.session_manager import get_session_health_info
from app.core.redis_manager import get_redis_manager

try:
    app = create_application()
    health = get_session_health_info()
    redis_mgr = get_redis_manager()
    print('✅ All components working!')
except Exception as e:
    print(f'❌ Error: {e}')
"

# 📊 Detailed logs
tail -f logs/app.log | grep -E "(Session|Redis|Factory|Middleware)"
```

---

## 📜 License

This project is licensed under the [MIT License](../LICENSE).

---

**Hormonia Backend System** - Empowering healthcare through AI-driven patient engagement.

