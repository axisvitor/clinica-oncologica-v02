# Frontend Docker Configuration Review Report

**Data:** 2025-10-05
**Projeto:** Clínica Oncológica V02
**Componente:** Frontend Hormonia (React + Vite + Nginx)

---

## 📋 Executive Summary

A configuração Docker do frontend possui **múltiplos arquivos conflitantes** e **configurações duplicadas** que podem causar problemas em produção. Foram identificados **9 problemas críticos** e **12 oportunidades de otimização**.

### Status Geral
- ✅ Multi-stage build implementado
- ✅ Build do Vite configurado
- ✅ Variáveis de ambiente declaradas
- ⚠️ **Configuração duplicada e conflitante**
- ⚠️ **Nginx com múltiplos arquivos sem hierarquia clara**
- ⚠️ **Proxy reverso incompleto**

---

## 🔍 Arquivos Revisados

### 1. `Dockerfile` ✅ Parcialmente Correto
**Localização:** `frontend-hormonia/Dockerfile`

**Pontos Positivos:**
- ✅ Multi-stage build (builder + nginx)
- ✅ Todas as variáveis VITE_ declaradas como ARG
- ✅ ARGs convertidos em ENVs para build
- ✅ Healthcheck configurado
- ✅ Build script correto: `npm run build:runtime`

**Problemas Críticos:**

#### ❌ P1: Porta exposta com variável não resolvida
```dockerfile
# LINHA 69 - PROBLEMA
EXPOSE $PORT
```
**Impacto:** `$PORT` não está definido no build. Docker não consegue expor porta.

**Correção:**
```dockerfile
# Definir PORT padrão
ENV PORT=3000
EXPOSE ${PORT}
```

#### ❌ P2: Nginx config não copiada
```dockerfile
# FALTANDO: Copiar nginx.conf principal
COPY nginx.conf /etc/nginx/nginx.conf.template
```
**Impacto:** Entrypoint espera `/etc/nginx/nginx.conf.template` mas arquivo não é copiado.

#### ❌ P3: Entrypoint não configurado
```dockerfile
# FALTANDO: Definir entrypoint antes do CMD
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]
```
**Impacto:** `docker-entrypoint.sh` não é executado, configuração runtime não funciona.

#### ⚠️ P4: Healthcheck usa variável não definida
```dockerfile
# LINHA 72 - PROBLEMA
HEALTHCHECK CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1
```
**Correção:**
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:${PORT:-3000}/ || exit 1
```

---

### 2. `nginx.conf` ⚠️ Configuração Completa mas Não Utilizada
**Localização:** `frontend-hormonia/nginx.conf`

**Pontos Positivos:**
- ✅ Configuração completa (worker_processes, events, http, server)
- ✅ Proxy para backend com upstream keepalive
- ✅ WebSocket configurado em `/ws`
- ✅ Compressão gzip otimizada
- ✅ Cache de proxy configurado
- ✅ Headers de segurança
- ✅ Usa variáveis ${BACKEND_HOST}, ${BACKEND_PORT}, ${PORT}

**Problemas:**

#### ❌ P5: Arquivo não copiado no Dockerfile
Este arquivo **NÃO está sendo utilizado** porque o Dockerfile não o copia.

**Correção no Dockerfile:**
```dockerfile
# Stage de produção
FROM nginx:alpine

# Copiar build
COPY --from=builder /app/dist /usr/share/nginx/html

# Copiar configuração PRINCIPAL do nginx
COPY nginx.conf /etc/nginx/nginx.conf.template

# Copiar entrypoint para processar variáveis
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENV PORT=3000
EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:${PORT}/ || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
```

#### ⚠️ P6: Configuração de runtime config incompleta
```nginx
# LINHAS 154-168 - Endpoints /api/config e /api/config.js
location = /api/config {
    try_files /api/config =404;
}
```
**Problema:** Estes endpoints são gerados pelo `docker-entrypoint.sh` em `/usr/share/nginx/html/api/config`, mas a configuração Nginx não especifica isso claramente.

**Melhoria:**
```nginx
location = /api/config {
    access_log off;
    default_type application/json;
    add_header Cache-Control "no-store, no-cache, must-revalidate" always;
    add_header Pragma "no-cache" always;
    root /usr/share/nginx/html;
    try_files /api/config =404;
}
```

---

### 3. `nginx.server.conf` ❌ Configuração Simplificada e Incompleta
**Localização:** `frontend-hormonia/nginx.server.conf`

**Análise:**
Este arquivo é uma **versão simplificada** sem proxy para backend.

**Problemas:**

#### ❌ P7: Sem proxy para /api/ e /ws
```nginx
# FALTANDO COMPLETAMENTE
location /api/ {
    proxy_pass http://backend;
    # ... headers e configurações
}

