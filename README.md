# Clínica Oncológica - Sistema Integrado

Sistema de gestão para clínica oncológica com backend FastAPI, frontend React e interface de quiz Next.js.

## Estrutura do Projeto

```
clinica-oncologica-v02-1/
├── backend-hormonia/       # API FastAPI (Python 3.13)
├── frontend-hormonia/      # Dashboard React 19 + Vite 6
├── quiz-mensal-interface/  # Interface de Quiz Next.js 14
```

## Pré-requisitos

- Node.js 20+
- Python 3.13+
- PostgreSQL 15+
- Redis 7+

## Setup por Aplicação

### Backend (FastAPI)

```bash
cd backend-hormonia

# Criar ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou: .venv\Scripts\activate  # Windows

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas configurações

# Rodar migrations
alembic upgrade head

# Iniciar servidor
uvicorn app.main:app --reload --port 8000
```

### Frontend (React + Vite)

```bash
cd frontend-hormonia

# Instalar dependências
npm install

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas configurações

# Desenvolvimento
npm run dev

# Build de produção
npm run build:prod

# Testes
npm run test
npm run test:e2e
```

### Quiz Interface (Next.js)

```bash
cd quiz-mensal-interface

# Instalar dependências
npm install

# Configurar variáveis de ambiente
cp .env.example .env.local
# Editar .env.local com suas configurações

# Desenvolvimento
npm run dev

# Build de produção
npm run build

# Testes
npm run test:unit
```

## Variáveis de Ambiente Obrigatórias

### Backend
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `ENCRYPTION_KEY` - 32 caracteres para criptografia AES
- `HASH_SALT` - 32 caracteres para hash
- `CSRF_SECRET_KEY` - 32 caracteres para CSRF

### Frontend
- `VITE_API_URL` - URL do backend
- `VITE_SENTRY_DSN` - (opcional) Sentry DSN
- `VITE_FIREBASE_*` - Configurações Firebase Auth

## Scripts Úteis

| App | Comando | Descrição |
|-----|---------|-----------|
| frontend | `npm run dev` | Inicia dev server |
| frontend | `npm run build:prod` | Build de produção |
| frontend | `npm run lint` | Linting |
| frontend | `npm run test` | Testes unitários |
| frontend | `npm run test:e2e` | Testes E2E |
| quiz | `npm run dev` | Inicia dev server |
| quiz | `npm run build` | Build de produção |
| backend | `uvicorn app.main:app --reload` | Dev server |
| backend | `alembic upgrade head` | Rodar migrations |
| backend | `pytest` | Testes |

## Importante

- **NÃO** execute `npm install` na raiz do projeto
- Cada aplicação tem seu próprio `node_modules`
- Use o diretório correto antes de instalar dependências
