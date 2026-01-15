# Quiz Mensal Interface - Railway Deployment Guide

## 🚀 Deploy Standalone (Pasta Única)

Este guia é para fazer deploy **APENAS** do quiz como serviço independente.

---

## 📋 Pré-requisitos

1. Conta no Railway
2. Backend já deployed (para obter URL)
3. Node.js 20+ e pnpm instalados (Railway gerencia automaticamente)

---

## 🔧 Passo 1: Criar Serviço no Railway

1. Acesse [Railway](https://railway.app)
2. Click "New Project" (ou use projeto existente)
3. Selecione "Deploy from GitHub repo"
4. Conecte seu repositório
5. **IMPORTANTE**: Defina **Root Directory** = `quiz-mensal-interface`

---

## 🔑 Passo 2: Configurar Variáveis de Ambiente

Copie o conteúdo do arquivo `.env` desta pasta e cole em:
**Settings → Variables → RAW Editor**

### Variáveis CRÍTICAS (apenas 1!)

```bash
# BACKEND CONNECTION (obter após deploy do backend)
NEXT_PUBLIC_API_URL=https://<backend-domain>.up.railway.app
```

### Variáveis AUTO-CONFIGURADAS
```bash
NODE_ENV=production
NEXT_TELEMETRY_DISABLED=1
```

### Variáveis OPCIONAIS
```bash
# Monitoring (apenas se usar)
NEXT_PUBLIC_SENTRY_DSN=<seu-sentry-dsn>
NEXT_PUBLIC_GOOGLE_ANALYTICS_ID=<seu-analytics-id>
```

---

## 📦 Passo 3: Deploy

1. Railway detectará `railway.json` automaticamente
2. **Builder**: Nixpacks (Node 20 + pnpm)
3. **Build**: `pnpm install --frozen-lockfile && pnpm build`
4. **Start**: `pnpm start`
5. Healthcheck: `GET /api/health` (timeout 300s)

### Build Process (Nixpacks)
```
Setup Phase:
  → Install Node.js 20
  → Install pnpm

Install Phase:
  → pnpm install --frozen-lockfile

Build Phase:
  → pnpm build (Next.js build)

Start Phase:
  → pnpm start (Next.js production server)
```

---

## ✅ Passo 4: Verificar Health

Após deploy bem-sucedido:

```bash
curl https://<seu-dominio>.up.railway.app/api/health
```

Resposta esperada:
```json
{
  "status": "ok",
  "timestamp": "2025-10-03T..."
}
```

---

## 🔄 Passo 5: Atualizar Backend CORS

Volte ao **backend** e adicione a URL do quiz:

```bash
ALLOWED_ORIGINS=["...","https://<quiz-domain>.up.railway.app"]
QUIZ_URL=https://<quiz-domain>.up.railway.app
```

Redeploy o backend.

---

## 🌐 Arquitetura

```
┌─────────────────────────────────────┐
│     Railway Project                  │
├─────────────────────────────────────┤
│                                      │
│  ┌──────────────┐                   │
│  │     quiz     │  Port: 3000       │
│  │  (Next.js)   │  /api/health      │
│  └──────────────┘                   │
│         │                            │
│         │ API calls → Backend       │
│         │                            │
│         ├─ Next.js 14 (App Router)  │
│         ├─ React Server Components  │
│         └─ API Routes (/api/*)      │
└─────────────────────────────────────┘
```

---

## 📝 Estrutura da Aplicação

### App Router (Next.js 14)
```
app/
├── layout.tsx              # Root layout
├── page.tsx                # Home page
├── api/
│   └── health/
│       └── route.ts        # Health check endpoint
└── quiz/
    └── monthly/
        └── [token]/        # Quiz with token
            └── page.tsx
```

### Health Endpoint
`app/api/health/route.ts` expõe:
- `GET /api/health` → Status check
- `HEAD /api/health` → Quick check (sem body)

---

## 🐛 Troubleshooting

### "API calls failing"
→ Verifique se `NEXT_PUBLIC_API_URL` está correto
→ Certifique-se que backend está online

### "Build fails on pnpm install"
→ Verifique se `pnpm-lock.yaml` existe
→ Se não, delete e rode `pnpm install` localmente

### "Health check timeout"
→ Health check tem timeout de 300s (5min)
→ Verifique logs se Next.js iniciou corretamente

### "Module not found errors"
→ Limpe cache: delete `.next/` e rebuilde

---

## 📁 Arquivos Importantes

- `railway.json` - Configuração Railway (Nixpacks)
- `.env` - Variáveis de ambiente (NÃO commitar)
- `package.json` - Dependências e scripts
- `pnpm-lock.yaml` - Lock file (COMMITAR)
- `next.config.mjs` - Configuração Next.js
- `app/api/health/route.ts` - Health endpoint

---

## 🔒 Segurança

- [ ] `.env` está no `.gitignore`
- [ ] Apenas variáveis `NEXT_PUBLIC_*` são públicas (seguro)
- [ ] CORS configurado no backend
- [ ] HTTPS forçado (Railway SSL)
- [ ] Telemetria desabilitada

---

## ⚡ Performance

### Build Optimization
```json
{
  "output": "standalone",
  "compress": true,
  "images": {
    "formats": ["image/webp"]
  }
}
```

### Cache Strategy
Next.js usa cache automático para:
- Static pages
- API routes (com revalidate)
- Images (otimização automática)

---

## 🎯 Features do Quiz

### Token-based Access
- Quizzes acessíveis via token único
- Tokens gerados pelo backend
- Expiração configurável (72h padrão)

### API Integration
- Chamadas para backend via `NEXT_PUBLIC_API_URL`
- Endpoints:
  - `POST /api/v2/quiz/submit`
  - `GET /api/v2/quiz/{token}`

---

## 📊 Monitoring

### Logs
Acesse no Railway:
```
Service → Deployments → [latest] → Logs
```

### Metrics
Railway fornece:
- CPU usage
- Memory usage
- Request rate
- Response time

---

**Deployment Type**: Standalone Service
**Builder**: Nixpacks (Node 20 + pnpm)
**Runtime**: Next.js 14 Production Server
**Health Check**: GET /api/health (300s timeout)
