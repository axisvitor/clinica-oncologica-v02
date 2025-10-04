# Railway Backend Connection - Frontend Configuration

## ✅ Status do Backend

**Backend está rodando com sucesso:**
- Porta: 8000
- Health check: ✅ Funcionando
- Workers: 4 (gunicorn + uvicorn)
- Logs: `GET /health - 200`

## 🚨 PROBLEMA ATUAL - Frontend não consegue resolver hostname

**Erro nginx:**
```
nginx: [emerg] host not found in upstream "backend:8000"
```

**Causa:**
- Frontend usa `BACKEND_HOST=backend` (default)
- Railway NÃO resolve hostname "backend" simples
- Precisa usar Railway internal networking

---

## 🔧 SOLUÇÃO: Configurar BACKEND_HOST no Railway

### Opção 1: Railway Private Networking (RECOMENDADA)

**No Railway Dashboard - Frontend Service:**

1. Vá em **Variables**
2. Adicione a variável:

```bash
BACKEND_HOST=backend-hormonia.railway.internal
BACKEND_PORT=8000
```

**Como descobrir o nome correto:**
- Formato Railway: `[nome-do-servico].railway.internal`
- O nome do serviço está visível no Railway Dashboard
- Geralmente é: `backend-hormonia`, `backend-production`, etc.

### Opção 2: Usar Service Reference Variable

Railway pode gerar automaticamente variáveis de referência entre serviços.

**No Railway Dashboard - Frontend Service:**

1. Vá em **Variables**
2. Clique em **+ New Variable** → **Service Reference**
3. Selecione o serviço backend
4. Railway criará automaticamente variáveis como:
   - `BACKEND_URL`
   - `BACKEND_HOST`
   - `BACKEND_PORT`

Então atualize o docker-entrypoint.sh para usar essas variáveis.

### Opção 3: Usar URL Pública (NÃO RECOMENDADO para produção)

Se quiser testar rapidamente:

```bash
# Railway Dashboard → Backend service → Settings
# Copiar a URL pública (ex: https://backend-hormonia-production.up.railway.app)

# Frontend Variables:
BACKEND_HOST=backend-hormonia-production.up.railway.app
BACKEND_PORT=443  # HTTPS
```

⚠️ **Problema:** Adiciona latência (sai da rede interna) e consome bandwidth público.

---

## 📋 INSTRUÇÃO PASSO A PASSO

### 1. Identificar nome do serviço backend

Vá no Railway Dashboard e verifique o nome EXATO do serviço backend.

Exemplos comuns:
- `backend-hormonia`
- `backend-production`
- `hormonia-backend`
- `backend`

### 2. Configurar variáveis no Frontend

**Railway Dashboard → Frontend Service → Variables:**

```bash
BACKEND_HOST=backend-hormonia.railway.internal
BACKEND_PORT=8000
```

**OU se usar nome diferente:**

```bash
BACKEND_HOST=[nome-exato-do-servico].railway.internal
BACKEND_PORT=8000
```

### 3. Redeploy Frontend

Railway fará rebuild automático após adicionar variáveis.

### 4. Verificar Logs

**Logs esperados após fix:**

```log
🔗 Backend configuration (with defaults applied):
   BACKEND_HOST=backend-hormonia.railway.internal
   BACKEND_PORT=8000
✅ nginx.conf created successfully
2025/10/04 20:25:00 [notice] 1#1: nginx/1.25.3
2025/10/04 20:25:00 [notice] 1#1: start worker processes
```

**SEM mais:**
```
❌ host not found in upstream "backend:8000"
```

---

## 🔍 Troubleshooting

### Se ainda não resolver:

**1. Verificar se services estão no mesmo projeto Railway:**
- Frontend e Backend devem estar no MESMO projeto
- Private networking só funciona dentro do mesmo projeto

**2. Verificar se backend está rodando:**
```bash
# No Railway Dashboard, verificar logs do backend
# Deve mostrar: "Listening at: http://0.0.0.0:8000"
```

**3. Testar resolução DNS (opcional):**

Adicione ao docker-entrypoint.sh (temporário para debug):
```bash
echo "🔍 Testing DNS resolution..."
nslookup backend-hormonia.railway.internal || echo "❌ DNS failed"
ping -c 1 backend-hormonia.railway.internal || echo "❌ Ping failed"
```

**4. Usar resolver dinâmico nginx (alternativa):**

Se DNS não resolver no startup, use resolver dinâmico:

```nginx
# nginx.conf
http {
    resolver 127.0.0.11 valid=10s ipv6=off;

    server {
        location /api/ {
            set $backend_upstream "${BACKEND_HOST}:${BACKEND_PORT}";
            proxy_pass http://$backend_upstream;
        }
    }
}
```

---

## ✅ Checklist Final

- [ ] Backend rodando com sucesso (logs mostram "Listening at 8000")
- [ ] Identificar nome EXATO do serviço backend no Railway
- [ ] Adicionar variáveis no Frontend service:
  - `BACKEND_HOST=[nome-servico].railway.internal`
  - `BACKEND_PORT=8000`
- [ ] Aguardar rebuild automático do frontend
- [ ] Verificar logs frontend - deve mostrar hostname correto
- [ ] Nginx inicia sem erro "host not found"
- [ ] Testar proxy: `curl https://[frontend-url]/api/health`

---

## 📚 Referências

- [Railway Private Networking](https://docs.railway.app/reference/private-networking)
- [Railway Service Variables](https://docs.railway.app/develop/variables#service-variables)
- [Nginx Resolver Directive](https://nginx.org/en/docs/http/ngx_http_core_module.html#resolver)
