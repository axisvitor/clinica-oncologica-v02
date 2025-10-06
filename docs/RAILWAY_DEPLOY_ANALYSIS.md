# Railway Deployment Configuration Analysis

**Data:** 2025-10-05
**Status:** PROBLEMAS CRÍTICOS IDENTIFICADOS
**Projeto:** Clínica Oncológica Backend (Hormonia)

---

## 📋 Status dos Arquivos de Configuração

### ✅ Arquivos Existentes

| Arquivo | Localização | Status | Observações |
|---------|-------------|--------|-------------|
| `Dockerfile` | `backend-hormonia/` | ✅ COMPLETO | Configurado para Railway com `$PORT` |
| `.env.railway.template` | `backend-hormonia/` | ✅ COMPLETO | Template completo de variáveis |
| `railway-deploy.yml` | `.github/workflows/` | ✅ COMPLETO | CI/CD configurado |
| Health endpoints | `app/api/v1/` | ✅ MÚLTIPLOS | 4 endpoints disponíveis |

### ❌ Arquivos Faltantes (CRÍTICO)

| Arquivo | Localização Esperada | Impacto | Prioridade |
|---------|---------------------|---------|------------|
| `railway.toml` | Raiz do projeto | **CRÍTICO** | **ALTA** |
| `Procfile` | `backend-hormonia/` | Médio | Média |
| `nixpacks.toml` | `backend-hormonia/` | Baixo | Baixa |

---

## 🚨 Problemas Críticos Identificados

### 1. **AUSÊNCIA DE railway.toml**
**Severidade:** CRÍTICA
**Impacto:** Deploy falhará ou será inconsistente

**Problema:**
- O workflow GitHub Actions `.github/workflows/railway-deploy.yml` ESPERA um `railway.toml` na raiz
- Linha 33-39 do workflow valida a existência deste arquivo
- Sem este arquivo, o deploy via `railway up` falhará

**Solução Necessária:**
- Criar `railway.toml` na raiz do projeto com configuração multi-serviço

---

### 2. **Configuração do Health Check**
**Severidade:** ALTA
**Impacto:** Railway pode reiniciar o serviço incorretamente

**Situação Atual:**
- Múltiplos endpoints de health check disponíveis:
  - `/health` - Basic (railway_health.py e health.py)
  - `/health/readiness` - Kubernetes-style
  - `/health/liveness` - Kubernetes-style
  - `/health/startup` - Railway-specific

**Problema:**
- Railway precisa saber QUAL endpoint usar
- Sem `railway.toml`, Railway usa padrões que podem não funcionar

---

### 3. **Variáveis de Ambiente**
**Severidade:** MÉDIA
**Impacto:** Falha na inicialização de serviços

**Variáveis Críticas Obrigatórias:**
```bash
# OBRIGATÓRIAS (app não inicia sem elas)
DATABASE_URL=postgresql+psycopg://...
SECRET_KEY=...
REDIS_URL=rediss://...

# FIREBASE (obrigatório para auth)
FIREBASE_PROJECT_ID=...
FIREBASE_PRIVATE_KEY=...
FIREBASE_CLIENT_EMAIL=...

# SUPABASE (obrigatório para RLS)
SUPABASE_URL=...
SUPABASE_KEY=...
```

**Status:**
- Template existe em `.env.railway.template`
- Workflow NÃO valida se variáveis estão configuradas no Railway
- Potencial falha silenciosa no deploy

---

## 🔍 Análise Detalhada

### Dockerfile (✅ ADEQUADO)

**Pontos Positivos:**
- Usa Python 3.13-slim
- Configurado para usar `$PORT` do Railway (linha 43)
- Health check configurado (linha 39-40)
- Multi-stage build não utilizado (adequado para Railway)
- Usuário não-root (segurança)

