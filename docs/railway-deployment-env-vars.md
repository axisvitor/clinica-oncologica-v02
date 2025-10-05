# Railway Environment Variables Configuration

## Overview
This document lists all required environment variables for deploying the Clínica Oncológica application to Railway.

## Frontend (frontend-hormonia) Environment Variables

### Required for Production

#### ⚠️ IMPORTANTE: Firebase Authentication (Produção Real)

**Para produção, você DEVE configurar Firebase Authentication (não use mock).**

Veja [firebase-production-setup.md](./firebase-production-setup.md) para guia completo.

```bash
# Firebase Authentication - OBRIGATÓRIO PARA PRODUÇÃO
VITE_FIREBASE_API_KEY=sua-api-key-do-firebase
VITE_FIREBASE_AUTH_DOMAIN=seu-projeto.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=seu-projeto
VITE_FIREBASE_STORAGE_BUCKET=seu-projeto.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789012
VITE_FIREBASE_APP_ID=1:123456789012:web:abcdef1234567890
VITE_FIREBASE_MEASUREMENT_ID=G-XXXXXXXXXX  # Opcional

# Desabilitar mock em produção
VITE_USE_MOCK_AUTH=false
```

#### API Configuration
```bash
# Backend API URLs (replace <your-backend> with actual Railway backend URL)
VITE_API_BASE_URL=https://<your-backend>.up.railway.app
VITE_API_URL=https://<your-backend>.up.railway.app/api/v1
```

#### WebSocket Configuration
```bash
# WebSocket URL for real-time features (replace <your-backend> with actual Railway backend URL)
VITE_WS_URL=wss://<your-backend>.up.railway.app/ws
# Alternative WebSocket base URL
VITE_WS_BASE_URL=wss://<your-backend>.up.railway.app/ws
```

## Backend (backend-hormonia) Environment Variables

### Required for Production

```bash
# Database
DATABASE_URL=postgresql://user:password@host:port/dbname

# Redis
REDIS_URL=redis://host:port

# API Configuration
API_V1_STR=/api/v1
SECRET_KEY=your-secret-key-here

# CORS (set to frontend URL)
BACKEND_CORS_ORIGINS=https://<your-frontend>.up.railway.app

# WebSocket
WS_HEARTBEAT_INTERVAL=30
WS_MESSAGE_QUEUE_SIZE=1000
```

### Optional WhatsApp Integration

```bash
# Evolution API for WhatsApp
ENABLE_EVOLUTION=true
EVOLUTION_API_URL=https://your-evolution-api.com
EVOLUTION_API_KEY=your-evolution-api-key
EVOLUTION_WEBHOOK_URL=https://<your-backend>.up.railway.app/api/v1/webhooks/whatsapp
```

## Mock Authentication Credentials

When `VITE_USE_MOCK_AUTH=true`, use these credentials to login:

### Default Users
- **Admin**: `admin@example.com` / `senha123`
- **Doctor**: `doctor@example.com` / `senha123`
- **User**: `user@example.com` / `senha123`

See [frontend-hormonia/src/lib/mock-auth-service.ts](../frontend-hormonia/src/lib/mock-auth-service.ts) for complete list.

## Verification Checklist

After deploying with these environment variables:

### Frontend Checks
1. ✅ Visit `https://<your-frontend>/api/config` - should return JSON with correct URLs
2. ✅ Visit `https://<your-frontend>/login` - should load login page
3. ✅ Login with mock credentials - should redirect to dashboard
4. ✅ Check browser console - should show "Using mock authentication"

### Backend Checks
1. ✅ Visit `https://<your-backend>/api/v1/health` - should return 200 OK
2. ✅ Test API endpoint: `GET https://<your-backend>/api/v1/auth/me` (with token)
3. ✅ Check logs for database connection
4. ✅ Verify Redis connection

## Troubleshooting

### White Screen Issue
**Symptom**: Blank white screen on production, no login page

**Root Cause**: Firebase not configured + mock auth disabled causes `isLoading` to stay `true` indefinitely

**Solution**: Set `VITE_USE_MOCK_AUTH=true` in Railway frontend service

### API Calls Fail
**Symptom**: API requests return errors or timeout

**Root Cause**: `VITE_API_BASE_URL` not set or pointing to localhost

**Solution**: Set correct Railway backend URL in `VITE_API_BASE_URL` and `VITE_API_URL`

### WebSocket Not Working
**Symptom**: Real-time features don't work

**Root Cause**: `VITE_WS_URL` not configured

**Solution**: Set `VITE_WS_URL=wss://<your-backend>.up.railway.app/ws`

## Build-time vs Runtime

**Important**: These environment variables must be available during **build time** for Vite to inject them into the frontend bundle.

Railway automatically rebuilds when you change environment variables, so:
1. Set all environment variables in Railway
2. Trigger a new deployment
3. The `scripts/post-build-config.js` will create the config endpoint with correct values

## References

- [config-initializer.tsx](../frontend-hormonia/src/lib/config-initializer.tsx) - Runtime config loading
- [firebase-client.ts](../frontend-hormonia/src/lib/firebase-client.ts) - Firebase initialization
- [AuthContext.tsx](../frontend-hormonia/src/contexts/AuthContext.tsx) - Authentication context
- [runtime-config.ts](../frontend-hormonia/src/lib/runtime-config.ts) - Config normalization
- [mock-auth-service.ts](../frontend-hormonia/src/lib/mock-auth-service.ts) - Mock authentication
