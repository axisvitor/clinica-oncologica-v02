# 🐳 Relatório de Revisão Docker - Backend Hormonia

**Data:** 2025-10-05
**Revisor:** Backend API Developer Agent
**Escopo:** Todos os arquivos Docker do backend-hormonia

---

## 📋 Sumário Executivo

### Status Geral: ⚠️ **REQUER ATENÇÃO**

**Arquivos Analisados:**
- ✅ `backend-hormonia/Dockerfile` (principal)
- ✅ `backend-hormonia/docker-compose.yml`
- ✅ `backend-hormonia/.dockerignore`
- ✅ `backend-hormonia/railway-debug.dockerfile`

**Problemas Identificados:**
- 🔴 **CRÍTICO:** 2 problemas
- 🟠 **ALTO:** 4 problemas
- 🟡 **MÉDIO:** 6 problemas
- 🔵 **BAIXO:** 3 problemas

---

## 🔴 PROBLEMAS CRÍTICOS

### 1. Healthcheck com Curl sem Instalação Prévia
**Arquivo:** `Dockerfile` (linha 39-40)
**Severidade:** 🔴 CRÍTICO

**Problema:**
```dockerfile
# Healthcheck usa curl mas curl pode não estar disponível após instalação
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1
```

**Impacto:**
- Healthcheck falha silenciosamente após build multi-stage
- Kubernetes/Railway não consegue verificar status da aplicação
- Rollouts podem falhar ou ficar em estado inconsistente

**Solução:**
```dockerfile
# Opção 1: Usar wget (já incluído no python:3.13-slim)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:${PORT:-8000}/health || exit 1

# Opção 2: Usar Python puro (mais confiável)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health').read()" || exit 1
```

---

### 2. Multi-Stage Build Ausente
**Arquivo:** `Dockerfile`
**Severidade:** 🔴 CRÍTICO

**Problema:**
- Imagem final contém build-essential, gcc, g++, curl desnecessários
- Tamanho da imagem ~800MB quando poderia ser ~300MB
- Superfície de ataque aumentada (mais binários = mais vulnerabilidades)

