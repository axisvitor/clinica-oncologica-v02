# S01: Stack local rodando

**Goal:** Backend FastAPI + Celery worker + Dragonfly + Postgres todos rodando localmente e se comunicando.
**Demo:** `curl localhost:8000/api/v2/health` retorna status verde, Celery worker aparece nos logs conectado ao broker, Alembic migrations aplicadas no Postgres.

## Must-Haves

- Backend responde em `localhost:8000` com health check verde
- Dragonfly responde ping em `localhost:6379`
- Postgres tem schema atualizado (`alembic upgrade head` roda sem erro)
- Celery worker conecta ao broker Dragonfly e aparece nos logs como ready
- `.env` configurado com DATABASE_URL, REDIS_URL, secrets locais, e AI_GEMINI_API_KEY
- Um usuário admin/médico existe no banco para autenticação no dashboard

## Proof Level

- This slice proves: operational
- Real runtime required: yes
- Human/UAT required: no (health checks automatizáveis)

## Verification

- `curl -s http://localhost:8000/api/v2/health | python3 -m json.tool` retorna JSON com status
- `redis-cli -h localhost -p 6379 ping` retorna PONG
- `cd backend-hormonia && alembic current` mostra head revision
- Celery worker logs mostram `celery@<hostname> ready`
- `curl -s http://localhost:8000/api/v2/auth/login -X POST -H 'Content-Type: application/json' -d '{"email":"...","password":"..."}' | python3 -m json.tool` retorna sessão

## Observability / Diagnostics

- Runtime signals: uvicorn logs, celery worker logs, dragonfly logs
- Inspection surfaces: `GET /api/v2/health`, `redis-cli ping`, `alembic current`
- Failure visibility: stack trace no stdout de cada serviço
- Redaction constraints: senhas e API keys no .env nunca nos logs

## Tasks

- [x] **T01: Dragonfly + Postgres + .env configurados** `est:30m`
  - Why: sem infra base nada mais funciona
  - Files: `backend-hormonia/docker-compose.yml`, `backend-hormonia/.env`
  - Do: subir Dragonfly via docker-compose, configurar .env a partir de .env.example com DATABASE_URL (Postgres local), REDIS_URL (localhost:6379), gerar SECURITY_SECRET_KEY, PHI_ENCRYPTION_KEY, ENCRYPTION_KEY_CURRENT locais, configurar AI_GEMINI_API_KEY (via secure_env_collect). Rodar `alembic upgrade head` para aplicar schema.
  - Verify: `redis-cli ping` retorna PONG, `alembic current` mostra head, psql conecta ao banco
  - Done when: Dragonfly + Postgres acessíveis, schema atualizado, .env funcional

- [x] **T02: Backend + Celery worker rodando** `est:30m`
  - Why: backend é o runtime central; Celery processa tasks async (welcome message, daily flows)
  - Files: `backend-hormonia/app/main.py`, `backend-hormonia/app/celery_app.py`
  - Do: instalar dependências Python (`pip install -r requirements.txt` ou `poetry install`), iniciar backend com `uvicorn app.main:app --port 8000`, iniciar Celery worker com `celery -A app.celery_app worker --loglevel=info`. Corrigir qualquer import error ou config missing.
  - Verify: `curl http://localhost:8000/api/v2/health` retorna JSON, worker logs mostram "ready"
  - Done when: health check verde, worker conectado ao broker

- [ ] **T03: Usuário admin/médico seed e login funcional** `est:20m`
  - Why: S04 precisa de um médico autenticado para criar pacientes; sem seed, nenhum login funciona
  - Files: `backend-hormonia/app/api/v2/routers/auth.py`
  - Do: criar um usuário admin/médico no banco via script ou endpoint, testar login via API, confirmar que sessão é criada no Dragonfly
  - Verify: `POST /api/v2/auth/login` com credenciais do seed retorna sessão com cookie
  - Done when: login funcional, sessão persistida no Dragonfly

## Files Likely Touched

- `backend-hormonia/docker-compose.yml`
- `backend-hormonia/.env`
- `backend-hormonia/app/main.py`
- `backend-hormonia/app/celery_app.py`
- `backend-hormonia/alembic/` (migrations)
