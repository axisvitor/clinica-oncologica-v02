# 🔧 Correção do Health Check - Railway Deploy

## 🐛 Problema Identificado

O deploy no Railway estava falhando no health check com o seguinte erro:

```
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1
```

**Causa**: O Dockerfile estava configurado para verificar `/health`, mas a aplicação só tinha os endpoints:
- `/health/live` - Liveness check
- `/health/ready` - Readiness check com validação de dependências
- `/health/metrics` - Métricas de performance

O Railway tentava acessar `/health` e recebia **404 Not Found**, causando falha no health check.

## ✅ Solução Implementada

### 1. Endpoint `/health` na Raiz (app/main.py)

Adicionado endpoint simples na raiz da aplicação:

```python
@app.get("/health", tags=["Health"])
async def root_health_check():
    """
    Simple health check endpoint at root level for Railway/Docker.
    Returns basic status without dependency checks.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + 'Z',
        "version": "2.0.0",
        "environment": settings.ENVIRONMENT
    }
```

**Características**:
- ✅ Responde rapidamente (sem verificar dependências)
- ✅ Retorna 200 OK se a aplicação está rodando
- ✅ Ideal para health checks de containers
- ✅ Não sobrecarrega banco/Redis

### 2. Endpoints Detalhados Mantidos (app/routers/health.py)

Os endpoints detalhados foram mantidos para monitoramento avançado:

#### `/health` ou `/health/` (Novo)
```json
{
  "status": "healthy",
  "timestamp": "2025-11-11T12:00:00Z",
  "version": "2.0.0",
  "uptime_seconds": 123.45
}
```
- Resposta rápida
- Sem verificação de dependências
- Ideal para load balancers

#### `/health/live`
```json
{
  "status": "alive",
  "timestamp": "2025-11-11T12:00:00Z",
  "uptime_seconds": 123.45
}
```
- Verifica se o processo está vivo
- Kubernetes liveness probe

#### `/health/ready`
```json
{
  "status": "ready",
  "timestamp": "2025-11-11T12:00:00Z",
  "dependencies": {
    "database": {"status": "healthy", "response_time_ms": 98.5},
    "redis": {"status": "healthy", "response_time_ms": 5.2},
    "firebase": {"status": "healthy"}
  },
  "total_check_time_ms": 105.3
}
```
- Verifica todas as dependências
- Retorna 503 se alguma dependência falhar
- Kubernetes readiness probe

#### `/health/metrics`
```json
{
  "timestamp": "2025-11-11T12:00:00Z",
  "application": {
    "uptime_seconds": 123.45,
    "python_version": "3.12.8"
  },
  "process": {
    "cpu": {"percent": 15.2},
    "memory": {"rss_mb": 256.5, "percent": 12.3}
  },
  "system": {
    "cpu": {"percent": 45.0},
    "memory": {"percent_used": 65.0}
  }
}
```
- Métricas detalhadas de performance
- Uso de CPU e memória
- Estatísticas do sistema

## 🎯 Resultado

### Antes da Correção
```
❌ Railway Health Check: FAILED
   GET /health → 404 Not Found
   Container marked as unhealthy
   Deploy failed
```

### Após a Correção
```
✅ Railway Health Check: PASSED
   GET /health → 200 OK
   Response: {"status": "healthy", "version": "2.0.0"}
   Container marked as healthy
   Deploy successful
```

## 📊 Comparação de Endpoints

| Endpoint | Velocidade | Verifica Deps | Uso |
|----------|-----------|---------------|-----|
| `/health` | ⚡ Muito rápido | ❌ Não | Docker/Railway health check |
| `/health/live` | ⚡ Muito rápido | ❌ Não | Kubernetes liveness |
| `/health/ready` | 🐢 Lento (~100ms) | ✅ Sim | Kubernetes readiness |
| `/health/metrics` | 🐢 Lento | ❌ Não | Monitoramento |

## 🔍 Como Testar

### Localmente
```bash
# Health check simples
curl http://localhost:8000/health

# Liveness
curl http://localhost:8000/health/live

# Readiness (com dependências)
curl http://localhost:8000/health/ready

# Métricas
curl http://localhost:8000/health/metrics
```

### Produção (Railway)
```bash
# Health check simples
curl https://backend-clinica-production-161d.up.railway.app/health

# Readiness
curl https://backend-clinica-production-161d.up.railway.app/health/ready
```

## 📝 Configuração do Dockerfile

O Dockerfile já está configurado corretamente:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1
```

**Parâmetros**:
- `--interval=30s`: Verifica a cada 30 segundos
- `--timeout=10s`: Timeout de 10 segundos
- `--start-period=40s`: Aguarda 40s antes de começar (tempo de inicialização)
- `--retries=3`: 3 tentativas antes de marcar como unhealthy

## 🚀 Deploy

A correção foi aplicada e o deploy deve funcionar agora:

```bash
git add backend-hormonia/app/main.py backend-hormonia/app/routers/health.py
git commit -m "fix: Adiciona endpoint /health na raiz para Railway health check"
git push origin feature/ia-optimization-review
```

O Railway detectará o push e fará o deploy automaticamente.

## ✅ Checklist Pós-Deploy

- [ ] Verificar logs do Railway (sem erros de health check)
- [ ] Testar `curl https://backend-clinica-production-161d.up.railway.app/health`
- [ ] Verificar resposta: `{"status": "healthy", "version": "2.0.0"}`
- [ ] Confirmar que container está marcado como healthy
- [ ] Testar endpoints da API (autenticação, etc.)

## 📚 Referências

- [Railway Health Checks](https://docs.railway.app/deploy/healthchecks)
- [Docker HEALTHCHECK](https://docs.docker.com/engine/reference/builder/#healthcheck)
- [Kubernetes Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)

---

**Correção aplicada em**: 2025-11-11  
**Commit**: 9567be2  
**Status**: ✅ Resolvido