**Solução:**
```dockerfile
# Stage 1: Builder
FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.13-slim

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:${PORT:-8000}/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

**Benefícios:**
- Redução de ~60% no tamanho da imagem
- Menor superfície de ataque
- Builds mais rápidos (cache melhorado)

---

## 🟠 PROBLEMAS ALTOS

### 3. Docker Compose: Senha Redis em Variável Não Segura
**Arquivo:** `docker-compose.yml` (linhas 12, 14, 29-30, 44-45, 61-62)
**Severidade:** 🟠 ALTO

**Problema:**
```yaml
command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD:-redis123}
```

- Senha padrão `redis123` muito fraca
- Exposição via logs do Docker
- Variável não está em arquivo `.env` dedicado

**Solução:**
```yaml
# docker-compose.yml
services:
  redis:
    image: redis:7-alpine
    container_name: hormonia-redis
    volumes:
      - redis_data:/data
      - ./config/redis.conf:/usr/local/etc/redis/redis.conf:ro
    command: redis-server /usr/local/etc/redis/redis.conf
    secrets:
      - redis_password
    healthcheck:
      test: ["CMD", "redis-cli", "-a", "$$(cat /run/secrets/redis_password)", "ping"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - backend

secrets:
  redis_password:
    file: ./secrets/redis_password.txt

networks:
  backend:
    driver: bridge
```

**Criar arquivo:** `config/redis.conf`
```conf
# Redis configuration for Hormonia Backend
bind 0.0.0.0
port 6379
requirepass ${REDIS_PASSWORD}
appendonly yes
appendfilename "appendonly.aof"
dir /data
maxmemory 256mb
maxmemory-policy allkeys-lru
```

---

### 4. Falta de Network Segregation no Docker Compose
**Arquivo:** `docker-compose.yml`
**Severidade:** 🟠 ALTO

**Problema:**
- Todos os serviços no mesmo network padrão
- Redis acessível de qualquer container
- Falta de isolamento entre camadas

**Solução:**
```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    container_name: hormonia-redis
    networks:
      - cache-network
    # ... resto da configuração

  celery-worker:
    build: .
    container_name: hormonia-celery-worker
    networks:
      - cache-network
      - app-network
    # ... resto da configuração

  celery-beat:
    build: .
    container_name: hormonia-celery-beat
    networks:
      - cache-network
      - app-network
    # ... resto da configuração

  celery-flower:
    build: .
    container_name: hormonia-celery-flower
    networks:
      - cache-network
      - monitoring-network
    # ... resto da configuração

networks:
  cache-network:
    driver: bridge
    internal: true  # Redis isolado, sem acesso externo
  app-network:
    driver: bridge
  monitoring-network:
    driver: bridge
```

---

### 5. Railway Debug Dockerfile Usa Python 3.11
**Arquivo:** `railway-debug.dockerfile` (linha 2)
**Severidade:** 🟠 ALTO

**Problema:**
```dockerfile
FROM python:3.11-slim
```

**Impacto:**
- Inconsistência com Dockerfile principal (3.13)
- Dependências podem ter comportamento diferente
- Debugging não reflete ambiente de produção

**Solução:**
```dockerfile
FROM python:3.13-slim

# ... resto igual, mas adicionar verificação de compatibilidade
RUN echo '#!/bin/bash
echo "=== Railway Debug Information (Python 3.13) ==="
python --version
echo "NumPy version (must be 2.x for Python 3.13):"
python -c "import numpy; print(numpy.__version__)"
# ... resto dos checks
' > /app/debug_start.sh
```

---

### 6. Volumes Montados em Modo Desenvolvimento no Compose
**Arquivo:** `docker-compose.yml` (linhas 25, 40, 57)
**Severidade:** 🟠 ALTO

**Problema:**
```yaml
volumes:
  - .:/app  # Monta diretório completo, incluindo arquivos desnecessários
```

**Impacto:**
- `.env`, `.git`, `__pycache__` são montados desnecessariamente
- Performance degradada em Windows/macOS (Docker Desktop)
- Arquivos locais podem sobrescrever arquivos do container

**Solução:**
```yaml
# Opção 1: Apenas para desenvolvimento local
celery-worker:
  build: .
  container_name: hormonia-celery-worker
  volumes:
    - ./app:/app/app:ro  # Apenas código fonte, read-only
  # ... resto

# Opção 2: Sem volumes em produção (usar .env para separar ambientes)
# docker-compose.prod.yml
celery-worker:
  build: .
  container_name: hormonia-celery-worker
  # Sem volumes - código está dentro da imagem
```

---

## 🟡 PROBLEMAS MÉDIOS

### 7. Falta de Labels no Dockerfile
**Arquivo:** `Dockerfile`
**Severidade:** 🟡 MÉDIO

**Problema:**
- Sem metadata de imagem (versão, maintainer, descrição)
- Dificulta rastreabilidade em ambientes multi-tenant

**Solução:**
```dockerfile
FROM python:3.13-slim AS builder

LABEL maintainer="Clínica Oncológica Hormonia <dev@hormonia.clinic>"
LABEL org.opencontainers.image.title="Hormonia Backend API"
LABEL org.opencontainers.image.description="FastAPI backend for oncology clinic management system"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.vendor="Hormonia Clinic"
LABEL org.opencontainers.image.source="https://github.com/hormonia-clinic/backend"
LABEL org.opencontainers.image.licenses="Proprietary"
LABEL python.version="3.13"
LABEL framework="FastAPI"

# ... resto do Dockerfile
```

---

### 8. Celery Flower Expõe Porta Sem Autenticação
**Arquivo:** `docker-compose.yml` (linhas 54-55)
**Severidade:** 🟡 MÉDIO

**Problema:**
```yaml
celery-flower:
  # ...
  command: celery -A app.celery_app flower --port=5555
  ports:
    - "5555:5555"  # Exposto publicamente sem autenticação
```

**Impacto:**
- Métricas de Celery acessíveis por qualquer um
- Possível vazamento de informações sensíveis

**Solução:**
```yaml
celery-flower:
  build: .
  container_name: hormonia-celery-flower
  command: >
    celery -A app.celery_app flower
    --port=5555
    --basic_auth=${FLOWER_USER}:${FLOWER_PASSWORD}
    --url_prefix=flower
  ports:
    - "127.0.0.1:5555:5555"  # Apenas localhost ou via reverse proxy
  environment:
    - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
    - CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@redis:6379/0
    - FLOWER_USER=${FLOWER_USER:-admin}
    - FLOWER_PASSWORD=${FLOWER_PASSWORD}
  env_file:
    - .env
```

**Adicionar ao `.env.example`:**
```bash
FLOWER_USER=admin
FLOWER_PASSWORD=change_this_in_production
```

---

### 9. Falta de Resource Limits no Docker Compose
**Arquivo:** `docker-compose.yml`
**Severidade:** 🟡 MÉDIO

**Problema:**
- Nenhum serviço tem limites de CPU/memória
- Um serviço pode consumir todos os recursos do host

**Solução:**
```yaml
version: '3.8'

services:
  redis:
    image: redis:7-alpine
    # ...
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 512M
        reservations:
          cpus: '0.25'
          memory: 256M

  celery-worker:
    build: .
    # ...
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
      replicas: 2  # Múltiplos workers para alta disponibilidade

  celery-beat:
    build: .
    # ...
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 256M
        reservations:
          cpus: '0.1'
          memory: 128M

  celery-flower:
    build: .
    # ...
    deploy:
      resources:
        limits:
          cpus: '0.25'
          memory: 256M
        reservations:
          cpus: '0.1'
          memory: 128M
```

---

### 10. Falta .dockerignore para railway-debug.dockerfile
**Arquivo:** `.dockerignore`
**Severidade:** 🟡 MÉDIO

**Problema:**
- `.dockerignore` atual exclui `Dockerfile*`, incluindo railway-debug.dockerfile
- Debug script pode não ter acesso a arquivos necessários

**Solução:**
```dockerignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.venv/
env/
ENV/
*.egg-info/
.eggs/
dist/
build/

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.hypothesis/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Environment (keep .env.example)
.env
.env.local
.env.*.local
!.env.example
!.env.railway.template

# Git
.git/
.gitignore
.gitattributes

# Docker (keep railway-debug.dockerfile)
docker-compose*.yml
!railway-debug.dockerfile
.dockerignore

# Documentation (keep critical docs)
docs/
*.md
README*
!README.md
!DEPLOYMENT.md

# Node
node_modules/

# Railway specific
.railway/

# Secrets
secrets/
*.key
*.pem
*.cert
```

---

### 11. CMD Não Usa Exec Form
**Arquivo:** `Dockerfile` (linha 43)
**Severidade:** 🟡 MÉDIO

**Problema:**
```dockerfile
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

**Impacto:**
- Shell wrapping (PID 1 é sh, não uvicorn)
- Sinais (SIGTERM) não são propagados corretamente
- Graceful shutdown não funciona

**Solução:**
```dockerfile
# Opção 1: Exec form com variável de ambiente
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

# Opção 2: Usar ENTRYPOINT com script de inicialização
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app"]
```

**Criar `docker-entrypoint.sh`:**
```bash
#!/bin/bash
set -e

# Use PORT environment variable or default to 8000
export PORT=${PORT:-8000}

# Execute command
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" "$@"
```

---

### 12. Healthcheck Start Period Pode Ser Insuficiente
**Arquivo:** `Dockerfile` (linha 39)
**Severidade:** 🟡 MÉDIO

**Problema:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3
```

**Impacto:**
- 40s pode ser insuficiente para:
  - Importação de todos os módulos Python
  - Conexão com Firebase/Supabase
  - Aquecimento de cache
- Em Railway, isso pode causar restart loops

**Solução:**
```dockerfile
# Aumentar start-period para aplicações complexas
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:${PORT:-8000}/health || exit 1

# Ou adicionar healthcheck progressivo (warm-up)
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:${PORT:-8000}/health || exit 1
```

---

## 🔵 PROBLEMAS BAIXOS

### 13. Falta de BuildKit Features
**Arquivo:** `Dockerfile`
**Severidade:** 🔵 BAIXO

**Problema:**
- Não usa cache mounts para pip
- Builds lentos em CI/CD

**Solução:**
```dockerfile
# syntax=docker/dockerfile:1.4

FROM python:3.13-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Use BuildKit cache mounts for faster builds
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel && \
    pip install --prefix=/install -r requirements.txt

# ... resto do Dockerfile
```

**Benefícios:**
- ~50% mais rápido em rebuilds
- Cache compartilhado entre branches

---

### 14. Dependências do Sistema Não Versionadas
**Arquivo:** `Dockerfile` (linha 8-12)
**Severidade:** 🔵 BAIXO

**Problema:**
```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
```

**Impacto:**
- Versões podem mudar entre builds
- Reprodutibilidade comprometida

**Solução:**
```dockerfile
# Pin versions for reproducibility
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.9 \
    libpq-dev=15.* \
    wget=1.21.* \
    && rm -rf /var/lib/apt/lists/*
```

---

### 15. Falta de .dockerignore Otimizado para Cache
**Arquivo:** `.dockerignore`
**Severidade:** 🔵 BAIXO

**Problema:**
- Ignora `*.md` completamente, mas alguns MD são críticos (CHANGELOG.md, API.md)
- Ignora `docs/` mas pode conter especificações OpenAPI

**Solução:**
```dockerignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
.venv/
env/
ENV/
*.egg-info/
.eggs/
dist/
build/

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.hypothesis/
*.coverage.*

# IDE
.vscode/
.idea/
*.swp
*.swo
*~
.editorconfig

# OS
.DS_Store
Thumbs.db
.directory

# Logs
*.log
logs/
*.log.*

# Environment
.env
.env.local
.env.*.local
!.env.example
!.env.railway.template
!.env.quiz.example

# Git
.git/
.gitignore
.gitattributes
.github/

# Docker
docker-compose*.yml
!railway-debug.dockerfile
.dockerignore

# Documentation (selective)
docs/
*.md
README*
!README.md
!CHANGELOG.md
!docs/openapi.yaml
!docs/api-spec.md

# Node
node_modules/
package-lock.json
yarn.lock

# Railway
.railway/

# Secrets
secrets/
*.key
*.pem
*.cert
credentials/

# Database
*.db
*.sqlite
*.sqlite3
migrations/versions/*.py.bak

# Temporary files
tmp/
temp/
*.tmp
*.bak
*.swp
```

---

## 📊 Análise de Conformidade

### ✅ Configurações Corretas

1. **Porta Dinâmica** - `${PORT:-8000}` configurado corretamente
2. **Usuário Não-Root** - `appuser` criado e usado
3. **Python 3.13** - Versão moderna com melhor performance
4. **Environment Variables** - `PYTHONUNBUFFERED=1` e `PYTHONDONTWRITEBYTECODE=1` configurados
5. **Healthcheck Presente** - Configurado (mas precisa correção de curl)
6. **Redis com Persistência** - `appendonly yes` configurado
7. **Celery Workers** - Separação correta de worker/beat/flower

### ⚠️ Configurações que Precisam de Atenção

1. **Healthcheck** - Usar wget ou Python puro ao invés de curl
2. **Multi-stage Build** - Implementar para reduzir tamanho da imagem
3. **Segredos Redis** - Usar Docker secrets ou HashiCorp Vault
4. **Network Isolation** - Segregar redes por função
5. **Resource Limits** - Adicionar limites de CPU/memória
6. **CMD Format** - Usar exec form ou ENTRYPOINT

---

## 🚀 Plano de Ação Recomendado

### Fase 1: Correções Críticas (Prioridade Máxima)
1. ✅ Implementar multi-stage build no Dockerfile
2. ✅ Corrigir healthcheck (wget ou Python)
3. ✅ Atualizar railway-debug.dockerfile para Python 3.13

### Fase 2: Segurança (Alta Prioridade)
4. ✅ Implementar Docker secrets para Redis
5. ✅ Adicionar autenticação no Flower
6. ✅ Segregar networks no docker-compose.yml

### Fase 3: Otimizações (Média Prioridade)
7. ✅ Adicionar resource limits
8. ✅ Corrigir CMD para exec form
9. ✅ Implementar BuildKit cache mounts
10. ✅ Adicionar labels ao Dockerfile

### Fase 4: Melhorias (Baixa Prioridade)
11. ✅ Versionar dependências do sistema
12. ✅ Otimizar .dockerignore
13. ✅ Aumentar healthcheck start-period

---

## 📝 Próximos Passos

1. **Revisar este documento** com a equipe de DevOps
2. **Priorizar correções** baseado no impacto em produção
3. **Implementar correções** em branch separada (`feat/docker-improvements`)
4. **Testar localmente** com docker-compose
5. **Testar em staging** (Railway/Render)
6. **Validar em produção** com monitoramento
7. **Documentar mudanças** em CHANGELOG.md

---

## 🔗 Referências

- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [FastAPI Docker Deployment](https://fastapi.tiangolo.com/deployment/docker/)
- [Python 3.13 Release Notes](https://docs.python.org/3.13/whatsnew/3.13.html)
- [Railway Docker Deployment](https://docs.railway.app/deploy/dockerfiles)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)

---

**Revisão concluída em:** 2025-10-05
**Próxima revisão recomendada:** Após implementação das correções críticas
