# Frontend Docker - Quick Fix Guide

**Data:** 2025-10-05
**Status:** Correções Prontas para Aplicar

---

## 🚀 Passos para Aplicar Correções

### 1. Backup dos Arquivos Atuais

```bash
cd frontend-hormonia

# Criar diretório de backup
mkdir -p .docker-backup

# Fazer backup
cp Dockerfile .docker-backup/Dockerfile.old
cp docker-entrypoint.sh .docker-backup/docker-entrypoint.sh.old
cp nginx.conf .docker-backup/nginx.conf.old
cp nginx.server.conf .docker-backup/nginx.server.conf.old 2>/dev/null || true
```

### 2. Aplicar Arquivo Corrigido - Dockerfile

```bash
# Copiar Dockerfile corrigido
cp ../docs/Dockerfile.corrected ./Dockerfile
```

**Ou aplicar manualmente as seguintes mudanças:**

#### Mudança 1: Adicionar ENV PORT antes do EXPOSE
```dockerfile
# ADICIONAR ANTES DA LINHA "EXPOSE"
ENV PORT=3000
EXPOSE ${PORT}
```

#### Mudança 2: Copiar nginx.conf como template
```dockerfile
# SUBSTITUIR LINHA:
COPY nginx.server.conf /etc/nginx/templates/default.conf.template

# POR:
COPY nginx.conf /etc/nginx/nginx.conf.template
```

#### Mudança 3: Adicionar entrypoint
```dockerfile
# ADICIONAR ANTES DO CMD:
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
```

#### Mudança 4: Corrigir healthcheck
```dockerfile
# SUBSTITUIR:
HEALTHCHECK CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1

# POR:
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:${PORT}/ || exit 1
```

### 3. Aplicar Entrypoint Corrigido

```bash
# Copiar entrypoint corrigido
cp ../docs/docker-entrypoint.sh.corrected ./docker-entrypoint.sh
chmod +x ./docker-entrypoint.sh
```

**Ou aplicar manualmente:**

#### Mudança: Alterar defaults do backend
```bash
# LINHA 16 - SUBSTITUIR:
export BACKEND_HOST="${BACKEND_HOST:-clinica-oncologica-v02.railway.internal}"

# POR (genérico Docker):
export BACKEND_HOST="${BACKEND_HOST:-backend}"
```

#### Mudança: Adicionar teste nginx
```bash
# ADICIONAR ANTES DO "exec nginx":
echo "🧪 Testing nginx configuration..."
nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Nginx configuration is valid"
else
    echo "❌ Nginx configuration test failed"
    exit 1
fi
```

### 4. Deletar nginx.server.conf (OPCIONAL)

```bash
# Se decidir usar APENAS nginx.conf completo
git rm nginx.server.conf
```

**OU atualizar nginx.server.conf com proxy completo** (veja seção abaixo).

---

## 🧪 Testar Build Local

### Teste 1: Build sem erros
```bash
docker build -t frontend-hormonia:test .
```

**Saída esperada:**
```
✅ Successfully built [image-id]
✅ Successfully tagged frontend-hormonia:test
```

### Teste 2: Executar container
```bash
docker run -d -p 3000:3000 \
  --name frontend-test \
  -e BACKEND_HOST=backend \
  -e BACKEND_PORT=8000 \
  -e VITE_API_URL=http://localhost:8000/api/v1 \
  -e VITE_API_BASE_URL=http://localhost:8000 \
  -e VITE_WS_BASE_URL=ws://localhost:8000/ws \
  frontend-hormonia:test
```

### Teste 3: Verificar logs
```bash
docker logs frontend-test
```

**Logs esperados:**
```
🔍 Debug info:
   Current user: nginx
   User ID: 100
✅ Runtime configuration generated successfully!
   - API URL: http://localhost:8000/api/v1
   - API Base: http://localhost:8000
   - WS URL: ws://localhost:8000/ws
🔧 Processing nginx.conf template...
✅ nginx.conf created successfully
🧪 Testing nginx configuration...
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
✅ Nginx configuration is valid
🚀 Starting nginx...
```

### Teste 4: Verificar runtime config
```bash
# Config JSON
curl http://localhost:3000/api/config

# Config JS
curl http://localhost:3000/api/config.js

# Health check
curl http://localhost:3000/health
```

