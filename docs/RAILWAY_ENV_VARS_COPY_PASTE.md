# 📋 Railway Environment Variables - Copy & Paste

## ✅ Variáveis Atualizadas para Redis SEM SSL (Porta 14149)

**⚠️ IMPORTANTE:** Copie APENAS as variáveis abaixo e cole no Railway Dashboard

---

## 🔧 Variáveis Redis (CORRIGIDAS)

```bash
# Redis Configuration - NO SSL
ENABLE_REDIS=true
REDIS_URL=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149
REDIS_PASSWORD=6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR
REDIS_HOST=redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com
REDIS_PORT=14149
REDIS_SSL=false
REDIS_MAX_CONNECTIONS=25
REDIS_SOCKET_TIMEOUT=10.0
REDIS_ENABLE_DB_ISOLATION=true
REDIS_CACHE_DB=1
REDIS_BROKER_DB=0
```

---

## 🔧 Variáveis Celery (CORRIGIDAS)

```bash
# Celery Configuration - NO SSL
CELERY_BROKER_URL=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
CELERY_RESULT_BACKEND=redis://default:6V7Bg9HKlUuxhXtbpnS4ygeiPKB3WQsR@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149/0
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_MAX_TASKS_PER_CHILD=1000
CELERY_WORKER_TIME_LIMIT=300
CELERY_WORKER_SOFT_TIME_LIMIT=240
CELERY_QUEUES=celery,flows,quiz,maintenance,monitoring
```

---

## ❌ Variáveis para REMOVER no Railway

**DELETE estas variáveis (não são necessárias sem SSL):**

```
REDIS_SSL_CERT_REQS
REDIS_SSL_MIN_VERSION
REDIS_SSL_CA_CERTS
```

---

## 📝 Passo a Passo no Railway Dashboard

1. **Acesse:** https://railway.app/dashboard
2. **Selecione:** `clinica-oncologica-v02` → `backend-hormonia`
3. **Clique:** Variables (menu lateral)
4. **Edite as variáveis acima** (copie e cole os valores)
5. **Delete:** `REDIS_SSL_CERT_REQS`, `REDIS_SSL_MIN_VERSION`, `REDIS_SSL_CA_CERTS`
6. **Clique:** Deploy Changes (Railway faz redeploy automático)

---

## ✅ Logs Esperados Após Deployment

```
INFO - Redis async: Using non-SSL connection
INFO - Async Redis client connected successfully
INFO - Monitoring system initialized successfully
INFO - WebSocket events service initialized with Redis
```

---

## 🔍 O Que Foi Mudado

### Antes (ERRADO):
- ❌ `REDIS_URL=rediss://...@redis-14149...:14150` (porta SSL inexistente)
- ❌ `REDIS_SSL=true` (tentando SSL em porta sem SSL)
- ❌ `CELERY_BROKER_URL=rediss://...` (SSL em porta sem SSL)

### Depois (CORRETO):
- ✅ `REDIS_URL=redis://...@redis-14149...:14149` (porta correta, sem SSL)
- ✅ `REDIS_SSL=false` (desabilitado)
- ✅ `CELERY_BROKER_URL=redis://...` (sem SSL)

---

## 🎯 Por Que Isso Conserta o Problema

**Erro original:**
```
Error 111 connecting to redis-14149...:14150. Connection refused.
```

**Causa:**
- Porta 14150 não existe ou não aceita conexões
- Porta 14149 existe MAS não suporta SSL/TLS
- Código tentava usar `rediss://` (com SSL) na porta errada

**Solução:**
- Usar porta 14149 (que existe e funciona)
- Usar `redis://` SEM SSL (scheme correto para essa porta)
- Remover configurações SSL desnecessárias

---

## 🔒 E a Segurança?

**Opção 1 (Atual - SEM SSL):**
- ✅ Funciona imediatamente
- ⚠️ Menos seguro (sem criptografia TLS)
- ✅ Adequado se Redis Cloud está em rede privada/VPC

**Opção 2 (Futuro - COM SSL):**
Se você conseguir uma porta SSL do Redis Cloud (ex: 14150 com TLS):
1. Mude `REDIS_URL` para usar `rediss://` + porta SSL
2. Mude `REDIS_SSL=true`
3. Adicione de volta `REDIS_SSL_CERT_REQS=required`
4. Adicione `REDIS_SSL_MIN_VERSION=TLSv1_2`

---

## 📞 Suporte

Se ainda tiver problemas após essas mudanças:
1. Verifique os logs do Railway: `railway logs --tail`
2. Teste conexão local: `redis-cli -u redis://...@redis-14149...:14149 ping`
3. Verifique firewall do Redis Cloud

**Documentos relacionados:**
- [RAILWAY_REDIS_SSL_CHECKLIST.md](./RAILWAY_REDIS_SSL_CHECKLIST.md)
- [REDIS_CA_CERTIFICATE_UPGRADE.md](./REDIS_CA_CERTIFICATE_UPGRADE.md)
- [ENV_VARIABLES_GUIDE.md](./ENV_VARIABLES_GUIDE.md)
