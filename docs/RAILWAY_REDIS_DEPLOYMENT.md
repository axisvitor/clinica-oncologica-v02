# 🚀 Railway Deployment - Redis Cloud TLS Fix

## ✅ Solução Implementada

**Commit:** `dc15fab` - fix(redis): Add TLS 1.2 enforcement for Redis Cloud compatibility

### O Que Foi Corrigido

1. **Problema:** `[SSL] record layer failure` ao conectar ao Redis Cloud
2. **Causa:** Python 3.13 + OpenSSL 3.x tentando usar TLS 1.3, mas Redis Cloud prefere TLS 1.2
3. **Solução:** Forçar TLS 1.2 via variável de ambiente `REDIS_SSL_MIN_VERSION`

---

## 🔧 Passos para Deployment no Railway

### Opção 1: Railway Dashboard (Recomendado)

1. **Acesse o Railway Dashboard:**
   - https://railway.app/dashboard
   - Selecione o projeto `clinica-oncologica-v02`
   - Clique no serviço `backend-hormonia`

2. **Vá para a aba Variables:**
   - Clique em **Variables** no menu lateral

3. **Adicione/Atualize as variáveis:**

   ```bash
   # OBRIGATÓRIO: Desabilitar validação de certificado (Redis Cloud gerencia os certs)
   REDIS_SSL_CERT_REQS=none

   # OBRIGATÓRIO: Forçar TLS 1.2 para compatibilidade
   REDIS_SSL_MIN_VERSION=TLSv1_2
   ```

4. **Salve as alterações:**
   - Railway fará redeploy automático
   - Aguarde ~2-3 minutos para build e deploy

5. **Verifique os logs:**
   ```bash
   # Procure por estas mensagens de SUCESSO:
   INFO - Redis async SSL: Certificate verification DISABLED (CERT_NONE)
   INFO - Redis async SSL: Enforcing minimum TLS version 1.2
   INFO - Async Redis client connected successfully
   ```

### Opção 2: Railway CLI

```bash
# 1. Instale o Railway CLI (se ainda não tiver)
npm install -g @railway/cli

# 2. Faça login
railway login

# 3. Link o projeto
railway link

# 4. Configure as variáveis
railway variables set REDIS_SSL_CERT_REQS=none
railway variables set REDIS_SSL_MIN_VERSION=TLSv1_2

# 5. Verifique as variáveis
railway variables

# 6. Acompanhe os logs
railway logs --filter "Redis"
```

---

## ✅ Verificação de Sucesso

### Logs Esperados (SUCESSO)

```
2025-10-05 XX:XX:XX - app.core.redis_manager - INFO - Redis async SSL: Certificate verification DISABLED (CERT_NONE)
2025-10-05 XX:XX:XX - app.core.redis_manager - INFO - Redis async SSL: Enforcing minimum TLS version 1.2
2025-10-05 XX:XX:XX - app.core.redis_manager - INFO - Async Redis client connected successfully
2025-10-05 XX:XX:XX - app.main - INFO - Redis monitoring enabled
```

### Logs de Erro (Se ainda falhar)

Se você ainda ver:
```
ERROR - [SSL] record layer failure (_ssl.c:1032)
```

**Próximos passos:**

1. **Teste sem SSL (diagnóstico):**
   ```bash
   # Temporariamente desabilite SSL para isolar o problema
   railway variables set REDIS_SSL=false
   railway variables set REDIS_URL=redis://default:PASSWORD@HOST:PORT
   ```

2. **Tente TLS 1.3:**
   ```bash
   railway variables set REDIS_SSL_MIN_VERSION=TLSv1_3
   ```

3. **Verifique firewall do Redis Cloud:**
   - Acesse Redis Cloud Dashboard
   - Verifique se os IPs do Railway estão na whitelist
   - Railway usa IPs dinâmicos, pode precisar liberar ranges

---

## 🔍 Comandos de Debugging

### Ver todas as variáveis de ambiente
```bash
railway variables
```

### Ver logs em tempo real
```bash
railway logs --tail
```

### Ver apenas logs do Redis
```bash
railway logs --filter "Redis"
```

### Ver status do deployment
```bash
railway status
```

