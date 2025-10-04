# ✅ FIX CRÍTICO: envsubst Variable Substitution

## 🎯 Problema Resolvido

**Erro Original:**
```
nginx: [emerg] invalid port in upstream "${BACKEND_HOST:-backend}:${BACKEND_PORT:-8000}"
```

**Causa Raiz:**
- `envsubst` **NÃO entende** sintaxe Bash `${VAR:-default}`
- `envsubst` **APENAS substitui** `${VAR}` ou `$VAR`
- nginx.conf recebia literalmente a string `"${BACKEND_HOST:-backend}"` ao invés do valor

---

## 🔧 Solução Implementada

### Arquitetura da Correção:

```mermaid
graph LR
    A[Railway Env Vars] -->|BACKEND_HOST=api| B[docker-entrypoint.sh]
    B -->|export with defaults| C[Shell Expansion]
    C -->|BACKEND_HOST=api OR backend| D[envsubst]
    D -->|Replace ${BACKEND_HOST}| E[nginx.conf]
    E -->|server api:8000| F[nginx starts ✅]
```

### Mudanças Aplicadas:

**1. nginx.conf (template):**
```diff
  upstream backend {
-     server ${BACKEND_HOST:-backend}:${BACKEND_PORT:-8000};
+     server ${BACKEND_HOST}:${BACKEND_PORT};
  }
```
**Razão**: Remover sintaxe Bash que envsubst não entende

**2. docker-entrypoint.sh:**
```diff
+ # Expand variables with defaults BEFORE envsubst
+ export BACKEND_HOST="${BACKEND_HOST:-backend}"
+ export BACKEND_PORT="${BACKEND_PORT:-8000}"
+
  envsubst '${BACKEND_HOST} ${BACKEND_PORT}' < template > nginx.conf
```
**Razão**: Shell expande os defaults ANTES do envsubst processar

---

## 📋 Railway Configuration Required

### Environment Variables (Frontend Service):

| Variable | Value | Default | Required |
|----------|-------|---------|----------|
| `BACKEND_HOST` | `your-backend-service.railway.internal` | `backend` | ⚠️ Recommended |
| `BACKEND_PORT` | `8000` | `8000` | ⚠️ Recommended |

**Como configurar:**
```bash
# Railway CLI
railway variables set BACKEND_HOST=backend-production
railway variables set BACKEND_PORT=8000

# Ou no Railway Dashboard:
Frontend Service → Variables → Add Variable
```

---

## ✅ Verificação do Fix

### Logs Esperados (Sucesso):

```log
🔍 Debug info:
   Current user: nginx
   User ID: 101

🔗 Backend configuration (with defaults applied):
   BACKEND_HOST=backend-production
   BACKEND_PORT=8000

✅ nginx.conf created successfully

[nginx starts without errors]
```

### Teste Local:

```bash
# Com variáveis Railway
docker run --rm \
  -e BACKEND_HOST=api-service \
  -e BACKEND_PORT=3000 \
  frontend-image

# Com defaults (sem variáveis)
docker run --rm frontend-image
# Deve usar: backend:8000
```

---

## 📊 Antes vs. Depois

### ❌ ANTES (Quebrado):
```nginx
# nginx.conf.template
upstream backend {
    server ${BACKEND_HOST:-backend}:${BACKEND_PORT:-8000};
}

# envsubst NÃO substitui (não entende :-)
# Resultado em nginx.conf:
upstream backend {
    server ${BACKEND_HOST:-backend}:${BACKEND_PORT:-8000};  # LITERAL!
}

# nginx tenta parsear e FALHA:
nginx: [emerg] invalid port in upstream "${BACKEND_HOST:-backend}:..."
```

### ✅ DEPOIS (Funcionando):
```bash
# docker-entrypoint.sh expande PRIMEIRO
export BACKEND_HOST="${BACKEND_HOST:-backend}"  # → "backend-production"
export BACKEND_PORT="${BACKEND_PORT:-8000}"      # → "8000"

# envsubst substitui valores já expandidos
envsubst < template > nginx.conf
```

```nginx
# Resultado em nginx.conf:
upstream backend {
    server backend-production:8000;  # ✅ Valores reais!
}

# nginx inicia com sucesso ✅
```

---

## 🎯 Checklist de Deploy

- [x] Fix aplicado: variáveis expandidas antes do envsubst
- [x] nginx.conf usa sintaxe simples `${VAR}`
- [x] docker-entrypoint.sh exporta com defaults
- [x] Documentação criada em `docs/railway-env-vars.md`
- [ ] **PENDENTE**: Configurar `BACKEND_HOST` no Railway
- [ ] **PENDENTE**: Configurar `BACKEND_PORT` no Railway
- [ ] **PENDENTE**: Deploy e verificar logs
- [ ] **PENDENTE**: Testar proxy `/api/*` → backend

---

## 🚀 Próximos Passos

1. **Commit e Push:**
   ```bash
   git add frontend-hormonia/nginx.conf frontend-hormonia/docker-entrypoint.sh docs/
   git commit -m "fix(frontend): corrigir envsubst variable substitution para nginx"
   git push
   ```

2. **Railway Configuration:**
   - Adicionar variáveis `BACKEND_HOST` e `BACKEND_PORT`
   - Verificar nome do serviço backend

3. **Deploy e Validação:**
   - Monitorar logs do frontend
   - Confirmar: "Backend configuration (with defaults applied)"
   - Testar: `curl https://your-app.railway.app/api/health`

4. **Troubleshooting (se necessário):**
   - 502/504 → verificar `BACKEND_HOST` (deve ser nome do serviço Railway)
   - Variáveis não substituídas → verificar sintaxe em nginx.conf
   - Permission denied → já corrigido (escreve em /etc/nginx/nginx.conf)

---

## 📝 Arquivos Modificados

```
frontend-hormonia/
├── nginx.conf                    # Template simplificado (${VAR})
├── docker-entrypoint.sh          # Expande variáveis com defaults
└── Dockerfile                    # Já configurado corretamente

docs/
├── railway-env-vars.md           # Documentação detalhada
└── fix-envsubst-summary.md       # Este resumo
```

---

**Status**: ✅ Fix completo, pronto para deploy no Railway
