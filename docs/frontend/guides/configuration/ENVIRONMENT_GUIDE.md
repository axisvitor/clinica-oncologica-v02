# Guia de Configuracao de Ambiente - Frontend Hormonia

Este documento descreve todas as variaveis de ambiente, mecanismos de configuracao e boas praticas para o frontend Hormonia.

## Indice

1. [Visao Geral](#visao-geral)
2. [Variaveis Obrigatorias](#variaveis-obrigatorias)
3. [Variaveis Opcionais](#variaveis-opcionais)
4. [Configuracao por Ambiente](#configuracao-por-ambiente)
5. [Exemplos Completos](#exemplos-completos)
6. [Seguranca](#seguranca)
7. [Troubleshooting](#troubleshooting)

---

## Visao Geral

### Convencao de Nomenclatura

No Vite, **todas as variaveis de ambiente expostas ao cliente devem comecar com `VITE_`**.

```env
# CORRETO - Acessivel no browser
VITE_API_URL=http://localhost:8000

# ERRADO - Nao sera exposta
API_URL=http://localhost:8000
```

### Como Acessar no Codigo

```typescript
// Em TypeScript/JavaScript
const apiUrl = import.meta.env.VITE_API_URL

// Verificar ambiente
const isDev = import.meta.env.MODE === 'development'
const isProd = import.meta.env.MODE === 'production'

// Variavel com fallback
const debugMode = import.meta.env.VITE_DEBUG_MODE === 'true' || false
```

### Ordem de Precedencia

As variaveis sao carregadas nesta ordem (ultima sobrescreve):

1. `.env` - Configuracao base (commitada)
2. `.env.local` - Sobrescreve local (nao commitada)
3. `.env.[mode]` - Especifica do modo (`.env.development`, `.env.production`)
4. `.env.[mode].local` - Sobrescreve especifica e local
5. Variaveis de ambiente do sistema

### Prioridade de Resolucao da URL da API

A aplicacao resolve a URL base da API na seguinte ordem de prioridade:

1. **Runtime Config** (`API_BASE_URL` from config.ts) - Para deploys dinamicos
2. **VITE_API_BASE_URL** - URL base explicita sem `/api/v2`
3. **VITE_API_URL** - URL completa, extrai a base removendo o sufixo
4. **Auto-Detection** - Usa `window.location` (apenas producao, nao localhost)
5. **Localhost Fallback** - `http://localhost:8000` (desenvolvimento)

---

## Variaveis Obrigatorias

### Backend API Configuration

#### VITE_API_BASE_URL

**Descricao**: URL base do backend (sem path `/api/v2`).

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String (URL) |
| **Obrigatoria** | Sim |
| **Padrao** | `http://localhost:8000` |

**Exemplos**:
```env
# Desenvolvimento local
VITE_API_BASE_URL=http://localhost:8000

# Producao
VITE_API_BASE_URL=https://api.hormonia.com.br

# Railway
VITE_API_BASE_URL=https://backend-production.up.railway.app
```

#### VITE_API_URL

**Descricao**: URL completa da API (com `/api/v2`).

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String (URL) |
| **Obrigatoria** | Sim |
| **Padrao** | `http://localhost:8000/api/v2` |

**Nota**: Redundante com `VITE_API_BASE_URL + /api/v2`. Mantida por compatibilidade.

### Firebase Authentication

Credenciais publicas do Firebase. **Seguras para expor no browser**.

| Variavel | Descricao | Formato |
|----------|-----------|---------|
| `VITE_FIREBASE_API_KEY` | Chave publica da API | `AIzaSyC...` |
| `VITE_FIREBASE_AUTH_DOMAIN` | Dominio de autenticacao | `<project-id>.firebaseapp.com` |
| `VITE_FIREBASE_PROJECT_ID` | ID unico do projeto | `hormonia-dev` |
| `VITE_FIREBASE_STORAGE_BUCKET` | Bucket do Storage | `<project-id>.firebasestorage.app` |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | ID para Cloud Messaging | `123456789012` |
| `VITE_FIREBASE_APP_ID` | ID unico da aplicacao | `1:123456789012:web:abc123` |

**Como obter**: Firebase Console -> Project Settings -> Web App

---

## Variaveis Opcionais

### WebSocket Configuration

#### VITE_WS_URL / VITE_WS_BASE_URL

**Descricao**: URL do WebSocket para recursos real-time.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String (WebSocket URL) |
| **Obrigatoria** | Nao (features WS serao desabilitadas) |
| **Padrao** | `ws://localhost:8000/ws` |

**Protocolo**:
- Desenvolvimento: `ws://`
- Producao (HTTPS): `wss://` (auto-upgrade)

**Auto-Upgrade**: WebSocket URLs sao automaticamente atualizadas para corresponder ao protocolo da pagina:
```typescript
// Pagina HTTPS
ws://api.yourdomain.com/ws -> wss://api.yourdomain.com/ws

// Pagina HTTP (desenvolvimento)
ws://localhost:8000/ws -> ws://localhost:8000/ws
```

### Application Settings

| Variavel | Descricao | Tipo | Padrao |
|----------|-----------|------|--------|
| `VITE_ENVIRONMENT` | Ambiente de execucao | `development` \| `staging` \| `production` | `development` |
| `VITE_DEBUG_MODE` | Logs detalhados | Boolean | `false` |
| `VITE_APP_NAME` | Nome da aplicacao | String | `Hormonia - Sistema de Gestao Oncologica` |
| `VITE_APP_VERSION` | Versao da aplicacao | String (semver) | Lido de `package.json` |

### Feature Flags

| Variavel | Descricao | Padrao |
|----------|-----------|--------|
| `VITE_WHATSAPP_INSTANCE_NAME` | Nome da instancia WhatsApp (habilita integracao quando definido) | `hormonia-instance` |
| `VITE_AI_ENABLE_CHAT` | Chat com IA | `true` |
| `VITE_AI_ENABLE_SUMMARY` | Resumo de IA para pacientes | `true` |
| `VITE_AI_ENABLE_ANALYTICS` | Dashboard de analytics com IA | `true` |
| `VITE_AI_ENABLE_INSIGHTS` | Insights de IA sobre pacientes | `false` |
| `VITE_AI_ENABLE_RECOMMENDATIONS` | Recomendacoes de IA | `true` |
| `VITE_ENABLE_DEBUG_TOOLS` | Ferramentas de debug na UI | `false` |
| `VITE_USE_MOCK_DATA` | Usa dados mockados | `false` |

**Uso no codigo**:
```typescript
import { FEATURES } from '@/config'

const Dashboard = () => (
  <div>
    {FEATURES.AI_ANALYTICS && <AIAnalyticsDashboard />}
    {FEATURES.AI_CHAT && <AIChatInterface />}
  </div>
)
```

### Security & Session

| Variavel | Descricao | Tipo | Padrao |
|----------|-----------|------|--------|
| `VITE_SESSION_TIMEOUT_MS` | Tempo ate expiracao da sessao | Number (ms) | `3600000` (1 hora) |
| `VITE_SESSION_TOKEN_REFRESH_THRESHOLD_MS` | Tempo antes da expiracao para renovar | Number (ms) | `300000` (5 min) |
| `VITE_SECURITY_ENABLE_HTTPS` | Forca uso de HTTPS | Boolean | `false` dev, `true` prod |
| `VITE_SECURITY_ENABLE_CSP` | Habilita Content Security Policy | Boolean | `true` |
| `VITE_SECURITY_ENABLE_HEADERS` | Habilita headers de seguranca | Boolean | `true` |

**Logica de refresh**:
```typescript
// Se token expira em menos de 5 min, renova automaticamente
if (tokenExpiresIn < VITE_SESSION_TOKEN_REFRESH_THRESHOLD_MS) {
  await refreshToken()
}
```

### Performance Configuration

| Variavel | Descricao | Tipo | Padrao |
|----------|-----------|------|--------|
| `VITE_REQUEST_TIMEOUT` | Timeout para requisicoes HTTP | Number (ms) | `30000` |
| `VITE_REQUEST_RETRY_ATTEMPTS` | Numero de tentativas em falha | Number | `3` |
| `VITE_REQUEST_RETRY_DELAY` | Delay inicial entre retries | Number (ms) | `1000` |
| `VITE_CACHE_DURATION` | Duracao do cache React Query | Number (ms) | `300000` |

### File Upload Configuration

| Variavel | Descricao | Tipo | Padrao |
|----------|-----------|------|--------|
| `VITE_MAX_FILE_SIZE` | Tamanho maximo de arquivo | Number (bytes) | `10485760` (10MB) |
| `VITE_SUPPORTED_FILE_TYPES` | MIME types permitidos | String (comma-separated) | `image/jpeg,image/png,image/gif,application/pdf` |

**Conversao de tamanhos**:
```env
# 5MB
VITE_MAX_FILE_SIZE=5242880

# 10MB (padrao)
VITE_MAX_FILE_SIZE=10485760

# 50MB
VITE_MAX_FILE_SIZE=52428800
```

### Localization

| Variavel | Descricao | Padrao |
|----------|-----------|--------|
| `VITE_DEFAULT_LANGUAGE` | Idioma padrao | `pt-BR` |
| `VITE_TIMEZONE` | Fuso horario | `America/Sao_Paulo` |
| `VITE_DATE_FORMAT` | Formato de data | `DD/MM/YYYY` |

### Monitoring & Analytics

| Variavel | Descricao | Formato |
|----------|-----------|---------|
| `VITE_SENTRY_DSN` | DSN do Sentry para error tracking | `https://abc123@o123.ingest.sentry.io/456` |
| `VITE_ANALYTICS_TRACKING_ID` | ID do Google Analytics | `G-XXXXXXXXXX` |

### Build Configuration

| Variavel | Descricao | Padrao |
|----------|-----------|--------|
| `VITE_BUILD_SOURCEMAP` | Gera sourcemaps | `true` dev, `false` prod |
| `VITE_BASE_URL` | Base URL para subdiretórios | `/` |

---

## Configuracao por Ambiente

### Desenvolvimento vs Producao

| Aspecto | Desenvolvimento | Producao |
|---------|----------------|----------|
| Protocolo API | `http://` | `https://` |
| Protocolo WS | `ws://` | `wss://` |
| Debug Mode | `true` | `false` |
| Debug Tools | `true` | `false` |
| Sourcemaps | `true` | `false` |
| Mock Data | Opcional | `false` |
| HTTPS Forcado | `false` | `true` |
| Sentry | Opcional | Recomendado |
| Analytics | Opcional | Recomendado |

### HTTP para HTTPS Auto-Upgrade

O API client automaticamente faz upgrade de HTTP para HTTPS em producao:

```typescript
// Se pagina e servida via HTTPS e API URL e HTTP
// http://api.yourdomain.com -> https://api.yourdomain.com
```

**Condicoes para auto-upgrade:**
- Protocolo da pagina e HTTPS
- Hostname nao e localhost ou 127.0.0.1
- Hostname nao e IP privado (192.168.x.x)

---

## Exemplos Completos

### Desenvolvimento Local (.env.development)

```env
VITE_ENVIRONMENT=development
VITE_DEBUG_MODE=true

VITE_API_BASE_URL=http://localhost:8000
VITE_API_URL=http://localhost:8000/api/v2
VITE_WS_URL=ws://localhost:8000/ws

VITE_FIREBASE_API_KEY=AIzaSyXXX-DEV
VITE_FIREBASE_AUTH_DOMAIN=hormonia-dev.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=hormonia-dev
VITE_FIREBASE_STORAGE_BUCKET=hormonia-dev.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789012
VITE_FIREBASE_APP_ID=1:123456789012:web:abcdefghij

VITE_USE_MOCK_DATA=false
VITE_ENABLE_DEBUG_TOOLS=true
VITE_BUILD_SOURCEMAP=true
```

### Staging (.env.staging)

```env
VITE_ENVIRONMENT=staging
VITE_DEBUG_MODE=true

VITE_API_BASE_URL=https://api-staging.hormonia.com.br
VITE_API_URL=https://api-staging.hormonia.com.br/api/v2
VITE_WS_URL=wss://api-staging.hormonia.com.br/ws

VITE_FIREBASE_API_KEY=AIzaSyXXX-STAGING
VITE_FIREBASE_AUTH_DOMAIN=hormonia-staging.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=hormonia-staging
VITE_FIREBASE_STORAGE_BUCKET=hormonia-staging.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=987654321098
VITE_FIREBASE_APP_ID=1:987654321098:web:zyxwvutsrq

VITE_ENABLE_DEBUG_TOOLS=true
VITE_BUILD_SOURCEMAP=true
VITE_SENTRY_DSN=https://xxx@sentry.io/staging
```

### Producao (.env.production)

```env
VITE_ENVIRONMENT=production
VITE_DEBUG_MODE=false

VITE_API_BASE_URL=https://api.hormonia.com.br
VITE_API_URL=https://api.hormonia.com.br/api/v2
VITE_WS_URL=wss://api.hormonia.com.br/ws

VITE_FIREBASE_API_KEY=AIzaSyXXX-PROD
VITE_FIREBASE_AUTH_DOMAIN=hormonia-prod.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=hormonia-prod
VITE_FIREBASE_STORAGE_BUCKET=hormonia-prod.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=555555555555
VITE_FIREBASE_APP_ID=1:555555555555:web:production

VITE_ENABLE_DEBUG_TOOLS=false
VITE_USE_MOCK_DATA=false
VITE_BUILD_SOURCEMAP=false
VITE_SECURITY_ENABLE_HTTPS=true
VITE_SECURITY_ENABLE_CSP=true
VITE_SECURITY_ENABLE_HEADERS=true

VITE_SENTRY_DSN=https://xxx@sentry.io/production
VITE_ANALYTICS_TRACKING_ID=G-XXXXXXXXXX
```

### Railway Deployment

```env
# Railway auto-injeta algumas variaveis
# Voce so precisa configurar:

VITE_FIREBASE_API_KEY=${{FIREBASE_API_KEY}}
VITE_FIREBASE_AUTH_DOMAIN=${{FIREBASE_AUTH_DOMAIN}}
VITE_FIREBASE_PROJECT_ID=${{FIREBASE_PROJECT_ID}}
VITE_FIREBASE_STORAGE_BUCKET=${{FIREBASE_STORAGE_BUCKET}}
VITE_FIREBASE_MESSAGING_SENDER_ID=${{FIREBASE_MESSAGING_SENDER_ID}}
VITE_FIREBASE_APP_ID=${{FIREBASE_APP_ID}}

# Railway fornece automaticamente:
# - PORT (porta do servidor)
# - RAILWAY_ENVIRONMENT
# - RAILWAY_PUBLIC_DOMAIN

# URLs podem usar RAILWAY_PUBLIC_DOMAIN
VITE_API_BASE_URL=${{RAILWAY_PUBLIC_DOMAIN}}
VITE_WS_BASE_URL=wss://${{RAILWAY_PUBLIC_DOMAIN}}/ws
```

**Build Command**: `npm run build:railway`

### Vercel Deployment

No Vercel Dashboard -> Settings -> Environment Variables, configure todas as variaveis VITE_*.

**Build Command**: `npm run build`
**Output Directory**: `dist`

### Netlify Deployment

Em `netlify.toml`:

```toml
[build]
  command = "npm run build"
  publish = "dist"

[build.environment]
  VITE_API_BASE_URL = "https://api.hormonia.com.br"
  VITE_WS_URL = "wss://api.hormonia.com.br/ws"
```

---

## Runtime Configuration

Para configuracao dinamica (Railway, Docker), use runtime config loading:

### Opcao 1: Arquivo config.js

Crie `/public/config.js`:

```javascript
window.RUNTIME_CONFIG = {
  VITE_API_BASE_URL: 'https://api.yourdomain.com',
  VITE_WS_BASE_URL: 'wss://api.yourdomain.com/ws'
};
```

Carregue em `index.html`:

```html
<head>
  <script src="/config.js"></script>
</head>
```

### Opcao 2: Backend Endpoint (Recomendado)

```python
# FastAPI endpoint
@app.get("/api/config")
async def get_config():
    return {
        "VITE_API_BASE_URL": os.getenv("API_BASE_URL"),
        "VITE_WS_BASE_URL": os.getenv("WS_BASE_URL")
    }
```

### Validacao de Configuracao

```typescript
import { validateConfiguration, getConfigurationStatus } from '@/lib/config-loader';

// Checar valores faltando
const missing = validateConfiguration();
if (missing.length > 0) {
  console.error('Missing configuration:', missing);
}

// Status detalhado
const status = getConfigurationStatus();
console.log('Configuration status:', status);
```

---

## Seguranca

### O Que NUNCA Colocar em VITE_*

**NUNCA** coloque estas informacoes em variaveis `VITE_*`:

- Chaves privadas de API
- Credenciais de banco de dados
- Tokens de autenticacao de servidor
- Secrets de OAuth
- Chaves de criptografia
- Senhas

**Por que?**: Variaveis `VITE_*` sao **publicas** e embutidas no JavaScript do browser.

### Variaveis Publicas Seguras

Estas variaveis **sao seguras** para expor:

- Firebase API Key (publica por design)
- URLs de API publicas
- IDs de tracking analytics
- Feature flags
- Configuracoes de UI

### Validacao em Producao

```typescript
// Valide variaveis criticas no startup
const requiredEnvVars = [
  'VITE_API_BASE_URL',
  'VITE_FIREBASE_API_KEY',
  'VITE_FIREBASE_PROJECT_ID'
]

requiredEnvVars.forEach(varName => {
  if (!import.meta.env[varName]) {
    throw new Error(`Missing required environment variable: ${varName}`)
  }
})
```

### Boas Praticas

1. **Sempre use URLs base sem barra final**
   ```bash
   # Correto
   VITE_API_BASE_URL=https://api.yourdomain.com

   # Errado
   VITE_API_BASE_URL=https://api.yourdomain.com/
   ```

2. **Prefira VITE_API_BASE_URL sobre VITE_API_URL**

3. **Use arquivos especificos por ambiente**
   ```
   .env.development
   .env.staging
   .env.production
   ```

4. **Nunca commite arquivos .env locais**
   ```gitignore
   .env
   .env.local
   .env.*.local
   ```

5. **Valide configuracao em producao**
   ```typescript
   if (import.meta.env.PROD) {
     const missing = validateConfiguration();
     if (missing.length > 0) {
       console.error('Production configuration incomplete:', missing);
     }
   }
   ```

---

## Troubleshooting

### Variavel nao esta sendo lida

**Sintomas**: `import.meta.env.VITE_MY_VAR` retorna `undefined`.

**Solucoes**:

1. **Nao comeca com `VITE_`**:
   ```env
   # Errado
   MY_VAR=value

   # Correto
   VITE_MY_VAR=value
   ```

2. **Servidor nao foi reiniciado**:
   ```bash
   # Reinicie o dev server apos alterar .env
   npm run dev
   ```

3. **Arquivo .env no lugar errado**:
   ```bash
   # .env deve estar na raiz do frontend-hormonia
   frontend-hormonia/
   ├── .env          # Aqui
   ├── src/
   └── package.json
   ```

4. **Valor com espacos ou aspas incorretos**:
   ```env
   # Errado
   VITE_API_URL = http://localhost:8000
   VITE_NAME="My App"

   # Correto
   VITE_API_URL=http://localhost:8000
   VITE_NAME=My App
   ```

### TypeScript nao reconhece import.meta.env

**Solucao**: Declare os tipos em `src/vite-env.d.ts`:

```typescript
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_FIREBASE_API_KEY: string
  readonly VITE_DEBUG_MODE: string
  // ... adicione todas as suas variaveis
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
```

### Variavel funciona em dev mas nao em producao

**Causas e solucoes**:

1. **Nao esta no .env.production**:
   ```bash
   cp .env .env.production
   # Edite com valores de producao
   ```

2. **Platform nao injeta a variavel**:
   - No Railway/Vercel/Netlify, configure via UI
   - Variaveis locais nao sao enviadas no deploy

3. **Build cache**:
   ```bash
   rm -rf dist node_modules/.vite
   npm run build
   ```

### CORS errors apos mudar VITE_API_URL

**Solucao**: Certifique-se que o backend permite o origin:

```python
# backend-hormonia/app/main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://hormonia.com.br",  # Adicione seu domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Mixed content errors (HTTP/HTTPS)

**Solucao**: Verifique configuracao de protocolo:

```bash
# Producao deve usar HTTPS
VITE_API_BASE_URL=https://api.yourdomain.com

# WebSocket fara auto-upgrade para wss://
VITE_WS_BASE_URL=wss://api.yourdomain.com/ws
```

### WebSocket connection fails

**Solucao**: Verifique URL e protocolo:

```bash
# Desenvolvimento
VITE_WS_BASE_URL=ws://localhost:8000/ws

# Producao (auto-upgrades para wss:// em paginas HTTPS)
VITE_WS_BASE_URL=ws://api.yourdomain.com/ws
```

### Configuracao nao carregando

**Solucao**: Inicialize configuracao cedo no ciclo de vida:

```typescript
import { initializeConfig } from '@/lib/config-loader';

// No entry point (main.tsx)
async function initApp() {
  await initializeConfig();
  // ... render app
}
```

---

## Referencias

- **[Vite Env Variables](https://vitejs.dev/guide/env-and-mode.html)** - Documentacao oficial
- **[Getting Started](../GETTING_STARTED.md)** - Setup inicial
- **[API Integration](../API_INTEGRATION.md)** - Como usar as APIs

---

*Ultima atualizacao: 2025-12-26*
*Mantido por: Equipe Hormonia*
