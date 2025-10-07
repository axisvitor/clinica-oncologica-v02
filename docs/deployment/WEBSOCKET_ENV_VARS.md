# WebSocket Environment Variables - Railway Deployment

## 🎯 Overview

Este documento especifica as variáveis de ambiente necessárias para configurar corretamente as conexões WebSocket entre frontend e backend no Railway.

## 📋 Frontend Environment Variables

Configure estas variáveis no serviço **frontend** do Railway:

### 1. VITE_WS_BASE_URL (Recomendado)
**Descrição:** URL base do WebSocket backend (sem trailing `/ws`)
**Formato:** `wss://BACKEND_DOMAIN` (production) ou `ws://localhost:8080` (development)
**Exemplo Production:**
```bash
VITE_WS_BASE_URL=wss://backend-production.up.railway.app
```

**Exemplo Development:**
```bash
VITE_WS_BASE_URL=ws://localhost:8080
```

### 2. VITE_WS_URL (Legacy - Opcional)
**Descrição:** URL completa do WebSocket incluindo `/ws` (mantido para backward compatibility)
**Formato:** `wss://BACKEND_DOMAIN/ws`
**Exemplo:**
```bash
VITE_WS_URL=wss://backend-production.up.railway.app/ws
```

### 3. VITE_METRICS_WS_URL (Opcional - Específico)
**Descrição:** URL específica para WebSocket de métricas (se diferente do padrão)
**Formato:** `wss://BACKEND_DOMAIN/api/v1/metrics/live`
**Exemplo:**
```bash
VITE_METRICS_WS_URL=wss://backend-production.up.railway.app/api/v1/metrics/live
```

## 🔧 Backend Environment Variables

Configure estas variáveis no serviço **backend** do Railway:

### 1. ALLOWED_ORIGINS
**Descrição:** Domínios permitidos para conexões CORS e WebSocket
**Formato:** JSON array de strings
**Exemplo Production:**
```bash
ALLOWED_ORIGINS=["https://frontend-production-18bb.up.railway.app", "https://quiz-interface-production.up.railway.app"]
```

**Exemplo Development:**
```bash
ALLOWED_ORIGINS=["http://localhost:3000", "http://localhost:5173"]
```

### 2. REDIS_URL
**Descrição:** URL de conexão Redis para pub/sub de WebSocket broadcasts
**Formato:** `redis://[password@]host:port` ou `rediss://[password@]host:port` (SSL)
**Exemplo:**
```bash
REDIS_URL=rediss://default:password@redis-14149.c322.us-east-1-2.ec2.redns.redis-cloud.com:14149
```

### 3. DATABASE_URL
**Descrição:** PostgreSQL connection string para autenticação WebSocket
**Formato:** `postgresql://user:password@host:port/database?sslmode=require`
**Exemplo:**
```bash
DATABASE_URL=postgresql://admin:password@database-clinica.cj8esaaygzp4.sa-east-1.rds.amazonaws.com:5432/postgres?sslmode=require
```

## 🚀 Railway Configuration Steps

### Frontend Service

1. Acesse o serviço **frontend** no Railway Dashboard
2. Clique em **Variables**
3. Adicione as variáveis:
   ```bash
   VITE_WS_BASE_URL=wss://backend-production.up.railway.app
   VITE_API_BASE_URL=https://backend-production.up.railway.app
   VITE_API_URL=https://backend-production.up.railway.app/api/v1
   ```
4. Click **Save** e aguarde o redeploy automático

### Backend Service

1. Acesse o serviço **backend** no Railway Dashboard
2. Clique em **Variables**
3. Verifique se existem:
   ```bash
   ALLOWED_ORIGINS=["https://frontend-production-18bb.up.railway.app"]
   REDIS_URL=rediss://...
   DATABASE_URL=postgresql://...
   ```
4. Se faltar alguma, adicione e salve

## 🧪 Testing WebSocket Connections

### 1. Verificar Variáveis de Ambiente (Frontend)

```typescript
// No console do navegador:
console.log('WS Base URL:', import.meta.env.VITE_WS_BASE_URL)
console.log('WS URL:', import.meta.env.VITE_WS_URL)
console.log('API Base URL:', import.meta.env.VITE_API_BASE_URL)
```

