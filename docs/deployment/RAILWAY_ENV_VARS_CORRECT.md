# Railway Environment Variables - Configuração Correta

## 🚨 PROBLEMA IDENTIFICADO

**Data**: 2025-10-06
**Commit**: 59e0819

### Sintoma
- Login travado em "loading infinito"
- WebSocket URL inválida: `wss:clinica-oncologica-v02-production.up.railway.appwsconnect`
- API URL inválida: `https:clinica-oncologica-v02-production.up.railway.appapiv1`

### Causa Raiz
Variáveis de ambiente no Railway **não incluem** `//` após protocolo nem paths completos:
```bash
# ❌ ERRADO (como estava)
VITE_API_URL=https:clinica-oncologica-v02-production.up.railway.appapiv1
VITE_WS_URL=wss:clinica-oncologica-v02-production.up.railway.appwsconnect
```

### Impacto
1. Browser recebe URLs malformadas
2. `new URL()` falha com "Invalid URL"
3. WebSocket não conecta
4. AuthContext entra em loop de reconexão
5. UI fica presa em loading

---

## ✅ CORREÇÃO - Frontend Service

**Railway Dashboard → `frontend-production-18bb` → Variables**

### URLs Principais
```bash
VITE_API_BASE_URL=https://clinica-oncologica-v02-production.up.railway.app
VITE_API_URL=https://clinica-oncologica-v02-production.up.railway.app/api/v1
VITE_API_BASE_PATH=/api/v1
```

### WebSocket
```bash
VITE_WS_BASE_URL=wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
VITE_WS_URL=wss://clinica-oncologica-v02-production.up.railway.app/ws/connect
```

### Timeouts
```bash
VITE_API_TIMEOUT=30000
VITE_REQUEST_TIMEOUT=30000
```

### Firebase (já configurado)
```bash
VITE_FIREBASE_API_KEY=AIzaSyDbZHMNV2eZQty03TgA4yNo_3L6UDSpHdI
VITE_FIREBASE_AUTH_DOMAIN=sistema-oncologico-auth.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=sistema-oncologico-auth
VITE_FIREBASE_STORAGE_BUCKET=sistema-oncologico-auth.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=608742835827
VITE_FIREBASE_APP_ID=1:608742835827:web:fa12840b0bd4949b7c8c06
VITE_FIREBASE_MEASUREMENT_ID=G-2QZQFKJMH2
VITE_FIREBASE_ENABLED=true
```

### Supabase (desabilitado, mas keys mantidas para Postgres)
```bash
VITE_SUPABASE_URL=https://rszpypytdciggybbpnrp.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
VITE_SUPABASE_AUTH_ENABLED=false
VITE_SUPABASE_REALTIME_ENABLED=false
```

### Outros (corrigir também)
```bash
VITE_SUPPORTED_FILE_TYPES=image/jpeg,image/png,image/gif,application/pdf
```

---

## ✅ CORREÇÃO - Backend Service

**Railway Dashboard → Backend → Variables**

### Database (CRÍTICO - SSL)
```bash
DATABASE_URL=postgresql://postgres.rszpypytdciggybbpnrp:[PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
```

**IMPORTANTE**:
- ✅ Incluir `?sslmode=require` no final
- ✅ Previne erro: `psycopg.OperationalError: SSL connection has been closed unexpectedly`
- ✅ Garante que psycopg mantém conexão TLS com Supabase

### CORS
```bash
ALLOWED_ORIGINS=https://frontend-production-18bb.up.railway.app,https://clinica-oncologica-v02-production.up.railway.app
```

### Firebase Admin
```bash
FIREBASE_BLOCK_PUBLIC_DOMAINS=false
```

---

## 📋 Checklist de Aplicação

### Passo 1: Frontend Variables
- [ ] Acesse Railway → `frontend-production-18bb` → Variables
- [ ] Edite cada variável VITE_API_* e VITE_WS_*
- [ ] Verifique que URLs incluem `://` e paths completos
- [ ] Salve alterações

### Passo 2: Backend Variables
- [ ] Acesse Railway → Backend → Variables
- [ ] Verifique `DATABASE_URL` inclui `?sslmode=require`
- [ ] Verifique `ALLOWED_ORIGINS` inclui ambos domínios Railway
- [ ] Salve alterações

### Passo 3: Redeploy
- [ ] Railway redeploy automático será triggered
- [ ] Aguarde build completar (status "Success")
- [ ] Verifique logs do backend: sem erro SSL

### Passo 4: Teste Frontend
- [ ] Hard refresh (Ctrl + Shift + R)
- [ ] DevTools → Console: WebSocket URL deve ser `wss://...?token=...`
- [ ] Login deve funcionar em 2-3s
- [ ] Dashboard carrega normalmente

---

## 🔍 Validação

### Script de Validação (criar)
```bash
# Validar formato de URLs
if [[ $VITE_WS_URL =~ ^wss:// ]]; then
  echo "✅ WebSocket URL válida"
else
  echo "❌ WebSocket URL inválida: falta wss://"
fi

if [[ $DATABASE_URL =~ sslmode=require ]]; then
  echo "✅ Database SSL mode configurado"
else
  echo "⚠️ Database sem sslmode=require"
fi
```

### Logs Esperados (Backend)
```
✓ Database connected successfully
✓ Firebase Admin SDK initialized
✓ WebSocket manager initialized
REQUEST | GET /api/v1/auth/me | Status: 200 | Total: 0.234s
```

### DevTools Esperados (Frontend)
```
WebSocket connection established
[ApiClient] Request successful: /api/v1/auth/me
```

---

## 🚨 Troubleshooting

### Erro: "Invalid URL"
**Causa**: Variável Railway sem `://`
**Fix**: Adicionar `https://` ou `wss://` completo

### Erro: "SSL connection closed"
**Causa**: DATABASE_URL sem `?sslmode=require`
**Fix**: Adicionar `?sslmode=require` ao final da URL

### Erro: 401 Unauthorized
**Causa**: Firebase domains não autorizados
**Fix**: Firebase Console → Authentication → Settings → Authorized domains

---

## 📚 Referências

- Commit normalização WebSocket: `dcff59c`
- Commit cache busting: `59e0819`
- Supabase SSL docs: https://supabase.com/docs/guides/database/connecting-to-postgres#ssl-modes
- Railway env vars: https://docs.railway.app/develop/variables

---

**Última atualização**: 2025-10-06
**Status**: CRÍTICO - Aplicar imediatamente
