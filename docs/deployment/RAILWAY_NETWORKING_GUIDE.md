# 🌐 Guia Completo: Railway Networking & Service Discovery

## 📋 Índice
1. [Como Funciona o Networking no Railway](#como-funciona)
2. [Conectar Frontend → Backend](#conectar-servicos)
3. [Configuração de Variáveis de Ambiente](#variaveis)
4. [Troubleshooting DNS](#troubleshooting)
5. [Comparação: Local vs Railway](#comparacao)

---

## 🏗️ Como Funciona o Networking no Railway {#como-funciona}

### Docker Compose (Local)
```yaml
services:
  frontend:
    ...
  backend:
    ...
    # DNS automático: hostname = nome do serviço
    # frontend pode acessar "backend:8000" diretamente
```

### Railway (Cloud)
```
┌─────────────┐         Private Network          ┌─────────────┐
│  Frontend   │ ────────────────────────────────→ │   Backend   │
│  Service    │   [backend].railway.internal     │   Service   │
└─────────────┘                                   └─────────────┘
     ↓                                                   ↓
  Public URL                                        Public URL
  (opcional)                                        (opcional)
```

**Diferenças Chave:**
- Railway NÃO usa hostnames simples como Docker Compose
- Railway usa **Private Networking** com DNS interno
- Formato: `[service-name].railway.internal`
- OU usa **Service Reference Variables** (automáticas)

---

## 🔗 Conectar Frontend → Backend {#conectar-servicos}

### Método 1: Private Networking (RECOMENDADO) ⭐

**Vantagens:**
- ✅ Mais rápido (rede interna)
- ✅ Mais seguro (não expõe na internet)
- ✅ Sem custos de egress
- ✅ Latência menor

**Configuração:**

#### Passo 1: Identificar Nome do Backend Service
```bash
# Railway Dashboard → Backend Service → Settings
# Exemplo: "backend-hormonia"
```

#### Passo 2: Configurar Variáveis no Frontend
```bash
# Railway Dashboard → Frontend Service → Variables

# Formato: [service-name].railway.internal
BACKEND_HOST=backend-hormonia.railway.internal
BACKEND_PORT=8000
```

#### Passo 3: Verificar nginx.conf
```nginx
upstream backend {
    # Após envsubst, deve ficar:
    server backend-hormonia.railway.internal:8000;
    keepalive 32;
}
```

### Método 2: Service Reference Variables (AUTOMÁTICO)

Railway gera automaticamente variáveis quando serviços estão conectados:

```bash
# Formato automático:
RAILWAY_SERVICE_[SERVICE_NAME]_URL

# Exemplo:
RAILWAY_SERVICE_BACKEND_HORMONIA_URL=https://backend.railway.app
```

**Usar no docker-entrypoint.sh:**
```bash
# Modificar linha 15:
export BACKEND_HOST="${RAILWAY_SERVICE_BACKEND_HORMONIA_URL:-backend}"

# OU extrair hostname da URL:
export BACKEND_HOST=$(echo $RAILWAY_SERVICE_BACKEND_HORMONIA_URL | sed 's|https://||')
export BACKEND_PORT="${BACKEND_PORT:-443}"
```

### Método 3: Public URL (NÃO RECOMENDADO)

⚠️ **Usar apenas se Private Networking não funcionar:**

```bash
# Railway Dashboard → Frontend Service → Variables
BACKEND_HOST=backend-hormonia-production.up.railway.app
BACKEND_PORT=443  # HTTPS sempre usa 443
```

**Desvantagens:**
- ❌ Latência maior (sai e volta pela internet)
- ❌ Custos de bandwidth
- ❌ Menos seguro
- ❌ Depende de DNS público

---

## 🔧 Configuração de Variáveis de Ambiente {#variaveis}

### Variáveis Essenciais do Frontend

```bash
# ==========================================
# BACKEND CONNECTION
# ==========================================
# OPÇÃO 1: Private Networking (preferido)
BACKEND_HOST=backend-hormonia.railway.internal
BACKEND_PORT=8000

# OPÇÃO 2: Public URL
# BACKEND_HOST=backend-hormonia-production.up.railway.app
# BACKEND_PORT=443

# ==========================================
# SUPABASE
# ==========================================
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key

# ==========================================
# FIREBASE (Runtime Config)
# ==========================================
# Carregados em runtime via /api/config
# Não são build args
VITE_FIREBASE_API_KEY=your-api-key
VITE_FIREBASE_AUTH_DOMAIN=your-app.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project
VITE_FIREBASE_STORAGE_BUCKET=your-app.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123:web:abc

# ==========================================
# API URLS (Build Time)
# ==========================================
VITE_API_URL=/api  # Proxy via nginx
VITE_API_BASE_URL=/api
VITE_WS_BASE_URL=/ws
```

### Variáveis do Backend (Exemplo)

```bash
# ==========================================
# DATABASE
# ==========================================
DATABASE_URL=postgresql://user:pass@host:5432/db

# ==========================================
# REDIS (Railway Addon)
# ==========================================
REDIS_URL=redis://:password@hostname:6379

# ==========================================
# API CONFIG
# ==========================================
PORT=8000
ENVIRONMENT=production
DEBUG=false

# ==========================================
# CORS (Importante para frontend)
# ==========================================
CORS_ORIGINS=https://your-frontend.railway.app
```

---

## 🔍 Troubleshooting DNS {#troubleshooting}

### Erro: "host not found in upstream"

```bash
nginx: [emerg] host not found in upstream "backend:8000"
```

**Causa:** Hostname não é resolvível no Railway

**Soluções:**

#### 1. Verificar Nome do Serviço Backend
```bash
# Railway Dashboard → Backend Service
# Nome do serviço: ____________ (copiar exato)
```

#### 2. Configurar BACKEND_HOST Correto
```bash
# Formato correto:
BACKEND_HOST=[nome-do-servico].railway.internal

# Exemplo:
BACKEND_HOST=backend-hormonia.railway.internal
```

#### 3. Testar Resolução DNS Manualmente

**Criar shell no container frontend:**
```bash
# Railway Dashboard → Frontend Service → Shell

# Testar DNS:
nslookup backend-hormonia.railway.internal

# Testar conectividade:
curl http://backend-hormonia.railway.internal:8000/health

# Ou instalar ferramentas:
apk add bind-tools curl
dig backend-hormonia.railway.internal
```

#### 4. Verificar Logs do Frontend

```bash
# Railway Dashboard → Frontend Service → Deployments → Logs

# Buscar por:
"Backend configuration (with defaults applied):"
"BACKEND_HOST=..." # ← Verificar valor
"BACKEND_PORT=..." # ← Verificar valor
```

### Erro: "Connection refused"

```bash
curl: (7) Failed to connect to backend port 8000: Connection refused
```

**Causas:**
1. Backend não está rodando
2. Backend não está escutando na porta correta
3. Firewall/Network policy bloqueando

**Soluções:**

```bash
# 1. Verificar status do backend
# Railway Dashboard → Backend Service → Status
# Deve estar "Active" e com checkmark verde

# 2. Verificar porta do backend
# Backend deve ter:
PORT=8000  # Variável de ambiente
# E escutar em: 0.0.0.0:8000 (não 127.0.0.1)

# 3. Verificar healthcheck
# Railway Dashboard → Backend Service → Settings → Healthcheck
# Healthcheck Path: /health
# Deve retornar 200 OK
```

### Erro: "upstream timed out"

```bash
upstream timed out (110: Connection timed out)
```

**Causas:**
1. Backend demora muito para responder
2. Timeout muito curto no nginx
3. Backend travado/lento

**Soluções:**

```nginx
# nginx.conf - Aumentar timeouts
location /api/ {
    proxy_connect_timeout 30s;  # Era 10s
    proxy_send_timeout 120s;     # Era 60s
    proxy_read_timeout 120s;     # Era 60s
}
```

---

## 🔄 Comparação: Local vs Railway {#comparacao}

### Desenvolvimento Local (Docker Compose)

```yaml
# docker-compose.yml
services:
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      - BACKEND_HOST=backend  # ← Hostname simples funciona
      - BACKEND_PORT=8000

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    # DNS automático: "backend" resolve internamente
```

**Como funciona:**
- Docker cria network bridge automática
- Cada serviço tem hostname = nome do serviço
- DNS interno resolve `backend` → IP do container

### Produção Railway

```bash
# Frontend Service → Variables
BACKEND_HOST=backend-hormonia.railway.internal  # ← Hostname completo
BACKEND_PORT=8000

# OU usar Service Reference (automático)
BACKEND_HOST=$RAILWAY_SERVICE_BACKEND_HORMONIA_URL
```

**Como funciona:**
- Railway Private Network usa DNS interno
- Hostname: `[service-name].railway.internal`
- OU Service Reference Variables automáticas
- Não existe hostname simples como Docker Compose

### Tabela Comparativa

| Aspecto | Docker Compose (Local) | Railway (Produção) |
|---------|----------------------|-------------------|
| **Hostname** | `backend` | `backend.railway.internal` |
| **DNS** | Automático | Private Networking |
| **Porta** | Qualquer | Deve expor corretamente |
| **Network** | Bridge automática | Private Network gerenciada |
| **Variáveis** | Arquivo .env | Railway Dashboard |
| **Configuração** | docker-compose.yml | railway.json + Variables |

---

## 📚 Recursos Adicionais

### Documentação Railway
- [Private Networking](https://docs.railway.app/guides/private-networking)
- [Environment Variables](https://docs.railway.app/guides/variables)
- [Service Networking](https://docs.railway.app/reference/networking)

### Troubleshooting Tools

```bash
# Dentro do container (Railway Shell):

# DNS lookup
nslookup [hostname]
dig [hostname]

# Conectividade
curl http://[hostname]:[port]/health
wget -O- http://[hostname]:[port]/health

# Network info
netstat -tuln  # Portas listening
ss -tuln       # Alternativa moderna

# Processos
ps aux | grep nginx
ps aux | grep node
```

### Boas Práticas

1. **Sempre usar Private Networking quando possível**
   - Mais rápido, seguro, econômico

2. **Configurar variáveis de ambiente corretamente**
   - Não confiar em defaults para produção

3. **Validar healthcheck do backend**
   - Deve responder 200 OK em `/health`

4. **Usar Service Reference Variables**
   - Evita hardcoded URLs/hostnames

5. **Logs são seus amigos**
   - Sempre verificar logs de deploy e runtime

6. **Testar localmente primeiro**
   - Docker Compose deve funcionar antes de Railway

---

## 🚀 Checklist de Deploy

- [ ] Backend deployado e ativo no Railway
- [ ] Backend tem healthcheck configurado (`/health`)
- [ ] Frontend tem variável `BACKEND_HOST` configurada
- [ ] Frontend tem variável `BACKEND_PORT` configurada
- [ ] Variáveis usando hostname correto (`.railway.internal`)
- [ ] nginx.conf processando variáveis corretamente
- [ ] Logs do frontend mostram valores corretos
- [ ] Teste manual de DNS/conectividade (via Shell)
- [ ] CORS configurado no backend (se necessário)
- [ ] Healthcheck do frontend funcionando

---

**Última atualização:** 2025-10-04
**Versão:** 1.0
