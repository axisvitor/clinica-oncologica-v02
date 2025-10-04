# 🚀 Fix Rápido: Erro DNS Railway

## ⚡ Problema
```
nginx: [emerg] host not found in upstream "backend:8000" in /etc/nginx/nginx.conf:98
```

---

## 🎯 Soluções Rápidas (escolha uma)

### Solução 1: Backend ESTÁ no Railway ⭐ (MAIS COMUM)

```bash
# 1. Descobrir nome do backend
# Railway Dashboard → Seu Projeto → Services
# Exemplo: "backend-hormonia"

# 2. Configurar variável
# Railway Dashboard → Frontend Service → Variables → New Variable
BACKEND_HOST=backend-hormonia.railway.internal
BACKEND_PORT=8000

# 3. Salvar (Railway redeploy automático)
# ✅ PRONTO!
```

**Como descobrir o nome do backend:**
1. Abra Railway Dashboard
2. Veja lista de Services no projeto
3. Copie o nome EXATO do backend
4. Adicione `.railway.internal` no final

**Exemplo:**
- Service name: `backend-hormonia` → Use: `backend-hormonia.railway.internal`
- Service name: `api` → Use: `api.railway.internal`
- Service name: `server` → Use: `server.railway.internal`

---

### Solução 2: Backend em URL Externa

```bash
# Railway Dashboard → Frontend Service → Variables

# URL completa do backend
BACKEND_HOST=api.seusite.com
BACKEND_PORT=443  # Usar 443 para HTTPS
```

**IMPORTANTE:** Configure CORS no backend:
```python
# Backend deve permitir origem do Railway
CORS_ORIGINS=https://seu-frontend.railway.app
```

---

### Solução 3: Desabilitar Backend Temporariamente

**Usar nginx.conf.fallback (sem backend):**

```bash
# 1. Modificar Dockerfile
# Linha 71, substituir:
COPY nginx.conf.fallback /etc/nginx/nginx.conf.template

# 2. Commit e push
git add frontend-hormonia/Dockerfile
git commit -m "fix: usar nginx.conf.fallback sem backend"
git push

# 3. Railway redeploy automático
```

**O que isso faz:**
- ✅ Frontend funciona normalmente
- ✅ Assets servidos (HTML, CSS, JS)
- ✅ Healthcheck passa
- ❌ `/api/*` retorna 503 (Backend unavailable)
- ❌ WebSocket desabilitado

---

## 🔍 Diagnóstico Rápido

### Verificar se backend está no Railway

```bash
# Railway CLI
railway status

# Ou Railway Dashboard:
# → Projeto → Services → Verificar se backend está listado
```

### Testar DNS manualmente

```bash
# Railway Dashboard → Frontend Service → Shell

# Instalar ferramentas
apk add bind-tools curl

# Testar DNS
nslookup backend-hormonia.railway.internal

# Testar conexão
curl http://backend-hormonia.railway.internal:8000/health
```

### Ver logs do erro

```bash
# Railway Dashboard → Frontend Service → Deployments → Logs

# Buscar por:
"host not found in upstream"
"Backend configuration (with defaults applied):"
```

---

## 📋 Checklist 3 Minutos

1. **[ ] Backend está no Railway?**
   - SIM → Usar Solução 1
   - NÃO → Usar Solução 2 ou 3

2. **[ ] Descobrir nome do backend**
   - Railway Dashboard → Services → (copiar nome)

3. **[ ] Configurar variável**
   ```
   BACKEND_HOST=[nome].railway.internal
   BACKEND_PORT=8000
   ```

4. **[ ] Salvar e aguardar**
   - Railway redeploy automático (~1-2 min)

5. **[ ] Verificar logs**
   - Buscar: "BACKEND_HOST=[nome].railway.internal" ✅
   - NÃO deve ter: "host not found" ❌

6. **[ ] Testar frontend**
   - Abrir URL pública
   - Frontend deve carregar ✅

---

## 🆘 Troubleshooting

### Erro persiste após configurar variável

**Verificar:**
```bash
# 1. Variável foi salva corretamente?
# Railway Dashboard → Frontend → Variables → Verificar valor

# 2. Redeploy foi triggado?
# Railway Dashboard → Frontend → Deployments → Ver último deploy

# 3. Logs mostram novo valor?
# Railway Dashboard → Frontend → Logs → Buscar "BACKEND_HOST="
```

**Forçar redeploy:**
```bash
# Railway Dashboard → Frontend Service → Settings
# → Triggers → Manual Deploy → Deploy
```

### DNS ainda não resolve

**Possíveis causas:**
1. Nome do serviço está errado
   - Verificar nome EXATO no Railway
   - Case-sensitive: `Backend` ≠ `backend`

2. Private Networking desabilitado
   - Railway Dashboard → Settings → Private Networking → Enable

3. Serviços em projetos diferentes
   - Frontend e Backend devem estar no MESMO projeto

### Backend não responde

**Verificar backend:**
```bash
# 1. Backend está Active?
# Railway Dashboard → Backend → Status (deve estar verde ✅)

# 2. Logs do backend
# Railway Dashboard → Backend → Logs
# Buscar por erros

# 3. Healthcheck do backend
# Railway Dashboard → Backend → Settings → Healthcheck
# Path: /health (deve existir)
```

---

## 📚 Documentação Completa

Após resolver o erro imediato, consulte:

- **[RAILWAY_DNS_ERROR_ANALYSIS.md](./RAILWAY_DNS_ERROR_ANALYSIS.md)**
  - Análise técnica detalhada do problema

- **[RAILWAY_NETWORKING_GUIDE.md](./RAILWAY_NETWORKING_GUIDE.md)**
  - Guia completo de networking Railway

- **[RAILWAY_DNS_FIX_CHECKLIST.md](./RAILWAY_DNS_FIX_CHECKLIST.md)**
  - Checklist passo a passo completo

---

## 💡 Dicas

1. **Sempre use `.railway.internal` para comunicação interna**
   - Mais rápido, seguro e econômico

2. **Configure variáveis ANTES do deploy**
   - Evita loops de redeploy

3. **Teste localmente primeiro**
   - Docker Compose deve funcionar antes de Railway

4. **Use Railway CLI para debug**
   ```bash
   railway login
   railway status
   railway logs
   ```

5. **Monitore logs durante deploy**
   - Ajuda a identificar problemas rapidamente

---

**Tempo estimado de fix:** 3-5 minutos
**Dificuldade:** ⭐ Fácil

**Última atualização:** 2025-10-04