### Teste 5: Cleanup
```bash
docker stop frontend-test
docker rm frontend-test
docker rmi frontend-hormonia:test
```

---

## 🐳 Testar com Docker Compose

### Opção 1: Usar docker-compose fornecido
```bash
# Copiar docker-compose para root
cp ../docs/docker-compose.frontend.yml ./docker-compose.yml

# Start
docker-compose up --build

# Verificar
curl http://localhost:3000/
curl http://localhost:3000/api/config
curl http://localhost:3000/health

# Stop
docker-compose down
```

### Opção 2: Testar com backend real

Editar `docker-compose.yml`:

```yaml
services:
  backend:
    build:
      context: ../backend-hormonia
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://...
      # ... outras variáveis
```

---

## 🔧 Alternativa: Atualizar nginx.server.conf

Se preferir manter `nginx.server.conf` em vez de usar `nginx.conf`:

```nginx
# Adicionar no topo de nginx.server.conf:

# Backend upstream
upstream backend {
    server ${BACKEND_HOST}:${BACKEND_PORT};
    keepalive 32;
}

# Connection upgrade mapping
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}

server {
    listen ${PORT};
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # ... [configurações existentes] ...

    # ADICIONAR: Runtime config endpoints
    location = /api/config {
        access_log off;
        default_type application/json;
        add_header Cache-Control "no-store, no-cache, must-revalidate" always;
        root /usr/share/nginx/html;
        try_files /api/config =404;
    }

    location = /api/config.js {
        access_log off;
        default_type application/javascript;
        add_header Cache-Control "no-store, no-cache, must-revalidate" always;
        root /usr/share/nginx/html;
        try_files /api/config.js =404;
    }

    # ADICIONAR: Proxy para backend
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 10s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        proxy_buffering off;
    }

    # ADICIONAR: WebSocket proxy
    location /ws {
        proxy_pass http://backend;
        proxy_http_version 1.1;

        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;

        proxy_buffering off;
    }

    # ... [resto do arquivo] ...
}
```

---

## ✅ Checklist de Validação

Após aplicar correções, verificar:

- [ ] `docker build` completa sem erros
- [ ] Logs mostram "✅ nginx.conf created successfully"
- [ ] Logs mostram "✅ Nginx configuration is valid"
- [ ] Container inicia sem crashes
- [ ] `curl localhost:3000/` retorna HTML
- [ ] `curl localhost:3000/api/config` retorna JSON
- [ ] `curl localhost:3000/health` retorna "healthy"
- [ ] Healthcheck passa (verificar `docker inspect`)

```bash
# Verificar healthcheck
docker inspect frontend-test | grep -A5 Health
```

---

## 🚨 Troubleshooting

### Erro: "nginx.conf.template not found"
**Causa:** Dockerfile não copia nginx.conf
**Solução:** Adicionar `COPY nginx.conf /etc/nginx/nginx.conf.template`

### Erro: "Failed to create nginx.conf"
**Causa:** Entrypoint não tem permissão
**Solução:** `RUN chmod +x /docker-entrypoint.sh` no Dockerfile

### Erro: "nginx: [emerg] host not found in upstream"
**Causa:** BACKEND_HOST não definido
**Solução:** Passar `-e BACKEND_HOST=backend` no `docker run`

### Erro: "/api/config not found"
**Causa:** Entrypoint não executado
**Solução:** Verificar se `ENTRYPOINT ["/docker-entrypoint.sh"]` está no Dockerfile

### Container não inicia
**Verificar logs:**
```bash
docker logs frontend-test
docker logs --tail 50 frontend-test
```

---

## 📝 Próximos Passos

1. **Aplicar correções** seguindo os passos acima
2. **Testar localmente** com Docker Compose
3. **Commitar mudanças:**
   ```bash
   git add Dockerfile docker-entrypoint.sh nginx.conf
   git commit -m "fix(frontend-docker): corrigir configuração Docker e proxy Nginx"
   ```
4. **Deploy em staging** para validar
5. **Deploy em production** após validação

---

## 📚 Referências

- Relatório completo: `docs/FRONTEND_DOCKER_REVIEW_REPORT.md`
- Dockerfile corrigido: `docs/Dockerfile.corrected`
- Entrypoint corrigido: `docs/docker-entrypoint.sh.corrected`
- Docker Compose: `docs/docker-compose.frontend.yml`