### 2. Testar Conexão WebSocket

```javascript
// No console do navegador (após login):
const token = localStorage.getItem('firebase_token')
const ws = new WebSocket(`wss://backend-production.up.railway.app/ws/connect?token=${token}`)

ws.onopen = () => console.log('✅ WebSocket conectado')
ws.onerror = (err) => console.error('❌ Erro WebSocket:', err)
ws.onmessage = (msg) => console.log('📨 Mensagem:', msg.data)
```

### 3. Verificar Logs Backend

```bash
# Via Railway CLI:
railway logs --service backend

# Procure por:
# ✓ "WebSocket connection opened"
# ✓ "User authenticated via Firebase token"
# ❌ "WebSocket authentication failed"
# ❌ "Invalid Firebase token"
```

## 🐛 Troubleshooting

### Erro: "WebSocket connection failed - 4001"

**Causa:** Token inválido ou expirado
**Solução:**
1. Verificar se `firebase_token` está em localStorage
2. Fazer logout/login para renovar token
3. Verificar logs backend para erros de autenticação

### Erro: "WebSocket connection failed - 1006"

**Causa:** URL incorreta ou backend inacessível
**Solução:**
1. Verificar se `VITE_WS_BASE_URL` está configurada corretamente
2. Testar se backend está respondendo: `curl https://backend-url/health`
3. Verificar CORS em `ALLOWED_ORIGINS` no backend

### Erro: "WebSocket closed unexpectedly"

**Causa:** Falta de heartbeat ou Redis disconnected
**Solução:**
1. Verificar se Redis está online
2. Verificar logs de heartbeat no backend
3. Aumentar `heartbeatInterval` no hook useMetricsWebSocket

### Erro: "Cannot connect - No Firebase token available"

**Causa:** Usuário não autenticado
**Solução:**
1. Fazer login primeiro
2. Verificar se `AuthContext` está fornecendo `user` e `session`
3. Verificar se `firebase_token` está em localStorage

## 📊 Monitoring WebSocket Connections

### Backend Metrics Endpoint

```bash
GET /api/v1/admin/system-stats

# Retorna:
{
  "websocket_connections": 42,
  "active_users": 38,
  "redis_status": "connected",
  "db_pool_size": 10
}
```

### WebSocket Events Log

```python
# backend-hormonia/app/services/websocket_manager.py

logger.info("WebSocket authenticated", extra={
    "user_email": user.email,
    "user_id": user.id,
    "connection_id": connection_id
})
```

## 🔐 Security Best Practices

1. **HTTPS/WSS Only in Production:**
   - Nunca use `ws://` em production, apenas `wss://`
   - Railway automatically provides SSL certificates

2. **Token Expiration:**
   - Firebase tokens expiram após 1 hora
   - Implementar auto-refresh via `AuthContext.refreshToken()`

3. **CORS Configuration:**
   - Restringir `ALLOWED_ORIGINS` apenas aos domínios necessários
   - Nunca usar `["*"]` em production

4. **Rate Limiting:**
   - Backend implementa rate limiting via Redis
   - Máximo 100 mensagens/minuto por conexão

5. **Heartbeat/Ping-Pong:**
   - Cliente envia ping a cada 30s
   - Backend responde com pong
   - Desconecta após 3 pings sem resposta

## 📚 Related Documentation

- [Authentication Timeout Fix](./AUTHENTICATION_TIMEOUT_FIX.md)
- [Firebase Redis Architecture](./FIREBASE_REDIS_ARCHITECTURE.md)
- [Railway Migration Guide](./RAILWAY_MIGRATION_GUIDE.md)
- [Database CORS Fix Summary](./DATABASE_CORS_FIX_SUMMARY.md)

## 🔄 Update History

| Date | Version | Changes |
|------|---------|---------|
| 2025-10-07 | 1.0.0 | Initial documentation with Railway configuration |
| 2025-10-07 | 1.1.0 | Added WebSocket helpers in AuthContext |
| 2025-10-07 | 1.2.0 | Added useMetricsWebSocket hook with heartbeat |

---

**Última atualização:** 2025-10-07
**Responsável:** Sistema de Deployment Railway
**Status:** ✅ Production Ready
