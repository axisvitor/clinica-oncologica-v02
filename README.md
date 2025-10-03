# Clínica Oncológica v2 - Sistema Hormonia

**Data**: 2025-10-02
**Versão**: 2.1
**Status**: Produção

## 📋 Visão Geral

Sistema completo de gestão oncológica com automação WhatsApp, IA e gestão de pacientes.

**Arquitetura**: Monorepo com 3 aplicações integradas
- **Backend**: FastAPI + PostgreSQL + Redis (Supabase + Firebase)
- **Frontend**: React + TypeScript + Vite
- **Quiz Interface**: Interface pública de questionários

## 🗂️ Estrutura do Repositório

```
clinica-oncologica-v02/
├── backend-hormonia/          # API Backend FastAPI
│   ├── app/                   # Código fonte
│   ├── alembic/               # Migrations
│   ├── tests/                 # Testes
│   ├── docs/                  # 📚 Documentação Backend
│   └── SCHEMA_MASTER_COMPLETO.sql (v2.1)
│
├── frontend-hormonia/         # Interface Admin/Médicos
│   ├── src/                   # Código React
│   ├── public/                # Assets
│   └── docs/                  # 📚 Documentação Frontend
│
└── quiz-mensal-interface/     # Interface Pública Quiz
    ├── src/                   # Código React
    └── docs/                  # 📚 Documentação Quiz
```

## 📚 Documentação

### Backend ([backend-hormonia/docs/](backend-hormonia/docs/README.md))
- [🔐 Segurança](backend-hormonia/docs/security/AUTHENTICATION_GUIDE.md)
  - [RLS via API](backend-hormonia/docs/security/rls/TESTES_RLS_API_GUIA.md)
  - [Firebase Setup](backend-hormonia/docs/security/FIREBASE_ENV_SETUP.md)
- [🗄️ Banco de Dados](backend-hormonia/docs/db/BANCO_DE_DADOS_COMPLETO.md)
  - [Schema Master](backend-hormonia/SCHEMA_MASTER_COMPLETO.sql) (v2.1)
- [🚀 API](backend-hormonia/docs/api/API.md)
- [📦 Deployment](backend-hormonia/docs/deployment/DEPLOYMENT.md)
- [🔴 Redis](backend-hormonia/docs/redis/REDIS_USAGE_GUIDE.md)
- [📊 Monitoramento](backend-hormonia/docs/monitoring/QUERY_PERFORMANCE_MONITORING.md)
- [🧪 Testes](backend-hormonia/docs/testing/QUIZ_E2E_TESTING_METRICS.md)

### Frontend ([frontend-hormonia/docs/](frontend-hormonia/docs/README.md))
- [🏗️ Arquitetura](frontend-hormonia/docs/architecture/TYPE_SYSTEM.md)
- [🔐 Auth Context](frontend-hormonia/docs/auth/MedicoAuthContext-Usage.md)
- [🧩 Componentes](frontend-hormonia/docs/components/COMPONENTS_GUIDE.md)
- [🚀 Deployment](frontend-hormonia/docs/deployment/DEPLOYMENT_GUIDE.md)
- [🧪 Testes](frontend-hormonia/docs/testing/TESTING_GUIDE.md)

### Quiz Interface ([quiz-mensal-interface/docs/](quiz-mensal-interface/docs/README.md))
- [🚀 Deployment](quiz-mensal-interface/docs/deployment/DEPLOYMENT_GUIDE.md)
- [🔗 Integração](quiz-mensal-interface/docs/integration/quiz-integration-report.md)
- [🔐 Segurança](quiz-mensal-interface/docs/security/SECURITY_AUDIT.md)

## 🚀 Quick Start

### Backend
```bash
cd backend-hormonia
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend-hormonia
npm install
npm run dev
```

### Quiz Interface
```bash
cd quiz-mensal-interface
npm install
npm run dev
```

## 🔐 Segurança

- **RLS (Row Level Security)**: 7 roles, políticas por tabela
- **Authentication**: JWT + Firebase + Supabase
- **Rate Limiting**: 100 req/min por IP
- **Audit Trail**: Logs completos de acesso

## ⚡ Performance

- **Redis Cache**: Dual-client (sync/async)
- **Connection Pooling**: DB + Redis otimizado
- **AI Cache**: 84.8% redução de chamadas Gemini
- **Middleware**: Stack otimizado

## 🗄️ Banco de Dados

- **PostgreSQL**: Supabase managed
- **Schema**: [SCHEMA_MASTER_COMPLETO.sql](backend-hormonia/SCHEMA_MASTER_COMPLETO.sql) v2.1
- **Migrations**: Alembic
- **RLS**: Validação runtime via middleware

## 🤖 Integrações

- **IA**: Google Gemini (insights, recomendações)
- **WhatsApp**: Evolution API (mensagens, flows)
- **Auth**: Firebase + Supabase dual-auth
- **Storage**: Firebase Storage
- **Cache**: Redis Cloud

## 📊 Stack Tecnológica

### Backend
- Python 3.13+
- FastAPI
- SQLAlchemy + Alembic
- PostgreSQL (Supabase)
- Redis
- Celery

### Frontend
- React 18
- TypeScript
- Vite
- Tailwind CSS
- Firebase SDK

### Quiz Interface
- React 18
- TypeScript
- Vite
- Tailwind CSS

## 🧪 Testing

```bash
# Backend
cd backend-hormonia && pytest --cov=app

# Frontend
cd frontend-hormonia && npm test

# Quiz
cd quiz-mensal-interface && npm test
```

## 📦 Deployment

- **Backend**: Railway/Render
- **Frontend**: Vercel/Netlify
- **Quiz**: Vercel/Netlify
- **DB**: Supabase
- **Cache**: Redis Cloud

Ver guias específicos em cada `docs/deployment/`

## 📄 Convenções

- **Língua**: PT-BR (padrão)
- **Canônicos**: Docs de referência atuais
- **Arquivados**: Relatórios em `docs/incidents/_archive/`
- **Versionamento**: Semântico (MAJOR.MINOR.PATCH)

## 📋 Relatórios Arquivados

Relatórios históricos de incidentes, migrações e correções estão organizados em:
- [Backend - Incidents Archive](backend-hormonia/docs/incidents/_archive/)
- [Frontend - Incidents Archive](frontend-hormonia/docs/incidents/_archive/)
- [Quiz - Incidents Archive](quiz-mensal-interface/docs/incidents/_archive/)

## 🆘 Troubleshooting

```bash
# Backend health
curl http://localhost:8000/health

# Redis health
curl http://localhost:8000/api/v1/redis/health

# DB connection
psql $DATABASE_URL -c "SELECT 1"
```

## 📞 Suporte

- **Documentação**: Ver índices em cada `docs/README.md`
- **Issues**: GitHub Issues
- **Wiki**: GitHub Wiki (em desenvolvimento)

---

**Clínica Oncológica v2** - Sistema Hormonia
Python 3.13+ | FastAPI | React | PostgreSQL | Redis | Firebase