**Configuração Atual:**
```dockerfile
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

**Recomendação:** ✅ Manter como está

---

### Health Check Endpoints (✅ BEM ESTRUTURADO)

**Endpoints Disponíveis:**

1. **Railway-Specific (`railway_health.py`):**
   - `/health` - Completo (DB + ServiceProvider + Redis + App)
   - `/health/readiness` - Prontidão (DB + ServiceProvider)
   - `/health/liveness` - Vitalidade (sempre retorna 200)
   - `/health/startup` - Inicialização (env vars)

2. **Standard (`health.py`):**
   - `/health` - Básico
   - `/health/detailed` - Detalhado
   - `/health/metrics` - Métricas (requer auth)

**Recomendação Railway:**
- **Health Check Path:** `/health`
- **Restart Policy Path:** `/health/liveness`
- **Timeout:** 30s (health check leva ~5s normalmente)

---

### GitHub Actions Workflow (⚠️ NECESSITA RAILWAY.TOML)

**Status Atual:**
- ✅ Valida Dockerfiles
- ✅ Roda testes
- ✅ Build de imagens Docker
- ❌ **FALHA:** Espera `railway.toml` na raiz (linha 35)

**Linha Problemática (railway-deploy.yml:35-38):**
```yaml
- name: Validate railway.toml
  run: |
    echo "Validating railway.toml configuration..."
    if [ ! -f railway.toml ]; then
      echo "❌ railway.toml not found"
      exit 1
    fi
```

**Deploy Command (linha 237):**
```yaml
railway up --detach
```

**Comportamento sem railway.toml:**
- ❌ Workflow FALHARÁ na validação
- ❌ Deploy não será executado

---

## 🎯 Railway.toml Recomendado

### Estrutura Multi-Serviço Proposta

```toml
# railway.toml - Multi-service configuration
# Supports: Backend API, Celery Worker, Celery Beat, Frontend

# =============================================================================
# BACKEND API SERVICE
# =============================================================================
[environments.production.backend-api]
build.context = "backend-hormonia"
build.dockerfile = "Dockerfile"

# Runtime Configuration
start_command = "uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4"
restart_policy_type = "on_failure"
restart_policy_max_retries = 3

# Health Check Configuration
health_check.path = "/health"
health_check.interval = 30
health_check.timeout = 10
health_check.failure_threshold = 3

# Resource Allocation
resources.memory = 512
resources.cpu = 1

# Environment Variables (reference Railway secrets)
env.ENVIRONMENT = "production"
env.DEBUG = "false"
env.WORKERS = "4"

# =============================================================================
# CELERY WORKER SERVICE
# =============================================================================
[environments.production.celery-worker]
build.context = "backend-hormonia"
build.dockerfile = "Dockerfile.worker"

start_command = "celery -A app.celery_app worker --loglevel=info --concurrency=4"
restart_policy_type = "always"

resources.memory = 512
resources.cpu = 1

# =============================================================================
# CELERY BEAT SERVICE (Scheduler)
# =============================================================================
[environments.production.celery-beat]
build.context = "backend-hormonia"
build.dockerfile = "Dockerfile.beat"

start_command = "celery -A app.celery_app beat --loglevel=info"
restart_policy_type = "always"

resources.memory = 256
resources.cpu = 0.5

# =============================================================================
# FRONTEND SERVICE
# =============================================================================
[environments.production.frontend]
build.context = "frontend-hormonia"
build.dockerfile = "Dockerfile"

start_command = "nginx -g 'daemon off;'"
restart_policy_type = "on_failure"

health_check.path = "/health"
health_check.interval = 30

