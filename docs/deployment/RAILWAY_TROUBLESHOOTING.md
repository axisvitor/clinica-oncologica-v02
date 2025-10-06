# Railway Production Troubleshooting Guide

## 🔍 Problemas Identificados nos Logs

### 1. CORS com Localhost em Produção (CRÍTICO)

**Sintoma:**
```
CORS Production Mode: 19 allowed origins
Allowed origins: [...localhost...]
```

**Causa:**
- ALLOWED_ORIGINS no .env contém origens de desenvolvimento

**Solução:**
1. Remover ALLOWED_ORIGINS do .env ou deixar vazio
2. Definir apenas:
   ```bash
   FRONTEND_URL=https://frontend-production-18bb.up.railway.app
   QUIZ_URL=https://quiz-interface-production.up.railway.app
   ```
3. O código `get_cors_origins()` constrói automaticamente em produção

**Validação:**
```bash
# Logs devem mostrar:
CORS Production Mode: 2 allowed origins
```

---

### 2. WebSocket 403 Forbidden (CRÍTICO)

**Sintoma:**
```
GET /ws?token=... → 403
WebSocket handshake failed
```

**Causa:**
- Frontend conecta em `/ws` mas backend espera `/ws/connect`

**Rotas disponíveis:**
- ✅ `/ws/connect` - Conexão WebSocket geral
- ✅ `/ws/patient/{id}` - WebSocket por paciente
- ✅ `/ws/enhanced/connect` - Enhanced WebSocket

**Solução Frontend:**
```bash
VITE_WS_URL=wss://backend.up.railway.app/ws/connect
VITE_WS_BASE_URL=wss://backend.up.railway.app/ws/connect
```

**Validação:**
```bash
# Logs devem mostrar:
101 Switching Protocols
WebSocket connection established
```

---

### 3. Firebase Domínio Rejeitado (CRÍTICO)

**Sintoma:**
```
WARNING - Rejected unauthorized domain: neoplasiaslitoral.com
ERROR - Security validation failed ... Unauthorized email domain
```

**Causa:**
- Domínio não está em FIREBASE_ALLOWED_DOMAINS
- Usuário sem custom claims (role)

**Solução:**
```bash
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com"]
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
FIREBASE_ALLOWED_ROLES=["admin","super_admin","doctor","medico"]
```

**Action Item:**
- Provisionar custom claims no Firebase Console para usuários

**Validação:**
```bash
# Logs devem mostrar:
Successfully validated Firebase user
Auto-provisioned user from Firebase
```

---

### 4. Redis TLS Async Failure (ALTA)

**Sintoma:**
```
ERROR - Failed to create async Redis client: [SSL] record layer failure
```

**Causa:**
- Mismatch entre configuração TLS ou versão TLS inadequada

**Solução:**
```bash
REDIS_URL=rediss://default:***@redis-14149...
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
REDIS_SSL_MIN_VERSION=TLSV1_2
```

**Validação:**
```bash
# Logs devem mostrar:
Redis async client created successfully
Monitoring initialized with Redis
```

---

### 5. 307 Redirect em /api/v1/patients (BAIXA)

**Sintoma:**
```
307 Temporary Redirect: /api/v1/patients → /api/v1/patients/
```

**Causa:**
- FastAPI redireciona para adicionar trailing slash

**Solução:**
- Adicionar `/` no frontend: `GET /api/v1/patients/`
- Ou aceitar o 307 (benigno, FastAPI redireciona automaticamente)

---

### 6. Postgres IPv6 Unreachable (BAIXA)

**Sintoma:**
```
psycopg.OperationalError: Network is unreachable (IPv6)
```

**Causa:**
- Container tenta IPv6 mas rede não suporta

**Impacto:**
- Apenas logs de auditoria (app continua funcional)

**Solução (se persistir):**
```bash
DATABASE_URL=postgresql+psycopg://...?hostaddr=<IPv4>
```

---

## 🚀 Checklist de Deploy Railway

### Backend Service:
- [ ] ENVIRONMENT=production
- [ ] DEBUG=false
- [ ] FRONTEND_URL com domínio Railway correto
- [ ] QUIZ_URL com domínio Railway correto
- [ ] ALLOWED_ORIGINS vazio ou removido
- [ ] FIREBASE_ALLOWED_DOMAINS com domínios autorizados
- [ ] REDIS_URL com rediss:// (SSL)
- [ ] REDIS_SSL_MIN_VERSION=TLSV1_2
- [ ] Provisionar custom claims no Firebase

### Frontend Service:
- [ ] VITE_API_URL com /api/v1
- [ ] VITE_WS_URL com /ws/connect
- [ ] VITE_ENVIRONMENT=production
- [ ] VITE_FORCE_HTTPS=true

### Quiz Service:
- [ ] NEXT_PUBLIC_API_URL com /api/v1
- [ ] NEXT_PUBLIC_QUIZ_PUBLIC_API_URL correto
- [ ] NODE_ENV=production

---

## 📊 Logs de Validação

