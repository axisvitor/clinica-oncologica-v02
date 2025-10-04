# 🔍 Análise Completa do Erro DNS Railway

## 📋 Status Atual

### ✅ Resolvido
- Permissões do nginx.conf
- Substituição de variáveis com envsubst
- Criação do nginx.conf no container
- Variáveis BACKEND_HOST e BACKEND_PORT sendo processadas

### ❌ Erro Crítico Atual
```bash
nginx: [emerg] host not found in upstream "backend:8000" in /etc/nginx/nginx.conf:98
```

## 🚨 Causa Raiz

### O Problema
O nginx não consegue resolver o hostname "backend:8000" porque:

1. **Railway NÃO usa hostnames simples**
   - Docker Compose usa: `backend`, `redis`, etc.
   - Railway usa: Service Discovery com internal networking

2. **Variável BACKEND_HOST usando default incorreto**
   ```bash
   # docker-entrypoint.sh (linha 15)
   export BACKEND_HOST="${BACKEND_HOST:-backend}"  # ← Default "backend" não existe no Railway
   ```

3. **Railway Private Networking**
   - Railway usa DNS interno: `[service-name].railway.internal`
   - OU variáveis de referência automáticas
   - O hostname "backend" não é resolvível no Railway

## 🏗️ Arquitetura de Networking

### Local (Docker Compose)
```yaml
services:
  frontend:
    ...
  backend:
    ...
  # DNS automático: "backend" resolve para o serviço
```

### Railway (Private Networking)
```
Frontend Service ──→ Private Network ──→ Backend Service
                     (DNS interno)

Hostname: [service-name].railway.internal
OU usar: Variáveis de referência do Railway
```

## 🎯 Soluções Disponíveis

### OPÇÃO 1: Railway Private Networking (RECOMENDADA) ⭐

**Passo 1: Identificar nome do serviço backend**
- No Railway Dashboard, verificar o nome exato do serviço backend
- Exemplo: `backend-hormonia`, `api`, `backend`

**Passo 2: Configurar variável BACKEND_HOST**
```bash
# Railway Dashboard → Frontend Service → Variables
BACKEND_HOST=nome-do-backend.railway.internal
BACKEND_PORT=8000
```

**Passo 3: Ou usar URL completa gerada pelo Railway**
```bash
# Railway gera automaticamente variáveis de referência
# Exemplo: RAILWAY_SERVICE_BACKEND_URL
BACKEND_HOST=$RAILWAY_SERVICE_BACKEND_URL  # Railway substitui automaticamente
```

### OPÇÃO 2: Resolver DNS Dinâmico no Nginx

**Modificar nginx.conf para resolver em tempo de execução:**

```nginx
upstream backend {
    # Usar resolver do Docker/Railway
    resolver 127.0.0.11 valid=10s;

    # Variável dinâmica ao invés de hostname fixo
    set $backend_host "${BACKEND_HOST}";
    set $backend_port "${BACKEND_PORT}";

    server $backend_host:$backend_port;
    keepalive 32;
    keepalive_timeout 60s;
}
```

### OPÇÃO 3: Proxy Direto sem Upstream

**Se backend ainda não está no Railway:**

```nginx
# Comentar bloco upstream
# upstream backend { ... }

# Usar proxy_pass direto
location /api/ {
    # Resolver dinâmico
    resolver 127.0.0.11;
    set $backend "https://seu-backend-externo.com";
    proxy_pass $backend;

    # OU servir apenas frontend estático
    # return 503 "Backend em manutenção";
}
```

### OPÇÃO 4: Usar Service Reference Variables (Railway Automático)

Railway gera automaticamente variáveis quando serviços estão conectados:

```bash
# Formato automático do Railway
RAILWAY_SERVICE_[SERVICE_NAME]_URL=https://service.railway.app

# Exemplo:
# Se backend se chama "backend-hormonia"
RAILWAY_SERVICE_BACKEND_HORMONIA_URL=https://backend-hormonia-production.up.railway.app

# Usar no docker-entrypoint.sh:
export BACKEND_HOST="${RAILWAY_SERVICE_BACKEND_HORMONIA_URL}"
```

## 📊 Checklist de Diagnóstico

### 1. Verificar Status do Backend no Railway
- [ ] Backend está deployado no mesmo projeto Railway?
- [ ] Qual o nome exato do serviço backend? ___________
- [ ] Backend tem URL pública ou apenas private networking?
- [ ] Backend está no status "Active"?

