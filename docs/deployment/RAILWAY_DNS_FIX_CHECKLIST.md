# ✅ Checklist: Corrigir Erro DNS Railway

## 🎯 Objetivo
Resolver erro: `nginx: [emerg] host not found in upstream "backend:8000"`

---

## 📋 Checklist de Diagnóstico

### Fase 1: Verificar Backend

- [ ] **1.1 Backend está deployado no Railway?**
  - [ ] Acessar Railway Dashboard
  - [ ] Verificar lista de serviços
  - [ ] Backend está presente? Sim / Não

- [ ] **1.2 Backend está ativo?**
  - [ ] Status: Active (✓) / Inactive (✗)
  - [ ] Deployment atual: Success / Failed
  - [ ] Logs mostram aplicação rodando?

- [ ] **1.3 Qual é o nome EXATO do serviço backend?**
  - [ ] Nome: ________________________
  - [ ] (Copiar exatamente como aparece no Railway)

- [ ] **1.4 Backend tem healthcheck funcionando?**
  - [ ] Healthcheck configurado em Settings?
  - [ ] Path: `/health` ou outro? ____________
  - [ ] Responde 200 OK?

### Fase 2: Verificar Networking

- [ ] **2.1 Frontend e Backend estão no mesmo projeto Railway?**
  - [ ] Sim / Não
  - [ ] Se não, podem se comunicar?

- [ ] **2.2 Private Networking está habilitado?**
  - [ ] Railway Dashboard → Settings → Private Networking
  - [ ] Status: Enabled / Disabled

- [ ] **2.3 Verificar variáveis de serviço disponíveis**
  ```bash
  # Railway Dashboard → Frontend Service → Shell
  env | grep RAILWAY
  ```
  - [ ] Copiar output: ________________________

### Fase 3: Verificar Configuração Frontend

- [ ] **3.1 Variável BACKEND_HOST está configurada?**
  - [ ] Railway Dashboard → Frontend → Variables
  - [ ] BACKEND_HOST existe? Sim / Não
  - [ ] Valor atual: ________________________

- [ ] **3.2 Variável BACKEND_PORT está configurada?**
  - [ ] BACKEND_PORT existe? Sim / Não
  - [ ] Valor atual: ________________________

- [ ] **3.3 Verificar logs do frontend**
  ```bash
  # Railway Dashboard → Frontend → Deployments → Logs
  # Buscar por:
  "Backend configuration (with defaults applied):"
  ```
  - [ ] BACKEND_HOST mostrado: ________________________
  - [ ] BACKEND_PORT mostrado: ________________________

### Fase 4: Testar Conectividade

- [ ] **4.1 Testar resolução DNS**
  ```bash
  # Railway Dashboard → Frontend Service → Shell
  nslookup [backend-name].railway.internal
  ```
  - [ ] DNS resolve? Sim / Não
  - [ ] IP retornado: ________________________

- [ ] **4.2 Testar conectividade HTTP**
  ```bash
  curl http://[backend-name].railway.internal:8000/health
  ```
  - [ ] Conecta? Sim / Não
  - [ ] Resposta: ________________________

---

## 🔧 Soluções por Cenário

### Cenário A: Backend NÃO deployado no Railway

**Situação:**
- Backend ainda não foi deployado
- Apenas frontend está no Railway

**Solução:**
```bash
# OPÇÃO 1: Deploy do backend
cd backend-hormonia
railway login
railway link  # Linkar ao projeto correto
railway up    # Deploy

# OPÇÃO 2: Desabilitar proxy backend temporariamente
# Modificar nginx.conf para não usar upstream backend
```

**Ações:**
- [ ] Decidir: Deploy backend OU desabilitar proxy?
- [ ] Se deploy: Seguir [RAILWAY_DEPLOYMENT_GUIDE.md]
- [ ] Se desabilitar: Seguir Cenário D

### Cenário B: Backend deployado, variáveis INCORRETAS

