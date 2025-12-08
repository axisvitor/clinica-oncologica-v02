# Environment Variables - Guia Completo

Este documento descreve todas as variáveis de ambiente usadas no frontend Hormonia, seus propósitos, valores padrão e exemplos de configuração para diferentes ambientes.

## Índice

1. [Visão Geral](#visão-geral)
2. [Variáveis por Categoria](#variáveis-por-categoria)
3. [Ambientes de Deployment](#ambientes-de-deployment)
4. [Segurança](#segurança)
5. [Troubleshooting](#troubleshooting)

---

## Visão Geral

### Convenção de Nomenclatura

No Vite, **todas as variáveis de ambiente expostas ao cliente devem começar com `VITE_`**.

```env
# ✅ CORRETO - Acessível no browser
VITE_API_URL=http://localhost:8000

# ❌ ERRADO - Não será exposta
API_URL=http://localhost:8000
```

### Como Acessar no Código

```typescript
// Em TypeScript/JavaScript
const apiUrl = import.meta.env.VITE_API_URL

// Verificar ambiente
const isDev = import.meta.env.MODE === 'development'
const isProd = import.meta.env.MODE === 'production'

// Variável com fallback
const debugMode = import.meta.env.VITE_DEBUG_MODE === 'true' || false
```

### Ordem de Precedência

As variáveis são carregadas nesta ordem (última sobrescreve):

1. `.env` - Configuração base (commitada)
2. `.env.local` - Sobrescreve local (não commitada)
3. `.env.[mode]` - Específica do modo (`.env.development`, `.env.production`)
4. `.env.[mode].local` - Sobrescreve específica e local
5. Variáveis de ambiente do sistema

---

## Variáveis por Categoria

### 1. Backend API Configuration

Configuram a conexão com o backend FastAPI.

#### VITE_API_BASE_URL

**Descrição**: URL base do backend (sem path `/api/v2`).

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String (URL) |
| **Obrigatória** | Sim |
| **Padrão** | `http://localhost:8000` |

**Exemplos**:
```env
# Desenvolvimento local
VITE_API_BASE_URL=http://localhost:8000

# Produção
VITE_API_BASE_URL=https://api.hormonia.com.br

# Railway
VITE_API_BASE_URL=https://backend-production.up.railway.app
```

**Uso no código**:
```typescript
import { apiClient } from '@/lib/api-client'

// Automaticamente usa VITE_API_BASE_URL
apiClient.setBaseURL(import.meta.env.VITE_API_BASE_URL)
```

---

#### VITE_API_URL

**Descrição**: URL completa da API (com `/api/v2`).

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String (URL) |
| **Obrigatória** | Sim |
| **Padrão** | `http://localhost:8000/api/v2` |

**Nota**: Esta é redundante com `VITE_API_BASE_URL + /api/v2`. Mantida por compatibilidade.

**Exemplos**:
```env
# Desenvolvimento
VITE_API_URL=http://localhost:8000/api/v2

# Produção
VITE_API_URL=https://api.hormonia.com.br/api/v2
```

---

#### VITE_WS_URL / VITE_WS_BASE_URL

**Descrição**: URL do WebSocket para recursos real-time.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String (WebSocket URL) |
| **Obrigatória** | Não (features WS serão desabilitadas) |
| **Padrão** | `ws://localhost:8000/ws` |

**Protocolo**:
- Desenvolvimento: `ws://`
- Produção (HTTPS): `wss://`

**Exemplos**:
```env
# Desenvolvimento local
VITE_WS_URL=ws://localhost:8000/ws

# Produção
VITE_WS_URL=wss://api.hormonia.com.br/ws

# Railway (auto HTTPS)
VITE_WS_URL=wss://backend-production.up.railway.app/ws
```

**Uso no código**:
```typescript
import { WebSocketManager } from '@/lib/websocket'

const ws = new WebSocketManager()
await ws.connect(token) // Usa VITE_WS_URL automaticamente
```

---

### 2. Firebase Authentication

Credenciais públicas do Firebase. **Seguras para expor no browser**.

#### VITE_FIREBASE_API_KEY

**Descrição**: Chave pública da API Firebase.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String |
| **Obrigatória** | Sim |
| **Exemplo** | `AIzaSyC...` |

**Como obter**: Firebase Console → Project Settings → Web App

---

#### VITE_FIREBASE_AUTH_DOMAIN

**Descrição**: Domínio de autenticação Firebase.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String (domain) |
| **Obrigatória** | Sim |
| **Formato** | `<project-id>.firebaseapp.com` |

**Exemplo**:
```env
VITE_FIREBASE_AUTH_DOMAIN=hormonia-dev.firebaseapp.com
```

---

#### VITE_FIREBASE_PROJECT_ID

**Descrição**: ID único do projeto Firebase.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String |
| **Obrigatória** | Sim |

**Exemplo**:
```env
VITE_FIREBASE_PROJECT_ID=hormonia-dev
```

---

#### VITE_FIREBASE_STORAGE_BUCKET

**Descrição**: Bucket do Firebase Storage.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String |
| **Obrigatória** | Sim |
| **Formato** | `<project-id>.firebasestorage.app` |

---

#### VITE_FIREBASE_MESSAGING_SENDER_ID

**Descrição**: ID do remetente para Cloud Messaging.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String (numeric) |
| **Obrigatória** | Sim |
| **Exemplo** | `123456789012` |

---

#### VITE_FIREBASE_APP_ID

**Descrição**: ID único da aplicação Firebase.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String |
| **Obrigatória** | Sim |
| **Formato** | `1:123456789012:web:abc123def456` |

---

### 3. Application Settings

Configurações gerais da aplicação.

#### VITE_ENVIRONMENT

**Descrição**: Ambiente de execução.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | `development` \| `staging` \| `production` |
| **Obrigatória** | Não |
| **Padrão** | `development` |

**Impacto**:
- Habilita/desabilita features de debug
- Altera níveis de log
- Controla error reporting

**Exemplos**:
```env
# Desenvolvimento
VITE_ENVIRONMENT=development

# Staging
VITE_ENVIRONMENT=staging

# Produção
VITE_ENVIRONMENT=production
```

---

#### VITE_DEBUG_MODE

**Descrição**: Habilita logs detalhados e ferramentas de debug.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Boolean (`true` \| `false`) |
| **Obrigatória** | Não |
| **Padrão** | `false` |

**Recomendação**: `true` em dev, `false` em produção.

**Impacto**:
```typescript
// Logs detalhados
if (import.meta.env.VITE_DEBUG_MODE === 'true') {
  console.log('[DEBUG]', data)
}

// Features de debug no window
window.__DEBUG__ = {
  config: getConfig(),
  apiClient: apiClient,
  // ...
}
```

---

#### VITE_APP_NAME

**Descrição**: Nome da aplicação (exibido no header, title, etc).

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String |
| **Obrigatória** | Não |
| **Padrão** | `Hormonia - Sistema de Gestão Oncológica` |

---

#### VITE_APP_VERSION

**Descrição**: Versão da aplicação (exibida no footer, about, etc).

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String (semver) |
| **Obrigatória** | Não |
| **Padrão** | Lido de `package.json` |

**Exemplo**:
```env
VITE_APP_VERSION=2.0.0
```

---

### 4. Feature Flags

Controlam habilitação/desabilitação de funcionalidades.

#### VITE_ENABLE_WHATSAPP_INTEGRATION

**Descrição**: Habilita integração com WhatsApp.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Boolean |
| **Obrigatória** | Não |
| **Padrão** | `true` |

**Impacto**: Mostra/oculta UI de WhatsApp e chamadas à API.

---

#### VITE_AI_CHAT_ENABLED

**Descrição**: Habilita chat com IA.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Boolean |
| **Obrigatória** | Não |
| **Padrão** | `true` |

---

#### VITE_AI_ANALYTICS_ENABLED

**Descrição**: Habilita dashboard de analytics com IA.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Boolean |
| **Obrigatória** | Não |
| **Padrão** | `true` |

---

#### VITE_AI_INSIGHTS_ENABLED

**Descrição**: Habilita insights de IA sobre pacientes.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Boolean |
| **Obrigatória** | Não |
| **Padrão** | `true` |

---

#### VITE_AI_RECOMMENDATIONS_ENABLED

**Descrição**: Habilita recomendações de IA.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Boolean |
| **Obrigatória** | Não |
| **Padrão** | `true` |

**Exemplo de uso**:
```typescript
import { FEATURES } from '@/config'

const Dashboard = () => (
  <div>
    {FEATURES.AI_ANALYTICS && <AIAnalyticsDashboard />}
    {FEATURES.AI_CHAT && <AIChatInterface />}
  </div>
)
```

---

#### VITE_ENABLE_DEBUG_TOOLS

**Descrição**: Habilita ferramentas de debug na UI.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Boolean |
| **Obrigatória** | Não |
| **Padrão** | `false` |

**Recomendação**: `true` apenas em desenvolvimento.

---

#### VITE_USE_MOCK_DATA

**Descrição**: Usa dados mockados ao invés da API real.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Boolean |
| **Obrigatória** | Não |
| **Padrão** | `false` |

**Uso**: Desenvolvimento offline ou testes.

---

### 5. Security & Session

Configurações de segurança e sessão.

#### VITE_SESSION_TIMEOUT

**Descrição**: Tempo até expiração da sessão (em milissegundos).

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Number (ms) |
| **Obrigatória** | Não |
| **Padrão** | `3600000` (1 hora) |

**Exemplos**:
```env
# 30 minutos
VITE_SESSION_TIMEOUT=1800000

# 1 hora (padrão)
VITE_SESSION_TIMEOUT=3600000

# 4 horas
VITE_SESSION_TIMEOUT=14400000
```

---

#### VITE_TOKEN_REFRESH_THRESHOLD

**Descrição**: Tempo antes da expiração para renovar token (em ms).

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Number (ms) |
| **Obrigatória** | Não |
| **Padrão** | `300000` (5 minutos) |

**Lógica**:
```typescript
// Se token expira em menos de 5 min, renova automaticamente
if (tokenExpiresIn < VITE_TOKEN_REFRESH_THRESHOLD) {
  await refreshToken()
}
```

---

#### VITE_FORCE_HTTPS

**Descrição**: Força uso de HTTPS (redireciona HTTP → HTTPS).

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Boolean |
| **Obrigatória** | Não |
| **Padrão** | `false` em dev, `true` em prod |

---

#### VITE_ENABLE_CSP

**Descrição**: Habilita Content Security Policy headers.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Boolean |
| **Obrigatória** | Não |
| **Padrão** | `true` |

---

### 6. Performance Configuration

Otimizações de performance.

#### VITE_REQUEST_TIMEOUT

**Descrição**: Timeout para requisições HTTP (em ms).

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Number (ms) |
| **Obrigatória** | Não |
| **Padrão** | `30000` (30 segundos) |

---

#### VITE_REQUEST_RETRY_ATTEMPTS

**Descrição**: Número de tentativas em caso de falha.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Number |
| **Obrigatória** | Não |
| **Padrão** | `3` |

**Lógica**:
```typescript
// Tenta até 3 vezes com backoff exponencial
// 1ª tentativa: imediata
// 2ª tentativa: após 1s
// 3ª tentativa: após 2s
```

---

#### VITE_REQUEST_RETRY_DELAY

**Descrição**: Delay inicial entre retries (em ms).

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Number (ms) |
| **Obrigatória** | Não |
| **Padrão** | `1000` (1 segundo) |

---

#### VITE_CACHE_DURATION

**Descrição**: Duração do cache React Query (em ms).

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Number (ms) |
| **Obrigatória** | Não |
| **Padrão** | `300000` (5 minutos) |

---

### 7. File Upload Configuration

Limites e validações para upload de arquivos.

#### VITE_MAX_FILE_SIZE

**Descrição**: Tamanho máximo de arquivo (em bytes).

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Number (bytes) |
| **Obrigatória** | Não |
| **Padrão** | `10485760` (10MB) |

**Conversão**:
```env
# 5MB
VITE_MAX_FILE_SIZE=5242880

# 10MB (padrão)
VITE_MAX_FILE_SIZE=10485760

# 50MB
VITE_MAX_FILE_SIZE=52428800
```

---

#### VITE_SUPPORTED_FILE_TYPES

**Descrição**: MIME types permitidos para upload (separados por vírgula).

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String (comma-separated) |
| **Obrigatória** | Não |
| **Padrão** | `image/jpeg,image/png,image/gif,application/pdf` |

**Exemplo**:
```env
VITE_SUPPORTED_FILE_TYPES=image/jpeg,image/png,image/gif,application/pdf,application/msword
```

**Uso no código**:
```typescript
const allowedTypes = import.meta.env.VITE_SUPPORTED_FILE_TYPES.split(',')

if (!allowedTypes.includes(file.type)) {
  throw new Error('Tipo de arquivo não permitido')
}
```

---

### 8. Localization

Configurações de idioma e formatação.

#### VITE_DEFAULT_LANGUAGE

**Descrição**: Idioma padrão da aplicação.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String (locale) |
| **Obrigatória** | Não |
| **Padrão** | `pt-BR` |

**Valores aceitos**: `pt-BR`, `en-US`

---

#### VITE_TIMEZONE

**Descrição**: Fuso horário para formatação de datas.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String (timezone) |
| **Obrigatória** | Não |
| **Padrão** | `America/Sao_Paulo` |

---

#### VITE_DATE_FORMAT

**Descrição**: Formato de data para exibição.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String (date format) |
| **Obrigatória** | Não |
| **Padrão** | `DD/MM/YYYY` |

---

### 9. Monitoring & Analytics

Integração com serviços de monitoramento.

#### VITE_SENTRY_DSN

**Descrição**: Data Source Name do Sentry para error tracking.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String (URL) |
| **Obrigatória** | Não (desabilita Sentry se vazio) |
| **Exemplo** | `https://abc123@o123.ingest.sentry.io/456` |

**Como obter**: Sentry Dashboard → Settings → Projects → Client Keys

---

#### VITE_ANALYTICS_TRACKING_ID

**Descrição**: ID de tracking do Google Analytics.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String |
| **Obrigatória** | Não |
| **Formato** | `G-XXXXXXXXXX` ou `UA-XXXXXXXXX-X` |

---

### 10. Build Configuration

Configurações do processo de build.

#### VITE_BUILD_SOURCEMAP

**Descrição**: Gera sourcemaps no build.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | Boolean |
| **Obrigatória** | Não |
| **Padrão** | `true` em dev, `false` em prod |

**Recomendação**: `false` em produção (segurança).

---

#### VITE_BASE_URL

**Descrição**: Base URL para deploy em subdiretórios.

| Propriedade | Valor |
|-------------|-------|
| **Tipo** | String (path) |
| **Obrigatória** | Não |
| **Padrão** | `/` |

**Exemplos**:
```env
# Root domain: https://hormonia.com.br
VITE_BASE_URL=/

# Subdirectory: https://example.com/app
VITE_BASE_URL=/app/
```

---

## Ambientes de Deployment

### Desenvolvimento Local

```env
# .env.development
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

---

### Staging

```env
# .env.staging
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

---

### Produção

```env
# .env.production
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
VITE_FORCE_HTTPS=true

VITE_SENTRY_DSN=https://xxx@sentry.io/production
VITE_ANALYTICS_TRACKING_ID=G-XXXXXXXXXX
```

---

### Railway Deployment

```env
# Railway auto-injeta algumas variáveis
# Você só precisa configurar:

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

# URLs são construídas automaticamente via runtime config
```

**Build Command**: `npm run build:railway`

---

### Vercel Deployment

No Vercel Dashboard → Settings → Environment Variables:

```
VITE_API_BASE_URL=https://api.hormonia.com.br
VITE_WS_URL=wss://api.hormonia.com.br/ws
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=...
# ... outras variáveis
```

**Build Command**: `npm run build`
**Output Directory**: `dist`

---

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

Ou configure via Netlify UI → Site Settings → Environment variables.

---

## Segurança

### O Que NUNCA Colocar em VITE_*

**NUNCA** coloque estas informações em variáveis `VITE_*`:

❌ Chaves privadas de API
❌ Credenciais de banco de dados
❌ Tokens de autenticação de servidor
❌ Secrets de OAuth
❌ Chaves de criptografia
❌ Senhas

**Por quê?**: Variáveis `VITE_*` são **públicas** e embutidas no JavaScript do browser.

### Variáveis Públicas Seguras

Estas variáveis **são seguras** para expor:

✅ Firebase API Key (pública por design)
✅ URLs de API públicas
✅ IDs de tracking analytics
✅ Feature flags
✅ Configurações de UI

### Validação em Produção

```typescript
// Valide variáveis críticas no startup
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

---

## Troubleshooting

### Variável não está sendo lida

**Sintomas**: `import.meta.env.VITE_MY_VAR` retorna `undefined`.

**Causas e soluções**:

1. **Não começa com `VITE_`**:
   ```env
   # ❌ Errado
   MY_VAR=value

   # ✅ Correto
   VITE_MY_VAR=value
   ```

2. **Servidor não foi reiniciado**:
   ```bash
   # Reinicie o dev server após alterar .env
   # Ctrl+C e depois:
   npm run dev
   ```

3. **Arquivo .env no lugar errado**:
   ```bash
   # .env deve estar na raiz do frontend-hormonia
   frontend-hormonia/
   ├── .env          # ✅ Aqui
   ├── src/
   └── package.json
   ```

4. **Valor com espaços ou aspas**:
   ```env
   # ❌ Errado
   VITE_API_URL = http://localhost:8000
   VITE_NAME="My App"

   # ✅ Correto
   VITE_API_URL=http://localhost:8000
   VITE_NAME=My App
   ```

---

### TypeScript não reconhece import.meta.env

**Solução**: Declare os tipos em `src/vite-env.d.ts`:

```typescript
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_FIREBASE_API_KEY: string
  readonly VITE_DEBUG_MODE: string
  // ... adicione todas as suas variáveis
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
```

---

### Variável funciona em dev mas não em produção

**Causas**:

1. **Não está no .env.production**:
   ```bash
   # Crie .env.production com as variáveis
   cp .env .env.production
   # Edite com valores de produção
   ```

2. **Platform não injeta a variável**:
   - No Railway/Vercel/Netlify, configure via UI
   - Variáveis locais não são enviadas no deploy

3. **Build cache**:
   ```bash
   # Limpe o cache e rebuilde
   rm -rf dist node_modules/.vite
   npm run build
   ```

---

### CORS errors após mudar VITE_API_URL

**Solução**: Certifique-se que o backend permite o origin:

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

---

## Referências

- **[Vite Env Variables](https://vitejs.dev/guide/env-and-mode.html)** - Documentação oficial
- **[Getting Started](GETTING_STARTED.md)** - Setup inicial
- **[API Integration](API_INTEGRATION.md)** - Como usar as APIs

---

*Última atualização: 2025-11-13*
*Mantido por: Equipe Hormonia*