resources.memory = 256
resources.cpu = 0.5
```

---

## ⚙️ Configuração de Timeouts Recomendada

### Health Check Timing

| Parâmetro | Valor | Justificativa |
|-----------|-------|---------------|
| `interval` | 30s | Balanço entre detecção rápida e overhead |
| `timeout` | 10s | Health check leva ~5s em média |
| `failure_threshold` | 3 | Permite falhas temporárias (ex: DB lento) |
| `start_period` | 60s | Tempo para inicialização completa |

### Restart Policy

| Serviço | Política | Justificativa |
|---------|----------|---------------|
| Backend API | `on_failure` | Evita restart desnecessário |
| Celery Worker | `always` | Garante processamento contínuo |
| Celery Beat | `always` | Scheduler crítico |
| Frontend | `on_failure` | Nginx raramente falha |

---

## 📊 Comparação: Com e Sem railway.toml

### ❌ SEM railway.toml (Situação Atual)

**Problemas:**
- Railway usa detecção automática (Nixpacks)
- Health check padrão: `GET /` (pode não existir)
- Restart policy: padrão (agressivo demais)
- Recursos: alocação automática (pode ser ineficiente)
- Multi-serviço: requer configuração manual no dashboard

**Riscos:**
- Reinícios desnecessários
- Deploy inconsistente entre ambientes
- Workflow GitHub Actions FALHA

### ✅ COM railway.toml (Recomendado)

**Benefícios:**
- Configuração declarativa versionada
- Health checks customizados
- Restart policies otimizadas
- Recursos alocados eficientemente
- Multi-serviço configurado automaticamente
- Workflow GitHub Actions FUNCIONA

---

## 🛠️ Plano de Ação Recomendado

### Prioridade ALTA (Fazer AGORA)

1. **Criar railway.toml na raiz**
   - Copiar configuração recomendada acima
   - Ajustar recursos conforme plano Railway
   - Commitar no repositório

2. **Validar Variáveis de Ambiente**
   - Criar checklist de variáveis obrigatórias
   - Documentar no Railway dashboard
   - Adicionar validação no workflow

3. **Testar Health Checks**
   - Validar `/health` retorna 200
   - Testar `/health/liveness` não falha
   - Verificar tempos de resposta < 5s

### Prioridade MÉDIA (Fazer em seguida)

4. **Criar Procfile (opcional)**
   ```procfile
   web: uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4
   worker: celery -A app.celery_app worker --loglevel=info
   beat: celery -A app.celery_app beat --loglevel=info
   ```

5. **Documentar Processo de Deploy**
   - Atualizar README com instruções Railway
   - Criar guia de troubleshooting
   - Documentar rollback procedure

6. **Monitoramento Pós-Deploy**
   - Configurar alertas Railway
   - Monitorar logs primeiras 24h
   - Validar performance vs esperado

### Prioridade BAIXA (Otimizações futuras)

7. **Criar nixpacks.toml (se necessário)**
   - Apenas se build automático falhar
   - Documentar dependências do sistema

8. **Otimizar Recursos**
   - Monitorar uso real de CPU/memória
   - Ajustar alocações no railway.toml
   - Implementar auto-scaling se necessário

---

## 📝 Checklist de Deploy Railway

### Antes do Deploy

- [ ] `railway.toml` criado e commitado
- [ ] Todas variáveis de ambiente configuradas no Railway
- [ ] Health checks testados localmente
- [ ] Dockerfile validado (`docker build` sucesso)
- [ ] Workflow GitHub Actions passa sem erros

### Durante o Deploy

- [ ] Workflow executa sem falhas
- [ ] `railway up` completa com sucesso
- [ ] Serviços iniciam sem erros
- [ ] Health checks retornam 200 OK

### Pós-Deploy

- [ ] Backend API acessível
- [ ] Frontend carrega corretamente
- [ ] Database conectada
- [ ] Redis conectado
- [ ] Celery processando tasks
- [ ] Logs sem erros críticos

---

## 🔗 Referências

- [Railway Documentation](https://docs.railway.app/)
- [Railway.toml Reference](https://docs.railway.app/deploy/config-as-code)
- [Railway Health Checks](https://docs.railway.app/deploy/healthchecks)
- [Railway Environment Variables](https://docs.railway.app/develop/variables)

---

## 📞 Próximos Passos

1. **Revisar este relatório** com o time de DevOps
2. **Criar railway.toml** usando template recomendado
3. **Testar deploy** em ambiente staging primeiro
4. **Monitorar** deploy em produção
5. **Iterar** baseado em métricas reais

---

**Última Atualização:** 2025-10-05
**Responsável:** GitHub CI/CD Pipeline Engineer
**Status:** AGUARDANDO CRIAÇÃO DO RAILWAY.TOML