**Situação:**
- Backend está ativo
- BACKEND_HOST usando default "backend"
- DNS não resolve "backend"

**Solução:**
```bash
# Railway Dashboard → Frontend Service → Variables → New Variable

# IMPORTANTE: Usar nome EXATO do serviço backend
# Formato: [nome-do-servico].railway.internal

# Exemplo 1: Se backend se chama "backend-hormonia"
BACKEND_HOST=backend-hormonia.railway.internal
BACKEND_PORT=8000

# Exemplo 2: Se backend se chama "api"
BACKEND_HOST=api.railway.internal
BACKEND_PORT=8000
```

**Ações:**
- [ ] Identificar nome exato: ________________________
- [ ] Adicionar variável BACKEND_HOST
- [ ] Adicionar variável BACKEND_PORT
- [ ] Salvar (Railway redeploy automático)
- [ ] Aguardar redeploy completar
- [ ] Verificar logs novamente

### Cenário C: Backend em URL Externa/Pública

**Situação:**
- Backend não está no Railway
- Backend em outro servidor/cloud
- Comunicação via internet pública

**Solução:**
```bash
# Railway Dashboard → Frontend Service → Variables

# URL completa do backend externo
BACKEND_HOST=api.seudominio.com
BACKEND_PORT=443  # HTTPS usa 443

# OU IP direto
BACKEND_HOST=203.0.113.45
BACKEND_PORT=8000
```

**Ações:**
- [ ] Confirmar URL/IP do backend: ________________________
- [ ] Confirmar porta: ________________________
- [ ] Configurar variáveis
- [ ] **IMPORTANTE:** Configurar CORS no backend:
  ```python
  # Backend deve permitir origem do frontend Railway
  CORS_ORIGINS=https://frontend-hormonia-production.up.railway.app
  ```

### Cenário D: Backend NÃO disponível - Servir apenas Frontend

**Situação:**
- Backend não disponível temporariamente
- Quer servir apenas frontend estático
- Desabilitar proxy /api/

**Solução - Opção 1: Modificar nginx.conf**

Criar novo arquivo temporário:

```nginx
# frontend-hormonia/nginx.conf.no-backend

# ... (copiar tudo do nginx.conf original) ...

# COMENTAR/REMOVER bloco upstream:
# upstream backend {
#     server ${BACKEND_HOST}:${BACKEND_PORT};
#     keepalive 32;
# }

# MODIFICAR location /api/:
location /api/ {
    # Retornar erro 503 temporário
    return 503 '{"error": "Backend em manutenção"}';
    add_header Content-Type application/json;
}

# MODIFICAR location /ws:
location /ws {
    # Desabilitar WebSocket
    return 503 '{"error": "WebSocket indisponível"}';
    add_header Content-Type application/json;
}
```

**Ações:**
- [ ] Criar nginx.conf.no-backend
- [ ] Renomear Dockerfile:
  ```dockerfile
  # Linha 71: Usar nova configuração
  COPY nginx.conf.no-backend /etc/nginx/nginx.conf.template
  ```
- [ ] Redeploy frontend
- [ ] Verificar /health retorna 200 OK
- [ ] Frontend estático funciona (sem API)

**Solução - Opção 2: Usar Resolver Dinâmico com Fallback**

```nginx
# nginx.conf - Modificar location /api/
location /api/ {
    # Tentar resolver backend
    resolver 127.0.0.11 valid=5s;
    set $backend_up 0;

    # Se backend não resolve, retornar erro
    if ($backend_up = 0) {
        return 503 '{"error": "Backend indisponível"}';
    }

    proxy_pass http://backend;
    # ... resto da config ...
}
```

---

## 🚀 Solução Rápida (TL;DR)

### Se backend ESTÁ no Railway:

