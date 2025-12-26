# Sistema de Gestao Oncologica - Hormonia

Sistema integrado de gestao para clinica oncologica com foco em comunicacao personalizada com pacientes, acompanhamento de tratamentos e engajamento atraves de quiz mensais.

---

## Visao Geral

O **Hormonia** e uma plataforma completa de gestao oncologica que combina:

- **Gestao de Pacientes**: Cadastro, acompanhamento e historico medico
- **Comunicacao Inteligente**: Integracao WhatsApp via Evolution API com IA para personalizacao
- **Quiz Mensal**: Interface dedicada para avaliacao periodica de pacientes
- **Dashboard Administrativo**: Metricas em tempo real e gestao do sistema
- **Seguranca de Nivel Empresarial**: Autenticacao Firebase, CSRF, rate limiting e criptografia

---

## Arquitetura de Alto Nivel

```
                                    +------------------+
                                    |   Firebase Auth  |
                                    +--------+---------+
                                             |
+-------------------+              +---------v---------+              +------------------+
|                   |              |                   |              |                  |
|  Frontend React   +------------->+   FastAPI Backend +------------->+   PostgreSQL     |
|  (Vite + TS)      |   HTTPS      |   (Python 3.13)   |              |   Database       |
|                   |              |                   |              |                  |
+-------------------+              +---------+---------+              +------------------+
                                             |
+-------------------+              +---------v---------+              +------------------+
|                   |              |                   |              |                  |
|  Quiz Interface   +------------->+   Redis Cache     |              |  Evolution API   |
|  (Next.js 14)     |              |   (Sessions/TTL)  |              |  (WhatsApp)      |
|                   |              |                   |              |                  |
+-------------------+              +-------------------+              +------------------+
                                             |
                                    +--------v---------+
                                    |   Celery + Redis |
                                    |   (Background)   |
                                    +------------------+
```

---

## Stack Tecnologica

### Backend (`/backend-hormonia`)

| Tecnologia | Versao | Proposito |
|------------|--------|-----------|
| Python | 3.13+ | Runtime |
| FastAPI | 0.115+ | Framework API |
| SQLAlchemy | 2.0+ | ORM |
| Alembic | 1.14+ | Migrations |
| PostgreSQL | 15+ | Banco de dados |
| Redis | 7+ | Cache e sessoes |
| Celery | 5.4+ | Tarefas em background |
| Firebase Admin | 6.6+ | Autenticacao |
| Google Gemini | - | IA para personalizacao |

### Frontend (`/frontend-hormonia`)

| Tecnologia | Versao | Proposito |
|------------|--------|-----------|
| React | 19.0 | Framework UI |
| TypeScript | 5.0+ | Tipagem estatica |
| Vite | 6.0+ | Build tool |
| TanStack Query | 5.62+ | Data fetching |
| Radix UI | - | Componentes acessiveis |
| Tailwind CSS | 4.0+ | Estilizacao |

### Quiz Interface (`/quiz-mensal-interface`)

| Tecnologia | Versao | Proposito |
|------------|--------|-----------|
| Next.js | 14.2+ | Framework fullstack |
| React | 18 | Framework UI |
| TypeScript | 5.0+ | Tipagem estatica |
| Shadcn/UI | - | Componentes |

---

## Estrutura de Documentacao

| Documento | Descricao |
|-----------|-----------|
| [architecture/](./architecture/) | Arquitetura e padroes do sistema |
| [api/](./api/) | Referencia da API v2 |
| [database/](./database/) | Modelos, migrations e schemas |
| [security/](./security/) | Autenticacao, CSRF, CORS, LGPD |
| [patient/](./patient/) | Flow de pacientes e onboarding |
| [quiz/](./quiz/) | Sistema de quiz mensal |
| [whatsapp/](./whatsapp/) | Integracao Evolution API |
| [ai/](./ai/) | Integracao Google Gemini |
| [errors/](./errors/) | Tratamento de erros e Circuit Breaker |
| [testing/](./testing/) | Testes e qualidade |
| [performance/](./performance/) | Metricas e otimizacao |

---

## Como Executar

### Pre-requisitos

- Node.js 20+
- Python 3.13+
- PostgreSQL 15+
- Redis 7+
- Conta Firebase (projeto configurado)
- Evolution API (opcional, para WhatsApp)

### Backend

```bash
cd backend-hormonia
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend-hormonia
npm install
npm run dev
# Acessar: http://localhost:5173
```

### Quiz Interface

```bash
cd quiz-mensal-interface
npm install
npm run dev
# Acessar: http://localhost:3001
```

---

## Metricas do Projeto

- **77** tabelas PostgreSQL
- **479+** indices de banco de dados
- **37** migrations Alembic
- **60+** endpoints API v2
- **5,423** funcoes de teste
- **3-layer** arquitetura de cache
- **2-5ms** latencia de validacao de sessao

---

## Seguranca

- **Autenticacao**: Firebase Auth com verificacao server-side
- **Sessoes**: Dual-layer (PostgreSQL + Redis) com TTL de 5 dias
- **CSRF**: Double Submit Cookie com HMAC-SHA256
- **Rate Limiting**: Sliding window por IP/usuario
- **Criptografia**: AES-256-GCM para dados sensiveis (LGPD)

---

*Documentacao gerada em 26 de Dezembro de 2025*
