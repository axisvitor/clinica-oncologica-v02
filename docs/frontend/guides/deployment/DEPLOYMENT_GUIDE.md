# Guia de Deploy do Frontend Hormonia

## Visao Geral

Este guia consolida todas as informacoes necessarias para deploy, build e validacao do Frontend Hormonia (React + TypeScript + Vite). Suporta Railway (recomendado), Vercel, Netlify e Docker.

**Arquitetura Runtime**: Sistema de configuracao multi-camada que carrega configuracoes de API runtime, window config, Vite env vars e fallbacks de producao.

---

## Sumario

1. [Processo de Build](#processo-de-build)
2. [Configuracao de Ambiente](#configuracao-de-ambiente)
3. [Deploy Railway (Recomendado)](#deploy-railway-recomendado)
4. [Outras Plataformas](#outras-plataformas)
5. [Checklist de Producao](#checklist-de-producao)
6. [Problemas Conhecidos e Solucoes](#problemas-conhecidos-e-solucoes)
7. [Validacao e Monitoramento](#validacao-e-monitoramento)
8. [Rollback](#rollback)

---

## Processo de Build

### Configuracao de Build (vite.config.ts)

| Configuracao | Valor | Status |
|--------------|-------|--------|
| Minificacao | `esbuild` | Configurado |
| Sourcemaps | `false` (producao) | Configurado |
| Remocao console | `drop: ["console", "debugger"]` | Configurado |
| Tree-shaking | `preset: "recommended"` | Configurado |
| Minificacao CSS | `lightningcss` | Configurado |
| Code splitting | Chunks manuais | Configurado |
| Limite chunk | 500KB warning | Configurado |

### Estrategia de Chunks

```javascript
manualChunks: {
  vendor: ["react", "react-dom"],
  router: ["react-router-dom", "@tanstack/react-query"],
  ui: ["@radix-ui/*", "lucide-react"],
  charts: ["recharts"],
  firebase: ["firebase/app", "firebase/auth"],
  utils: ["lodash", "date-fns", "clsx", "tailwind-merge"],
  forms: ["react-hook-form", "zod"]
}
```

### Scripts de Build

```bash
# Build padrao
npm run build

# Build producao explicito
npm run build:prod

# Typecheck
npm run typecheck

# Lint
npm run lint

# Preview local
npm run preview

# Build Railway
npm run build:railway
```

### Limites de Bundle

- Main chunk: < 500KB
- Vendor chunk: < 300KB
- UI chunk: < 200KB
- Total inicial: < 1MB

---

## Configuracao de Ambiente

### Variaveis Obrigatorias

```env
# Core
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false

# API
VITE_API_URL=https://backend.up.railway.app/api/v2
VITE_API_BASE_URL=https://backend.up.railway.app
VITE_WS_BASE_URL=wss://backend.up.railway.app/ws

# Firebase (credenciais publicas SDK Web)
VITE_FIREBASE_API_KEY=<api-key>
VITE_FIREBASE_AUTH_DOMAIN=<project>.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=<project-id>
VITE_FIREBASE_STORAGE_BUCKET=<bucket>
VITE_FIREBASE_MESSAGING_SENDER_ID=<sender-id>
VITE_FIREBASE_APP_ID=<app-id>

# Nginx (obrigatorio para proxy)
BACKEND_URL=https://backend.up.railway.app
```

### Variaveis Opcionais

```env
# Supabase (se usado)
VITE_SUPABASE_URL=https://xxxxx.supabase.co
VITE_SUPABASE_ANON_KEY=<anon-key>

# Seguranca
VITE_SECURITY_ENABLE_HTTPS=true
VITE_SECURITY_ENABLE_CSP=true
VITE_SECURITY_ENABLE_HEADERS=true
VITE_SESSION_TIMEOUT_MS=3600000

# AI Features
VITE_AI_ENABLE_CHAT=true
VITE_AI_ENABLE_SUMMARY=true
VITE_AI_ENABLE_ANALYTICS=true
VITE_AI_ENABLE_INSIGHTS=false
VITE_AI_ENABLE_RECOMMENDATIONS=true

# Monitoramento
VITE_SENTRY_DSN=<sentry-dsn>
VITE_ANALYTICS_TRACKING_ID=<analytics-id>
```

---

## Deploy Railway (Recomendado)

### Passo 1: Criar Servico

1. Acesse [Railway](https://railway.app)
2. "New Project" > "Deploy from GitHub repo"
3. Conecte repositorio
4. **Root Directory**: `frontend-hormonia`

### Passo 2: Configurar Variaveis

Em **Settings > Variables > RAW Editor**, adicione:

```bash
# Conexao Backend
VITE_API_URL=https://<backend>.up.railway.app
VITE_API_BASE_URL=https://<backend>.up.railway.app
VITE_WS_URL=wss://<backend>.up.railway.app/ws
BACKEND_URL=https://<backend>.up.railway.app

# Firebase
VITE_FIREBASE_API_KEY=<api-key>
VITE_FIREBASE_AUTH_DOMAIN=<project>.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=<project-id>
VITE_FIREBASE_APP_ID=<app-id>

# Producao
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false
```

### Passo 3: Deploy

Railway detecta `railway.json` automaticamente:
- Build: Node 20 + npm install + Vite build
- Runtime: Nginx Alpine
- Healthcheck: `GET /health` (timeout 120s)

### Passo 4: Atualizar CORS no Backend

```bash
ALLOWED_ORIGINS=["https://<frontend>.up.railway.app"]
FRONTEND_URL=https://<frontend>.up.railway.app
```

### Arquitetura Railway

```
Railway Project
├── frontend (Nginx:3000)
│   ├── /health - Healthcheck
│   ├── /api/* - Proxy para Backend
│   ├── /ws - Proxy WebSocket
│   └── /* - Arquivos estaticos
└── backend (FastAPI:8000)
```

---

## Outras Plataformas

### Vercel

```json
// vercel.json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "vite",
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        { "key": "X-Content-Type-Options", "value": "nosniff" },
        { "key": "X-Frame-Options", "value": "DENY" },
        { "key": "X-XSS-Protection", "value": "1; mode=block" }
      ]
    }
  ],
  "rewrites": [{ "source": "/((?!api/).*)", "destination": "/index.html" }]
}
```

### Netlify

```toml
# netlify.toml
[build]
  publish = "dist"
  command = "npm run build"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200

[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-XSS-Protection = "1; mode=block"
```

### Docker

```dockerfile
# Multi-stage build
FROM node:18-alpine as build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

---

## Checklist de Producao

### Pre-Deploy

- [ ] Variaveis de ambiente configuradas
- [ ] VITE_API_URL aponta para producao
- [ ] Firebase credenciais configuradas
- [ ] HTTPS forcado (VITE_SECURITY_ENABLE_HTTPS=true)
- [ ] CSP habilitado (VITE_SECURITY_ENABLE_CSP=true)
- [ ] Sem secrets hardcoded

### Build

- [ ] `npm run build` sem erros
- [ ] `npm run typecheck` passa (0 erros)
- [ ] `npm run lint` passa (0 warnings)
- [ ] Bundle size dentro dos limites
- [ ] Code splitting funcionando

### Seguranca

- [ ] Sem console.log em producao
- [ ] Sem debugger statements
- [ ] Input validation implementado
- [ ] CORS configurado no backend
- [ ] Headers de seguranca ativos:
  - X-Frame-Options: DENY
  - X-Content-Type-Options: nosniff
  - Referrer-Policy: strict-origin-when-cross-origin

### Performance

- [ ] Lazy loading em rotas
- [ ] Imagens otimizadas
- [ ] First Contentful Paint < 2s
- [ ] Time to Interactive < 3.5s
- [ ] Cache headers configurados

### Testes

- [ ] `npm run test:run` passa
- [ ] Testes E2E criticos passam
- [ ] Login/logout funciona
- [ ] Gestao de pacientes funciona
- [ ] Browsers testados: Chrome, Firefox, Safari, Edge

### Pos-Deploy

- [ ] Aplicacao carrega
- [ ] API conectividade OK
- [ ] WebSocket funciona
- [ ] Firebase auth funciona
- [ ] Sem erros no console
- [ ] Monitoramento ativo

---

## Problemas Conhecidos e Solucoes

### Erro: "host not found in upstream 'backend'"

**Causa**: Variavel `BACKEND_URL` nao configurada no Railway.

**Solucao**:
```bash
# Settings > Variables
BACKEND_URL=https://<seu-backend>.up.railway.app
```

### Erros TypeScript de Tipos Recharts (19 erros)

**Arquivo**: `/src/components/ui/charts/LazyRechartsComponents.tsx`

**Solucao**:
```typescript
// Usar ComponentProps ao inves de imports inexistentes
import type { ComponentProps } from 'react'
import { LineChart, AreaChart, BarChart, PieChart } from 'recharts'

type LineChartProps = ComponentProps<typeof LineChart>
type AreaChartProps = ComponentProps<typeof AreaChart>
type BarChartProps = ComponentProps<typeof BarChart>
type PieChartProps = ComponentProps<typeof PieChart>
```

### Erros React Router v6 (4 erros)

**Arquivo**: `/src/App.tsx`

**Solucao**:
```typescript
import type { NonIndexRouteObject, LazyRouteFunction } from 'react-router-dom'

const routes = adminRoutes.map(route => ({
  ...route,
  lazy: route.lazy as LazyRouteFunction<NonIndexRouteObject>
}))
```

### Erros API Client Types (2 erros)

**Arquivo**: `/src/lib/api-client/types.ts`

**Solucao**:
```typescript
export type AlertType = 'info' | 'warning' | 'error' | 'success'
export type AlertSeverity = 'low' | 'medium' | 'high' | 'critical'
```

### Erro Route Definition Type (1 erro)

**Arquivo**: `/src/app/routes/routeDefinitions.tsx`

**Solucao**:
```typescript
// Usar import dinamico simples
const LazyComponent = lazy(() => import('./Component'))
```

### API Calls Falhando (CORS)

**Solucao**: Adicionar URL do frontend no backend:
```bash
ALLOWED_ORIGINS=["https://<frontend>.up.railway.app"]
```

### 502 Bad Gateway em /api

**Solucao**: Verificar se `VITE_API_URL` esta correto e backend online.

---

## Validacao e Monitoramento

### Sequencia de Validacao

```bash
# 1. Typecheck
npm run typecheck
# Esperado: 0 erros

# 2. Lint
npm run lint
# Esperado: 0 warnings

# 3. Build producao
npm run build:prod
# Esperado: Build com sucesso

# 4. Verificar bundles
ls -lh dist/js/
# Esperado: Chunks < 500KB

# 5. Testes unitarios
npm run test:run
# Esperado: Todos passando

# 6. Preview local
npm run preview
# Esperado: http://localhost:4173 funciona

# 7. Healthcheck (apos deploy)
curl https://<dominio>.up.railway.app/health
# Esperado: 200 OK
```

### Tracking de Erros (Sentry)

```typescript
import * as Sentry from '@sentry/react';

if (import.meta.env.PROD && import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    tracesSampleRate: 0.1,
    environment: 'production'
  });
}
```

### Validacao de Deploy

```typescript
async function validateDeployment() {
  const config = await loadConfig();

  // Testar API
  const response = await fetch(`${config.API_BASE_URL}/health`);
  if (!response.ok) throw new Error('API health check failed');

  console.log('Deploy validado com sucesso!');
}
```

---

## Rollback

### Triggers de Rollback

- Bugs criticos identificados
- Degradacao de performance
- Vulnerabilidades de seguranca
- Problemas de integridade de dados

### Procedimento

1. Identificar severidade do problema
2. Notificar stakeholders
3. Reverter para deploy anterior (Railway: Deployments > Rollback)
4. Verificar rollback bem-sucedido
5. Documentar incidente
6. Planejar correcao

### Backup Pre-Deploy

- [ ] Versao anterior documentada
- [ ] Variaveis de ambiente documentadas
- [ ] Procedimento de rollback testado

---

## Contatos de Emergencia

- **DevOps Lead**: [Contato]
- **Backend Team**: [Contato]
- **Frontend Team**: [Contato]
- **Security Team**: [Contato]
- **Product Owner**: [Contato]

---

## Score de Prontidao

| Categoria | Peso | Criterios |
|-----------|------|-----------|
| Build Configuration | 25% | Minificacao, tree-shaking, splitting |
| Security | 25% | CSP, headers, sem secrets |
| Environment Setup | 20% | Variaveis, multi-ambiente |
| Package Scripts | 10% | CI/CD, qualidade |
| TypeScript Compilation | 20% | Sem erros de tipo |

**Meta**: 100% antes de deploy.

---

**Ultima Atualizacao**: 2025-12-26
**Versao**: 3.0.0 (Consolidado)