```bash
# 1. Descobrir nome do backend
# Railway Dashboard → Backend Service → (copiar nome)

# 2. Configurar variável no frontend
# Railway Dashboard → Frontend Service → Variables → New Variable
BACKEND_HOST=[nome-do-backend].railway.internal
BACKEND_PORT=8000

# 3. Salvar e aguardar redeploy automático

# 4. Verificar logs
# Railway Dashboard → Frontend → Deployments → Logs
# Buscar: "BACKEND_HOST=[nome-do-backend].railway.internal"
```

### Se backend NÃO está no Railway:

**Opção A: Deploy do backend**
```bash
cd backend-hormonia
railway login
railway link
railway up
# Depois seguir passos acima
```

**Opção B: Usar backend externo**
```bash
# Railway Dashboard → Frontend Service → Variables
BACKEND_HOST=sua-api-externa.com
BACKEND_PORT=443
```

**Opção C: Desabilitar backend temporariamente**
```bash
# Modificar nginx.conf para não usar upstream
# Ver Cenário D acima
```

---

## 🧪 Testes de Validação

Após aplicar solução, validar:

### 1. Nginx Inicia Sem Erros
```bash
# Logs do frontend NÃO devem ter:
# ❌ "host not found in upstream"

# Logs devem mostrar:
# ✅ "nginx.conf created successfully"
# ✅ "Backend configuration (with defaults applied):"
# ✅ "BACKEND_HOST=[valor-correto]"
```

### 2. Healthcheck Passa
```bash
# Railway Dashboard → Frontend → Status
# ✅ Checkmark verde
# ✅ Healthcheck: Passing
```

### 3. Frontend Carrega
```bash
# Abrir URL pública do frontend
# ✅ HTML carrega
# ✅ Assets carregam (JS, CSS)
# ✅ Sem erros 502/503
```

### 4. API Proxy Funciona (se backend disponível)
```bash
# No browser, testar:
curl https://frontend-url.railway.app/api/health

# ✅ Deve retornar resposta do backend
# ❌ Se retornar 502/503, backend não está acessível
```

### 5. WebSocket Funciona (se backend disponível)
```bash
# No browser console:
const ws = new WebSocket('wss://frontend-url.railway.app/ws');
ws.onopen = () => console.log('✅ WebSocket conectado');
ws.onerror = (e) => console.log('❌ WebSocket erro:', e);
```

---

## 📊 Status Final

### Problema Original
- [x] Erro: `nginx: [emerg] host not found in upstream "backend:8000"`

### Causa Identificada
- [ ] Backend não deployado
- [ ] Variável BACKEND_HOST incorreta
- [ ] DNS não resolve hostname
- [ ] Outro: ________________________

### Solução Aplicada
- [ ] Cenário A: Deploy backend
- [ ] Cenário B: Corrigir variáveis
- [ ] Cenário C: Backend externo
- [ ] Cenário D: Desabilitar backend
- [ ] Outro: ________________________

### Resultado
- [ ] ✅ Frontend deployado com sucesso
- [ ] ✅ Nginx iniciando sem erros
- [ ] ✅ Healthcheck passando
- [ ] ✅ Frontend carregando
- [ ] ✅ API proxy funcionando (se aplicável)
- [ ] ✅ WebSocket funcionando (se aplicável)

---

## 📝 Notas Adicionais

**Documentação relacionada:**
- [RAILWAY_DNS_ERROR_ANALYSIS.md](./RAILWAY_DNS_ERROR_ANALYSIS.md) - Análise técnica completa
- [RAILWAY_NETWORKING_GUIDE.md](./RAILWAY_NETWORKING_GUIDE.md) - Guia de networking
- [RAILWAY_DEPLOYMENT_GUIDE.md](./RAILWAY_DEPLOYMENT_GUIDE.md) - Deploy completo

**Próximos passos (após resolver DNS):**
1. Configurar CORS no backend
2. Validar autenticação/autorização
3. Configurar rate limiting
4. Monitorar logs e métricas
5. Setup de alertas

---

**Data:** 2025-10-04
**Status:** Aguardando informações do backend Railway