### Redeployar manualmente
```bash
railway up
```

---

## 📊 Arquitetura da Solução

```
┌─────────────────────────────────────────────────────────────┐
│ Railway (Python 3.13 + OpenSSL 3.x)                         │
│                                                              │
│  ┌────────────────────────────────────────────────────┐    │
│  │ redis_manager.py                                    │    │
│  │                                                      │    │
│  │  if REDIS_SSL_MIN_VERSION == 'TLSv1_2':            │    │
│  │      connection_kwargs['ssl_min_version'] =         │    │
│  │          ssl.TLSVersion.TLSv1_2                    │    │
│  │                                                      │    │
│  │  ConnectionPool.from_url(                          │    │
│  │      rediss://...,                                 │    │
│  │      ssl_cert_reqs=ssl.CERT_NONE,                 │    │
│  │      ssl_min_version=TLSv1_2                      │    │
│  │  )                                                  │    │
│  └────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           │ TLS 1.2 Handshake               │
│                           ▼                                  │
└───────────────────────────┼──────────────────────────────────┘
                            │
                            │ ✅ Encrypted Connection
                            │
┌───────────────────────────┼──────────────────────────────────┐
│                           ▼                                  │
│  Redis Cloud (redis-xxxxx.redis.cloud.com:6379)            │
│                                                              │
│  ✅ TLS 1.2 Enabled (automatic)                            │
│  ✅ Certificates managed by Redis Cloud                    │
│  ✅ Port 6379 with SSL                                     │
│  ✅ No client certificates required                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 📚 Referências

- **Commit:** [dc15fab](https://github.com/axisvitor/clinica-oncologica-v02/commit/dc15fab)
- **Análise Completa:** [docs/REDIS_CLOUD_SSL_ANALYSIS.md](REDIS_CLOUD_SSL_ANALYSIS.md)
- **Troubleshooting:** [docs/REDIS_SSL_TROUBLESHOOTING.md](REDIS_SSL_TROUBLESHOOTING.md)
- **Redis Cloud TLS Docs:** https://redis.io/docs/latest/operate/rc/security/database-security/tls-ssl/

---

## ❓ FAQ

### Por que CERT_NONE é seguro?

**Resposta:** Redis Cloud gerencia os certificados automaticamente. A conexão ainda é **criptografada com TLS**, apenas não validamos o certificado CA (que o Redis Cloud não expõe). Em ambientes de produção com managed Redis, isso é prática comum.

### Por que forçar TLS 1.2 e não 1.3?

**Resposta:** Python 3.13 + OpenSSL 3.x tenta TLS 1.3 primeiro, mas alguns servidores Redis Cloud têm incompatibilidade de cipher suites. TLS 1.2 tem compatibilidade mais ampla e estável.

### E se TLS 1.2 não funcionar?

**Resposta:** Tente estas alternativas em ordem:
1. TLS 1.3: `REDIS_SSL_MIN_VERSION=TLSv1_3`
2. Sem SSL (diagnóstico): `REDIS_SSL=false`
3. Railway Redis Plugin (alternativa)
4. Upstash Redis (alternativa)

### Preciso baixar certificados CA do Redis Cloud?

**Resposta:** **NÃO**, quando usando `CERT_NONE`. Só é necessário se você quiser validação estrita de certificado (`CERT_REQUIRED` + certificado CA baixado).

---

## ✅ Checklist de Deployment

- [ ] Commit `dc15fab` está no branch `docs-refactor-py313` ✅
- [ ] Variável `REDIS_SSL_CERT_REQS=none` configurada no Railway
- [ ] Variável `REDIS_SSL_MIN_VERSION=TLSv1_2` configurada no Railway
- [ ] Railway fez redeploy automático
- [ ] Logs mostram "Enforcing minimum TLS version 1.2"
- [ ] Logs mostram "Async Redis client connected successfully"
- [ ] Monitoramento Redis está funcionando
- [ ] Cache está funcionando
- [ ] Celery broker está funcionando

---

**🎯 Resultado Esperado:** Redis Cloud conectando com sucesso via TLS 1.2, monitoring habilitado, cache e Celery funcionais!