location /ws {
    proxy_pass http://backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```
**Impacto:** Frontend não consegue se comunicar com backend via proxy.

#### ❌ P8: Não define upstream backend
```nginx
# FALTANDO
upstream backend {
    server ${BACKEND_HOST}:${BACKEND_PORT};
    keepalive 32;
}
```

#### ⚠️ P9: Está sendo copiado no Dockerfile
```dockerfile
# LINHA 66 do Dockerfile
COPY nginx.server.conf /etc/nginx/templates/default.conf.template
```
**Problema:** Docker está usando o arquivo **ERRADO** (simplificado sem proxy).

**Decisão Necessária:**
- **Opção 1:** Deletar `nginx.server.conf` e usar `nginx.conf` completo
- **Opção 2:** Atualizar `nginx.server.conf` com proxy completo

---

### 4. `docker-entrypoint.sh` ✅ Bem Configurado
**Localização:** `frontend-hormonia/docker-entrypoint.sh`

**Pontos Positivos:**
- ✅ Define defaults: `BACKEND_HOST`, `BACKEND_PORT`, `PORT`
- ✅ Gera arquivos de configuração runtime em `/usr/share/nginx/html/api/`
- ✅ Processa `nginx.conf.template` com `envsubst`
- ✅ Logs de debug detalhados

**Problemas:**

#### ⚠️ P10: Não está configurado no Dockerfile
```dockerfile
# FALTANDO no Dockerfile
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
ENTRYPOINT ["/docker-entrypoint.sh"]
```

#### ⚠️ P11: Backend host padrão incorreto
```bash
# LINHA 16 - PODE SER MELHORADO
export BACKEND_HOST="${BACKEND_HOST:-clinica-oncologica-v02.railway.internal}"
```
**Sugestão:** Para deploy genérico Docker:
```bash
export BACKEND_HOST="${BACKEND_HOST:-backend}"
export BACKEND_PORT="${BACKEND_PORT:-8000}"
```

---

### 5. `vite.config.ts` ✅ Bem Configurado
**Pontos Positivos:**
- ✅ Plugin de runtime config injection
- ✅ Code splitting otimizado
- ✅ Tree shaking configurado
- ✅ Build production minificado

---

### 6. `scripts/post-build-config.js` ✅ Correto
**Pontos Positivos:**
- ✅ Cria `/dist/api/config` e `/dist/api/config.js`
- ✅ Injeta script no index.html
- ✅ Fallback para defaults

---

## 🚨 Problemas Resumidos

### Críticos (Impedem Funcionamento)
1. ❌ **P1:** Porta `$PORT` não definida no Dockerfile
2. ❌ **P2:** `nginx.conf` não copiado no Dockerfile
3. ❌ **P3:** Entrypoint não configurado no Dockerfile
4. ❌ **P5:** Arquivo `nginx.conf` (completo) não utilizado
5. ❌ **P7:** `nginx.server.conf` sem proxy para backend
6. ❌ **P8:** Upstream backend não definido
7. ❌ **P10:** Entrypoint não configurado no Dockerfile

### Médios (Afetam Performance/Segurança)
8. ⚠️ **P4:** Healthcheck sem variável PORT
9. ⚠️ **P6:** Runtime config nginx não especifica root
10. ⚠️ **P9:** Usando arquivo nginx errado
11. ⚠️ **P11:** Backend host específico do Railway

### Baixos (Otimizações)
12. Falta CSP (Content Security Policy)
13. Rate limiting não configurado
14. Logs podem ser melhorados

---

## ✅ Configurações Corrigidas

### Dockerfile Completo Corrigido

```dockerfile
# Frontend Dockerfile - React/Vite com build otimizado
FROM node:20-slim AS builder

# Definir diretório de trabalho
WORKDIR /app

# Copiar arquivos de dependências
COPY package*.json ./

# Instalar dependências
RUN npm ci --prefer-offline --no-audit

# Copiar código fonte
COPY . .

# Declarar ARGs para variáveis de ambiente
# API Configuration
ARG VITE_API_BASE_URL
ARG VITE_API_URL
ARG VITE_WS_URL

# Firebase Configuration
ARG VITE_FIREBASE_API_KEY
ARG VITE_FIREBASE_AUTH_DOMAIN
ARG VITE_FIREBASE_PROJECT_ID
ARG VITE_FIREBASE_STORAGE_BUCKET
ARG VITE_FIREBASE_MESSAGING_SENDER_ID
ARG VITE_FIREBASE_APP_ID
ARG VITE_FIREBASE_MEASUREMENT_ID

# Feature Flags
ARG VITE_ENABLE_ANALYTICS
ARG VITE_ENABLE_SENTRY
ARG VITE_DEV_MODE

# Converter ARGs em ENVs para o build do Vite
# API Configuration
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL

# Firebase Configuration
ENV VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY
ENV VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN
ENV VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID
ENV VITE_FIREBASE_STORAGE_BUCKET=$VITE_FIREBASE_STORAGE_BUCKET
ENV VITE_FIREBASE_MESSAGING_SENDER_ID=$VITE_FIREBASE_MESSAGING_SENDER_ID
ENV VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID
ENV VITE_FIREBASE_MEASUREMENT_ID=$VITE_FIREBASE_MEASUREMENT_ID

# Feature Flags
ENV VITE_ENABLE_ANALYTICS=$VITE_ENABLE_ANALYTICS
ENV VITE_ENABLE_SENTRY=$VITE_ENABLE_SENTRY
ENV VITE_DEV_MODE=$VITE_DEV_MODE

# Build da aplicação
RUN npm run build:runtime

# ============================================
# Stage de produção com Nginx
# ============================================
FROM nginx:alpine

# Instalar wget para healthcheck
RUN apk add --no-cache wget

# Copiar build do stage anterior
COPY --from=builder /app/dist /usr/share/nginx/html

# Copiar configuração COMPLETA do Nginx (usa template para envsubst)
COPY nginx.conf /etc/nginx/nginx.conf.template

# Copiar script de entrypoint para processar variáveis
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Definir porta padrão (Railway sobrescreve via $PORT)
ENV PORT=3000

# Expor porta
EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:${PORT}/ || exit 1

# Comando de inicialização via entrypoint
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
```

---

### docker-entrypoint.sh Melhorado

```bash
#!/bin/sh
set -e

# Debug: Show current user and permissions
echo "🔍 Debug info:"
echo "   Current user: $(whoami)"
echo "   User ID: $(id -u)"
id
ls -la /etc/nginx/nginx.conf.template || echo "❌ Template not found"
ls -la /etc/nginx/nginx.conf 2>/dev/null || echo "⚠️ nginx.conf doesn't exist yet (expected)"

# ============================================
# ENVIRONMENT VARIABLES WITH DEFAULTS
# ============================================
# Backend configuration (use Docker service name or Railway internal URL)
export BACKEND_HOST="${BACKEND_HOST:-backend}"
export BACKEND_PORT="${BACKEND_PORT:-8000}"
export PORT="${PORT:-3000}"

# Debug: show backend configuration BEFORE substitution
echo "🔗 Backend configuration (with defaults applied):"
echo "   BACKEND_HOST=${BACKEND_HOST}"
echo "   BACKEND_PORT=${BACKEND_PORT}"
echo "   PORT=${PORT}"

# ============================================
# RUNTIME CONFIGURATION GENERATION
# ============================================
echo "🔧 Generating runtime configuration from environment variables..."

# Path to the config files
CONFIG_FILE="/usr/share/nginx/html/api/config"
CONFIG_JS_FILE="/usr/share/nginx/html/api/config.js"

# Ensure api directory exists
mkdir -p /usr/share/nginx/html/api

# Generate JSON configuration
cat > "$CONFIG_FILE" << EOF
{
  "VITE_SUPABASE_URL": "${VITE_SUPABASE_URL:-}",
  "VITE_SUPABASE_ANON_KEY": "${VITE_SUPABASE_ANON_KEY:-}",
  "VITE_API_URL": "${VITE_API_URL:-http://localhost:8000/api/v1}",
  "VITE_API_BASE_URL": "${VITE_API_BASE_URL:-http://localhost:8000}",
  "VITE_WS_BASE_URL": "${VITE_WS_BASE_URL:-ws://localhost:8000/ws}",
  "VITE_WHATSAPP_INSTANCE_NAME": "${VITE_WHATSAPP_INSTANCE_NAME:-hormonia-instance}",
  "VITE_ENVIRONMENT": "${VITE_ENVIRONMENT:-production}",
  "VITE_DEBUG_MODE": "${VITE_DEBUG_MODE:-false}",
  "VITE_SESSION_TIMEOUT": "${VITE_SESSION_TIMEOUT:-3600000}",
  "VITE_TOKEN_REFRESH_THRESHOLD": "${VITE_TOKEN_REFRESH_THRESHOLD:-300000}",
  "VITE_MAX_FILE_SIZE": "${VITE_MAX_FILE_SIZE:-10485760}",
  "VITE_SUPPORTED_FILE_TYPES": "${VITE_SUPPORTED_FILE_TYPES:-image/jpeg,image/png,image/gif,application/pdf}"
}
EOF

# Generate JavaScript version
cat > "$CONFIG_JS_FILE" << EOF
window.__ENV_CONFIG__ = {
  "VITE_SUPABASE_URL": "${VITE_SUPABASE_URL:-}",
  "VITE_SUPABASE_ANON_KEY": "${VITE_SUPABASE_ANON_KEY:-}",
  "VITE_API_URL": "${VITE_API_URL:-http://localhost:8000/api/v1}",
  "VITE_API_BASE_URL": "${VITE_API_BASE_URL:-http://localhost:8000}",
  "VITE_WS_BASE_URL": "${VITE_WS_BASE_URL:-ws://localhost:8000/ws}",
  "VITE_WHATSAPP_INSTANCE_NAME": "${VITE_WHATSAPP_INSTANCE_NAME:-hormonia-instance}",
  "VITE_ENVIRONMENT": "${VITE_ENVIRONMENT:-production}",
  "VITE_DEBUG_MODE": "${VITE_DEBUG_MODE:-false}",
  "VITE_SESSION_TIMEOUT": "${VITE_SESSION_TIMEOUT:-3600000}",
  "VITE_TOKEN_REFRESH_THRESHOLD": "${VITE_TOKEN_REFRESH_THRESHOLD:-300000}",
  "VITE_MAX_FILE_SIZE": "${VITE_MAX_FILE_SIZE:-10485760}",
  "VITE_SUPPORTED_FILE_TYPES": "${VITE_SUPPORTED_FILE_TYPES:-image/jpeg,image/png,image/gif,application/pdf}"
};
console.log('[Runtime Config] Configuration loaded from environment');
EOF

# Display loaded configuration (without sensitive keys)
echo "✅ Runtime configuration generated successfully!"
echo "   - API URL: ${VITE_API_URL:-http://localhost:8000/api/v1}"
echo "   - API Base: ${VITE_API_BASE_URL:-http://localhost:8000}"
echo "   - WS URL: ${VITE_WS_BASE_URL:-ws://localhost:8000/ws}"
echo "   - Environment: ${VITE_ENVIRONMENT:-production}"
echo "   - Supabase URL: ${VITE_SUPABASE_URL:+[SET]}"

# Verify config files were created
if [ ! -f "$CONFIG_FILE" ] || [ ! -f "$CONFIG_JS_FILE" ]; then
    echo "⚠️ WARNING: Runtime config files may not have been created properly"
fi

# ============================================
# NGINX CONFIGURATION
# ============================================

# Process nginx.conf template with environment variables
envsubst '${BACKEND_HOST} ${BACKEND_PORT} ${PORT}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf

# Verify nginx config was created successfully
if [ ! -f /etc/nginx/nginx.conf ]; then
    echo "❌ ERROR: Failed to create nginx.conf"
    exit 1
fi

echo "✅ nginx.conf created successfully"

# Test nginx configuration
nginx -t

# Start nginx
exec nginx -g 'daemon off;'
```

---

### nginx.conf - Seção de Runtime Config Melhorada

```nginx
# Runtime config endpoints (generated at container startup)
location = /api/config {
    access_log off;
    default_type application/json;
    add_header Cache-Control "no-store, no-cache, must-revalidate" always;
    add_header Pragma "no-cache" always;

    # Especificar root explicitamente
    root /usr/share/nginx/html;
    try_files /api/config =404;
}

location = /api/config.js {
    access_log off;
    default_type application/javascript;
    add_header Cache-Control "no-store, no-cache, must-revalidate" always;
    add_header Pragma "no-cache" always;

    # Especificar root explicitamente
    root /usr/share/nginx/html;
    try_files /api/config.js =404;
}
```

---

## 📝 Recomendações de Implementação

### Prioridade Alta (Implementar Imediatamente)

1. **Atualizar Dockerfile:**
   - Copiar `nginx.conf` como template
   - Configurar entrypoint
   - Definir ENV PORT=3000
   - Corrigir healthcheck

2. **Deletar `nginx.server.conf`** ou atualizar com proxy completo

3. **Testar build localmente:**
   ```bash
   docker build -t frontend-test .
   docker run -p 3000:3000 \
     -e BACKEND_HOST=backend \
     -e BACKEND_PORT=8000 \
     -e VITE_API_URL=http://localhost:8000/api/v1 \
     frontend-test
   ```

### Prioridade Média

4. **Adicionar docker-compose.yml para testes:**
   ```yaml
   version: '3.8'
   services:
     frontend:
       build: .
       ports:
         - "3000:3000"
       environment:
         - BACKEND_HOST=backend
         - BACKEND_PORT=8000
         - VITE_API_URL=http://localhost:8000/api/v1
       depends_on:
         - backend

     backend:
       image: your-backend-image
       ports:
         - "8000:8000"
   ```

5. **Adicionar CSP headers no nginx.conf**

### Prioridade Baixa

6. Rate limiting
7. Métricas Prometheus
8. Logs estruturados JSON

---

## 🧪 Plano de Testes

### Teste 1: Build local
```bash
cd frontend-hormonia
docker build -t frontend-test .
```

### Teste 2: Runtime config
```bash
docker run -d -p 3000:3000 \
  -e BACKEND_HOST=backend \
  -e VITE_API_URL=http://backend:8000/api/v1 \
  frontend-test

# Verificar config
curl http://localhost:3000/api/config
curl http://localhost:3000/api/config.js
```

### Teste 3: Proxy backend (requer backend rodando)
```bash
# Iniciar backend mock
docker run -d --name backend -p 8000:8000 your-backend

# Iniciar frontend
docker run -d -p 3000:3000 \
  --link backend:backend \
  -e BACKEND_HOST=backend \
  frontend-test

# Testar proxy
curl http://localhost:3000/api/health
```

---

## 📊 Checklist de Validação

- [ ] Build do Docker completa sem erros
- [ ] Porta ${PORT} exposta corretamente
- [ ] nginx.conf.template copiado
- [ ] docker-entrypoint.sh executável e configurado
- [ ] Runtime config gerado em /api/config
- [ ] Proxy /api/ funciona
- [ ] Proxy /ws funciona (WebSocket)
- [ ] Healthcheck responde
- [ ] Logs nginx visíveis
- [ ] Variáveis BACKEND_HOST e BACKEND_PORT aplicadas

---

## 🎯 Conclusão

A configuração Docker do frontend está **parcialmente correta**, mas tem **problemas críticos de integração** entre os arquivos. O principal problema é a **duplicação de configurações** e o uso do arquivo nginx errado.

### Ação Recomendada:
1. **Atualizar Dockerfile** com correções indicadas
2. **Deletar nginx.server.conf** (usar apenas nginx.conf completo)
3. **Testar build localmente** antes de deploy
4. **Validar proxy para backend** em ambiente de testes

### Impacto Esperado:
- ✅ Frontend conseguirá se comunicar com backend via proxy
- ✅ Configuração runtime funcionará corretamente
- ✅ Deploy em Railway/Docker funcionará sem erros
- ✅ WebSocket funcionará corretamente