### Sucesso - Backend Iniciado:
```
INFO - CORS Production Mode: 2 allowed origins
INFO - Allowed origins: ['https://frontend...', 'https://quiz...']
INFO - Redis async client created successfully
INFO - Monitoring initialized with Redis
INFO - WebSocket events service initialized
INFO - Application startup complete
```

### Sucesso - WebSocket Conectado:
```
INFO - 101 Switching Protocols
INFO - WebSocket connection established for user_id=...
```

### Sucesso - Autenticação Firebase:
```
INFO - Successfully validated Firebase user
INFO - Auto-provisioned user from Firebase: admin@neoplasiaslitoral.com
```

---

## 🔧 Comandos Úteis Railway

```bash
# Ver logs em tempo real
railway logs --service backend

# Verificar variáveis de ambiente
railway variables --service backend

# Redeploy após mudanças
railway up --service backend

# Health check
curl https://backend.up.railway.app/health
```

---

## 📝 Arquivos de Referência

- CORS: `backend-hormonia/app/config.py` (get_cors_origins)
- Middleware: `backend-hormonia/app/core/middleware_setup.py`
- WebSocket: `backend-hormonia/app/api/websockets.py`
- Firebase Auth: `backend-hormonia/app/services/firebase_user_sync_service.py`
- Redis: `backend-hormonia/app/core/redis_manager.py`

---

## 🎯 Solução Rápida por Problema

### CORS Localhost:
```bash
# Railway Variables
ALLOWED_ORIGINS=""
FRONTEND_URL=https://frontend-production-18bb.up.railway.app
QUIZ_URL=https://quiz-interface-production.up.railway.app
```

### WebSocket 403:
```bash
# Frontend .env
VITE_WS_URL=wss://backend-production.up.railway.app/ws/connect
```

### Firebase Rejeitado:
```bash
# Railway Variables
FIREBASE_ALLOWED_DOMAINS=["neoplasiaslitoral.com"]
FIREBASE_REQUIRE_CUSTOM_CLAIMS=true
FIREBASE_ALLOWED_ROLES=["admin","super_admin","doctor","medico"]
```

### Redis TLS:
```bash
# Railway Variables
REDIS_URL=rediss://default:password@host:port
REDIS_SSL=true
REDIS_SSL_MIN_VERSION=TLSV1_2
```

---

## 🔍 Diagnóstico de Problemas

### Como identificar problema CORS:
1. Verificar logs Railway: `railway logs --service backend | grep CORS`
2. Procurar por "localhost" em allowed origins
3. Verificar se quantidade de origins > 2 em produção

### Como identificar problema WebSocket:
1. Verificar logs Railway: `railway logs --service backend | grep ws`
2. Procurar por status 403 ou "handshake failed"
3. Verificar path da conexão no frontend

### Como identificar problema Firebase:
1. Verificar logs Railway: `railway logs --service backend | grep Firebase`
2. Procurar por "Rejected unauthorized domain"
3. Verificar custom claims no Firebase Console

### Como identificar problema Redis:
1. Verificar logs Railway: `railway logs --service backend | grep Redis`
2. Procurar por "SSL" ou "TLS" errors
3. Verificar se REDIS_URL usa rediss:// (com s)

---

## 📚 Recursos Adicionais

### Documentação Railway:
- [Railway Docs](https://docs.railway.app/)
- [Environment Variables](https://docs.railway.app/develop/variables)
- [Deployment Logs](https://docs.railway.app/deploy/logs)

### Documentação FastAPI:
- [CORS](https://fastapi.tiangolo.com/tutorial/cors/)
- [WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)

### Documentação Firebase:
- [Custom Claims](https://firebase.google.com/docs/auth/admin/custom-claims)
- [Email Domains](https://firebase.google.com/docs/auth/admin/manage-users)

---

## ⚠️ Troubleshooting Avançado

### Se CORS continuar falhando:
1. Verificar ordem do middleware em `middleware_setup.py`
2. Confirmar que CORSMiddleware está sendo aplicado
3. Testar com curl para isolar problema do browser:
   ```bash
   curl -H "Origin: https://frontend.up.railway.app" \
        -H "Access-Control-Request-Method: GET" \
        -X OPTIONS https://backend.up.railway.app/api/v1/health
   ```

### Se WebSocket continuar 403:
1. Verificar se autenticação está passando token correto
2. Testar conexão sem autenticação em rota de teste
3. Verificar logs de middleware de autenticação

### Se Firebase continuar rejeitando:
1. Verificar formato de FIREBASE_ALLOWED_DOMAINS (deve ser JSON array)
2. Confirmar que custom claims foram salvos no Firebase
3. Testar com usuário que tem role conhecida
4. Verificar logs de firebase_user_sync_service.py

### Se Redis continuar falhando:
1. Testar conexão direta com redis-cli
2. Verificar certificados TLS
3. Considerar usar Redis sem SSL para debugging
4. Verificar se Railway Redis está acessível

---

**Todos os problemas críticos agora têm solução documentada!**