### 2. Verificar Configuração de Networking
- [ ] Frontend e Backend estão no mesmo projeto?
- [ ] Private Networking está habilitado?
- [ ] Verificar variáveis de serviço disponíveis:
  ```bash
  # No frontend service, rodar:
  env | grep RAILWAY
  ```

### 3. Verificar nginx.conf Processado
```bash
# Ver nginx.conf final gerado:
cat /etc/nginx/nginx.conf | grep -A 5 "upstream backend"

# Deve mostrar:
upstream backend {
    server [hostname-correto]:8000;  # ← Verificar se hostname está correto
    ...
}
```

### 4. Testar Resolução DNS Manual
```bash
# Dentro do container frontend:
nslookup backend.railway.internal
# OU
ping backend.railway.internal
# OU
curl http://backend.railway.internal:8000/health
```

## 🛠️ Implementação da Solução

### Solução Imediata: Configurar BACKEND_HOST no Railway

**Passo a Passo:**

1. **Identificar Backend URL/Hostname:**
   ```bash
   # No Railway Dashboard → Backend Service
   # Copiar:
   # - Private Domain: [service].railway.internal
   # - OU Public URL se usar comunicação pública
   ```

2. **Configurar Variável no Frontend:**
   ```bash
   # Railway Dashboard → Frontend Service → Variables → Add Variable

   # OPÇÃO A: Private Networking (interno)
   BACKEND_HOST=backend-hormonia.railway.internal
   BACKEND_PORT=8000

   # OPÇÃO B: Public URL (se necessário)
   BACKEND_HOST=backend-hormonia-production.up.railway.app
   BACKEND_PORT=443  # HTTPS usa porta 443
   ```

3. **Redeploy Frontend:**
   ```bash
   # Railway automaticamente redeploy ao salvar variáveis
   # OU manual trigger deploy
   ```

4. **Verificar Logs:**
   ```bash
   # Railway Dashboard → Frontend Service → Logs
   # Buscar por:
   "Backend configuration (with defaults applied):"
   "BACKEND_HOST=..." # ← Verificar valor correto
   ```

### Solução Alternativa: Modificar nginx.conf para DNS Dinâmico

Se não conseguir descobrir hostname correto, usar resolução dinâmica:

```nginx
# nginx.conf - linha 94-101
# Substituir bloco upstream por:

upstream backend {
    # Resolver dinâmico do Docker/Railway
    resolver 127.0.0.11 valid=10s ipv6=off;

    # IMPORTANTE: Não usar variáveis ${} aqui pois já foram substituídas pelo envsubst
    # O envsubst já processou e substituiu por valores reais
    server ${BACKEND_HOST}:${BACKEND_PORT};

    keepalive 32;
    keepalive_timeout 60s;
}
```

**ATENÇÃO:** O resolver só funciona se o hostname for resolvível via DNS.

## 📚 Referências Railway

### Private Networking
- [Railway Private Networking Docs](https://docs.railway.app/guides/private-networking)
- Service Discovery: `[service-name].railway.internal`
- Automatic Service Variables: `RAILWAY_SERVICE_[NAME]_URL`

### Environment Variables
- [Railway Environment Variables](https://docs.railway.app/guides/variables)
- Service Reference Variables (automáticas entre serviços)
- Custom Variables (configuradas manualmente)

### Networking Best Practices
1. Usar Private Networking quando possível (mais seguro, mais rápido)
2. Usar Service Reference Variables para conectar serviços
3. Evitar hardcoded URLs/hostnames
4. Sempre ter fallback/defaults para desenvolvimento local

## 🔄 Próximos Passos

1. **Identificar configuração correta do backend no Railway**
2. **Configurar BACKEND_HOST com valor correto**
3. **Testar conectividade frontend → backend**
4. **Validar healthcheck do backend**
5. **Configurar CORS se necessário**

## 📝 Notas Importantes

- **Railway NÃO é Docker Compose:** Networking funciona diferente
- **Hostname "backend" NÃO existe no Railway:** Precisa usar internal domain ou public URL
- **Variáveis de ambiente são ESSENCIAIS:** Não confiar em defaults para produção
- **Private Networking é preferido:** Mais rápido e seguro que comunicação pública

---

**Status:** Aguardando informação sobre configuração do backend no Railway
**Próxima Ação:** Configurar BACKEND_HOST com valor correto do Railway
